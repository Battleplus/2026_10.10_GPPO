"""Identity-safe public-window and candidate contracts for N2."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import pickle
from dataclasses import dataclass
from typing import Any


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _catalog_digest(candidates: list[dict]) -> str:
    return canonical_digest(sorted(candidates, key=lambda row: str(row.get("id", ""))))


def public_prefix(observation: dict) -> dict:
    """Select only fields returned by the environment's public observation API."""
    required = {"schema", "time", "horizon", "map", "platforms", "depots", "tasks", "chapter1_snapshot"}
    if not isinstance(observation, dict) or not required.issubset(observation):
        raise ValueError("PUBLIC_OBSERVATION_SCHEMA")
    return copy.deepcopy({key: observation[key] for key in sorted(required)})


def validate_public_view(observation: dict, candidates: list[dict], expected_context: dict | None = None) -> dict:
    """Validate a live public observation/catalog pair at model-consumption boundaries."""
    prefix = public_prefix(observation)
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("CANDIDATE_CATALOG_INVALID")
    ids = [row.get("id") for row in candidates if isinstance(row, dict)]
    if (len(ids) != len(candidates) or any(not isinstance(cid, str) or not cid for cid in ids)
            or len(ids) != len(set(ids)) or ids.count("NOOP") != 1):
        raise ValueError("CANDIDATE_IDENTITY_INVALID")
    if expected_context is not None and expected_context.get("time") != prefix["time"]:
        raise ValueError("SNAPSHOT_CONTEXT_TIME_MISMATCH")
    return {
        "time": int(prefix["time"]),
        "public_prefix_sha256": canonical_digest(prefix),
        "candidate_catalog_sha256": _catalog_digest(candidates),
        "candidate_ids": tuple(ids),
    }


def preaction_snapshot(env, parent_id: str, repeat: int, window_id: str) -> dict:
    observation = env.public_observation()
    prefix = public_prefix(observation)
    candidates = env.candidates()
    if not candidates or not any(c.get("id") == "NOOP" for c in candidates):
        raise ValueError("NOOP_REQUIRED")
    ids = [c.get("id") for c in candidates]
    if any(not isinstance(cid, str) or not cid for cid in ids) or len(ids) != len(set(ids)):
        raise ValueError("CANDIDATE_IDENTITY_INVALID")
    context = {
        "parent_id": parent_id,
        "repeat": int(repeat),
        "window_id": window_id,
        "time": int(observation["time"]),
        "public_prefix_sha256": canonical_digest(prefix),
        "candidate_catalog_sha256": _catalog_digest(candidates),
    }
    source_sha256 = canonical_digest(env.scenario)
    internal_blob = pickle.dumps(env, protocol=5)
    return {
        "context": context,
        "phase": "pre_action",
        "source_sha256": source_sha256,
        "internal_snapshot_sha256": hashlib.sha256(internal_blob).hexdigest(),
        "PublicPrefix": prefix,
        "candidate_catalog": copy.deepcopy(candidates),
        "candidate_keys": [
            {**context, "candidate_id": cid} for cid in ids
        ],
        "internal_snapshot": copy.deepcopy(env),
    }


def verify_preaction(
    snapshot: dict,
    observation: dict,
    candidates: list[dict],
    expected_context: dict | None = None,
) -> None:
    if snapshot.get("phase") != "pre_action":
        raise ValueError("SNAPSHOT_PHASE_MISMATCH")
    context = snapshot.get("context")
    if not isinstance(context, dict):
        raise ValueError("SNAPSHOT_CONTEXT_INVALID")
    prefix = public_prefix(observation)
    if canonical_digest(snapshot.get("PublicPrefix")) != context.get("public_prefix_sha256"):
        raise ValueError("PUBLIC_PREFIX_BINDING_MISMATCH")
    if canonical_digest(prefix) != context.get("public_prefix_sha256"):
        raise ValueError("PRE_POST_ACTION_MIXED")
    if type(context.get("time")) is not int or context["time"] != prefix["time"]:
        raise ValueError("SNAPSHOT_CONTEXT_TIME_MISMATCH")
    if expected_context is not None:
        for field in ("parent_id", "repeat", "window_id"):
            if context.get(field) != expected_context.get(field):
                raise ValueError("SNAPSHOT_CONTEXT_MISMATCH")
    saved_catalog = snapshot.get("candidate_catalog")
    if not isinstance(saved_catalog, list):
        raise ValueError("SAVED_CATALOG_INVALID")
    saved_ids = [row.get("id") for row in saved_catalog if isinstance(row, dict)]
    if (len(saved_ids) != len(saved_catalog) or any(not isinstance(cid, str) or not cid for cid in saved_ids)
            or len(saved_ids) != len(set(saved_ids))):
        raise ValueError("CANDIDATE_IDENTITY_INVALID")
    if _catalog_digest(saved_catalog) != context.get("candidate_catalog_sha256"):
        raise ValueError("SAVED_CATALOG_BINDING_MISMATCH")
    if not isinstance(candidates, list):
        raise ValueError("CANDIDATE_CATALOG_INVALID")
    live_ids = [row.get("id") for row in candidates if isinstance(row, dict)]
    if (len(live_ids) != len(candidates) or any(not isinstance(cid, str) or not cid for cid in live_ids)
            or len(live_ids) != len(set(live_ids))):
        raise ValueError("CANDIDATE_IDENTITY_INVALID")
    if _catalog_digest(candidates) != context.get("candidate_catalog_sha256"):
        raise ValueError("CANDIDATE_CATALOG_MISMATCH")
    candidate_ids = live_ids
    keys = snapshot.get("candidate_keys")
    if not isinstance(keys, list) or len(keys) != len(candidate_ids):
        raise ValueError("CANDIDATE_KEY_BINDING_MISMATCH")
    key_ids = []
    for key in keys:
        if not isinstance(key, dict) or not isinstance(key.get("candidate_id"), str):
            raise ValueError("CANDIDATE_KEY_BINDING_MISMATCH")
        key_ids.append(key["candidate_id"])
        if any(key.get(field) != context[field] for field in context):
            raise ValueError("CANDIDATE_KEY_CONTEXT_MISMATCH")
    if len(key_ids) != len(set(key_ids)) or set(key_ids) != set(candidate_ids):
        raise ValueError("CANDIDATE_KEY_BINDING_MISMATCH")
    if canonical_digest(snapshot["internal_snapshot"].scenario) != snapshot.get("source_sha256"):
        raise ValueError("SOURCE_SNAPSHOT_MISMATCH")
    internal_blob = pickle.dumps(snapshot["internal_snapshot"], protocol=5)
    if hashlib.sha256(internal_blob).hexdigest() != snapshot.get("internal_snapshot_sha256"):
        raise ValueError("INTERNAL_SNAPSHOT_MISMATCH")


def restore_preaction(snapshot: dict):
    restored = copy.deepcopy(snapshot["internal_snapshot"])
    observation = restored.public_observation()
    candidates = restored.candidates()
    verify_preaction(snapshot, observation, candidates)
    return restored


def public_candidate_features(observation: dict, candidate: dict) -> dict:
    """Bounded numeric features derived only from the public observation and catalog."""
    platforms = {str(p["id"]): p for p in observation["platforms"]}
    tasks = {str(t["id"]): t for t in observation["tasks"]}
    depots = {str(d["id"]): d for d in observation["depots"]}
    row = {"action_noop": float(candidate.get("id") == "NOOP")}
    if candidate.get("id") == "NOOP":
        return row
    platform = platforms.get(str(candidate.get("platform_id")))
    task = tasks.get(str(candidate.get("task_id")))
    if platform is None or task is None:
        raise ValueError("CANDIDATE_NOT_IN_PUBLIC_OBSERVATION")
    row.update({
        "task_priority": float(task["priority"]),
        "task_deadline_remaining": float(task["deadline"] - observation["time"]),
        "task_is_delivery": float(task["kind"] == "delivery"),
        "task_is_inspection": float(task["kind"] == "inspection"),
        "platform_capacity_kg": float(platform["capacity_kg"]),
        "platform_energy": float(platform["energy"]),
        "platform_is_helicopter": float(platform["type"] == "helicopter"),
        "estimated_completion": float(candidate["estimated_completion"]),
        "required_energy": float(candidate["required_energy"]),
    })
    if task["kind"] == "delivery":
        depot = depots[str(task["depot_id"])]
        row["public_stock_remaining"] = float(depot["stock"].get(task["commodity"], 0.0))
        row["quantity_kg"] = float(task["quantity"])
    return row


@dataclass(frozen=True)
class LabelLeaf:
    value: float | None
    valid: bool
    unknown_reason: str | None

    def __post_init__(self):
        if type(self.valid) is not bool:
            raise ValueError("LABEL_VALIDITY_TYPE")
        if self.valid and (type(self.value) not in (int, float) or not math.isfinite(float(self.value)) or self.unknown_reason is not None):
            raise ValueError("VALID_LABEL_INCOMPLETE")
        if not self.valid and (self.value is not None or not self.unknown_reason):
            raise ValueError("UNKNOWN_LABEL_MUST_NOT_BE_ZERO_FILLED")
