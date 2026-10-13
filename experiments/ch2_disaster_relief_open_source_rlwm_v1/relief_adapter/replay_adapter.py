"""Replay-aligned wrapper around the existing decision-repeat adapter."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .decision_repeat import DecisionRepeatReliefAdapter
from .replay_contract import (
    ACTION_COUNT,
    COMMIT_ACTION_INDEX,
    DISPATCH_ACTION_COUNT,
    MAX_PLATFORMS,
    MAX_TASKS,
    action_physical_time_delta,
    adapter_signature_sha256 as replay_contract_sha256,
)


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ReplayReliefAdapter(DecisionRepeatReliefAdapter):
    """Adds R2-compatible incoming transition metadata to adapter observations.

    Base observations remain responsible for simulator state and feature encoding.
    The added fields are replay metadata and are not appended to ``vector``.
    """

    @property
    def commit_action_index(self) -> int:
        return int(self.commit_action)

    def _replay_signature(self, observation: dict[str, Any]) -> str:
        base_signature = str(observation.get("adapter_signature_sha256", ""))
        return _canonical_sha256(
            {
                "base_adapter_signature_sha256": base_signature,
                "replay_contract_sha256": replay_contract_sha256(),
                "source_tree_sha256": getattr(self, "source_tree_sha256", None),
            }
        )

    def _stamp(
        self,
        observation: dict[str, Any],
        *,
        dt: int,
        reward: float,
        is_first: bool,
        is_last: bool,
        is_terminal: bool,
    ) -> dict[str, Any]:
        if dt not in (0, 1):
            raise ValueError(f"unsupported physical-time dt: {dt}")
        if is_terminal and not is_last:
            raise ValueError("is_terminal implies is_last")
        if len(observation.get("action_mask", ())) != ACTION_COUNT:
            raise ValueError(
                f"fixed adapter requires {ACTION_COUNT} action-mask entries"
            )
        if int(self.commit_action) != COMMIT_ACTION_INDEX:
            raise ValueError(
                f"COMMIT action index must be {COMMIT_ACTION_INDEX}, "
                f"got {self.commit_action}"
            )

        result = dict(observation)
        mask = [bool(value) for value in result["action_mask"]]
        mask[COMMIT_ACTION_INDEX] = True
        if len(getattr(self, "_used_platforms", ())) >= MAX_PLATFORMS:
            mask[:DISPATCH_ACTION_COUNT] = [False] * DISPATCH_ACTION_COUNT
        result.update(
            {
                "action_mask": tuple(mask),
                "action_size": ACTION_COUNT,
                "commit_action_index": COMMIT_ACTION_INDEX,
                "replay_contract_sha256": replay_contract_sha256(),
                "source_tree_sha256": getattr(self, "source_tree_sha256", None),
                "is_first": bool(is_first),
                "is_last": bool(is_last),
                "is_terminal": bool(is_terminal),
                "dt": int(dt),
                "reward": float(reward),
            }
        )
        result["adapter_signature_sha256"] = self._replay_signature(result)
        return result

    def reset(self, policy: str = "LEARNED") -> dict[str, Any]:
        observation = super().reset(policy=policy)
        observation = self._stamp(
            observation,
            dt=0,
            reward=0.0,
            is_first=True,
            is_last=False,
            is_terminal=False,
        )
        self._last_observation = copy.deepcopy(observation)
        return copy.deepcopy(observation)

    def step(self, action: int):
        observation, reward, terminated, truncated, info = super().step(action)
        adapter_info = dict(info.get("adapter", {}))
        dt = int(adapter_info.get("physical_time_delta", -1))
        discount_exponent = int(adapter_info.get("discount_exponent", -1))
        expected_dt = action_physical_time_delta(int(action))
        if dt != discount_exponent or dt != expected_dt:
            raise ValueError(
                "action, adapter physical_time_delta, and discount_exponent "
                "must agree"
            )
        is_last = bool(terminated or truncated)
        is_terminal = bool(terminated)
        observation = self._stamp(
            observation,
            dt=dt,
            reward=float(reward),
            is_first=False,
            is_last=is_last,
            is_terminal=is_terminal,
        )
        self._last_observation = copy.deepcopy(observation)
        adapter_info.update(
            {
                "dt": dt,
                "is_first": False,
                "is_last": is_last,
                "is_terminal": is_terminal,
                "reward": float(reward),
                "commit_action_index": COMMIT_ACTION_INDEX,
                "replay_contract_sha256": replay_contract_sha256(),
            }
        )
        info = dict(info)
        info["adapter"] = adapter_info
        return observation, float(reward), bool(terminated), bool(truncated), info


__all__ = ["ReplayReliefAdapter"]
