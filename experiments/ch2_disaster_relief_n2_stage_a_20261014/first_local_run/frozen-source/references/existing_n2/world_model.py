"""Local engineering interfaces for a dynamic civilian action-consequence model.

This module is not a frozen research model or collector. It accepts only public
feature tensors; stable IDs bind tensors and are validated as metadata.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

try:
    from n2_contracts import validate_public_view
except ImportError:
    from ..n2_contracts import validate_public_view


SCHEMA = "n2-engineering-consequence/2"
GLOBAL_BINARY_HEADS = 2
GLOBAL_CONTINUOUS_HEADS = 4
TASK_BINARY_HEADS = 4
TASK_CONTINUOUS_HEADS = 2
GLOBAL_BINARY_NAMES = ("reward_improved", "energy_saved")
GLOBAL_CONTINUOUS_NAMES = (
    "cumulative_reward_delta", "energy_use_delta",
    "other_task_on_time_count_delta", "inspection_report_count_delta",
)
TASK_BINARY_NAMES = (
    "service_completed_by_horizon", "service_on_time", "deadline_missed", "report_received_by_deadline",
)
TASK_CONTINUOUS_NAMES = ("completion_elapsed_fraction", "report_delay_fraction")


@dataclass(frozen=True)
class InputBinding:
    candidate_ids: tuple[tuple[str, ...], ...]
    task_ids: tuple[tuple[str, ...], ...]


def _validate_binding(binding: InputBinding, candidate_mask: torch.Tensor, task_mask: torch.Tensor) -> None:
    if candidate_mask.dtype != torch.bool or task_mask.dtype != torch.bool:
        raise ValueError("ACTIVE_MASK_DTYPE")
    if candidate_mask.ndim != 2 or task_mask.ndim != 2 or candidate_mask.shape[0] != task_mask.shape[0]:
        raise ValueError("ACTIVE_MASK_SHAPE")
    batch, candidate_slots = candidate_mask.shape
    task_batch, task_slots = task_mask.shape
    if len(binding.candidate_ids) != batch or len(binding.task_ids) != batch:
        raise ValueError("BINDING_BATCH_SIZE")
    for row in range(batch):
        candidate_ids = binding.candidate_ids[row]
        task_ids = binding.task_ids[row]
        if len(candidate_ids) != candidate_slots or len(task_ids) != task_slots:
            raise ValueError("BINDING_SLOT_COUNT")
        active_candidate_ids = [candidate_ids[i] for i in range(candidate_slots) if bool(candidate_mask[row, i])]
        active_task_ids = [task_ids[i] for i in range(task_slots) if bool(task_mask[row, i])]
        if not active_candidate_ids or active_candidate_ids.count("NOOP") != 1:
            raise ValueError("NOOP_BINDING")
        if len(active_candidate_ids) != len(set(active_candidate_ids)):
            raise ValueError("DUPLICATE_CANDIDATE_ID")
        if any(not value for value in active_candidate_ids + active_task_ids):
            raise ValueError("EMPTY_ENTITY_ID")
        if len(active_task_ids) != len(set(active_task_ids)):
            raise ValueError("DUPLICATE_PUBLIC_TASK_ID")


class DynamicConsequenceModel(nn.Module):
    """Shared candidate encoder with dynamic public-task keyed readouts."""

    format_version = SCHEMA

    def __init__(self, context_dim: int, candidate_dim: int, task_dim: int, hidden_dim: int = 64):
        super().__init__()
        if min(context_dim, candidate_dim, task_dim, hidden_dim) <= 0:
            raise ValueError("MODEL_DIMENSION")
        self.config = {
            "context_dim": int(context_dim),
            "candidate_dim": int(candidate_dim),
            "task_dim": int(task_dim),
            "hidden_dim": int(hidden_dim),
            "global_binary_heads": GLOBAL_BINARY_HEADS,
            "global_continuous_heads": GLOBAL_CONTINUOUS_HEADS,
            "task_binary_heads": TASK_BINARY_HEADS,
            "task_continuous_heads": TASK_CONTINUOUS_HEADS,
        }
        self.candidate_encoder = nn.Sequential(
            nn.Linear(context_dim + candidate_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
        )
        self.global_binary = nn.Linear(hidden_dim, GLOBAL_BINARY_HEADS)
        self.global_continuous = nn.Linear(hidden_dim, GLOBAL_CONTINUOUS_HEADS)
        self.task_encoder = nn.Sequential(
            nn.Linear(hidden_dim + task_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
        )
        self.task_binary = nn.Linear(hidden_dim, TASK_BINARY_HEADS)
        self.task_continuous = nn.Linear(hidden_dim, TASK_CONTINUOUS_HEADS)

    def forward(
        self,
        context: torch.Tensor,
        candidate_features: torch.Tensor,
        task_features: torch.Tensor,
        candidate_mask: torch.Tensor,
        task_mask: torch.Tensor,
        binding: InputBinding,
    ) -> dict[str, torch.Tensor]:
        _validate_binding(binding, candidate_mask, task_mask)
        if context.ndim != 2 or candidate_features.ndim != 3 or task_features.ndim != 3:
            raise ValueError("FEATURE_RANK")
        batch, candidate_slots, candidate_dim = candidate_features.shape
        task_batch, task_slots, task_dim = task_features.shape
        if context.shape != (batch, self.config["context_dim"]):
            raise ValueError("CONTEXT_SHAPE")
        if (batch != task_batch or candidate_dim != self.config["candidate_dim"]
                or task_dim != self.config["task_dim"]
                or candidate_mask.shape != (batch, candidate_slots)
                or task_mask.shape != (batch, task_slots)):
            raise ValueError("FEATURE_SHAPE")
        if not all(torch.isfinite(value).all() for value in (context, candidate_features, task_features)):
            raise ValueError("PUBLIC_FEATURE_NONFINITE")

        context_expanded = context[:, None, :].expand(-1, candidate_slots, -1)
        hidden = self.candidate_encoder(torch.cat((context_expanded, candidate_features), dim=-1))
        active_candidates = candidate_mask.unsqueeze(-1)
        binary = self.global_binary(hidden).masked_fill(~active_candidates, 0.0)
        continuous = self.global_continuous(hidden).masked_fill(~active_candidates, 0.0)

        candidate_task = hidden[:, :, None, :].expand(-1, -1, task_slots, -1)
        task_public = task_features[:, None, :, :].expand(-1, candidate_slots, -1, -1)
        task_hidden = self.task_encoder(torch.cat((candidate_task, task_public), dim=-1))
        task_active = candidate_mask[:, :, None] & task_mask[:, None, :]
        task_binary = self.task_binary(task_hidden).masked_fill(~task_active.unsqueeze(-1), 0.0)
        task_continuous = self.task_continuous(task_hidden).masked_fill(~task_active.unsqueeze(-1), 0.0)
        return {
            "binary": binary,
            "continuous": continuous,
            "per_task": task_binary,
            "per_task_continuous": task_continuous,
            "candidate_mask": candidate_mask,
            "task_mask": task_mask,
            "candidate_ids": binding.candidate_ids,
            "task_ids": binding.task_ids,
        }


def _masked_element_loss(prediction: torch.Tensor, target: torch.Tensor, valid: torch.Tensor, kind: str) -> torch.Tensor:
    if prediction.shape != target.shape or valid.shape != target.shape or valid.dtype != torch.bool:
        raise ValueError("TARGET_MASK_SHAPE")
    if not torch.isfinite(prediction).all() or not torch.isfinite(target[valid]).all():
        raise ValueError("VALID_TARGET_NONFINITE")
    if not bool(valid.any()):
        return prediction.sum() * 0.0
    p, t = prediction[valid], target[valid]
    if kind == "bce":
        if bool(((t < 0) | (t > 1)).any()):
            raise ValueError("BCE_TARGET_RANGE")
        return F.binary_cross_entropy_with_logits(p, t)
    if kind == "huber":
        return F.smooth_l1_loss(p, t, beta=1.0)
    raise ValueError("LOSS_KIND")


def pair_weighted_ranking_loss(
    predicted: torch.Tensor,
    target: torch.Tensor,
    valid: torch.Tensor,
    window_ids: tuple[tuple[str, int, str], ...],
) -> tuple[torch.Tensor, dict[str, int | str]]:
    """Average all valid unequal-label pairs; each pair has equal weight."""
    if predicted.ndim != 1 or target.shape != predicted.shape or valid.shape != predicted.shape:
        raise ValueError("RANK_TENSOR_SHAPE")
    if valid.dtype != torch.bool or len(window_ids) != predicted.shape[0]:
        raise ValueError("RANK_BINDING_SHAPE")
    for identity in window_ids:
        if (not isinstance(identity, tuple) or len(identity) != 3
                or not isinstance(identity[0], str) or not identity[0]
                or type(identity[1]) is not int or identity[1] < 0
                or not isinstance(identity[2], str) or not identity[2]):
            raise ValueError("RANK_WINDOW_IDENTITY")
    pair_losses: list[torch.Tensor] = []
    for i in range(len(predicted)):
        for j in range(i + 1, len(predicted)):
            if window_ids[i] != window_ids[j] or not bool(valid[i]) or not bool(valid[j]):
                continue
            if bool(target[i] == target[j]):
                continue
            direction = torch.sign(target[i] - target[j])
            pair_losses.append(F.softplus(-direction * (predicted[i] - predicted[j])))
    loss = torch.stack(pair_losses).mean() if pair_losses else predicted.sum() * 0.0
    return loss, {"reduction": "pair_weighted", "valid_pair_count": len(pair_losses)}


def consequence_loss(
    prediction: dict[str, torch.Tensor],
    target: dict[str, torch.Tensor],
    valid: dict[str, torch.Tensor],
    window_ids: tuple[tuple[str, int, str], ...],
) -> tuple[torch.Tensor, dict[str, torch.Tensor | int | str]]:
    binary_loss = _masked_element_loss(prediction["binary"], target["binary"], valid["binary"], "bce")
    continuous_loss = _masked_element_loss(
        prediction["continuous"], target["continuous"], valid["continuous"], "huber"
    )
    task_binary_loss = _masked_element_loss(prediction["per_task"], target["per_task"], valid["per_task"], "bce")
    task_continuous_loss = _masked_element_loss(
        prediction["per_task_continuous"], target["per_task_continuous"],
        valid["per_task_continuous"], "huber",
    )
    utility = prediction["continuous"][:, :, 0].reshape(-1)
    utility_target = target["continuous"][:, :, 0].reshape(-1)
    utility_valid = valid["continuous"][:, :, 0].reshape(-1)
    # Ranking comparisons are scoped to one decision window. Candidate IDs are
    # metadata only; the pair order cannot alter the pair-weighted denominator.
    rank_ids = tuple(window_ids[b] for b in range(len(window_ids)) for _ in range(prediction["continuous"].shape[1]))
    rank_loss, rank_stats = pair_weighted_ranking_loss(utility, utility_target, utility_valid, rank_ids)
    total = binary_loss + continuous_loss + task_binary_loss + task_continuous_loss + rank_loss
    return total, {
        "binary": binary_loss,
        "continuous": continuous_loss,
        "per_task_binary": task_binary_loss,
        "per_task_continuous": task_continuous_loss,
        "ranking": rank_loss,
        "ranking_reduction": rank_stats["reduction"],
        "valid_pair_count": rank_stats["valid_pair_count"],
    }


def critic_only_value(
    base_value: torch.Tensor,
    wm_candidate_value: torch.Tensor,
    policy_probabilities: torch.Tensor,
    candidate_mask: torch.Tensor,
    *,
    scale: float = 1.0,
) -> torch.Tensor:
    """Detached WM candidate values may augment value; never feed actor logits."""
    if (wm_candidate_value.shape != policy_probabilities.shape
            or candidate_mask.shape != policy_probabilities.shape
            or candidate_mask.dtype != torch.bool
            or base_value.shape != policy_probabilities.shape[:1]):
        raise ValueError("CRITIC_AUX_SHAPE")
    if not bool(candidate_mask.any(dim=1).all()):
        raise ValueError("CRITIC_AUX_EMPTY_CATALOG")
    normalized = policy_probabilities.detach().masked_fill(~candidate_mask, 0.0)
    normalized = normalized / normalized.sum(dim=1, keepdim=True).clamp_min(1e-12)
    auxiliary = (normalized * wm_candidate_value.detach().masked_fill(~candidate_mask, 0.0)).sum(dim=1)
    return base_value + float(scale) * auxiliary


class CriticOnlyGppoAdapter(nn.Module):
    """Equal-capacity G/G-WM scalar critic adapter around the existing GraphPolicy."""

    def __init__(self, hidden_dim: int = 8):
        super().__init__()
        self.value_adapter = nn.Sequential(nn.Linear(1, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1))
        self.source_identity: str | None = None
        self.transform = "detach-WM; detach-policy-probability; candidate-ID-aligned expectation"

    def forward(
        self,
        actor_logits: torch.Tensor,
        base_value: torch.Tensor,
        candidate_mask: torch.Tensor,
        candidate_ids: tuple[str, ...],
        *,
        wm_candidate_value: torch.Tensor | None = None,
        wm_candidate_ids: tuple[str, ...] | None = None,
        wm_enabled: bool,
        wm_source_identity: str | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if actor_logits.ndim != 2 or actor_logits.shape != candidate_mask.shape or candidate_mask.dtype != torch.bool:
            raise ValueError("GPPO_ADAPTER_CANDIDATE_SHAPE")
        if base_value.shape != (actor_logits.shape[0],) or not bool(candidate_mask.any(dim=1).all()):
            raise ValueError("GPPO_ADAPTER_VALUE_SHAPE")
        if actor_logits.shape[0] != 1 or len(candidate_ids) != actor_logits.shape[1] or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("GPPO_ADAPTER_CANDIDATE_BINDING")
        if wm_enabled:
            if (wm_candidate_value is None or wm_candidate_ids is None
                    or wm_candidate_value.shape != (1, len(wm_candidate_ids))
                    or len(set(wm_candidate_ids)) != len(wm_candidate_ids)):
                raise ValueError("GPPO_ADAPTER_WM_SHAPE")
            if not wm_source_identity:
                raise ValueError("GPPO_ADAPTER_WM_PROVENANCE")
            if not set(wm_candidate_ids).issubset(candidate_ids):
                raise ValueError("GPPO_ADAPTER_UNKNOWN_WM_CANDIDATE")
            active_ids = {candidate_ids[index] for index, active in enumerate(candidate_mask[0].tolist()) if active}
            if not active_ids.issubset(wm_candidate_ids):
                raise ValueError("GPPO_ADAPTER_MISSING_WM_CANDIDATE")
            self.source_identity = wm_source_identity
            lookup = {candidate_id: index for index, candidate_id in enumerate(wm_candidate_ids)}
            aligned = wm_candidate_value.new_zeros((1, len(candidate_ids)))
            for index, candidate_id in enumerate(candidate_ids):
                if candidate_id in lookup:
                    aligned[0, index] = wm_candidate_value[0, lookup[candidate_id]]
            auxiliary = critic_only_value(
                torch.zeros_like(base_value), aligned,
                torch.softmax(actor_logits.detach(), dim=-1), candidate_mask,
            )
        else:
            if wm_candidate_value is not None:
                raise ValueError("BASELINE_MUST_NOT_RECEIVE_WM")
            auxiliary = torch.zeros_like(base_value)
        adapted = base_value + self.value_adapter(auxiliary.unsqueeze(-1)).squeeze(-1)
        return actor_logits, adapted

    def provenance(self) -> dict[str, str | None]:
        return {"schema": SCHEMA, "wm_source_identity": self.source_identity, "transform": self.transform}


def gppo_critic_forward(
    policy: nn.Module,
    policy_input: dict[str, Any],
    adapter: CriticOnlyGppoAdapter,
    *,
    legal_candidate_ids: tuple[str, ...] | None = None,
    wm_candidate_value: torch.Tensor | None = None,
    wm_candidate_ids: tuple[str, ...] | None = None,
    wm_enabled: bool,
    wm_source_identity: str | None = None,
) -> tuple[tuple[str, ...], torch.Tensor, torch.Tensor]:
    """Call the reviewed civilian GraphPolicy forward and adapt only its value."""
    try:
        from ..ch2_disaster_relief_graph_v2.graph_policy import encode_public_graph
    except ImportError:
        from graph_policy import encode_public_graph
    graph = encode_public_graph(policy_input)
    logits, base_value = policy._graph_outputs(graph)
    candidate_ids = graph.candidate_ids
    if legal_candidate_ids is None:
        legal_candidate_ids = candidate_ids
    if not set(legal_candidate_ids).issubset(candidate_ids) or len(set(legal_candidate_ids)) != len(legal_candidate_ids):
        raise ValueError("GPPO_LEGAL_CANDIDATE_BINDING")
    legal = set(legal_candidate_ids)
    candidate_mask = torch.tensor([[candidate_id in legal for candidate_id in candidate_ids]], dtype=torch.bool, device=logits.device)
    actor_logits, adapted_value = adapter(
        logits.unsqueeze(0), base_value.reshape(1), candidate_mask, candidate_ids,
        wm_candidate_value=wm_candidate_value,
        wm_candidate_ids=wm_candidate_ids,
        wm_enabled=wm_enabled,
        wm_source_identity=wm_source_identity,
    )
    return candidate_ids, actor_logits.squeeze(0), adapted_value.squeeze(0)


def public_policy_tensors(policy_input: dict[str, Any], *, device: torch.device | str = "cpu") -> tuple[dict[str, torch.Tensor], InputBinding]:
    """Make WM tensors from public fields only; entity IDs remain join metadata."""
    observation = policy_input.get("observation") if isinstance(policy_input, dict) else None
    candidates = policy_input.get("candidates") if isinstance(policy_input, dict) else None
    if not isinstance(observation, dict) or not isinstance(candidates, list) or not candidates:
        raise ValueError("WM_PUBLIC_POLICY_INPUT")
    validate_public_view(observation, candidates, policy_input.get("contract_context"))
    public_tasks = sorted(observation.get("tasks", []), key=lambda item: str(item["id"]))
    public_task_by_id = {task["id"]: task for task in public_tasks}
    candidate_ids = tuple(str(item["id"]) for item in candidates)
    task_ids = tuple(str(item["id"]) for item in public_tasks)
    if candidate_ids.count("NOOP") != 1 or len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("WM_PUBLIC_CANDIDATE_IDS")
    if any(item.get("task_id") is not None and item["task_id"] not in public_task_by_id for item in candidates):
        raise ValueError("WM_CANDIDATE_PRIVATE_TASK_BINDING")
    horizon = max(1.0, float(observation["horizon"]))
    now = float(observation["time"])
    map_data = observation["map"]
    platforms = observation.get("platforms", [])
    context = torch.tensor([[
        now / horizon,
        horizon / 100.0,
        float(map_data["rows"]) / 100.0,
        float(map_data["cols"]) / 100.0,
        len(public_tasks) / max(1.0, len(public_tasks) + len(platforms)),
    ]], dtype=torch.float32, device=device)
    candidate_rows = []
    for candidate in candidates:
        noop = candidate.get("type") == "noop"
        task = public_task_by_id.get(candidate.get("task_id"), {})
        completion = float(candidate.get("estimated_completion", now))
        energy = float(candidate.get("required_energy", 0.0))
        candidate_rows.append([
            float(noop),
            float(candidate.get("type") == "dispatch"),
            max(0.0, completion - now) / horizon,
            energy / 100.0,
        ])
    candidate_features = torch.tensor([candidate_rows], dtype=torch.float32, device=device)
    task_rows = []
    for task in public_tasks:
        task_rows.append([
            float(task.get("kind") == "inspection"),
            float(task.get("kind") == "delivery"),
            max(0.0, float(task.get("deadline", now)) - now) / horizon,
            float(task.get("priority", 0.0)) / 5.0,
            float(task.get("quantity") or 0.0) / 20.0,
        ])
    task_features = torch.tensor([task_rows], dtype=torch.float32, device=device)
    if not task_rows:
        task_features = torch.empty((1, 0, 5), dtype=torch.float32, device=device)
    return {
        "context": context,
        "candidate_features": candidate_features,
        "task_features": task_features,
        "candidate_mask": torch.ones((1, len(candidate_ids)), dtype=torch.bool, device=device),
        "task_mask": torch.ones((1, len(task_ids)), dtype=torch.bool, device=device),
    }, InputBinding((candidate_ids,), (task_ids,))


def branch_records_to_targets(
    candidate_ids: tuple[str, ...],
    task_ids: tuple[str, ...],
    branch_records: list[dict[str, Any]],
    *,
    window_id: tuple[str, int, str],
    device: torch.device | str = "cpu",
) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor], tuple[tuple[str, int, str], ...]]:
    """Join paired branch labels by public IDs into one dynamic parent-window target."""
    if candidate_ids.count("NOOP") != 1 or len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("TARGET_CANDIDATE_IDS")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("TARGET_TASK_IDS")
    by_id = {str(record.get("candidate_id")): record for record in branch_records}
    if len(by_id) != len(branch_records) or set(by_id) != set(candidate_ids):
        raise ValueError("TARGET_CANDIDATE_COVERAGE")
    contexts = [record.get("contract_context") for record in branch_records]
    if not contexts or any(not isinstance(context, dict) for context in contexts):
        raise ValueError("TARGET_CONTEXT_MISSING")
    expected_identity = (window_id[0], window_id[1], window_id[2])
    for record, context in zip(branch_records, contexts):
        identity = (context.get("parent_id"), context.get("repeat"), context.get("window_id"))
        if identity != expected_identity or record.get("window_start") != context.get("time"):
            raise ValueError("TARGET_WINDOW_IDENTITY_MISMATCH")
    if len({record.get("source_state_sha256") for record in branch_records}) != 1:
        raise ValueError("TARGET_SOURCE_IDENTITY_MISMATCH")
    c_count, t_count = len(candidate_ids), len(task_ids)
    target = {
        "binary": torch.zeros((1, c_count, GLOBAL_BINARY_HEADS), dtype=torch.float32, device=device),
        "continuous": torch.zeros((1, c_count, GLOBAL_CONTINUOUS_HEADS), dtype=torch.float32, device=device),
        "per_task": torch.zeros((1, c_count, t_count, TASK_BINARY_HEADS), dtype=torch.float32, device=device),
        "per_task_continuous": torch.zeros((1, c_count, t_count, TASK_CONTINUOUS_HEADS), dtype=torch.float32, device=device),
    }
    valid = {name: torch.zeros_like(value, dtype=torch.bool) for name, value in target.items()}
    for ci, candidate_id in enumerate(candidate_ids):
        record = by_id[candidate_id]
        labels = record.get("paired_targets")
        if not isinstance(labels, dict) or tuple(labels.get("public_task_ids", ())) != task_ids:
            raise ValueError("TARGET_TASK_BINDING")
        if tuple(labels.get("global_binary_names", ())) != GLOBAL_BINARY_NAMES:
            raise ValueError("TARGET_GLOBAL_BINARY_HEAD_ORDER")
        if tuple(labels.get("global_continuous_names", ())) != GLOBAL_CONTINUOUS_NAMES:
            raise ValueError("TARGET_GLOBAL_CONTINUOUS_HEAD_ORDER")
        if tuple(labels.get("task_binary_names", ())) != TASK_BINARY_NAMES:
            raise ValueError("TARGET_TASK_BINARY_HEAD_ORDER")
        if tuple(labels.get("task_continuous_names", ())) != TASK_CONTINUOUS_NAMES:
            raise ValueError("TARGET_TASK_CONTINUOUS_HEAD_ORDER")
        if set(labels.get("task_binary", {})) != set(task_ids) or set(labels.get("task_binary_valid", {})) != set(task_ids):
            raise ValueError("TARGET_TASK_BINARY_COVERAGE")
        if set(labels.get("task_continuous", {})) != set(task_ids) or set(labels.get("task_continuous_valid", {})) != set(task_ids):
            raise ValueError("TARGET_TASK_CONTINUOUS_COVERAGE")
        if (len(labels["global_binary"]) != GLOBAL_BINARY_HEADS
                or len(labels["global_binary_valid"]) != GLOBAL_BINARY_HEADS
                or len(labels["global_continuous"]) != GLOBAL_CONTINUOUS_HEADS
                or len(labels["global_continuous_valid"]) != GLOBAL_CONTINUOUS_HEADS):
            raise ValueError("TARGET_GLOBAL_HEAD_SHAPE")
        target["binary"][0, ci] = torch.as_tensor(labels["global_binary"], dtype=torch.float32, device=device)
        valid["binary"][0, ci] = torch.as_tensor(labels["global_binary_valid"], dtype=torch.bool, device=device)
        target["continuous"][0, ci] = torch.as_tensor(labels["global_continuous"], dtype=torch.float32, device=device)
        valid["continuous"][0, ci] = torch.as_tensor(labels["global_continuous_valid"], dtype=torch.bool, device=device)
        if candidate_id == "NOOP":
            continue
        for ti, task_id in enumerate(task_ids):
            target["per_task"][0, ci, ti] = torch.as_tensor(labels["task_binary"][task_id], dtype=torch.float32, device=device)
            valid["per_task"][0, ci, ti] = torch.as_tensor(labels["task_binary_valid"][task_id], dtype=torch.bool, device=device)
            target["per_task_continuous"][0, ci, ti] = torch.as_tensor(labels["task_continuous"][task_id], dtype=torch.float32, device=device)
            valid["per_task_continuous"][0, ci, ti] = torch.as_tensor(labels["task_continuous_valid"][task_id], dtype=torch.bool, device=device)
    return target, valid, (window_id,)


def public_branch_batch(
    policy_input: dict[str, Any],
    branch_records: list[dict[str, Any]],
    *,
    window_id: tuple[str, int, str],
    device: torch.device | str = "cpu",
) -> dict[str, Any]:
    """Assemble public model inputs and ID-bound branch targets for one window."""
    inputs, binding = public_policy_tensors(policy_input, device=device)
    candidate_ids = binding.candidate_ids[0]
    task_ids = binding.task_ids[0]
    target, valid, window_ids = branch_records_to_targets(
        candidate_ids, task_ids, branch_records, window_id=window_id, device=device,
    )
    return {"inputs": {**inputs, "binding": binding}, "target": target, "valid": valid, "window_ids": window_ids}


class CriticAugmentedGraphPolicy:
    """PPO policy facade: existing GraphPolicy actor; detached WM critic-only path."""

    def __init__(self, base_policy: nn.Module, adapter: CriticOnlyGppoAdapter, world_model: DynamicConsequenceModel):
        self.base_policy = base_policy
        self.adapter = adapter
        self.world_model = world_model.requires_grad_(False).eval()
        self.variant = base_policy.variant
        self.source_identity = _tensor_state_digest(self.world_model.state_dict())
        self.fallback_counts: dict[str, int] = {"only_noop": 0}

    @property
    def architecture_evidence(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "policy_variant": self.variant,
            "critic_adapter_type": type(self.adapter).__name__,
            "critic_adapter_parameter_count": sum(parameter.numel() for parameter in self.adapter.parameters()),
            "wm_source_identity": self.source_identity,
            "wm_input_source": "public_policy_input_only",
            "wm_transform": self.adapter.transform,
            "actor_reads_wm": False,
            "wm_trainable_in_policy_optimizer": False,
            "wrapper_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
        }

    def parameters(self):
        yield from self.base_policy.parameters()
        yield from self.adapter.parameters()

    def state_dict(self) -> dict[str, torch.Tensor]:
        result = {f"policy.{name}": value for name, value in self.base_policy.state_dict().items()}
        result.update({f"adapter.{name}": value for name, value in self.adapter.state_dict().items()})
        result.update({f"world_model.{name}": value for name, value in self.world_model.state_dict().items()})
        return result

    def load_state_dict(self, state_dict: dict[str, torch.Tensor], strict: bool = True) -> None:
        prefixes = ("policy.", "adapter.", "world_model.")
        unknown = [key for key in state_dict if not any(key.startswith(prefix) for prefix in prefixes)]
        if strict and unknown:
            raise ValueError("CRITIC_AUGMENTED_STATE_KEY_UNKNOWN")
        groups = {}
        for prefix in prefixes:
            groups[prefix] = {key[len(prefix):]: value for key, value in state_dict.items() if key.startswith(prefix)}
        if strict and any(not group for group in groups.values()):
            raise ValueError("CRITIC_AUGMENTED_STATE_GROUP_MISSING")
        if strict:
            expected = {
                "policy.": set(self.base_policy.state_dict()),
                "adapter.": set(self.adapter.state_dict()),
                "world_model.": set(self.world_model.state_dict()),
            }
            if any(set(groups[prefix]) != keys for prefix, keys in expected.items()):
                raise ValueError("CRITIC_AUGMENTED_STATE_KEYS_MISMATCH")
            if _tensor_state_digest(groups["world_model."]) != self.source_identity:
                raise ValueError("CRITIC_AUGMENTED_WM_SOURCE_MISMATCH")
        self.base_policy.load_state_dict(groups["policy."], strict=strict)
        self.adapter.load_state_dict(groups["adapter."], strict=strict)
        self.world_model.load_state_dict(groups["world_model."], strict=strict)
        self.world_model.requires_grad_(False).eval()
        restored_source = _tensor_state_digest(self.world_model.state_dict())
        if restored_source != self.source_identity:
            raise ValueError("CRITIC_AUGMENTED_WM_SOURCE_MISMATCH")

    def train(self, mode: bool = True):
        self.base_policy.train(mode)
        self.adapter.train(mode)
        self.world_model.eval()
        return self

    def eval(self):
        return self.train(False)

    def _adapt_value(self, policy_input: dict[str, Any], base_value: torch.Tensor, actor_logits: torch.Tensor) -> torch.Tensor:
        candidate_ids = tuple(str(item["id"]) for item in policy_input["candidates"])
        enabled = any(candidate_id != "NOOP" for candidate_id in candidate_ids)
        if not enabled:
            self.fallback_counts["only_noop"] += 1
            values = None
            wm_ids = None
        else:
            features, binding = public_policy_tensors(policy_input, device=next(self.world_model.parameters()).device)
            with torch.no_grad():
                output = self.world_model(
                    features["context"], features["candidate_features"], features["task_features"],
                    features["candidate_mask"], features["task_mask"], binding,
                )
                values = output["continuous"][:, :, 0]
            wm_ids = binding.candidate_ids[0]
        _, adapted = self.adapter(
            actor_logits.unsqueeze(0), base_value.reshape(1),
            torch.ones((1, len(candidate_ids)), dtype=torch.bool, device=actor_logits.device),
            candidate_ids, wm_candidate_value=values, wm_candidate_ids=wm_ids,
            wm_enabled=enabled, wm_source_identity=self.source_identity if enabled else None,
        )
        return adapted.squeeze(0)

    def sample_batch(self, policy_input: dict[str, Any], deterministic: bool = False) -> dict[str, Any]:
        sample = self.base_policy.sample_batch(policy_input, deterministic=deterministic)
        graph = self._encoded(policy_input)
        logits, base_value = self.base_policy._graph_outputs(graph)
        sample["value"] = self._adapt_value(policy_input, base_value, logits)
        return sample

    def evaluate_batch(self, policy_input: dict[str, Any], actions: list[str], masks: list[dict[str, Any]]) -> dict[str, Any]:
        output = self.base_policy.evaluate_batch(policy_input, actions, masks)
        graph = self._encoded(policy_input)
        logits, base_value = self.base_policy._graph_outputs(graph)
        output["value"] = self._adapt_value(policy_input, base_value, logits)
        return output

    def value(self, policy_input: dict[str, Any]) -> torch.Tensor:
        graph = self._encoded(policy_input)
        logits, base_value = self.base_policy._graph_outputs(graph)
        return self._adapt_value(policy_input, base_value, logits)

    def _encoded(self, policy_input: dict[str, Any]):
        try:
            from ..ch2_disaster_relief_graph_v2.graph_policy import encode_public_graph
        except ImportError:
            from graph_policy import encode_public_graph
        return encode_public_graph(policy_input)


class GppoEngineeringTrainer:
    """One real scalar-PPO actor/critic update through the shared civilian policy."""

    def __init__(
        self,
        policy: nn.Module,
        adapter: CriticOnlyGppoAdapter,
        *,
        data_identity: str,
        wm_enabled: bool,
        wm_source_identity: str | None,
        learning_rate: float = 1e-3,
    ):
        if not data_identity:
            raise ValueError("GPPO_DATA_IDENTITY_REQUIRED")
        if wm_enabled and not wm_source_identity:
            raise ValueError("GPPO_WM_SOURCE_REQUIRED")
        self.policy = policy
        self.adapter = adapter
        self.data_identity = data_identity
        self.wm_enabled = bool(wm_enabled)
        self.wm_source_identity = wm_source_identity
        self.learning_rate = float(learning_rate)
        self.optimizer = torch.optim.Adam([
            {"params": list(policy.parameters()), "name": "gppo_policy"},
            {"params": list(adapter.parameters()), "name": "critic_adapter"},
        ], lr=self.learning_rate)
        self.update_index = 0
        self.next_batch_index = 0

    def _metadata(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "policy_variant": self.policy.variant,
            "adapter_config": {"type": type(self.adapter).__name__, "parameter_count": sum(p.numel() for p in self.adapter.parameters())},
            "data_identity": self.data_identity,
            "wm_enabled": self.wm_enabled,
            "wm_source_identity": self.wm_source_identity,
            "wm_transform": self.adapter.transform,
            "learning_rate": self.learning_rate,
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
        }

    def update(
        self,
        policy_input: dict[str, Any],
        *,
        selected_candidate_id: str,
        legal_candidate_ids: tuple[str, ...],
        old_log_probability: torch.Tensor,
        advantage: torch.Tensor,
        return_target: torch.Tensor,
        wm_candidate_value: torch.Tensor | None,
        wm_candidate_ids: tuple[str, ...] | None,
        batch_index: int,
        clip_ratio: float = 0.2,
        failpoint: str | None = None,
    ) -> dict[str, Any]:
        if failpoint not in (None, "after_optimizer_step"):
            raise ValueError("GPPO_UNKNOWN_FAILPOINT")
        if batch_index != self.next_batch_index:
            raise ValueError("GPPO_BATCH_BOUNDARY")
        candidate_ids, logits, value = gppo_critic_forward(
            self.policy, policy_input, self.adapter,
            legal_candidate_ids=legal_candidate_ids,
            wm_candidate_value=wm_candidate_value,
            wm_candidate_ids=wm_candidate_ids,
            wm_enabled=self.wm_enabled,
            wm_source_identity=self.wm_source_identity,
        )
        if selected_candidate_id not in legal_candidate_ids or selected_candidate_id not in candidate_ids:
            raise ValueError("GPPO_SELECTED_CANDIDATE_INVALID")
        if old_log_probability.numel() != 1 or advantage.numel() != 1 or return_target.numel() != 1:
            raise ValueError("GPPO_TARGET_SHAPE")
        mask = torch.tensor([candidate_id in set(legal_candidate_ids) for candidate_id in candidate_ids], dtype=torch.bool, device=logits.device)
        distribution = torch.distributions.Categorical(logits=logits.masked_fill(~mask, torch.finfo(logits.dtype).min))
        selected_index = candidate_ids.index(selected_candidate_id)
        log_probability = distribution.log_prob(torch.tensor(selected_index, device=logits.device))
        ratio = torch.exp(log_probability - old_log_probability.reshape(()))
        clipped = ratio.clamp(1.0 - clip_ratio, 1.0 + clip_ratio)
        actor_loss = -torch.minimum(ratio * advantage.reshape(()), clipped * advantage.reshape(()))
        value_loss = 0.5 * (value.reshape(()) - return_target.reshape(())) ** 2
        loss = actor_loss + value_loss
        if not bool(torch.isfinite(loss)):
            raise ValueError("GPPO_NONFINITE_LOSS")

        params = list(self.policy.parameters()) + list(self.adapter.parameters())
        model_before = copy.deepcopy(self.policy.state_dict())
        adapter_before = copy.deepcopy(self.adapter.state_dict())
        optimizer_before = copy.deepcopy(self.optimizer.state_dict())
        rng_before = torch.random.get_rng_state().clone()
        update_index_before = self.update_index
        next_batch_index_before = self.next_batch_index
        self.optimizer.zero_grad(set_to_none=True)
        try:
            loss.backward()
            gradients = [p.grad for p in params if p.grad is not None]
            if not gradients or not all(torch.isfinite(gradient).all() for gradient in gradients):
                raise ValueError("GPPO_NONFINITE_OR_EMPTY_GRADIENT")
            self.optimizer.step()
            if failpoint == "after_optimizer_step":
                raise RuntimeError("GPPO_INJECTED_AFTER_OPTIMIZER_STEP")
            self.update_index += 1
            self.next_batch_index = batch_index + 1
            return {
                "update_index": self.update_index,
                "batch_index": batch_index,
                "actor_loss": float(actor_loss.detach()),
                "value_loss": float(value_loss.detach()),
                "total_loss": float(loss.detach()),
                "actor_logits_sha256": hashlib.sha256(logits.detach().cpu().contiguous().numpy().tobytes()).hexdigest().upper(),
                "metadata": self._metadata(),
            }
        except BaseException:
            self.policy.load_state_dict(model_before, strict=True)
            self.adapter.load_state_dict(adapter_before, strict=True)
            self.optimizer.load_state_dict(optimizer_before)
            torch.random.set_rng_state(rng_before)
            self.update_index = update_index_before
            self.next_batch_index = next_batch_index_before
            self.optimizer.zero_grad(set_to_none=True)
            raise

    def save_checkpoint(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = self._metadata()
        payload = {
            "metadata": metadata,
            "metadata_sha256": hashlib.sha256(json.dumps(metadata, sort_keys=True).encode("utf-8")).hexdigest().upper(),
            "policy": self.policy.state_dict(),
            "adapter": self.adapter.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "update_index": self.update_index,
            "next_batch_index": self.next_batch_index,
            "torch_rng_state": torch.random.get_rng_state(),
        }
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".pending")
        try:
            temporary.write_bytes(buffer.getvalue())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return {"path": str(path), "metadata_sha256": payload["metadata_sha256"], "next_batch_index": self.next_batch_index}

    def restore_checkpoint(self, path: str | Path) -> dict[str, Any]:
        payload = torch.load(Path(path), map_location=next(self.policy.parameters()).device, weights_only=False)
        expected = self._metadata()
        digest = hashlib.sha256(json.dumps(expected, sort_keys=True).encode("utf-8")).hexdigest().upper()
        if payload.get("metadata") != expected or payload.get("metadata_sha256") != digest:
            raise ValueError("GPPO_CHECKPOINT_IDENTITY_MISMATCH")
        checkpoint_update = int(payload["update_index"])
        checkpoint_batch = int(payload["next_batch_index"])
        if checkpoint_update != checkpoint_batch:
            raise ValueError("GPPO_CHECKPOINT_BOUNDARY")
        policy_before = copy.deepcopy(self.policy.state_dict())
        adapter_before = copy.deepcopy(self.adapter.state_dict())
        optimizer_before = copy.deepcopy(self.optimizer.state_dict())
        rng_before = torch.random.get_rng_state().clone()
        update_index_before, next_batch_index_before = self.update_index, self.next_batch_index
        try:
            self.policy.load_state_dict(payload["policy"], strict=True)
            self.adapter.load_state_dict(payload["adapter"], strict=True)
            self.optimizer.load_state_dict(payload["optimizer"])
            torch.random.set_rng_state(payload["torch_rng_state"].cpu())
            self.update_index = checkpoint_update
            self.next_batch_index = checkpoint_batch
        except BaseException:
            self.policy.load_state_dict(policy_before, strict=True)
            self.adapter.load_state_dict(adapter_before, strict=True)
            self.optimizer.load_state_dict(optimizer_before)
            torch.random.set_rng_state(rng_before)
            self.update_index, self.next_batch_index = update_index_before, next_batch_index_before
            raise
        return {"update_index": self.update_index, "next_batch_index": self.next_batch_index}


def _tensor_state_digest(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(json.dumps(list(value.shape)).encode("ascii"))
        digest.update(value.numpy().tobytes())
    return digest.hexdigest().upper()


class EngineeringTrainer:
    """Small real optimizer path with strict identity and rollback probes."""

    def __init__(self, model: DynamicConsequenceModel, *, data_identity: str, learning_rate: float = 1e-3):
        if not data_identity:
            raise ValueError("DATA_IDENTITY_REQUIRED")
        self.model = model
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.data_identity = data_identity
        self.update_index = 0
        self.learning_rate = float(learning_rate)

    def _identity(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "model_config": self.model.config,
            "data_identity": self.data_identity,
            "learning_rate": self.learning_rate,
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
        }

    def update(self, batch: dict[str, Any], *, failpoint: str | None = None) -> dict[str, Any]:
        if failpoint not in (None, "after_optimizer_step"):
            raise ValueError("UNKNOWN_FAILPOINT")
        # Validate bindings and target support before touching gradients or state.
        inputs = batch["inputs"]
        prediction_probe = self.model(
            inputs["context"], inputs["candidate_features"], inputs["task_features"],
            inputs["candidate_mask"], inputs["task_mask"], inputs["binding"],
        )
        loss_probe, _ = consequence_loss(prediction_probe, batch["target"], batch["valid"], batch["window_ids"])
        if not bool(torch.isfinite(loss_probe)):
            raise ValueError("NONFINITE_LOSS")

        model_before = copy.deepcopy(self.model.state_dict())
        optimizer_before = copy.deepcopy(self.optimizer.state_dict())
        rng_before = torch.random.get_rng_state().clone()
        self.optimizer.zero_grad(set_to_none=True)
        try:
            prediction = self.model(
                inputs["context"], inputs["candidate_features"], inputs["task_features"],
                inputs["candidate_mask"], inputs["task_mask"], inputs["binding"],
            )
            loss, parts = consequence_loss(prediction, batch["target"], batch["valid"], batch["window_ids"])
            loss.backward()
            gradients = [p.grad for p in self.model.parameters() if p.grad is not None]
            if not gradients or not all(torch.isfinite(grad).all() for grad in gradients):
                raise ValueError("NONFINITE_OR_EMPTY_GRADIENT")
            self.optimizer.step()
            if failpoint == "after_optimizer_step":
                raise RuntimeError("INJECTED_AFTER_OPTIMIZER_STEP")
            self.update_index += 1
            return {
                "update_index": self.update_index,
                "loss": float(loss.detach()),
                "parts": {key: float(value.detach()) if isinstance(value, torch.Tensor) else value
                          for key, value in parts.items()},
                "parameter_sha256": _tensor_state_digest(self.model.state_dict()),
            }
        except BaseException:
            self.model.load_state_dict(model_before, strict=True)
            self.optimizer.load_state_dict(optimizer_before)
            torch.random.set_rng_state(rng_before)
            self.optimizer.zero_grad(set_to_none=True)
            raise

    def save_checkpoint(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        identity = self._identity()
        payload = {
            "identity": identity,
            "identity_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest().upper(),
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "update_index": self.update_index,
            "next_update_index": self.update_index,
            "sampler_position": self.update_index,
            "torch_rng_state": torch.random.get_rng_state(),
            "model_sha256": _tensor_state_digest(self.model.state_dict()),
        }
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(buffer.getvalue())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return {"path": str(path), "identity_sha256": payload["identity_sha256"], "model_sha256": payload["model_sha256"]}

    def restore_checkpoint(self, path: str | Path) -> dict[str, Any]:
        payload = torch.load(Path(path), map_location=next(self.model.parameters()).device, weights_only=False)
        expected_identity = self._identity()
        expected_digest = hashlib.sha256(json.dumps(expected_identity, sort_keys=True).encode("utf-8")).hexdigest().upper()
        if payload.get("identity") != expected_identity or payload.get("identity_sha256") != expected_digest:
            raise ValueError("CHECKPOINT_IDENTITY_MISMATCH")
        checkpoint_update = int(payload["update_index"])
        if checkpoint_update != int(payload["next_update_index"]) or checkpoint_update != int(payload["sampler_position"]):
            raise ValueError("CHECKPOINT_UPDATE_BOUNDARY")
        model_before = copy.deepcopy(self.model.state_dict())
        optimizer_before = copy.deepcopy(self.optimizer.state_dict())
        rng_before = torch.random.get_rng_state().clone()
        update_index_before = self.update_index
        try:
            self.model.load_state_dict(payload["model"], strict=True)
            if _tensor_state_digest(self.model.state_dict()) != payload.get("model_sha256"):
                raise ValueError("CHECKPOINT_MODEL_DIGEST")
            self.optimizer.load_state_dict(payload["optimizer"])
            torch.random.set_rng_state(payload["torch_rng_state"].cpu())
            self.update_index = checkpoint_update
        except BaseException:
            self.model.load_state_dict(model_before, strict=True)
            self.optimizer.load_state_dict(optimizer_before)
            torch.random.set_rng_state(rng_before)
            self.update_index = update_index_before
            raise
        return {"update_index": self.update_index, "model_sha256": payload["model_sha256"]}
