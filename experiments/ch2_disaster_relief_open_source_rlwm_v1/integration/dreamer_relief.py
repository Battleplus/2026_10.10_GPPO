"""A small public-mask and physical-time overlay for pinned R2-Dreamer.

The encoder, RSSM, reconstruction/reward/continuation heads, actor/value heads,
replay implementation, and optimizer are from NM512/r2dreamer at
``546e4fab8146ea4b14e1d7726bbc1a8a1d50322f``.  The copied ``_cal_grad``
structure follows that revision's standard ``rep_loss == 'dreamer'`` branch;
it is overridden only because the upstream implementation assumes one
discounted model step per action and does not apply action masks.
"""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch import nn
from torch.amp import GradScaler, autocast
from torch.distributions import Categorical
from torch.optim.lr_scheduler import LambdaLR


PINNED_UPSTREAM_REVISION = "546e4fab8146ea4b14e1d7726bbc1a8a1d50322f"
_UPSTREAM_ROOT = (
    Path(__file__).resolve().parents[1]
    / "upstream_r2"
    / f"r2dreamer-{PINNED_UPSTREAM_REVISION}"
)
if not _UPSTREAM_ROOT.is_dir():
    raise RuntimeError(f"pinned R2-Dreamer source is missing: {_UPSTREAM_ROOT}")

_upstream_path = str(_UPSTREAM_ROOT)
if _upstream_path in sys.path:
    sys.path.remove(_upstream_path)
sys.path.insert(0, _upstream_path)

existing_dreamer = sys.modules.get("dreamer")
if existing_dreamer is not None:
    existing_path = Path(getattr(existing_dreamer, "__file__", "")).resolve().parent
    if existing_path != _UPSTREAM_ROOT.resolve():
        raise RuntimeError(f"a different 'dreamer' module is already imported: {existing_path}")

from dreamer import Dreamer as R2Dreamer  # noqa: E402
from buffer import Buffer as R2Buffer  # noqa: E402
from optim import LaProp  # noqa: E402
import networks  # noqa: E402
import tools  # noqa: E402
from tools import to_f32  # noqa: E402


ADAPTER_SCHEMA = "relief-dreamer-adapter/1"
OBSERVATION_SCHEMA = "relief-public-observation/1"
MASK_THRESHOLD = 0.5


class ReliefReplayBuffer(R2Buffer):
    """Pinned R2 storage/sampler with an isolated previous-action shift.

    The overlay clones each sampled TensorDict before assigning the shifted
    action key. This avoids overlapping-view mutation in the current
    compatibility runtime while retaining the upstream replay storage and
    SliceSampler. When frame IDs are supplied, every sample is identity-checked.
    """

    overlay_name = "relief-replay-clone-before-action-shift/1"

    def __init__(self, config):
        super().__init__(config)
        self.sample_count = 0
        self.alignment_trace: list[dict[str, Any]] = []

    def sample(self):
        sampled_raw, info = self._buffer.sample(return_info=True)
        sampled_view = sampled_raw.view(-1, self.batch_length + 1)
        raw_action_before = sampled_view["action"].clone()
        raw_frame_ids_before = (
            sampled_view["frame_id"].clone()
            if "frame_id" in sampled_view.keys()
            else None
        )
        sampled = sampled_view.clone()
        if sampled.device.type == "cpu" and self.device.type == "cuda":
            sampled = sampled.pin_memory().to(self.device, non_blocking=True)
        elif sampled.device != self.device:
            sampled = sampled.to(self.device, non_blocking=True)

        initial = (sampled["stoch"][:, 0], sampled["deter"][:, 0])
        source_action = sampled["action"][:, :-1].clone()
        data = sampled[:, 1:].clone()
        data.set_("action", source_action)
        index = [
            ind.view(-1, self.batch_length + 1)[:, 1:]
            for ind in info["index"]
        ]

        check: dict[str, Any] = {
            "sample_index": self.sample_count,
            "action_shift_applied": True,
            "sampled_source_unchanged": torch.equal(
                sampled_view["action"], raw_action_before
            ),
            "frame_identity_checked": "frame_id" in sampled.keys(),
        }
        if not check["sampled_source_unchanged"]:
            raise RuntimeError("sampling overlay modified its source action tensor")
        if "frame_id" in sampled.keys():
            source_ids = sampled["frame_id"][:, :-1]
            target_ids = sampled["frame_id"][:, 1:]
            if not torch.equal(target_ids, source_ids + 1):
                raise RuntimeError("sampled frame identities are not contiguous")
            if raw_frame_ids_before is None or not torch.equal(
                sampled_view["frame_id"], raw_frame_ids_before
            ):
                raise RuntimeError("sampling overlay modified source frame identities")
            if not torch.equal(data["action"], source_action):
                raise RuntimeError("sampled action is not aligned to its source frame")
            if "action_mask" in data.keys() and not torch.equal(
                data["action_mask"], sampled["action_mask"][:, 1:]
            ):
                raise RuntimeError("sampled action mask lost its target-frame identity")
            if "dt" in data.keys() and not torch.equal(
                data["dt"], sampled["dt"][:, 1:]
            ):
                raise RuntimeError("sampled dt lost its target-frame identity")
            check["source_frame_ids"] = source_ids.detach().cpu().tolist()
            check["target_frame_ids"] = target_ids.detach().cpu().tolist()
            check["source_action_indices"] = source_action.argmax(-1).detach().cpu().tolist()
            check["shifted_action_indices"] = data["action"].argmax(-1).detach().cpu().tolist()
        if len(self.alignment_trace) == 64:
            self.alignment_trace.pop(0)
        self.alignment_trace.append(check)
        self.sample_count += 1
        return data, index, initial


class _DiscreteOneHotSpace:
    """Expose a Gym Discrete space through R2-Dreamer's one-hot convention."""

    def __init__(self, n: int):
        self.n = int(n)
        self.shape = (self.n,)
        self.discrete = True


def _tensor(value: Any, *, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value.to(device=device, dtype=dtype)
    return torch.as_tensor(value, device=device, dtype=dtype)


def _validate_dt(dt: torch.Tensor) -> torch.Tensor:
    dt = to_f32(dt)
    if dt.ndim == 2:
        dt = dt.unsqueeze(-1)
    if dt.ndim < 3 or dt.shape[-1] != 1:
        raise ValueError(f"dt must have shape (..., time, 1), got {tuple(dt.shape)}")
    if not torch.isfinite(dt).all():
        raise ValueError("dt contains a non-finite value")
    if not torch.logical_or(dt == 0.0, dt == 1.0).all():
        raise ValueError("the relief adapter contract permits only dt=0 or dt=1")
    return dt


def time_discount_powers(
    dt: torch.Tensor,
    gamma: float,
    trace_lambda: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return per-transition gamma**dt and lambda**dt for physical minutes."""
    dt = _validate_dt(dt)
    if not (0.0 <= gamma <= 1.0 and 0.0 <= trace_lambda <= 1.0):
        raise ValueError("gamma and trace_lambda must be in [0, 1]")
    return torch.pow(torch.as_tensor(gamma, device=dt.device), dt), torch.pow(
        torch.as_tensor(trace_lambda, device=dt.device), dt
    )


def shift_outgoing_time_powers(
    outgoing_dt: torch.Tensor,
    gamma: float,
    trace_lambda: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Align imagined action durations with the states they produce.

    R2-Dreamer computes returns from rewards at indices ``1:`` and pairs them
    with actions at ``:-1``.  Index zero therefore has no incoming imagined
    transition and receives unit powers.
    """
    outgoing_dt = _validate_dt(outgoing_dt)
    gamma_pow, lambda_pow = time_discount_powers(outgoing_dt, gamma, trace_lambda)
    incoming_gamma = torch.ones_like(gamma_pow)
    incoming_lambda = torch.ones_like(lambda_pow)
    incoming_gamma[:, 1:] = gamma_pow[:, :-1]
    incoming_lambda[:, 1:] = lambda_pow[:, :-1]
    return incoming_gamma, incoming_lambda


def physical_time_reward_continuation(
    predicted_reward: torch.Tensor,
    predicted_continuation: torch.Tensor,
    incoming_dt: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Enforce adapter semantics for zero-time selection microsteps."""
    incoming_dt = _validate_dt(incoming_dt)
    if predicted_reward.shape != predicted_continuation.shape:
        raise ValueError("reward and continuation predictions must have matching shapes")
    if predicted_reward.shape != incoming_dt.shape:
        raise ValueError("incoming dt must align with reward and continuation predictions")
    if not torch.isfinite(predicted_reward).all() or not torch.isfinite(predicted_continuation).all():
        raise ValueError("reward and continuation predictions must be finite")
    zero_time = incoming_dt == 0.0
    reward = torch.where(zero_time, torch.zeros_like(predicted_reward), predicted_reward)
    continuation = torch.where(
        zero_time, torch.ones_like(predicted_continuation), predicted_continuation
    )
    return reward, continuation


def lambda_return_by_physical_time(
    last: torch.Tensor,
    terminal: torch.Tensor,
    reward: torch.Tensor,
    value: torch.Tensor,
    bootstrap: torch.Tensor,
    incoming_dt: torch.Tensor,
    gamma: float,
    trace_lambda: float,
) -> torch.Tensor:
    """R2-style lambda return with discounts based on elapsed physical minutes.

    ``incoming_dt[:, t]`` describes the transition that produced state/reward
    at ``t``.  Truncation stops the trace but still bootstraps; termination
    disables both continuation and bootstrap.
    """
    if not (last.shape == terminal.shape == reward.shape == value.shape == bootstrap.shape):
        raise ValueError("last, terminal, reward, value and bootstrap shapes must match")
    incoming_dt = _validate_dt(incoming_dt)
    if incoming_dt.shape != reward.shape:
        raise ValueError("incoming dt must align with the state/reward sequence")
    gamma_pow, lambda_pow = time_discount_powers(incoming_dt, gamma, trace_lambda)
    live = (1.0 - to_f32(terminal))[:, 1:] * gamma_pow[:, 1:]
    continuation = (1.0 - to_f32(last))[:, 1:] * lambda_pow[:, 1:]
    interm = to_f32(reward)[:, 1:] + (1.0 - continuation) * live * to_f32(bootstrap)[:, 1:]
    output = [to_f32(bootstrap)[:, -1]]
    for index in reversed(range(live.shape[1])):
        output.append(interm[:, index] + live[:, index] * continuation[:, index] * output[-1])
    return torch.stack(list(reversed(output))[:-1], dim=1)


def adapter_frame_tensors(
    observation: dict[str, Any],
    *,
    is_first: bool | None = None,
    outgoing_action: int | torch.Tensor,
    incoming_reward: float | None = None,
    incoming_dt: int | None = None,
    incoming_terminated: bool | None = None,
    incoming_truncated: bool | None = None,
    episode_id: int,
    device: str | torch.device = "cpu",
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    """Convert one adapter observation to an R2 replay frame.

    The action stored in frame ``t`` is outgoing from observation ``t``.
    Reward/terminal flags/dt in frame ``t`` are the incoming result of the
    action from frame ``t-1``; this is the alignment expected by R2 ``Buffer``.
    Adapter identities are returned separately and never enter the encoder.
    """
    if not isinstance(observation, dict) or observation.get("schema") != ADAPTER_SCHEMA:
        raise ValueError("unsupported relief adapter observation schema")
    if observation.get("simulator_observation_schema") not in (None, OBSERVATION_SCHEMA):
        raise ValueError("unsupported simulator public-observation schema")
    if is_first is None:
        is_first = bool(observation.get("is_first", False))
    if incoming_reward is None:
        incoming_reward = float(observation.get("reward", 0.0))
    if incoming_dt is None:
        incoming_dt = int(observation.get("dt", 0))
    if incoming_terminated is None:
        incoming_terminated = bool(observation.get("is_terminal", False))
    if incoming_truncated is None:
        is_last = bool(observation.get("is_last", False))
        incoming_truncated = is_last and not incoming_terminated
    action_size = observation.get("action_size")
    if type(action_size) is not int or action_size <= 1:
        raise ValueError("adapter action_size must be a positive fixed integer")
    action_keys = observation.get("action_keys")
    if not isinstance(action_keys, (tuple, list)) or len(action_keys) != action_size:
        raise ValueError("adapter action key table does not match action_size")
    mask = _tensor(observation.get("action_mask"), device=torch.device(device), dtype=torch.bool)
    if mask.shape != (action_size,):
        raise ValueError("adapter action mask does not match action_size")
    commit_index = observation.get("commit_action_index", action_size - 1)
    if type(commit_index) is not int or not (0 <= commit_index < action_size):
        raise ValueError("invalid adapter COMMIT action index")
    if not bool(mask[commit_index]):
        raise ValueError("adapter must keep COMMIT legal")

    vector = _tensor(observation.get("vector"), device=torch.device(device), dtype=torch.float32)
    if vector.ndim != 1 or vector.numel() != observation.get("vector_length"):
        raise ValueError("adapter vector shape does not match vector_length")
    if not torch.isfinite(vector).all():
        raise ValueError("adapter vector contains non-finite features")

    if isinstance(outgoing_action, torch.Tensor):
        action = outgoing_action.to(device=device, dtype=torch.float32).reshape(-1)
        if action.shape != (action_size,):
            raise ValueError("outgoing one-hot action has the wrong shape")
        if not torch.equal(action, F.one_hot(action.argmax(), action_size).to(action.dtype)):
            raise ValueError("outgoing action must be one-hot")
    else:
        if isinstance(outgoing_action, bool) or not isinstance(outgoing_action, int):
            raise TypeError("outgoing_action must be an action index or one-hot tensor")
        if not (0 <= outgoing_action < action_size):
            raise ValueError("outgoing action is outside the adapter action space")
        action = F.one_hot(torch.tensor(outgoing_action), action_size).to(torch.float32).to(device)
    if not bool(mask[action.argmax()]):
        raise ValueError("outgoing action is masked in the current public observation")
    if incoming_dt not in (0, 1):
        raise ValueError("incoming dt must be 0 or 1")
    if incoming_dt == 0 and incoming_terminated:
        raise ValueError("a zero-time decision microstep cannot terminate an episode")
    if incoming_terminated and incoming_truncated:
        raise ValueError("a transition cannot be both terminated and truncated")

    frame = {
        "vector": vector.unsqueeze(0),
        "action_mask": mask.unsqueeze(0),
        "is_first": torch.tensor([is_first], device=device, dtype=torch.bool),
        "action": action.unsqueeze(0),
        "reward": torch.tensor([[incoming_reward]], device=device, dtype=torch.float32),
        "dt": torch.tensor([[incoming_dt]], device=device, dtype=torch.float32),
        "is_terminal": torch.tensor([[incoming_terminated]], device=device, dtype=torch.bool),
        "is_last": torch.tensor([[incoming_terminated or incoming_truncated]], device=device, dtype=torch.bool),
        "episode": torch.tensor([episode_id], device=device, dtype=torch.int32),
    }
    binding = {
        "schema": observation["schema"],
        "adapter_signature_sha256": observation.get("adapter_signature_sha256"),
        "feature_layout_sha256": observation.get("feature_layout_sha256"),
        "action_size": action_size,
        "commit_action_index": commit_index,
        "action_keys": tuple(action_keys),
        "task_ids_by_slot": tuple(observation.get("task_ids_by_slot", ())),
        "platform_ids_by_slot": tuple(observation.get("platform_ids_by_slot", ())),
    }
    return frame, binding


def checkpoint_metadata(
    *,
    adapter_signature_sha256: str,
    feature_layout_sha256: str,
    action_size: int,
    commit_action_index: int,
    gamma: float,
    trace_lambda: float,
) -> dict[str, Any]:
    """Return the external metadata that binds a checkpoint to its interface."""
    if not adapter_signature_sha256 or not feature_layout_sha256:
        raise ValueError("adapter and feature-layout hashes are required")
    return {
        "upstream_repository": "NM512/r2dreamer",
        "upstream_revision": PINNED_UPSTREAM_REVISION,
        "representation_loss": "dreamer",
        "adapter_schema": ADAPTER_SCHEMA,
        "simulator_observation_schema": OBSERVATION_SCHEMA,
        "adapter_signature_sha256": adapter_signature_sha256,
        "feature_layout_sha256": feature_layout_sha256,
        "action_size": int(action_size),
        "commit_action_index": int(commit_action_index),
        "gamma_per_physical_minute": float(gamma),
        "lambda_per_physical_minute": float(trace_lambda),
        "mask_threshold": MASK_THRESHOLD,
        "mask_loss": "per_frame_balanced_binary_cross_entropy",
        "replay_alignment": "outgoing_action_frame; incoming_reward_dt_flags_frame",
        "replay_buffer_class": "integration.dreamer_relief.ReliefReplayBuffer",
        "replay_buffer_base": "NM512/r2dreamer.Buffer",
        "replay_buffer_revision": PINNED_UPSTREAM_REVISION,
        "replay_buffer_sample_overlay": ReliefReplayBuffer.overlay_name,
    }


def validate_checkpoint_metadata(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    keys = (
        "upstream_revision",
        "representation_loss",
        "adapter_schema",
        "simulator_observation_schema",
        "adapter_signature_sha256",
        "feature_layout_sha256",
        "action_size",
        "commit_action_index",
        "gamma_per_physical_minute",
        "lambda_per_physical_minute",
        "mask_threshold",
        "mask_loss",
        "replay_alignment",
        "replay_buffer_class",
        "replay_buffer_base",
        "replay_buffer_revision",
        "replay_buffer_sample_overlay",
    )
    for key in keys:
        if actual.get(key) != expected.get(key):
            raise ValueError(f"checkpoint contract mismatch for {key}")


def predicted_imagination_mask(
    logits: torch.Tensor,
    *,
    commit_action_index: int,
    threshold: float = MASK_THRESHOLD,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Threshold a model prediction and guarantee a legal COMMIT fallback."""
    if logits.ndim < 1 or not (0 <= commit_action_index < logits.shape[-1]):
        raise ValueError("invalid mask logits or COMMIT index")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("mask threshold must be in [0, 1]")
    predicted = torch.sigmoid(to_f32(logits)) >= threshold
    fallback = ~predicted.any(dim=-1)
    predicted = predicted.clone()
    predicted[..., commit_action_index] = True
    return predicted, fallback


class _MaskedOneHotDistribution:
    """Straight-through one-hot policy with exact-zero illegal probabilities.

    Finite masked logits avoid the ``-inf - -inf`` path in R2's OneHotDist
    mode and entropy calculations. The sentinel underflows to exact zero in
    float32 softmax while keeping log-probability arithmetic finite.
    """

    def __init__(self, logits: torch.Tensor):
        self._categorical = Categorical(logits=logits)
        if not torch.isfinite(self._categorical.logits).all():
            raise ValueError("masked categorical logits must remain finite")

    @property
    def logits(self) -> torch.Tensor:
        return self._categorical.logits

    @property
    def probs(self) -> torch.Tensor:
        return self._categorical.probs

    @property
    def mode(self) -> torch.Tensor:
        probs = self.probs
        hard = F.one_hot(probs.argmax(dim=-1), probs.shape[-1]).to(probs.dtype)
        return hard.detach() + probs - probs.detach()

    def rsample(
        self,
        sample_shape: torch.Size | tuple[int, ...] = torch.Size(),
        temperature: float = 1.0,
    ) -> torch.Tensor:
        if temperature <= 0:
            raise ValueError("temperature must be positive")
        logits = self.logits
        sample_shape = torch.Size(sample_shape)
        if sample_shape:
            logits = logits.expand(*sample_shape, *logits.shape)
        return F.gumbel_softmax(logits, tau=temperature, hard=True, dim=-1)

    def sample(self, **kwargs):
        raise NotImplementedError("use rsample() for the straight-through policy")

    def log_prob(self, value: torch.Tensor) -> torch.Tensor:
        if value.shape[-1] != self.logits.shape[-1]:
            raise ValueError("one-hot action size does not match distribution")
        return self._categorical.log_prob(value.argmax(dim=-1))

    def entropy(self) -> torch.Tensor:
        return self._categorical.entropy()


def masked_onehot_distribution(
    actor,
    features: torch.Tensor,
    legal_mask: torch.Tensor,
    *,
    commit_action_index: int,
    unimix_ratio: float,
) -> _MaskedOneHotDistribution:
    """Use the upstream actor logits with probability mass only on legal actions."""
    if not (0.0 <= unimix_ratio < 1.0):
        raise ValueError("unimix_ratio must be in [0, 1)")
    logits = to_f32(actor.last(actor.mlp(features)))
    legal_mask = _validate_action_mask(
        legal_mask, logits.shape, commit_action_index=commit_action_index
    )
    if not torch.isfinite(logits).all():
        raise ValueError("actor logits must be finite")
    masked_logits = logits.masked_fill(~legal_mask, -torch.inf)
    probabilities = torch.softmax(masked_logits, dim=-1)
    legal_uniform = legal_mask.to(probabilities.dtype) / legal_mask.sum(-1, keepdim=True)
    probabilities = (1.0 - unimix_ratio) * probabilities + unimix_ratio * legal_uniform
    probabilities = torch.where(legal_mask, probabilities, torch.zeros_like(probabilities))
    legal_logits = torch.log(probabilities.clamp_min(torch.finfo(probabilities.dtype).tiny))
    final_logits = legal_logits.masked_fill(~legal_mask, -1.0e9)
    return _MaskedOneHotDistribution(final_logits)


def _validate_action_mask(
    mask: torch.Tensor,
    logits_shape: torch.Size | tuple[int, ...],
    *,
    commit_action_index: int,
) -> torch.Tensor:
    mask = mask.to(dtype=torch.bool)
    if tuple(mask.shape) != tuple(logits_shape):
        raise ValueError(f"action mask shape {tuple(mask.shape)} does not match logits {tuple(logits_shape)}")
    if not bool(mask[..., commit_action_index].all()):
        raise ValueError("action mask must keep COMMIT legal")
    if not bool(mask.any(dim=-1).all()):
        raise ValueError("action mask has no legal action")
    return mask


class ReliefDreamer(R2Dreamer):
    """Pinned R2-Dreamer with public action masks and physical-time returns."""

    def __init__(
        self,
        config,
        obs_space,
        act_space,
        *,
        commit_action_index: int = 64,
        mask_threshold: float = MASK_THRESHOLD,
        mask_loss_scale: float = 1.0,
    ):
        if str(config.rep_loss) != "dreamer":
            raise ValueError("relief integration requires the upstream standard dreamer representation loss")
        if bool(config.compile):
            raise ValueError("compile must be false for the time-aware overlay")
        if config.encoder.mlp_keys != "^vector$" or config.decoder.mlp_keys != "^vector$":
            raise ValueError("only the public vector may enter the encoder and reconstruction decoder")
        if config.encoder.cnn_keys != "^$" or config.decoder.cnn_keys != "^$":
            raise ValueError("relief integration does not accept image or metadata encoder inputs")
        shapes = {name: tuple(space.shape) for name, space in obs_space.spaces.items()}
        if shapes.get("vector") is None or len(shapes["vector"]) != 1:
            raise ValueError("observation space must contain one flat public vector")
        if shapes.get("action_mask") != (int(act_space.n) if hasattr(act_space, "n") else int(act_space.shape[0]),):
            raise ValueError("action_mask must match the fixed discrete action space")
        if not (0.0 <= mask_threshold <= 1.0):
            raise ValueError("mask_threshold must be in [0, 1]")
        if mask_loss_scale <= 0:
            raise ValueError("mask_loss_scale must be positive")

        if hasattr(act_space, "n") and not hasattr(act_space, "discrete"):
            act_space = _DiscreteOneHotSpace(act_space.n)
        if not (hasattr(act_space, "discrete") and bool(act_space.discrete)):
            raise ValueError("R2-Dreamer action space must use its one-hot discrete convention")
        action_size = int(act_space.n) if hasattr(act_space, "n") else int(act_space.shape[0])
        if commit_action_index != action_size - 1:
            raise ValueError("relief action contract fixes COMMIT at the last action index")

        super().__init__(config, obs_space, act_space)
        if not self.act_discrete or self.act_dim != action_size:
            raise RuntimeError("pinned R2-Dreamer did not construct a discrete one-hot actor")
        self.commit_action_index = commit_action_index
        self.mask_threshold = float(mask_threshold)
        self.mask_loss_scale = float(mask_loss_scale)
        self._unimix_ratio = float(config.actor.dist.unimix_ratio)
        self._gamma = 1.0 - 1.0 / float(self.horizon)
        hidden = int(config.actor.units)
        self.legal_mask_head = nn.Sequential(
            nn.Linear(self.rssm.feat_size, hidden),
            nn.RMSNorm(hidden, eps=1e-4),
            nn.ELU(),
            nn.Linear(hidden, action_size),
        )
        nn.init.zeros_(self.legal_mask_head[-1].weight)
        nn.init.zeros_(self.legal_mask_head[-1].bias)
        self._named_params.update(
            {f"legal_mask_head.{name}": parameter for name, parameter in self.legal_mask_head.named_parameters()}
        )
        self._optimizer = LaProp(
            self._named_params.values(),
            lr=config.lr,
            betas=(config.beta1, config.beta2),
            eps=config.eps,
        )
        self._scaler = GradScaler()
        self._scheduler = LambdaLR(
            self._optimizer,
            lr_lambda=(lambda step: min(1.0, (step + 1) / config.warmup)) if config.warmup else (lambda step: 1.0),
        )
        self._upstream_agc = self._agc
        self._last_grad_finite = False
        self._agc = self._checked_agc
        self.clone_and_freeze()

    def _checked_agc(self, parameters):
        bad = [
            name
            for name, parameter in self._named_params.items()
            if parameter.grad is not None and not torch.isfinite(parameter.grad).all()
        ]
        self._last_grad_finite = not bad
        if bad:
            raise FloatingPointError(f"non-finite Dreamer gradients: {bad[:8]}")
        return self._upstream_agc(parameters)

    def clone_and_freeze(self):
        super().clone_and_freeze()
        if hasattr(self, "legal_mask_head"):
            self._frozen_legal_mask_head = copy.deepcopy(self.legal_mask_head)
            for original, frozen in zip(self.legal_mask_head.parameters(), self._frozen_legal_mask_head.parameters()):
                frozen.data = original.data
                frozen.requires_grad_(False)

    def _action_mask(self, mask: Any, *, device: torch.device, batch_shape: tuple[int, ...]) -> torch.Tensor:
        mask = _tensor(mask, device=device, dtype=torch.bool)
        if mask.shape != (*batch_shape, self.act_dim):
            raise ValueError(f"action mask shape {tuple(mask.shape)} does not match batch/action shape {batch_shape}")
        if not bool(mask[..., self.commit_action_index].all()):
            raise ValueError("public action mask must keep COMMIT legal")
        if not bool(mask.any(dim=-1).all()):
            raise ValueError("public action mask has no legal action")
        return mask

    def _masked_actor(self, actor, features: torch.Tensor, legal_mask: torch.Tensor):
        legal_mask = self._action_mask(
            legal_mask,
            device=features.device,
            batch_shape=tuple(features.shape[:-1]),
        )
        return masked_onehot_distribution(
            actor,
            features,
            legal_mask,
            commit_action_index=self.commit_action_index,
            unimix_ratio=self._unimix_ratio,
        )

    @torch.no_grad()
    def act(self, obs, state, eval=False):
        if "vector" not in obs or "action_mask" not in obs or "is_first" not in obs:
            raise ValueError("Dreamer observation must include vector, public action_mask, and is_first")
        torch.compiler.cudagraph_mark_step_begin()
        p_obs = self.preprocess(obs)
        embed = self._frozen_encoder(p_obs)
        prev_stoch, prev_deter, prev_action = state["stoch"], state["deter"], state["prev_action"]
        stoch, deter, _ = self._frozen_rssm.obs_step(
            prev_stoch, prev_deter, prev_action, embed, obs["is_first"]
        )
        feat = self._frozen_rssm.get_feat(stoch, deter)
        mask = self._action_mask(
            obs["action_mask"], device=feat.device, batch_shape=tuple(feat.shape[:-1])
        )
        action_dist = self._masked_actor(self._frozen_actor, feat, mask)
        action = action_dist.mode if eval else action_dist.rsample()
        next_state = type(state)(
            {"stoch": stoch, "deter": deter, "prev_action": action}, batch_size=state.batch_size
        )
        return action, next_state

    @torch.no_grad()
    def _imagine(self, start, imag_horizon):
        features = []
        actions = []
        masks = []
        fallback_count = torch.zeros((), device=self.device, dtype=torch.float32)
        stoch, deter = start
        for _ in range(imag_horizon):
            feat = self._frozen_rssm.get_feat(stoch, deter)
            mask_logits = self._frozen_legal_mask_head(feat)
            mask, no_predicted_action = predicted_imagination_mask(
                mask_logits,
                commit_action_index=self.commit_action_index,
                threshold=self.mask_threshold,
            )
            fallback_count = fallback_count + no_predicted_action.to(torch.float32).sum()
            policy = self._masked_actor(self._frozen_actor, feat, mask)
            action = policy.rsample()
            features.append(feat)
            actions.append(action)
            masks.append(mask)
            stoch, deter = self._frozen_rssm.img_step(stoch, deter, action)
        features = torch.stack(features, dim=1)
        actions = torch.stack(actions, dim=1)
        masks = torch.stack(masks, dim=1)
        outgoing_dt = actions[..., self.commit_action_index : self.commit_action_index + 1].round().detach()
        incoming_discount, incoming_lambda = shift_outgoing_time_powers(
            outgoing_dt, self._gamma, self.lamb
        )
        incoming_dt = torch.zeros_like(outgoing_dt)
        incoming_dt[:, 1:] = outgoing_dt[:, :-1]
        self._last_imagination_metrics = {
            "mask_fallbacks": fallback_count,
            "mask_mean_legal_actions": masks.to(torch.float32).sum(-1).mean(),
            "commit_fraction": outgoing_dt.mean(),
        }
        return features, actions, masks, incoming_dt, incoming_discount, incoming_lambda

    def _lambda_return(self, last, terminal, reward, value, bootstrap, discount, trace):
        if not (last.shape == terminal.shape == reward.shape == value.shape == bootstrap.shape == discount.shape == trace.shape):
            raise ValueError("time-aware lambda-return inputs must have matching shapes")
        live = (1.0 - to_f32(terminal))[:, 1:] * to_f32(discount)[:, 1:]
        continuation = (1.0 - to_f32(last))[:, 1:] * to_f32(trace)[:, 1:]
        interm = to_f32(reward)[:, 1:] + (1.0 - continuation) * live * to_f32(bootstrap)[:, 1:]
        output = [to_f32(bootstrap)[:, -1]]
        for index in reversed(range(live.shape[1])):
            output.append(interm[:, index] + live[:, index] * continuation[:, index] * output[-1])
        return torch.stack(list(reversed(output))[:-1], dim=1)

    def _balanced_mask_loss(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        target = target.to(torch.float32)
        if logits.shape != target.shape:
            raise ValueError("mask prediction and replay target shapes differ")
        if not torch.logical_or(target == 0.0, target == 1.0).all():
            raise ValueError("replay action_mask targets must be binary")
        if not bool(target[..., self.commit_action_index].all()):
            raise ValueError("replay action_mask target has an illegal COMMIT")
        positive_count = target.sum(dim=-1)
        negative_count = (1.0 - target).sum(dim=-1)
        positive_loss = (F.softplus(-logits) * target).sum(dim=-1) / positive_count.clamp_min(1.0)
        negative_loss = (F.softplus(logits) * (1.0 - target)).sum(dim=-1) / negative_count.clamp_min(1.0)
        class_count = (positive_count > 0).to(torch.float32) + (negative_count > 0).to(torch.float32)
        return ((positive_loss + negative_loss) / class_count.clamp_min(1.0)).mean()

    def _cal_grad(self, data, initial):
        """Pinned upstream standard Dreamer loss with mask and physical-time hooks.

        This method retains the upstream RSSM KL, vector reconstruction,
        reward/continuation, imagined actor/value and replay value losses. The
        only added objective is current-state public action-mask prediction.
        """
        if self.rep_loss != "dreamer":
            raise RuntimeError("only the upstream standard dreamer representation path is supported")
        if "dt" not in data or "action_mask" not in data:
            raise ValueError("R2 replay data must contain incoming dt and same-state action_mask")
        losses = {}
        metrics = {}
        batch, sequence = data.shape

        embed = self.encoder(data)
        post_stoch, post_deter, post_logit = self.rssm.observe(
            embed, data["action"], initial, data["is_first"]
        )
        _, prior_logit = self.rssm.prior(post_deter)
        dyn_loss, rep_loss = self.rssm.kl_loss(post_logit, prior_logit, self.kl_free)
        losses["dyn"] = torch.mean(dyn_loss)
        losses["rep"] = torch.mean(rep_loss)
        feat = self.rssm.get_feat(post_stoch, post_deter)
        recon_losses = {
            key: torch.mean(-dist.log_prob(data[key]))
            for key, dist in self.decoder(post_stoch, post_deter).items()
        }
        losses.update(recon_losses)

        mask_logits = self.legal_mask_head(feat)
        action_mask = _tensor(data["action_mask"], device=feat.device, dtype=torch.bool)
        if action_mask.shape != mask_logits.shape:
            raise ValueError("same-state replay mask shape does not match world-model features")
        losses["legal_mask"] = self._balanced_mask_loss(mask_logits, action_mask)
        with torch.no_grad():
            mask_prediction = torch.sigmoid(mask_logits) >= self.mask_threshold
            mask_prediction[..., self.commit_action_index] = True
            true_positive = (mask_prediction & action_mask).sum().to(torch.float32)
            predicted_positive = mask_prediction.sum().to(torch.float32)
            actual_positive = action_mask.sum().to(torch.float32)
            metrics["mask/precision"] = true_positive / predicted_positive.clamp_min(1.0)
            metrics["mask/recall"] = true_positive / actual_positive.clamp_min(1.0)
            metrics["mask/false_negative_count"] = (action_mask & ~mask_prediction).sum().to(torch.float32)

        losses["rew"] = torch.mean(-self.reward(feat).log_prob(to_f32(data["reward"])))
        continuation = 1.0 - to_f32(data["is_terminal"])
        losses["con"] = torch.mean(-self.cont(feat).log_prob(continuation))
        metrics["dyn_entropy"] = torch.mean(self.rssm.get_dist(prior_logit).entropy())
        metrics["rep_entropy"] = torch.mean(self.rssm.get_dist(post_logit).entropy())

        start = (
            post_stoch.reshape(-1, *post_stoch.shape[2:]).detach(),
            post_deter.reshape(-1, *post_deter.shape[2:]).detach(),
        )
        imag_feat, imag_action, imag_mask, imag_dt, imag_discount, imag_trace = self._imagine(
            start, self.imag_horizon + 1
        )
        imag_feat, imag_action = imag_feat.detach(), imag_action.detach()
        imag_reward_prediction = self._frozen_reward(imag_feat).mode()
        imag_continuation_prediction = self._frozen_cont(imag_feat).mean
        imag_reward, imag_cont = physical_time_reward_continuation(
            imag_reward_prediction, imag_continuation_prediction, imag_dt
        )
        imag_value = self._frozen_value(imag_feat).mode()
        imag_slow_value = self._frozen_slow_value(imag_feat).mode()
        weight = torch.ones_like(imag_cont)
        weight[:, 1:] = torch.cumprod(
            imag_cont[:, 1:] * imag_discount[:, 1:], dim=1
        )
        last = torch.zeros_like(imag_cont)
        terminal = torch.where(imag_dt == 0.0, torch.zeros_like(imag_cont), 1.0 - imag_cont)
        ret = self._lambda_return(
            last,
            terminal,
            imag_reward,
            imag_value,
            imag_value,
            imag_discount,
            imag_trace,
        )
        ret_offset, ret_scale = self.return_ema(ret)
        advantage = (ret - imag_value[:, :-1]) / ret_scale
        policy = self._masked_actor(self.actor, imag_feat, imag_mask)
        logpi = policy.log_prob(imag_action)[:, :-1].unsqueeze(-1)
        entropy = policy.entropy()[:, :-1].unsqueeze(-1)
        losses["policy"] = torch.mean(
            weight[:, :-1].detach()
            * -(logpi * advantage.detach() + self.act_entropy * entropy)
        )

        imag_value_dist = self.value(imag_feat)
        target_padded = torch.cat([ret, 0 * ret[:, -1:]], dim=1)
        losses["value"] = torch.mean(
            weight[:, :-1].detach()
            * (
                -imag_value_dist.log_prob(target_padded.detach())
                - imag_value_dist.log_prob(imag_slow_value.detach())
            )[:, :-1].unsqueeze(-1)
        )
        ret_normed = (ret - ret_offset) / ret_scale
        metrics["ret"] = torch.mean(ret_normed)
        metrics["ret_005"] = self.return_ema.ema_vals[0]
        metrics["ret_095"] = self.return_ema.ema_vals[1]
        metrics["adv"] = torch.mean(advantage)
        metrics["adv_std"] = torch.std(advantage)
        metrics["con"] = torch.mean(imag_cont)
        metrics["rew"] = torch.mean(imag_reward)
        metrics["val"] = torch.mean(imag_value)
        metrics["tar"] = torch.mean(ret)
        metrics["slowval"] = torch.mean(imag_slow_value)
        metrics["weight"] = torch.mean(weight)
        metrics["action_entropy"] = torch.mean(entropy)
        metrics["mask/imag_fallbacks"] = self._last_imagination_metrics["mask_fallbacks"]
        metrics["mask/imag_mean_legal_actions"] = self._last_imagination_metrics["mask_mean_legal_actions"]
        metrics["mask/imag_commit_fraction"] = self._last_imagination_metrics["commit_fraction"]
        metrics.update(tools.tensorstats(imag_action, "action"))

        last = to_f32(data["is_last"])
        terminal = to_f32(data["is_terminal"])
        reward = to_f32(data["reward"])
        feat = self.rssm.get_feat(post_stoch, post_deter)
        bootstrap = ret[:, 0].reshape(batch, sequence, 1)
        value = self._frozen_value(feat).mode()
        slow_value = self._frozen_slow_value(feat).mode()
        incoming_dt = _validate_dt(data["dt"])
        if incoming_dt.shape != reward.shape:
            raise ValueError("replay dt must align with incoming reward and state")
        if torch.logical_and(incoming_dt == 0.0, terminal != 0.0).any():
            raise ValueError("a zero-time replay microstep cannot be terminal")
        replay_discount, replay_trace = time_discount_powers(incoming_dt, self._gamma, self.lamb)
        replay_return = self._lambda_return(
            last, terminal, reward, value, bootstrap, replay_discount, replay_trace
        )
        replay_padded = torch.cat([replay_return, 0 * replay_return[:, -1:]], dim=1)
        value_dist = self.value(feat)
        replay_weight = 1.0 - last
        losses["repval"] = torch.mean(
            replay_weight[:, :-1]
            * (
                -value_dist.log_prob(replay_padded.detach())
                - value_dist.log_prob(slow_value.detach())
            )[:, :-1].unsqueeze(-1)
        )
        metrics.update(tools.tensorstats(replay_return, "ret_replay"))
        metrics.update(tools.tensorstats(value, "value_replay"))
        metrics.update(tools.tensorstats(slow_value, "slow_value_replay"))

        total_loss = sum(
            value * (self.mask_loss_scale if name == "legal_mask" else self._loss_scales[name])
            for name, value in losses.items()
        )
        if not torch.isfinite(total_loss).all():
            raise FloatingPointError("non-finite total Dreamer loss")
        self._scaler.scale(total_loss).backward()
        metrics.update({f"loss/{name}": loss for name, loss in losses.items()})
        metrics["opt/loss"] = total_loss
        return (post_stoch, post_deter), metrics

    def checkpoint_metadata(self, adapter_observation: dict[str, Any]) -> dict[str, Any]:
        if adapter_observation.get("schema") != ADAPTER_SCHEMA:
            raise ValueError("checkpoint metadata requires an adapter observation")
        return checkpoint_metadata(
            adapter_signature_sha256=str(adapter_observation["adapter_signature_sha256"]),
            feature_layout_sha256=str(adapter_observation["feature_layout_sha256"]),
            action_size=int(adapter_observation["action_size"]),
            commit_action_index=int(adapter_observation.get("commit_action_index", self.commit_action_index)),
            gamma=self._gamma,
            trace_lambda=self.lamb,
        )
