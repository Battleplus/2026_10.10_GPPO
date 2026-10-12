"""Evaluate a preregistered N01 cost sample with frozen checkpoint weights."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_sample(
    package_root: str | Path,
    sample_manifest_path: str | Path,
    scenario_root: str | Path,
    checkpoint_root: str | Path,
    checkpoint_manifest_path: str | Path,
    output_root: str | Path,
    *,
    resource_check=None,
) -> dict:
    import torch

    from evaluator import _episode_row, _evaluate_learned, _load_policy
    from independent_audit import audit_run
    from ppo_trainer import (
        EXPECTED_VARIANTS,
        PPOConfig,
        SEEDS,
        _optimizer_state_digest,
        _state_digest,
        sha256_file,
    )

    package = Path(package_root).resolve()
    manifest_path = Path(sample_manifest_path).resolve(strict=True)
    scenarios_dir = Path(scenario_root).resolve(strict=True)
    checkpoints_dir = Path(checkpoint_root).resolve(strict=True)
    checkpoint_manifest_file = Path(checkpoint_manifest_path).resolve(strict=True)
    output = Path(output_root).resolve()
    sample_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint_manifest = json.loads(checkpoint_manifest_file.read_text(encoding="utf-8"))
    if (
        sample_manifest.get("sample_identity") != "n01-100-episode-cost-diagnostic-v1"
        or sample_manifest.get("episode_count") != 100
        or sample_manifest.get("results_excluded_from_final_2800") is not True
    ):
        raise PermissionError("sample manifest is not the frozen N01 100-episode diagnostic")
    if checkpoint_manifest.get("schema") != "n01-frozen-checkpoints/1":
        raise PermissionError("unsupported frozen-checkpoint manifest")
    if checkpoint_manifest.get("input_registry_sha256") != sha256_file(package / "registered_data" / "input_registry.json"):
        raise PermissionError("checkpoint manifest is bound to a different registered data identity")
    expected_ids = {f"{variant}-{seed}" for variant in EXPECTED_VARIANTS for seed in SEEDS}
    entries = checkpoint_manifest.get("checkpoints", [])
    if {entry.get("run_id") for entry in entries} != expected_ids or len(entries) != 6:
        raise PermissionError("checkpoint manifest must bind all six fixed final checkpoints")

    barrier_rows = []
    source_hash_maps = []
    policy_cache = {}
    for entry in sorted(entries, key=lambda item: item["run_id"]):
        run_id = entry["run_id"]
        checkpoint_path = checkpoints_dir / entry["file"]
        if not checkpoint_path.is_file() or _sha256(checkpoint_path) != entry.get("sha256"):
            raise PermissionError(f"frozen checkpoint hash mismatch: {run_id}")
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        variant, seed_text = run_id.rsplit("-", 1)
        seed = int(seed_text)
        if (
            payload.get("schema") != "relief-ppo-checkpoint/1"
            or payload.get("variant") != variant
            or int(payload.get("seed", -1)) != seed
            or int(payload.get("round_number", -1)) != 32
            or int(payload.get("target_rounds", -1)) != 32
            or payload.get("training_complete") is not True
            or payload.get("data_hash") != checkpoint_manifest["input_registry_sha256"]
            or payload.get("config") != __import__("dataclasses").asdict(PPOConfig())
        ):
            raise PermissionError(f"frozen checkpoint identity/configuration mismatch: {run_id}")
        model_state_hash = _state_digest(payload["model_state"])
        optimizer_state_hash = _optimizer_state_digest(payload["optimizer_state"])
        if (
            model_state_hash != entry.get("model_state_sha256")
            or optimizer_state_hash != entry.get("optimizer_state_sha256")
        ):
            raise PermissionError(f"frozen checkpoint state digest mismatch: {run_id}")
        source_hash_maps.append(payload.get("source_hashes"))
        policy = _load_policy(package, checkpoint_path, variant, seed, checkpoint_manifest["input_registry_sha256"])
        if policy.architecture_evidence != entry.get("architecture_evidence"):
            raise PermissionError(f"frozen checkpoint architecture mismatch: {run_id}")
        policy_cache[run_id] = policy
        barrier_rows.append({
            "run_id": run_id,
            "file": entry["file"],
            "sha256": entry["sha256"],
            "model_state_sha256": model_state_hash,
            "optimizer_state_sha256": optimizer_state_hash,
            "source_hashes_sha256": hashlib.sha256(
                json.dumps(payload["source_hashes"], sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "round_number": 32,
            "training_complete": True,
            "architecture_evidence": policy.architecture_evidence,
        })
    if any(value != source_hash_maps[0] for value in source_hash_maps[1:]):
        raise PermissionError("frozen checkpoints disagree on their historical source provenance")
    _write_json(output / "checkpoint_barrier.json", {
        "schema": "n01-fixed-checkpoint-barrier/1",
        "passed": True,
        "checkpoint_count": 6,
        "historical_source_hashes": source_hash_maps[0],
        "historical_source_identity_sha256": hashlib.sha256(
            json.dumps(source_hash_maps[0], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "adapter_package_sha256": _sha256(checkpoint_manifest_file),
        "input_registry_sha256": checkpoint_manifest["input_registry_sha256"],
        "checkpoints": barrier_rows,
    })

    selected = []
    for condition, items in sample_manifest["sample"].items():
        if len(items) != 20:
            raise ValueError(f"sample condition {condition} does not contain 20 episodes")
        for item in items:
            selected.append((condition, item))
    if len(selected) != 100:
        raise ValueError("sample manifest does not contain exactly 100 scenarios")

    policy_name = "L1-8201"
    policy = policy_cache[policy_name]
    rows = []
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    for condition, item in selected:
        if resource_check:
            resource_check()
        episode_wall_start, episode_cpu_start = time.perf_counter(), time.process_time()
        scenario_path = scenarios_dir / condition / item["file"]
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        if scenario.get("scenario_id") != item["scenario_id"]:
            raise ValueError("sample scenario id/file mapping mismatch")
        trajectory, timings = _evaluate_learned(scenario, policy, "L1")
        audited = audit_run(scenario, trajectory, expected_policy="L1")
        row, _ = _episode_row(scenario, "L1", 8201, trajectory, timings, item["stratum"])
        row["condition"] = condition
        row["parent_id"] = item["scenario_id"]
        row["episode_wall_seconds"] = time.perf_counter() - episode_wall_start
        row["episode_cpu_seconds"] = time.process_time() - episode_cpu_start
        row["platform_count"] = len(scenario["platforms"])
        row["task_count"] = len(scenario["tasks"])
        candidate_counts = [len(transition["candidates"]) for transition in trajectory["transitions"]]
        row["max_candidate_count"] = max(candidate_counts, default=0)
        row["max_candidate_density"] = row["max_candidate_count"] / max(1, row["platform_count"] * row["task_count"])
        rows.append(row)
        stem = f"{condition}/{item['scenario_id']}"
        _write_json(output / "trajectories" / f"{stem}.json", trajectory)
        _write_json(output / "audits" / f"{stem}.json", audited)
        _write_json(output / "episode_rows" / f"{stem}.json", row)
    total_wall = time.perf_counter() - started_wall
    total_cpu = time.process_time() - started_cpu
    condition_summary = {}
    for condition in sample_manifest["condition_episodes"]:
        condition_rows = [row for row in rows if row["condition"] == condition]
        condition_summary[condition] = {
            "episode_count": len(condition_rows),
            "wall_seconds": sum(float(row["episode_wall_seconds"]) for row in condition_rows),
            "cpu_seconds": sum(float(row["episode_cpu_seconds"]) for row in condition_rows),
            "decision_wall_seconds": sum(float(row["metrics"]["decision_wall_seconds"]) for row in condition_rows),
            "decision_cpu_seconds": sum(float(row["metrics"]["decision_cpu_seconds"]) for row in condition_rows),
            "platform_count_distribution": {str(n): sum(row["platform_count"] == n for row in condition_rows) for n in sorted({row["platform_count"] for row in condition_rows})},
            "task_count_distribution": {str(n): sum(row["task_count"] == n for row in condition_rows) for n in sorted({row["task_count"] for row in condition_rows})},
            "max_candidate_count": max(row["max_candidate_count"] for row in condition_rows),
            "max_candidate_density": max(row["max_candidate_density"] for row in condition_rows),
            "trajectory_count": len(condition_rows),
        }
    result = {
        "schema": "n01-sample-evaluation/1",
        "status": "complete",
        "sample_identity": sample_manifest["sample_identity"],
        "method": policy_name,
        "sample_size": len(rows),
        "results_excluded_from_final_2800": True,
        "wall_seconds": total_wall,
        "cpu_seconds": total_cpu,
        "condition_summary": condition_summary,
        "scenario_manifest_sha256": _sha256(manifest_path),
        "checkpoint_manifest_sha256": _sha256(checkpoint_manifest_file),
        "checkpoint_barrier_sha256": _sha256(output / "checkpoint_barrier.json"),
        "episode_rows_sha256": hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    _write_json(output / "episode_metrics.json", {"runs": rows})
    _write_json(output / "sample_summary.json", result)
    return result
