"""Full-scope, fixed-checkpoint N01 evaluation with a hash-bound dry run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any
import zipfile


IDENTITY = "ch2-disaster-relief-n01-full-evaluation-r1-20261011"
CONDITIONS = (
    "original", "scale_8x12", "scale_12x18", "carrier_competition", "stock_competition",
)
METHODS = ("C0", "C1", "L0-8201", "L0-8202", "L0-8203", "L1-8201", "L1-8202", "L1-8203")
SPLITS = ("heldout", "development")
EVALUATION_CAP_WALL = 5400.0
EVALUATION_CAP_CPU = 4500.0
SOURCE_INPUTS = (
    "n01_full_evaluator.py", "evaluator.py", "n01_fixed_sample_evaluator.py",
    "n01_sample_manifest.json", "n01_scenarios/scenario_counts.json",
    "baselines.py", "graph_policy.py", "literal_graph_ops.py", "relief_env.py",
    "scenario_schema.py", "independent_audit.py", "dataset_protocol.py", "ppo_trainer.py",
    "resource_supervisor.py", "process_guardian.py", "stable_identity.py", "runtime-spec.json",
    "protocol/preregistered_protocol.json",
    "n01_full_evaluation_stage_budget.json", "N01_FULL_EVALUATION_PRIOR_COST.json",
    "n01_fixed_checkpoint_manifest.json", "n01_scenarios/scenario_manifest.json",
    "registered_data/input_registry.json", "PRIOR_RESOURCE_COST.json",
    "n01_full_systemd_runner.sh", "n01_full_systemd_settle.py",
    "n01_full_evaluation.service", "n01_systemd_contract_probe.service",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _scenario_sha256(value: Any) -> str:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _verify_current_identity(package: Path) -> dict:
    manifest_path = package / "N01_FULL_EVALUATION_IDENTITY.json"
    identity = json.loads(manifest_path.read_text(encoding="utf-8"))
    if identity.get("schema") != "n01-full-evaluation-identity/1" or identity.get("evaluation_identity") != IDENTITY:
        raise PermissionError("full evaluation identity manifest does not match this runner")
    expected = identity.get("current_source_hashes", {})
    if set(expected) != set(SOURCE_INPUTS):
        raise PermissionError("identity manifest source inventory is incomplete or unexpected")
    actual = {relative: _sha256(package / relative) for relative in SOURCE_INPUTS}
    if actual != expected:
        changed = sorted(name for name in SOURCE_INPUTS if actual.get(name) != expected.get(name))
        raise PermissionError("current evaluation source identity mismatch: " + ", ".join(changed))
    return identity


def _expected_run_keys(scenarios: list[dict]) -> list[dict]:
    keys = []
    for scenario in scenarios:
        for method in METHODS:
            seed = None if method in ("C0", "C1") else int(method.rsplit("-", 1)[1])
            model = method if method in ("C0", "C1") else method.rsplit("-", 1)[0]
            keys.append({
                "condition": scenario["condition"],
                "parent_id": scenario["scenario_id"],
                "split": scenario["split"],
                "method": model,
                "seed": seed,
            })
    keys.sort(key=lambda item: (
        item["condition"], item["parent_id"], item["method"], -1 if item["seed"] is None else item["seed"]
    ))
    identities = [
        (row["condition"], row["parent_id"], row["method"], row["seed"])
        for row in keys
    ]
    if len(keys) != 2800 or len(set(identities)) != 2800:
        raise ValueError("full evaluation matrix must contain 2,800 unique condition-parent-method-seed keys")
    return keys


def _verify_checkpoints(
    package: Path,
    checkpoint_root: Path,
    checkpoint_manifest_path: Path,
    *,
    strict_model_load: bool = True,
) -> tuple[dict, dict[str, Any]]:
    import torch

    from evaluator import _load_policy
    from ppo_trainer import (
        EXPECTED_VARIANTS,
        PPOConfig,
        SEEDS,
        _optimizer_state_digest,
        _state_digest,
        sha256_file,
    )

    manifest = json.loads(checkpoint_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "n01-frozen-checkpoints/1":
        raise PermissionError("checkpoint manifest schema is not the frozen N01 checkpoint schema")
    registry_path = package / "registered_data" / "input_registry.json"
    registry_hash = sha256_file(registry_path)
    if manifest.get("input_registry_sha256") != registry_hash:
        raise PermissionError("checkpoint manifest is bound to a different registered data registry")
    expected = {f"{variant}-{seed}" for variant in EXPECTED_VARIANTS for seed in SEEDS}
    entries = manifest.get("checkpoints")
    if not isinstance(entries, list) or len(entries) != 6 or {item.get("run_id") for item in entries} != expected:
        raise PermissionError("exactly six unique frozen L0/L1 checkpoints for seeds 8201/8202/8203 are required")
    identity = json.loads((package / "N01_FULL_EVALUATION_IDENTITY.json").read_text(encoding="utf-8"))
    bound_checkpoints = identity.get("checkpoint_sha256", {})
    if bound_checkpoints != {item["run_id"]: item["sha256"] for item in entries}:
        raise PermissionError("full evaluation identity does not bind all six checkpoint file hashes")
    if manifest.get("historical_source_hashes") is None:
        raise PermissionError("checkpoint manifest has no historical training source identity")

    policies = {}
    barrier_rows = []
    source_maps = []
    for entry in sorted(entries, key=lambda item: item["run_id"]):
        run_id = entry["run_id"]
        relative = Path(entry.get("file", ""))
        if relative.is_absolute() or len(relative.parts) != 1 or relative.suffix != ".pt":
            raise PermissionError(f"invalid checkpoint file entry: {run_id}")
        checkpoint = (checkpoint_root / relative).resolve(strict=True)
        if checkpoint.parent != checkpoint_root.resolve() or _sha256(checkpoint) != entry.get("sha256"):
            raise PermissionError(f"frozen checkpoint file/hash mismatch: {run_id}")
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        variant, seed_text = run_id.rsplit("-", 1)
        if (
            payload.get("schema") != "relief-ppo-checkpoint/1"
            or payload.get("variant") != variant
            or int(payload.get("seed", -1)) != int(seed_text)
            or int(payload.get("round_number", -1)) != 32
            or int(payload.get("target_rounds", -1)) != 32
            or payload.get("training_complete") is not True
            or payload.get("data_hash") != registry_hash
            or payload.get("config") != __import__("dataclasses").asdict(PPOConfig())
        ):
            raise PermissionError(f"checkpoint identity/configuration mismatch: {run_id}")
        model_hash = _state_digest(payload["model_state"])
        optimizer_hash = _optimizer_state_digest(payload["optimizer_state"])
        if model_hash != entry.get("model_state_sha256") or optimizer_hash != entry.get("optimizer_state_sha256"):
            raise PermissionError(f"checkpoint state digest mismatch: {run_id}")
        if payload.get("architecture_evidence") != entry.get("architecture_evidence"):
            raise PermissionError(f"checkpoint architecture evidence mismatch: {run_id}")
        policy = _load_policy(package, checkpoint, variant, int(seed_text), registry_hash) if strict_model_load else None
        if policy is not None and policy.architecture_evidence != entry.get("architecture_evidence"):
            raise PermissionError(f"checkpoint architecture evidence differs from strict runtime model: {run_id}")
        source_maps.append(payload.get("source_hashes"))
        if policy is not None:
            policies[run_id] = policy
        barrier_rows.append({
            "run_id": run_id,
            "file": relative.as_posix(),
            "sha256": entry["sha256"],
            "model_state_sha256": model_hash,
            "optimizer_state_sha256": optimizer_hash,
            "architecture_evidence": entry["architecture_evidence"],
            "round_number": 32,
        })
    if any(item != source_maps[0] for item in source_maps[1:]):
        raise PermissionError("frozen checkpoints disagree on source provenance")
    if source_maps[0] != manifest.get("historical_source_hashes"):
        raise PermissionError("checkpoint provenance differs from the frozen checkpoint manifest")
    barrier = {
        "schema": "n01-full-checkpoint-barrier/1",
        "passed": True,
        "checkpoint_manifest_sha256": _sha256(checkpoint_manifest_path),
        "input_registry_sha256": registry_hash,
        "checkpoint_count": len(barrier_rows),
        "historical_source_hashes": source_maps[0],
        "checkpoints": barrier_rows,
    }
    return barrier, policies


def prepare_plan(
    package_root: str | Path,
    scenario_root: str | Path,
    checkpoint_root: str | Path,
    checkpoint_manifest_path: str | Path,
    *,
    strict_model_load: bool = True,
) -> tuple[dict, dict[str, Any]]:
    package = Path(package_root).resolve(strict=True)
    identity = _verify_current_identity(package)
    scenarios_dir = Path(scenario_root).resolve(strict=True)
    checkpoints_dir = Path(checkpoint_root).resolve(strict=True)
    checkpoint_manifest = Path(checkpoint_manifest_path).resolve(strict=True)
    scenario_manifest_path = package / "n01_scenarios" / "scenario_manifest.json"
    manifest = json.loads(scenario_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("identity") != "ch2-disaster-relief-n01-v1" or manifest.get("source_parent_count") != 70:
        raise PermissionError("unsupported N01 scenario manifest identity/count")
    if tuple(manifest.get("methods", ())) != METHODS:
        raise PermissionError("scenario manifest policy order/coverage differs from the frozen eight policies")
    if set(manifest.get("conditions", {})) != set(CONDITIONS):
        raise PermissionError("scenario manifest must contain the exact five registered conditions")

    scenarios = []
    scenario_hashes = {}
    split_counts = Counter()
    strata_counts = Counter()
    external_task_counts = Counter()
    ordinary_task_counts = Counter()
    seen_parent_keys = set()
    for condition in CONDITIONS:
        condition_manifest = manifest["conditions"][condition]
        entries = condition_manifest.get("scenario_hashes", [])
        if condition_manifest.get("parents") != 70 or len(entries) != 70:
            raise PermissionError(f"condition {condition} does not contain exactly 70 parents")
        for entry in entries:
            scenario_id = entry.get("scenario_id")
            split = "development" if "-development-" in str(scenario_id) else "heldout" if "-heldout-" in str(scenario_id) else None
            if split is None:
                raise PermissionError(f"scenario split is missing from ID: {scenario_id}")
            parent_key = (condition, scenario_id)
            if parent_key in seen_parent_keys:
                raise PermissionError(f"duplicate scenario identity: {condition}/{scenario_id}")
            seen_parent_keys.add(parent_key)
            scenario_path = (scenarios_dir / condition / f"{scenario_id}.json").resolve(strict=True)
            if scenario_path.parent != (scenarios_dir / condition).resolve():
                raise PermissionError("scenario path escapes its registered condition directory")
            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            actual_hash = _scenario_sha256(scenario)
            if actual_hash != entry.get("scenario_sha256"):
                raise PermissionError(f"canonical scenario hash mismatch: {condition}/{scenario_id}")
            if scenario.get("scenario_id") != scenario_id:
                raise PermissionError(f"scenario content identity mismatch: {condition}/{scenario_id}")
            if len(scenario.get("tasks", [])) != int(entry.get("task_count", -1)):
                raise PermissionError(f"task count differs from scenario registry: {condition}/{scenario_id}")
            stratum = scenario_id.split("-graph-v1-", 1)[1].rsplit("-", 1)[0].split("-", 1)[-1]
            if stratum not in {"control", "failure", "energy_change", "stock_loss", "report_delay", "combined", "external_commitment"}:
                raise PermissionError(f"unknown registered scenario stratum: {scenario_id}")
            split_counts[(condition, split)] += 1
            strata_counts[(condition, stratum)] += 1
            if stratum == "external_commitment":
                external_task_counts[(condition, len(scenario["tasks"]))] += 1
            else:
                ordinary_task_counts[(condition, len(scenario["tasks"]))] += 1
            scenario_hashes[f"{condition}/{scenario_path.name}"] = actual_hash
            scenarios.append({
                "condition": condition,
                "scenario_id": scenario_id,
                "split": split,
                "stratum": stratum,
                "source_parent_id": entry.get("source_parent_id"),
                "task_count": len(scenario["tasks"]),
                "external_commitment_parent": stratum == "external_commitment",
                "path": scenario_path.relative_to(scenarios_dir).as_posix(),
                "sha256": actual_hash,
            })
    for condition in CONDITIONS:
        if split_counts[(condition, "heldout")] != 56 or split_counts[(condition, "development")] != 14:
            raise PermissionError(f"condition {condition} must contain 56 heldout and 14 development scenarios")
    if len(scenarios) != 350:
        raise PermissionError("scenario manifest did not resolve exactly 350 unique inputs")
    for condition in CONDITIONS:
        if strata_counts[(condition, "external_commitment")] != 10:
            raise PermissionError(f"condition {condition} must preserve all 10 external-commitment parents")
    if external_task_counts[("scale_8x12", 14)] != 10 or ordinary_task_counts[("scale_8x12", 12)] != 60:
        raise PermissionError("8x12 input task counts must preserve 14 external-commitment and 12 ordinary tasks")
    if external_task_counts[("scale_12x18", 21)] != 10 or ordinary_task_counts[("scale_12x18", 18)] != 60:
        raise PermissionError("12x18 input task counts must preserve 21 external-commitment and 18 ordinary tasks")

    barrier, policies = _verify_checkpoints(package, checkpoints_dir, checkpoint_manifest, strict_model_load=strict_model_load)
    keys = _expected_run_keys(scenarios)
    if Counter(row["split"] for row in keys) != Counter({"heldout": 2240, "development": 560}):
        raise AssertionError("run key split counts do not sum to the frozen evaluation scope")
    plan = {
        "schema": "n01-full-evaluation-plan/1",
        "evaluation_identity": IDENTITY,
        "scenario_manifest_sha256": _sha256(scenario_manifest_path),
        "scenario_count": len(scenarios),
        "scenario_hashes": scenario_hashes,
        "stratum_parent_counts": {condition: {stratum: strata_counts[(condition, stratum)] for stratum in sorted({key[1] for key in strata_counts if key[0] == condition})} for condition in CONDITIONS},
        "external_commitment_task_counts": {"scale_8x12": 14, "scale_12x18": 21, "external_commitment_parent_count_per_condition": 10},
        "ordinary_scaled_task_counts": {"scale_8x12": 12, "scale_12x18": 18, "ordinary_parent_count_per_condition": 60},
        "checkpoint_barrier": barrier,
        "checkpoint_manifest_sha256": _sha256(checkpoint_manifest),
        "identity_manifest_sha256": _sha256(package / "N01_FULL_EVALUATION_IDENTITY.json"),
        "current_source_hashes": identity["current_source_hashes"],
        "policy_count": len(METHODS),
        "episode_count": len(keys),
        "split_episode_counts": {"heldout": 2240, "development": 560},
        "scenarios": scenarios,
        "run_keys": keys,
        "run_keys_sha256": _canonical_sha256(keys),
        "static_only": True,
    }
    plan["plan_sha256"] = _canonical_sha256(plan)
    return plan, policies


def _require_fresh_directory(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"output already exists; restart/resume is rejected: {path}")


def _approved_budget(package: Path) -> dict:
    budget_path = package / "n01_full_evaluation_stage_budget.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    if (
        budget.get("evaluation_identity") != IDENTITY
        or budget.get("schema") != "n01-stage-budget/1"
        or budget.get("status") != "proposed"
    ):
        raise PermissionError("stage budget is not bound to this new evaluation identity")
    expected_stages = {
        "admission": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
        "evaluation": {"wall_seconds": EVALUATION_CAP_WALL, "cpu_seconds": EVALUATION_CAP_CPU},
        "export": {"wall_seconds": 300.0, "cpu_seconds": 180.0},
        "shutdown": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
    }
    if budget.get("stages") != expected_stages:
        raise PermissionError("approved stage caps differ from the independently reviewed proposal")
    if budget.get("identity_total") != {"wall_seconds": 5940.0, "cpu_seconds": 4800.0}:
        raise PermissionError("approved new-identity total caps differ from the reviewed 5,940/4,800 seconds")
    approval_path = package.parent / "N1_FULL_EVALUATION_BUDGET_APPROVAL.json"
    if not approval_path.is_file():
        raise PermissionError("full evaluation requires the external independent budget-approval record")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if (
        approval.get("schema") != "n01-stage-budget-approval/1"
        or approval.get("status") != "approved"
        or approval.get("evaluation_identity") != IDENTITY
        or approval.get("stage_budget_sha256") != _sha256(budget_path)
        or approval.get("stages") != expected_stages
        or approval.get("identity_total") != budget["identity_total"]
        or not approval.get("approval_reference")
        or not approval.get("approved_by")
    ):
        raise PermissionError("external independent approval does not bind the frozen identity and proposed stage budget")
    budget["external_approval"] = {
        "path": approval_path.name,
        "sha256": _sha256(approval_path),
        "approval_reference": approval["approval_reference"],
        "approved_by": approval["approved_by"],
    }
    return budget


def _read_bound_prior_cost(package: Path) -> dict:
    path = package / "N01_FULL_EVALUATION_PRIOR_COST.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "n01-full-evaluation-prior-cost/1":
        raise PermissionError("new identity cumulative known-use receipt has an unsupported schema")
    evidence_root = (package / receipt.get("evidence_root_relative", "")).resolve(strict=True)
    if evidence_root != package.parent.resolve():
        raise PermissionError("prior-cost evidence root must be the parent engineering-revision directory")
    for relative, expected in receipt.get("evidence_sha256", {}).items():
        evidence = (evidence_root / relative).resolve(strict=True)
        if evidence_root not in evidence.parents or _sha256(evidence) != str(expected).lower():
            raise PermissionError(f"prior-cost evidence hash mismatch: {relative}")
    return {
        "stage_costs": {},
        "total_wall_seconds": float(receipt["known_total_wall_seconds"]),
        "total_cpu_seconds": float(receipt["known_total_cpu_seconds"]),
        "receipt_sha256": _sha256(path),
    }


def _load_ledger(work_root: Path) -> list[dict]:
    path = work_root / "resource-ledger.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("schema") != "resource-ledger-entry/1":
            raise ValueError("new evaluation resource ledger contains an unsupported row")
        rows.append(row)
    return rows


def _check_target_runtime(package: Path) -> dict:
    import numpy as np
    import torch

    spec = json.loads((package / "runtime-spec.json").read_text(encoding="utf-8"))
    for key, value in spec["environment"].items():
        if os.environ.get(key) != value:
            raise PermissionError(f"target runtime environment mismatch: {key}")
    if torch.get_num_threads() != int(spec["torch_threads"]):
        torch.set_num_threads(int(spec["torch_threads"]))
    if torch.get_num_interop_threads() != int(spec["torch_interop_threads"]):
        torch.set_num_interop_threads(int(spec["torch_interop_threads"]))
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    actual = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "device": "cpu",
        "affinity": affinity,
        "torch_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(),
        "cuda_is_initialized": bool(torch.cuda.is_initialized()),
    }
    expected = {key: spec[key] for key in ("python", "torch", "numpy", "device", "torch_threads", "torch_interop_threads")}
    if any(actual[key] != value for key, value in expected.items()):
        raise PermissionError("target Python/Torch/NumPy/device identity differs from runtime spec")
    if actual["affinity"] != [0] or actual["cuda_is_initialized"]:
        raise PermissionError("target must be CPU 0 only and CUDA must remain uninitialized")
    return actual


def _verify_systemd_execution_contract() -> dict:
    expected = {
        "Type": "exec", "KillMode": "control-group", "MemoryAccounting": "yes",
        "MemoryMax": "4294967296", "CPUAccounting": "yes", "CPUAffinity": "0",
        "RuntimeMaxUSec": "1h 38min 20s",
        "TimeoutStopUSec": "40s",
    }
    invocation_id = os.environ.get("INVOCATION_ID")
    if not invocation_id:
        raise PermissionError("admission requires a systemd invocation ID")
    memberships = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    relative = next((line.split("::", 1)[1] for line in memberships if line.startswith("0::")), None)
    if relative is None:
        raise PermissionError("admission requires unified cgroup-v2 membership")
    unit_name = relative.rsplit("/", 1)[-1]
    command = ["systemctl", "--user", "show", unit_name, "--no-pager", *[f"--property={name}" for name in (*expected, "InvocationID", "ActiveState", "ControlGroup")]]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise PermissionError(f"cannot read active systemd unit contract: {result.stderr.strip()}")
    observed = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    mismatches = [f"{name}: expected {value!r}, observed {observed.get(name)!r}" for name, value in expected.items() if observed.get(name) != value]
    if observed.get("InvocationID") != invocation_id:
        mismatches.append("InvocationID does not match the current process")
    if observed.get("ActiveState") != "active" or observed.get("ControlGroup") != relative:
        mismatches.append("unit is not active in the current process cgroup")
    cgroup = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if not cgroup.is_dir():
        mismatches.append("current unit cgroup directory is missing")
    else:
        try:
            members = {int(pid) for pid in (cgroup / "cgroup.procs").read_text(encoding="ascii").split()}
            memory_max = (cgroup / "memory.max").read_text(encoding="ascii").strip()
            cpu_stat = (cgroup / "cpu.stat").read_text(encoding="ascii")
            cpu_max_path = cgroup / "cpu.max"
            cpu_max = cpu_max_path.read_text(encoding="ascii").strip() if cpu_max_path.is_file() else None
        except (OSError, ValueError) as exc:
            raise PermissionError(f"cannot read current unit cgroup resource evidence: {exc}") from exc
        if os.getpid() not in members:
            mismatches.append("admission process is absent from the current unit cgroup")
        if memory_max != expected["MemoryMax"]:
            mismatches.append(f"cgroup memory.max: expected {expected['MemoryMax']!r}, observed {memory_max!r}")
        if "usage_usec" not in cpu_stat:
            mismatches.append("cgroup cpu.stat usage_usec is missing")
    if mismatches:
        raise PermissionError("systemd execution contract mismatch: " + "; ".join(mismatches))
    return {
        "unit_name": unit_name,
        "invocation_id": invocation_id,
        "control_group": relative,
        "systemd_properties": observed,
        "cgroup_memory_max": memory_max,
        "cgroup_cpu_max": cpu_max,
        "kernel_cpu_quota_status": "enforced-readback" if cpu_max and cpu_max.split()[:1] != ["max"] else "unavailable",
        "cgroup_cpu_stat": cpu_stat,
        "contract_status": "accepted",
    }


def _verify_admission(package: Path, work_root: Path, plan_path: Path) -> dict:
    admission_path = work_root / "n01_runtime_admission.json"
    receipt_path = work_root / "receipts" / "01-n01_full_admission.json"
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    identity = _verify_current_identity(package)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("status") != "complete"
        or receipt.get("first_error") is not None
        or receipt.get("result", {}).get("status") != "accepted"
        or admission.get("schema") != "n01-full-runtime-admission/1"
        or admission.get("evaluation_identity") != IDENTITY
        or admission.get("plan_sha256") != plan.get("plan_sha256")
        or admission.get("identity_manifest_sha256") != _sha256(package / "N01_FULL_EVALUATION_IDENTITY.json")
        or admission.get("current_source_hashes") != identity.get("current_source_hashes")
        or admission.get("scenario_manifest_sha256") != plan.get("scenario_manifest_sha256")
        or admission.get("checkpoint_manifest_sha256") != plan.get("checkpoint_manifest_sha256")
        or admission.get("runtime_spec_sha256") != _sha256(package / "runtime-spec.json")
    ):
        raise PermissionError("runtime admission does not bind this plan and evaluation identity")
    return admission


def _execute_guarded_child(package: Path, work_root: Path, stage: str, action) -> dict:
    from resource_supervisor import ResourceSupervisor
    import resource_supervisor

    ledger = work_root / "resource-ledger.jsonl"
    work_root.mkdir(parents=True, exist_ok=True)
    count = len(_load_ledger(work_root))
    receipt_path = work_root / "receipts" / f"{count + 1:02d}-{stage}.json"
    budget = _approved_budget(package)
    prior = _read_bound_prior_cost(package)
    stage_wall_cap, stage_cpu_cap = resource_supervisor.STAGE_LIMITS[stage]
    stage_wall_reserve, stage_cpu_reserve = resource_supervisor.STAGE_STOP_RESERVES.get(stage, (0.0, 0.0))
    stage_wall_stop = stage_wall_cap - stage_wall_reserve
    stage_cpu_stop = stage_cpu_cap - stage_cpu_reserve
    resource_supervisor.STAGE_LIMITS[stage] = (stage_wall_stop, stage_cpu_stop)
    resource_supervisor.TOTAL_WALL_LIMIT = prior["total_wall_seconds"] + float(budget["identity_total"]["wall_seconds"]) - resource_supervisor.TOTAL_WALL_STOP_RESERVE
    resource_supervisor.TOTAL_CPU_LIMIT = prior["total_cpu_seconds"] + float(budget["identity_total"]["cpu_seconds"]) - resource_supervisor.TOTAL_CPU_STOP_RESERVE
    stop_metadata = {
        "configured_stage_wall_cap_seconds": stage_wall_cap,
        "configured_stage_cpu_cap_seconds": stage_cpu_cap,
        "stage_wall_early_stop_threshold_seconds": stage_wall_stop,
        "stage_cpu_early_stop_threshold_seconds": stage_cpu_stop,
        "stage_wall_stop_reserve_seconds": stage_wall_reserve,
        "stage_cpu_stop_reserve_seconds": stage_cpu_reserve,
        "configured_identity_wall_cap_seconds": float(budget["identity_total"]["wall_seconds"]),
        "configured_identity_cpu_cap_seconds": float(budget["identity_total"]["cpu_seconds"]),
        "identity_wall_early_stop_threshold_seconds": float(budget["identity_total"]["wall_seconds"]) - resource_supervisor.TOTAL_WALL_STOP_RESERVE,
        "identity_cpu_early_stop_threshold_seconds": float(budget["identity_total"]["cpu_seconds"]) - resource_supervisor.TOTAL_CPU_STOP_RESERVE,
        "identity_wall_stop_reserve_seconds": resource_supervisor.TOTAL_WALL_STOP_RESERVE,
        "identity_cpu_stop_reserve_seconds": resource_supervisor.TOTAL_CPU_STOP_RESERVE,
    }
    supervisor = None
    try:
        supervisor = ResourceSupervisor(
            stage, ledger, (package, work_root),
            prior_cost_path=package / "N01_FULL_EVALUATION_PRIOR_COST.json",
        )
        supervisor.start_monitor()
        supervisor.check(force_disk=True)
        result = action(supervisor)
        receipt = {"schema": "driver-stage-receipt/1", "stage": stage, "status": "complete", "result": result, "first_error": None, "partial_checkpoints": []}
        row = supervisor.finish(status="complete", metadata={"receipt": str(receipt_path), **stop_metadata})
        receipt["resource_entry"] = row
        _write_json(receipt_path, receipt)
        row = supervisor.close()
        receipt["resource_entry"] = row
        _write_json(receipt_path, receipt)
        return result
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        receipt = {
            "schema": "driver-stage-receipt/1", "stage": stage, "status": "failed",
            "first_error": error, "error_traceback": traceback.format_exc(),
            "partial_checkpoints": [],
        }
        if supervisor is not None:
            supervisor.record_error(exc)
            _write_json(receipt_path, receipt)
            if supervisor._finished_row is None:
                supervisor.finish(status="failed", error=exc, metadata={"receipt": str(receipt_path), **stop_metadata})
            receipt["resource_entry"] = supervisor.close(error=exc)
        _write_json(receipt_path, receipt)
        raise


def _guarded_dispatch(package: Path, work_root: Path, stage: str, child_mode: str, child_args: list[str]) -> int:
    if sys.platform != "linux":
        raise RuntimeError("new evaluation stages require the accepted Linux target runtime")
    budget = _approved_budget(package)
    rows = _load_ledger(work_root)
    if any(row.get("stage") == stage for row in rows):
        raise PermissionError(f"stage {stage} already has a receipt; same-identity retry/resubmission is rejected")
    runtime = json.loads((package / "runtime-spec.json").read_text(encoding="utf-8"))
    prior = _read_bound_prior_cost(package)
    import process_guardian

    process_guardian.TOTAL_WALL_CAP = prior["total_wall_seconds"] + float(budget["identity_total"]["wall_seconds"])
    process_guardian.TOTAL_CPU_CAP = prior["total_cpu_seconds"] + float(budget["identity_total"]["cpu_seconds"])
    process_guardian.TOTAL_WALL_LIMIT = process_guardian.TOTAL_WALL_CAP - process_guardian.TOTAL_WALL_STOP_RESERVE
    process_guardian.TOTAL_CPU_LIMIT = process_guardian.TOTAL_CPU_CAP - process_guardian.TOTAL_CPU_STOP_RESERVE
    child_argv = ["--package-root", str(package), "--work-root", str(work_root), "--mode", child_mode, *child_args]
    return process_guardian.run_guarded_stage(
        argv=child_argv,
        driver_path=Path(__file__).resolve(),
        package_root=package,
        work_root=work_root,
        stage=stage,
        runtime_environment=runtime["environment"],
        prior_resource_cost=prior,
    )


def _export_result(work_root: Path) -> dict:
    evaluation = work_root / "evaluation"
    summary_path = evaluation / "summary.json"
    metrics_path = evaluation / "episode_metrics.json"
    if not summary_path.is_file() or not metrics_path.is_file():
        raise PermissionError("evaluation output is incomplete; export is refused")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = json.loads(metrics_path.read_text(encoding="utf-8")).get("runs", [])
    if summary.get("status") != "complete" or summary.get("episode_count") != 2800 or len(rows) != 2800:
        raise PermissionError("evaluation summary/rows do not prove complete 2,800 episode coverage")
    for folder in ("trajectories", "audits", "episode_rows"):
        if sum(1 for _ in (evaluation / folder).rglob("*.json")) != 2800:
            raise PermissionError(f"export is missing episode files in {folder}")
    export_dir = work_root / "export"
    _require_fresh_directory(export_dir)
    export_dir.mkdir(parents=True, exist_ok=False)
    archive = export_dir / "n01-full-evaluation.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(evaluation.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(evaluation).as_posix())
    result = {
        "schema": "n01-full-evaluation-export/1",
        "evaluation_identity": IDENTITY,
        "episode_count": 2800,
        "audit_count": 2800,
        "archive": archive.name,
        "archive_sha256": _sha256(archive),
        "summary_sha256": _sha256(summary_path),
        "episode_metrics_sha256": _sha256(metrics_path),
    }
    _write_json(export_dir / "export_manifest.json", result)
    return result


def _verify_shutdown(work_root: Path) -> dict:
    rows = _load_ledger(work_root)
    required = {
        "n01_full_admission": "accepted",
        "n01_full_evaluation": "complete",
        "n01_full_export": "complete",
    }
    for stage, expected_status in required.items():
        matches = [row for row in rows if row.get("stage") == stage]
        if len(matches) != 1 or matches[0].get("status") != expected_status or matches[0].get("first_error") is not None:
            raise PermissionError(f"shutdown requires exactly one successful {stage} receipt")
    memberships = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    relative = next((line.split("::", 1)[1] for line in memberships if line.startswith("0::")), None)
    if relative is None:
        raise RuntimeError("shutdown requires unified cgroup-v2 membership")
    cgroup = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if not cgroup.is_dir():
        raise RuntimeError(f"shutdown cgroup is missing: {cgroup}")
    active: set[int] = set()

    def fail_walk(error: OSError) -> None:
        raise error

    for directory, _subdirs, _files in os.walk(cgroup, onerror=fail_walk):
        procs_file = Path(directory) / "cgroup.procs"
        try:
            active.update(int(value) for value in procs_file.read_text(encoding="ascii").split())
        except OSError as exc:
            raise RuntimeError(f"shutdown cannot inspect cgroup membership: {procs_file}: {exc}") from exc
    caller_chain = set()
    pid = os.getpid()
    while pid > 1:
        proc = Path(f"/proc/{pid}")
        try:
            status = (proc / "status").read_text(encoding="ascii")
        except FileNotFoundError:
            break
        parent_pid = next((int(line.split()[1]) for line in status.splitlines() if line.startswith("PPid:")), 0)
        if pid in active:
            caller_chain.add(pid)
        if parent_pid <= 0 or parent_pid == pid:
            break
        pid = parent_pid
    if os.getpid() not in active:
        raise RuntimeError("shutdown child is absent from its recorded unit cgroup")
    survivors = sorted(active - caller_chain)
    if survivors:
        raise RuntimeError(f"non-caller processes remain in the systemd unit cgroup: {survivors}")
    if any(path.name.endswith(".tmp") for path in work_root.rglob("*")):
        raise RuntimeError("temporary output remains at shutdown")
    result = {"schema": "n01-full-evaluation-shutdown/1", "status": "complete", "evaluation_identity": IDENTITY, "unit_cgroup": str(cgroup), "caller_chain_pids": sorted(caller_chain), "non_caller_processes": survivors}
    _write_json(work_root / "shutdown_check.json", result)
    return result


def _case_differences(rows: list[dict]) -> dict:
    by_key = {
        (row["condition"], row["parent_id"], row["method"], row["seed"]): row
        for row in rows
    }
    results = {}
    for condition in CONDITIONS:
        for split in SPLITS:
            parent_rows = [row for row in rows if row["condition"] == condition and row["split"] == split]
            cases = {"L1-C1": [], "L1-L0": []}
            for c1 in parent_rows:
                if c1["method"] != "C1":
                    continue
                for seed in (8201, 8202, 8203):
                    l1 = by_key[(condition, c1["parent_id"], "L1", seed)]
                    l0 = by_key[(condition, c1["parent_id"], "L0", seed)]
                    c1_value = float(c1["metrics"]["weighted_on_time_delivery_rate"] or 0.0)
                    l1_value = float(l1["metrics"]["weighted_on_time_delivery_rate"] or 0.0)
                    l0_value = float(l0["metrics"]["weighted_on_time_delivery_rate"] or 0.0)
                    common = {
                        "parent_id": c1["parent_id"],
                        "seed": seed,
                        "heldout_or_development": split,
                        "L1": l1_value,
                    }
                    cases["L1-C1"].append({**common, "C1": c1_value, "difference": l1_value - c1_value})
                    cases["L1-L0"].append({**common, "L0": l0_value, "difference": l1_value - l0_value})
            results[f"{condition}/{split}"] = {
                contrast: sorted(values, key=lambda item: (item["difference"], item["parent_id"], item["seed"]))[:10]
                for contrast, values in cases.items()
            }
    return results


def run_evaluation(
    package_root: str | Path,
    scenario_root: str | Path,
    checkpoint_root: str | Path,
    checkpoint_manifest_path: str | Path,
    plan_path: str | Path,
    output_root: str | Path,
    *,
    guardian_token: str | None,
    resource_check=None,
) -> dict:
    package = Path(package_root).resolve(strict=True)
    if not guardian_token or os.environ.get("RELIEF_GRAPH_GUARDIAN_TOKEN") != guardian_token:
        raise PermissionError("evaluation execution must run as a child of the process guardian")
    budget = _approved_budget(package)
    plan = json.loads(Path(plan_path).resolve(strict=True).read_text(encoding="utf-8"))
    if plan.get("schema") != "n01-full-evaluation-plan/1" or plan.get("evaluation_identity") != IDENTITY:
        raise PermissionError("preflight plan is missing or bound to a different evaluation identity")
    expected_plan_hash = plan.pop("plan_sha256", None)
    if _canonical_sha256(plan) != expected_plan_hash:
        raise PermissionError("preflight plan hash is invalid")
    plan["plan_sha256"] = expected_plan_hash
    fresh_plan, policies = prepare_plan(package, scenario_root, checkpoint_root, checkpoint_manifest_path)
    if fresh_plan["plan_sha256"] != expected_plan_hash:
        raise PermissionError("preflight inputs changed since the static dry run")
    _verify_admission(package, Path(output_root).resolve().parent, Path(plan_path).resolve())
    output = Path(output_root).resolve()
    _require_fresh_directory(output)
    state_path = output.parent / "n01_full_evaluation_state.json"
    _require_fresh_directory(state_path)
    _write_json(state_path, {"schema": "n01-full-evaluation-state/1", "status": "started", "evaluation_identity": IDENTITY, "plan_sha256": expected_plan_hash})
    output.mkdir(parents=True, exist_ok=False)

    from evaluator import _episode_row, _evaluate_baseline, _evaluate_learned, _build_summary

    _write_json(output / "checkpoint_barrier.json", fresh_plan["checkpoint_barrier"])
    scenario_root_path = Path(scenario_root).resolve(strict=True)
    rows = []
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    for scenario_meta in fresh_plan["scenarios"]:
        if resource_check:
            resource_check()
        scenario_path = scenario_root_path / scenario_meta["path"]
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        for method in METHODS:
            if resource_check:
                resource_check()
            episode_wall, episode_cpu = time.perf_counter(), time.process_time()
            if method in ("C0", "C1"):
                trajectory, timings = _evaluate_baseline(scenario, method)
                seed = None
            else:
                variant, seed_text = method.rsplit("-", 1)
                seed = int(seed_text)
                trajectory, timings = _evaluate_learned(scenario, policies[method], variant)
            row, audited = _episode_row(scenario, method if method in ("C0", "C1") else variant, seed, trajectory, timings, scenario_meta["stratum"])
            row.update({
                "condition": scenario_meta["condition"],
                "split": scenario_meta["split"],
                "parent_id": scenario_meta["scenario_id"],
                "episode_wall_seconds": time.perf_counter() - episode_wall,
                "episode_cpu_seconds": time.process_time() - episode_cpu,
            })
            rows.append(row)
            stem = f"{scenario_meta['condition']}/{scenario_meta['split']}/{method}/{scenario_meta['scenario_id']}"
            _write_json(output / "trajectories" / f"{stem}.json", trajectory)
            _write_json(output / "audits" / f"{stem}.json", audited)
            _write_json(output / "episode_rows" / f"{stem}.json", row)
    identities = [(row["condition"], row["parent_id"], row["method"], row["seed"]) for row in rows]
    if len(rows) != 2800 or len(set(identities)) != 2800:
        raise RuntimeError("completed output did not contain exactly 2,800 unique evaluation rows")
    if Counter(row["split"] for row in rows) != Counter({"heldout": 2240, "development": 560}):
        raise RuntimeError("completed output has invalid heldout/development split counts")
    wall_seconds, cpu_seconds = time.perf_counter() - start_wall, time.process_time() - start_cpu
    if wall_seconds > EVALUATION_CAP_WALL or cpu_seconds > EVALUATION_CAP_CPU:
        raise RuntimeError("evaluation exceeded the proposed identity stage cap")

    summaries = {}
    for condition in CONDITIONS:
        summaries[condition] = {}
        for split in SPLITS:
            subset = [row for row in rows if row["condition"] == condition and row["split"] == split]
            expected = 56 if split == "heldout" else 14
            if len({row["parent_id"] for row in subset if row["method"] == "C1"}) != expected:
                raise RuntimeError(f"missing {split} parents in {condition}")
            summaries[condition][split] = {
                "parent_count": expected,
                "episode_count": len(subset),
                "interpretation": "confirmatory-heldout" if split == "heldout" else "descriptive-development-only",
                "metrics": _build_summary(subset),
            }
            if split == "heldout":
                paired = summaries[condition][split]["metrics"].get("paired_primary_differences", {})
                for contrast in ("L1_minus_C1", "L1_minus_L0"):
                    detail = paired.get(contrast, {})
                    per_seed = detail.get("per_seed", {})
                    detail["per_seed_direction"] = {
                        seed: "positive" if value > 0 else "negative" if value < 0 else "zero"
                        for seed, value in per_seed.items()
                    }
                    if (
                        not detail.get("paired_parent_bootstrap_95_percentile_interval")
                        or set(per_seed) != {"8201", "8202", "8203"}
                        or set(detail["per_seed_direction"]) != {"8201", "8202", "8203"}
                    ):
                        raise RuntimeError(f"heldout {condition}/{contrast} is missing paired intervals or per-seed directions")
    result = {
        "schema": "n01-full-evaluation-result/1",
        "status": "complete",
        "evaluation_identity": IDENTITY,
        "plan_sha256": expected_plan_hash,
        "stage_budget_sha256": _sha256(package / "n01_full_evaluation_stage_budget.json"),
        "scenario_manifest_sha256": fresh_plan["scenario_manifest_sha256"],
        "checkpoint_manifest_sha256": fresh_plan["checkpoint_manifest_sha256"],
        "checkpoint_barrier_sha256": _sha256(output / "checkpoint_barrier.json"),
        "episode_count": len(rows),
        "split_episode_counts": {"heldout": 2240, "development": 560},
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "condition_split_summaries": summaries,
        "paired_comparison_scope": "same registered parent scenario within the same condition and split; training seeds are shown separately",
        "development_inferential_claims_allowed": False,
        "worst_10_primary_cases": _case_differences(rows),
        "episode_rows_sha256": _canonical_sha256(rows),
        "all_rows_sha256": _canonical_sha256([
            (row["condition"], row["parent_id"], row["method"], row["seed"]) for row in rows
        ]),
        "audit_count": len(rows),
        "audit_pass_count": sum(row["audit_validation_level"] == "full_artifact" for row in rows),
    }
    if result["audit_pass_count"] != 2800:
        raise RuntimeError("not all 2,800 trajectories passed the full independent audit")
    _write_json(output / "episode_metrics.json", {"runs": rows})
    _write_json(output / "summary.json", result)
    _write_json(state_path, {"schema": "n01-full-evaluation-state/1", "status": "complete", "evaluation_identity": IDENTITY, "plan_sha256": expected_plan_hash, "summary_sha256": _sha256(output / "summary.json")})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--scenario-root", type=Path)
    parser.add_argument("--checkpoint-root", type=Path)
    parser.add_argument("--checkpoint-manifest", type=Path)
    parser.add_argument("--mode", choices=("dry-run", "admit", "evaluate", "export", "shutdown", "_admit_child", "_evaluate_child", "_export_child", "_shutdown_child"), default="dry-run")
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--plan-input", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--_guardian-token", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    package = args.package_root.resolve(strict=True)
    scenario_root = args.scenario_root or package / "n01_scenarios"
    checkpoint_root = args.checkpoint_root or package / "fixed_checkpoints"
    checkpoint_manifest = args.checkpoint_manifest or package / "n01_fixed_checkpoint_manifest.json"
    if args.mode in ("admit", "evaluate", "export", "shutdown"):
        if not args.work_root:
            parser.error("--work-root is required for guarded stages")
        stage_modes = {
            "admit": ("n01_full_admission", "_admit_child"),
            "evaluate": ("n01_full_evaluation", "_evaluate_child"),
            "export": ("n01_full_export", "_export_child"),
            "shutdown": ("n01_full_shutdown", "_shutdown_child"),
        }
        stage, child_mode = stage_modes[args.mode]
        child_args = ["--scenario-root", str(Path(scenario_root).resolve()), "--checkpoint-root", str(Path(checkpoint_root).resolve()), "--checkpoint-manifest", str(Path(checkpoint_manifest).resolve())]
        if args.plan_input:
            child_args.extend(["--plan-input", str(args.plan_input.resolve())])
        if args.output_root:
            child_args.extend(["--output-root", str(args.output_root.resolve())])
        return _guarded_dispatch(package, args.work_root.resolve(), stage, child_mode, child_args)
    if args.mode == "dry-run":
        if args.output_root and args.output_root.exists():
            raise FileExistsError(f"execution output already exists; restart is rejected: {args.output_root}")
        if not args.plan_output:
            parser.error("--plan-output is required for --mode dry-run")
        plan_path = args.plan_output.resolve()
        _require_fresh_directory(plan_path)
        plan, _ = prepare_plan(package, scenario_root, checkpoint_root, checkpoint_manifest, strict_model_load=False)
        plan["static_only"] = True
        plan["plan_sha256"] = _canonical_sha256({key: value for key, value in plan.items() if key != "plan_sha256"})
        _write_json(plan_path, plan)
        print(json.dumps({"status": "static_preflight_passed", "episodes": 2800, "heldout": 2240, "development": 560, "plan": str(plan_path), "plan_sha256": plan["plan_sha256"]}, sort_keys=True))
        return 0
    if args.mode == "_admit_child":
        _require_child_guardian(args._guardian_token)
        work_root = args.work_root.resolve()
        plan_path = work_root / "preflight_plan.json"
        _require_fresh_directory(plan_path)
        def admit(supervisor):
            systemd_contract = _verify_systemd_execution_contract()
            runtime = _check_target_runtime(package)
            plan, _ = prepare_plan(package, scenario_root, checkpoint_root, checkpoint_manifest)
            _write_json(plan_path, plan)
            result = {
                "schema": "n01-full-runtime-admission/1", "status": "accepted",
                "evaluation_identity": IDENTITY, "plan_sha256": plan["plan_sha256"],
                "identity_manifest_sha256": _sha256(package / "N01_FULL_EVALUATION_IDENTITY.json"),
                "current_source_hashes": plan["current_source_hashes"],
                "scenario_manifest_sha256": plan["scenario_manifest_sha256"],
                "checkpoint_manifest_sha256": plan["checkpoint_manifest_sha256"],
                "runtime_spec_sha256": _sha256(package / "runtime-spec.json"),
                "budget_approval": _approved_budget(package)["external_approval"],
                "runtime_observed": runtime,
                "systemd_execution_contract": systemd_contract,
            }
            _write_json(work_root / "n01_runtime_admission.json", result)
            supervisor.check(force_disk=True)
            return result
        _execute_guarded_child(package, work_root, "n01_full_admission", admit)
        return 0
    if args.mode == "_evaluate_child":
        _require_child_guardian(args._guardian_token)
        def evaluate(supervisor):
            return run_evaluation(
                package, scenario_root, checkpoint_root, checkpoint_manifest,
                args.plan_input or args.work_root / "preflight_plan.json",
                args.output_root or args.work_root / "evaluation",
                guardian_token=args._guardian_token,
                resource_check=supervisor.check,
            )
        result = _execute_guarded_child(package, args.work_root.resolve(), "n01_full_evaluation", evaluate)
        print(json.dumps({"status": result["status"], "episodes": result["episode_count"]}, sort_keys=True))
        return 0
    if args.mode == "_export_child":
        _require_child_guardian(args._guardian_token)
        _execute_guarded_child(package, args.work_root.resolve(), "n01_full_export", lambda supervisor: _export_result(args.work_root.resolve()))
        return 0
    if args.mode == "_shutdown_child":
        _require_child_guardian(args._guardian_token)
        _execute_guarded_child(package, args.work_root.resolve(), "n01_full_shutdown", lambda supervisor: _verify_shutdown(args.work_root.resolve()))
        return 0
    parser.error("unsupported execution mode")
    return 2


def _require_child_guardian(token: str | None) -> None:
    if not token or os.environ.get("RELIEF_GRAPH_GUARDIAN_TOKEN") != token:
        raise PermissionError("stage child must be launched by the independent process guardian")


if __name__ == "__main__":
    raise SystemExit(main())
