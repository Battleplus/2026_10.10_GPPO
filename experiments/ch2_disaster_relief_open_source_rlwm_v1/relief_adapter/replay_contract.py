"""Stable action and replay metadata contract for the relief adapter."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


MAX_PLATFORMS = 4
MAX_TASKS = 16
DISPATCH_ACTION_COUNT = MAX_PLATFORMS * MAX_TASKS
COMMIT_ACTION_INDEX = DISPATCH_ACTION_COUNT
ACTION_COUNT = DISPATCH_ACTION_COUNT + 1


def dispatch_action_index(platform_slot: int, task_slot: int) -> int:
    if not 0 <= platform_slot < MAX_PLATFORMS:
        raise ValueError(f"platform_slot out of range: {platform_slot}")
    if not 0 <= task_slot < MAX_TASKS:
        raise ValueError(f"task_slot out of range: {task_slot}")
    return platform_slot * MAX_TASKS + task_slot


def dispatch_action_pair(action_index: int) -> tuple[int, int]:
    if not 0 <= action_index < DISPATCH_ACTION_COUNT:
        raise ValueError(f"not a dispatch action: {action_index}")
    return divmod(action_index, MAX_TASKS)


def action_physical_time_delta(action_index: int) -> int:
    if 0 <= action_index < DISPATCH_ACTION_COUNT:
        return 0
    if action_index == COMMIT_ACTION_INDEX:
        return 1
    raise ValueError(f"action index out of range: {action_index}")


def contract_document() -> dict[str, Any]:
    return {
        "contract_version": "relief-decision-repeat/1",
        "observation": {
            "vector": "float32[F]",
            "action_mask": "bool[65]",
            "is_first": "bool scalar; true only on reset observation",
            "is_last": "bool scalar; true on termination or truncation",
            "is_terminal": "bool scalar; true only on environment termination",
            "dt": "integer physical minutes advanced by the incoming action",
            "adapter_signature_sha256": "static string; external verification only",
            "encoder_inputs": ["vector"],
            "metadata_not_encoder_inputs": [
                "action_mask",
                "is_first",
                "is_last",
                "is_terminal",
                "dt",
                "adapter_signature_sha256",
            ],
        },
        "actions": {
            "platform_slots": MAX_PLATFORMS,
            "task_slots": MAX_TASKS,
            "dispatch_encoding": "platform_slot * 16 + task_slot",
            "dispatch_indices_inclusive": [0, DISPATCH_ACTION_COUNT - 1],
            "commit_action_index": COMMIT_ACTION_INDEX,
            "action_count": ACTION_COUNT,
            "dispatch_physical_time_delta": 0,
            "commit_physical_time_delta": 1,
            "commit_is_only_physical_time_advancing_action": True,
            "commit_is_always_legal": True,
            "full_platform_batch_allows_only_commit": True,
            "dispatch_never_auto_commits": True,
        },
        "replay_alignment": {
            "raw_record_x_t": "obs_t plus outgoing action_t",
            "raw_record_x_t_plus_1": "obs_t_plus_1 plus reward/is_last/is_terminal/dt for transition t",
            "discount_exponent": "dt",
            "dt_zero_dispatch_transition": "zero physical-time discount exponent",
            "dt_one_commit_transition": "one physical-minute discount exponent",
        },
    }


def adapter_signature_sha256() -> str:
    payload = json.dumps(
        contract_document(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stamp_observation(
    observation: Mapping[str, Any],
    *,
    dt: int,
    is_first: bool = False,
    is_last: bool = False,
    is_terminal: bool = False,
    adapter_signature: str | None = None,
) -> dict[str, Any]:
    """Copy an observation and attach RSSM/replay transition metadata."""
    if dt not in (0, 1):
        raise ValueError(f"dt must be 0 or 1, got {dt!r}")
    if is_terminal and not is_last:
        raise ValueError("is_terminal implies is_last")
    if "vector" not in observation or "action_mask" not in observation:
        raise ValueError("observation requires vector and action_mask")
    if len(observation["action_mask"]) != ACTION_COUNT:
        raise ValueError(
            f"action_mask must contain {ACTION_COUNT} entries, "
            f"got {len(observation['action_mask'])}"
        )
    result = dict(observation)
    result.update(
        {
            "is_first": bool(is_first),
            "is_last": bool(is_last),
            "is_terminal": bool(is_terminal),
            "dt": int(dt),
            "adapter_signature_sha256": (
                adapter_signature or adapter_signature_sha256()
            ),
        }
    )
    return result
