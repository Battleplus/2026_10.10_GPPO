"""Budgeted admission, engineering smoke, training, evaluation, and export CLI."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import random
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from dataset_protocol import build_registry, validate_registry
from resource_supervisor import (
    CARRY_FORWARD_RECEIPT_NAME,
    ResourceSupervisor,
    _read_prior_resource_cost,
    ledger_summary,
)


HERE = Path(__file__).resolve().parent
REQUIRED_RUNTIME = {
    "python": "3.11.16",
    "torch": "2.7.0+cu128",
    "numpy": "1.26.0",
    "device": "cpu",
    "affinity": [0],
    "torch_threads": 1,
    "torch_interop_threads": 1,
    "environment": {
        "CUDA_VISIBLE_DEVICES": "",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    },
}
TRAINING_SEEDS = (8201, 8202, 8203)
VARIANTS = ("L0", "L1")
ENGINEERING_SEED = 913771
_CURRENT_INVOCATION_SETUP_WALL = 0.0
_CURRENT_INVOCATION_SETUP_CPU = 0.0


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _jsonl_append(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_cpu_environment() -> None:
    for key, value in REQUIRED_RUNTIME["environment"].items():
        os.environ[key] = value


def _load_torch_numpy():
    _configure_cpu_environment()
    import numpy as np
    import torch

    if torch.get_num_threads() != 1:
        torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
        raise RuntimeError("PyTorch did not accept the one-thread CPU configuration")
    return torch, np


def _establish_current_runtime(*, set_affinity: bool) -> tuple[dict, bool]:
    _configure_cpu_environment()
    actual_affinity = []
    affinity_error = None
    if hasattr(os, "sched_setaffinity") and hasattr(os, "sched_getaffinity"):
        if set_affinity:
            try:
                os.sched_setaffinity(0, {0})
            except OSError as exc:
                affinity_error = f"{type(exc).__name__}: {exc}"
        actual_affinity = sorted(os.sched_getaffinity(0))
    torch, np = _load_torch_numpy()
    actual = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "device": "cpu",
        "affinity": actual_affinity,
        "affinity_error": affinity_error,
        "torch_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(),
        "environment": {key: os.environ.get(key) for key in REQUIRED_RUNTIME["environment"]},
        "cuda_is_initialized": bool(torch.cuda.is_initialized()),
    }
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in REQUIRED_RUNTIME.items()
        if actual.get(key) != value
    }
    if actual["cuda_is_initialized"]:
        mismatches["cuda_is_initialized"] = {"expected": False, "actual": True}
    if affinity_error is not None:
        mismatches["affinity_error"] = {"expected": None, "actual": affinity_error}
    return actual, not bool(mismatches)


def _runtime_identity(package_root: Path, work_root: Path) -> dict:
    _read_prior_resource_cost(package_root / CARRY_FORWARD_RECEIPT_NAME, required=True)
    registry_path = package_root / "registered_data" / "input_registry.json"
    return {
        "package_root": str(package_root.resolve()),
        "work_root": str(work_root.resolve()),
        "source_hashes": _source_hashes(package_root),
        "input_registry_sha256": _sha256(registry_path),
    }


def _read_bound_admission(package_root: Path, work_root: Path) -> tuple[dict, dict]:
    admission_path = work_root / "runtime_admission.json"
    if not admission_path.is_file():
        raise PermissionError("runtime admission is missing from this work root")
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    identity = _runtime_identity(package_root, work_root)
    if (
        admission.get("schema") != "runtime-admission/1"
        or any(admission.get(key) != value for key, value in identity.items())
        or admission.get("runtime_spec_sha256") != _sha256(package_root / "runtime-spec.json")
    ):
        raise PermissionError("runtime admission source, data, package, or work-root identity mismatch")
    return admission, identity


def _bound_work_file(work_root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PermissionError(f"{label} path is missing")
    path = Path(value)
    try:
        resolved = (path if path.is_absolute() else work_root / path).resolve(strict=True)
    except OSError as exc:
        raise PermissionError(f"{label} is missing") from exc
    root = work_root.resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise PermissionError(f"{label} is outside this work root or is not a file")
    return resolved


def _require_settled_prerequisite_stages(work_root: Path) -> dict[str, dict[str, str]]:
    ledger_path = work_root / "resource-ledger.jsonl"
    try:
        rows = ledger_summary(ledger_path)["entries"]
    except (OSError, ValueError) as exc:
        raise PermissionError("main resource ledger is missing or invalid") from exc

    expected_statuses = {"admission": "accepted", "engineering_smoke": "complete"}
    evidence: dict[str, dict[str, str]] = {}
    for stage, expected_status in expected_statuses.items():
        matches = [row for row in rows if row.get("stage") == stage]
        if len(matches) != 1:
            raise PermissionError(f"{stage} must have exactly one settled main-ledger entry")
        row = matches[0]
        if (
            row.get("status") != expected_status
            or row.get("first_error") is not None
            or row.get("outer_guardian_error") is not None
            or row.get("outer_guardian_kill_reason") is not None
        ):
            raise PermissionError(f"{stage} main resource-ledger settlement did not succeed")

        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            raise PermissionError(f"{stage} main resource-ledger metadata is missing")
        receipt_path = _bound_work_file(work_root, metadata.get("receipt"), f"{stage} driver receipt")
        guardian_path = _bound_work_file(
            work_root,
            metadata.get("outer_guardian_receipt"),
            f"{stage} outer guardian receipt",
        )
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            guardian = json.loads(guardian_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PermissionError(f"{stage} settlement receipt is missing or invalid") from exc

        receipt_guardian_path = _bound_work_file(
            work_root,
            receipt.get("outer_guardian_receipt"),
            f"{stage} driver-receipt guardian link",
        )
        if (
            receipt_guardian_path != guardian_path
            or receipt.get("schema") != "driver-stage-receipt/1"
            or receipt.get("stage") != stage
            or receipt.get("status") != expected_status
            or receipt.get("first_error") is not None
            or receipt.get("resource_entry") != row
            or guardian.get("schema") != "outer-process-guardian/1"
            or guardian.get("stage") != stage
            or guardian.get("status") != "complete"
            or guardian.get("first_error") is not None
            or guardian.get("outer_guardian_error") is not None
            or guardian.get("outer_guardian_kill_reason") is not None
            or guardian.get("child_returncode") != 0
            or guardian.get("resource_entry") != row
        ):
            raise PermissionError(f"{stage} driver or outer guardian settlement is not successful")
        evidence[stage] = {
            "ledger_sha256": _sha256(ledger_path),
            "driver_receipt_sha256": _sha256(receipt_path),
            "outer_guardian_receipt_sha256": _sha256(guardian_path),
        }
    return evidence


def _require_current_runtime_acceptance(package_root: Path, work_root: Path) -> dict:
    actual, accepted = _establish_current_runtime(set_affinity=True)
    admission, identity = _read_bound_admission(package_root, work_root)
    settled_stages = _require_settled_prerequisite_stages(work_root)
    admission_path = work_root / "runtime_admission.json"
    smoke_path = work_root / "engineering_smoke" / "smoke_complete.json"
    if not accepted or not smoke_path.is_file():
        raise PermissionError("formal stages require accepted target-runtime admission and same-work-root engineering smoke")
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    smoke_root = smoke_path.parent
    smoke_export_path = smoke_root / "export_manifest.json"
    if not smoke_export_path.is_file() or _sha256(smoke_export_path) != smoke.get("export_core", {}).get("manifest_sha256"):
        raise PermissionError("engineering smoke export manifest is missing or changed")
    smoke_export = json.loads(smoke_export_path.read_text(encoding="utf-8"))
    _verify_export_manifest(smoke_root, smoke_export)
    export_paths = {entry.get("path") for entry in smoke_export.get("files", [])}
    strict_restore_path = smoke_root / "strict_restore.json"
    controlled_failure_path = smoke_root / "controlled_failure" / "failure_receipt.json"
    if (
        "strict_restore.json" not in export_paths
        or "controlled_failure/failure_receipt.json" not in export_paths
        or not strict_restore_path.is_file()
        or json.loads(strict_restore_path.read_text(encoding="utf-8")) != smoke.get("strict_restore_equivalence")
        or not controlled_failure_path.is_file()
        or json.loads(controlled_failure_path.read_text(encoding="utf-8")) != smoke.get("controlled_failure_probe")
        or {item["path"]: item["sha256"] for item in smoke_export.get("sources", [])} != identity["source_hashes"]
    ):
        raise PermissionError("engineering smoke export does not bind its restore and controlled-failure evidence")
    freeze_path = work_root / "budget_freeze.json"
    if not freeze_path.is_file():
        raise PermissionError("same-work-root smoke budget freeze is missing")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    admitted_runtime = dict(admission.get("actual", {}))
    cuda_before_witness = admitted_runtime.pop("cuda_is_initialized_before_witness", None)
    if (
        admission.get("schema") != "runtime-admission/1"
        or admission.get("status") != "accepted"
        or admission.get("target_runtime_acceptance") is not True
        or any(admission.get(key) != value for key, value in identity.items())
        or admitted_runtime != actual
        or cuda_before_witness is not False
        or admission.get("kernel_witness", {}).get("cuda_initialized_after_witness") is not False
    ):
        raise PermissionError("runtime admission does not bind this package, data registry, work root, and process runtime")
    if (
        smoke.get("schema") != "engineering-smoke-result/1"
        or smoke.get("status") != "complete"
        or smoke.get("target_runtime_acceptance") is not True
        or smoke.get("runtime_admission_sha256") != _sha256(admission_path)
        or any(smoke.get(key) != value for key, value in identity.items())
        or smoke.get("actual_runtime") != actual
        or smoke.get("export_core", {}).get("status") != "complete"
        or smoke.get("strict_restore_equivalence", {}).keys() != {"L0", "L1"}
        or not all(item.get("equivalent") is True for item in smoke.get("strict_restore_equivalence", {}).values())
        or smoke.get("controlled_failure_probe", {}).get("status") != "expected_failure_recorded"
        or smoke.get("budget_freeze_sha256") != _sha256(freeze_path)
        or freeze.get("target_runtime_acceptance") is not True
        or any(freeze.get(key) != value for key, value in identity.items())
        or freeze.get("runtime_admission_sha256") != _sha256(admission_path)
        or freeze.get("engineering_smoke_export_manifest_sha256") != smoke.get("export_core", {}).get("manifest_sha256")
        or freeze.get("engineering_smoke_export_manifest_sha256") != _sha256(smoke_export_path)
    ):
        raise PermissionError("engineering smoke is incomplete or does not bind the accepted source/runtime identity")
    return {
        "actual_runtime": actual,
        "identity": identity,
        "admission_sha256": _sha256(admission_path),
        "budget_freeze_sha256": _sha256(freeze_path),
        "settled_prerequisite_stages": settled_stages,
    }


def _run_preflight(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    actual_runtime, runtime_accepted = _establish_current_runtime(set_affinity=True)
    torch, np = _load_torch_numpy()
    actual = {**actual_runtime, "cuda_is_initialized_before_witness": bool(torch.cuda.is_initialized())}
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in REQUIRED_RUNTIME.items()
        if actual.get(key) != value
    }
    if not runtime_accepted:
        mismatches["target_runtime"] = {"expected": REQUIRED_RUNTIME, "actual": actual_runtime}

    torch.manual_seed(738102)
    module = torch.nn.Linear(16, 8, bias=True, device="cpu")
    optimizer = torch.optim.Adam(module.parameters(), lr=3e-4)
    inputs = torch.arange(32, dtype=torch.float32).reshape(2, 16) / 32.0
    target = torch.linspace(-1.0, 1.0, 16, dtype=torch.float32).reshape(2, 8)
    before = [parameter.detach().clone() for parameter in module.parameters()]
    prediction = module(inputs)
    loss = torch.nn.functional.mse_loss(prediction, target)
    loss.backward()
    grad_norm = torch.nn.utils.clip_grad_norm_(module.parameters(), 0.5)
    optimizer.step()
    changed = any(not torch.equal(old, new.detach()) for old, new in zip(before, module.parameters()))
    if not torch.isfinite(loss) or not torch.isfinite(grad_norm) or not changed:
        raise RuntimeError("CPU tensor/autograd/Adam kernel witness failed")
    if torch.cuda.is_initialized():
        raise RuntimeError("GPU initialized during CPU-only kernel witness")
    witness = {
        "kernel": "torch.nn.Linear forward + MSE backward + clipped gradient + Adam step",
        "device": str(prediction.device),
        "loss": float(loss.detach().item()),
        "grad_norm_preclip": float(grad_norm.detach().item()),
        "parameter_changed": changed,
        "input_sha256": hashlib.sha256(inputs.numpy().tobytes()).hexdigest(),
        "prediction_sha256": hashlib.sha256(prediction.detach().numpy().tobytes()).hexdigest(),
        "post_step_parameter_sha256": hashlib.sha256(b"".join(parameter.detach().numpy().tobytes() for parameter in module.parameters())).hexdigest(),
        "cuda_initialized_after_witness": bool(torch.cuda.is_initialized()),
    }
    runtime_spec = json.loads((package_root / "runtime-spec.json").read_text(encoding="utf-8"))
    identity = _runtime_identity(package_root, work_root)
    receipt = {
        "schema": "runtime-admission/1",
        "runtime_spec_sha256": _sha256(package_root / "runtime-spec.json"),
        "runtime_spec": runtime_spec,
        "actual": actual,
        **identity,
        "mismatches": mismatches,
        "kernel_witness": witness,
        "status": "accepted" if not mismatches else "rejected",
        "target_runtime_acceptance": not bool(mismatches),
    }
    _json_write(work_root / "runtime_admission.json", receipt)
    supervisor.check()
    if mismatches:
        raise RuntimeError(f"runtime admission mismatch: {mismatches}")
    return receipt


def _fixture_scenarios(package_root: Path) -> tuple[list[dict], dict[str, str]]:
    fixture_dir = package_root / "fixtures"
    names = ("control", "failure", "energy_change", "stock_loss", "report_delay", "combined", "external_commitment")
    scenarios = []
    hashes = {}
    for name in names:
        path = fixture_dir / f"{name}.json"
        data = path.read_bytes()
        scenario = json.loads(data.decode("utf-8"))
        if scenario.get("scenario_id") != name:
            raise ValueError(f"engineering fixture identity mismatch: {name}")
        scenarios.append(scenario)
        hashes[path.name] = hashlib.sha256(data).hexdigest()
    return scenarios, hashes


def _source_hashes(package_root: Path) -> dict[str, str]:
    root = str(package_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    from ppo_trainer import source_identity

    return source_identity(package_root)


def _checkpoint_inventory(root: Path) -> list[dict]:
    if not root.exists():
        return []
    return [
        {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(root.rglob("*.pt")) if path.is_file()
    ]


def _prepare_fresh_attempt(path: Path, label: str) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"{label} identity already contains evidence; preserve it and use an unused identity")
    path.mkdir(parents=True, exist_ok=True)


def _run_engineering_smoke(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    smoke_root = work_root / "engineering_smoke"
    _prepare_fresh_attempt(smoke_root, "engineering smoke")
    smoke_setup_started_wall = time.perf_counter()
    smoke_setup_started_cpu = time.process_time()
    actual_runtime, current_target_runtime = _establish_current_runtime(set_affinity=True)
    admission, identity = _read_bound_admission(package_root, work_root)
    admitted_runtime = dict(admission.get("actual", {}))
    admitted_cuda_before = admitted_runtime.pop("cuda_is_initialized_before_witness", None)
    target_runtime_receipt_matches = (
        admitted_runtime == actual_runtime
        and admitted_cuda_before is False
        and admission.get("kernel_witness", {}).get("cuda_initialized_after_witness") is False
    )
    torch, _ = _load_torch_numpy()
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from evaluator import _episode_row, _evaluate_baseline, _evaluate_learned
    from graph_policy import build_paired_policies, build_policy
    from ppo_trainer import PPOTrainer, PPOConfig, load_registered_scenarios, verify_next_update_equivalence
    from independent_audit import audit_run

    scenarios, fixture_hashes = _fixture_scenarios(package_root)
    data_hash = hashlib.sha256(json.dumps(fixture_hashes, sort_keys=True).encode("utf-8")).hexdigest()
    data_load_started_wall = time.perf_counter()
    data_load_started_cpu = time.process_time()
    registered_train_scenarios, _ = load_registered_scenarios(package_root, "train")
    registered_data_load_wall = time.perf_counter() - data_load_started_wall
    registered_data_load_cpu = time.process_time() - data_load_started_cpu
    if len(registered_train_scenarios) != 56:
        raise RuntimeError("engineering smoke data-load probe did not read the full registered training split")
    init_wall = time.perf_counter()
    init_cpu = time.process_time()
    l0, l1, pairing = build_paired_policies(ENGINEERING_SEED, device="cpu")
    paired_init_wall = time.perf_counter() - init_wall
    paired_init_cpu = time.process_time() - init_cpu
    _json_write(smoke_root / "paired_architecture_evidence.json", pairing)
    round_wall_samples: list[float] = []
    round_cpu_samples: list[float] = []
    final_save_wall_samples: list[float] = []
    final_save_cpu_samples: list[float] = []
    trainer_init_wall_samples: list[float] = []
    trainer_init_cpu_samples: list[float] = []
    trainers = {}
    strict_restore = {}
    setup_wall_through_first_round_start: float | None = None
    setup_cpu_through_first_round_start: float | None = None

    def create_trainer(variant: str, model: torch.nn.Module, run_dir: Path) -> PPOTrainer:
        return PPOTrainer(
            model,
            variant=variant,
            seed=ENGINEERING_SEED,
            scenarios=scenarios,
            data_hash=data_hash,
            package_root=package_root,
            run_dir=run_dir,
            config=PPOConfig(),
            resource_check=supervisor.check,
            allow_engineering_scenarios=True,
        )

    for variant, model in (("L0", l0), ("L1", l1)):
        run_dir = smoke_root / "smoke_models" / variant
        trainer_started_wall = time.perf_counter()
        trainer_started_cpu = time.process_time()
        trainer = create_trainer(variant, model, run_dir)
        trainer_init_wall_samples.append(time.perf_counter() - trainer_started_wall)
        trainer_init_cpu_samples.append(time.process_time() - trainer_started_cpu)
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        if setup_wall_through_first_round_start is None:
            setup_wall_through_first_round_start = started_wall - smoke_setup_started_wall
            setup_cpu_through_first_round_start = started_cpu - smoke_setup_started_cpu
        first_round = trainer.train_round()
        round_wall_samples.append(time.perf_counter() - started_wall)
        round_cpu_samples.append(time.process_time() - started_cpu)
        checkpoint_one = run_dir / "checkpoints" / "round_0001.pt"
        if not checkpoint_one.is_file():
            raise RuntimeError(f"{variant} first round did not save a checkpoint")

        resume_run_dir = smoke_root / "restore_probes" / variant

        def restore_factory(variant=variant, resume_run_dir=resume_run_dir) -> PPOTrainer:
            restored_model = build_policy(variant, ENGINEERING_SEED, device="cpu")
            return create_trainer(variant, restored_model, resume_run_dir)

        proof_started_wall = time.perf_counter()
        proof_started_cpu = time.process_time()
        proof = verify_next_update_equivalence(trainer, restore_factory, checkpoint_one)
        proof_wall = time.perf_counter() - proof_started_wall
        proof_cpu = time.process_time() - proof_started_cpu
        strict_restore[variant] = {**proof, "proof_wall_seconds": proof_wall, "proof_cpu_seconds": proof_cpu}
        round_wall_samples.append(float(first_round["round_wall_seconds_including_checkpoint"]))
        round_cpu_samples.append(float(first_round["round_cpu_seconds_including_checkpoint"]))
        round_wall_samples.extend((
            float(proof["expected_round_wall_seconds_including_checkpoint"]),
            float(proof["restored_round_wall_seconds_including_checkpoint"]),
        ))
        round_cpu_samples.extend((
            float(proof["expected_round_cpu_seconds_including_checkpoint"]),
            float(proof["restored_round_cpu_seconds_including_checkpoint"]),
        ))
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        final_checkpoint = trainer.save_checkpoint(
            run_dir / "final.pt", training_complete=True, target_rounds=2
        )
        final_save_wall_samples.append(time.perf_counter() - started_wall)
        final_save_cpu_samples.append(time.process_time() - started_cpu)
        if trainer.round_number != 2 or final_checkpoint["round_number"] != 2:
            raise RuntimeError(f"{variant} engineering smoke did not reach two rounds")
        trainers[variant] = trainer
    _json_write(smoke_root / "strict_restore.json", strict_restore)

    evaluation_rows = []
    for scenario in scenarios:
        supervisor.check()
        for policy_name in ("C0", "C1"):
            result, timings = _evaluate_baseline(scenario, policy_name)
            audited = audit_run(scenario, result, expected_policy=policy_name)
            row, _ = _episode_row(scenario, policy_name, None, result, timings, scenario["scenario_id"])
            evaluation_rows.append(row)
            stem = f"{policy_name}/{scenario['scenario_id']}"
            _json_write(smoke_root / "evaluation" / "trajectories" / f"{stem}.json", result)
            _json_write(smoke_root / "evaluation" / "audits" / f"{stem}.json", audited)
            _jsonl_append(smoke_root / "evaluation" / "task_rows.jsonl", {
                "parent_id": scenario["scenario_id"], "policy": policy_name, "rows": audited["task_rows"]
            })
        for policy_name in VARIANTS:
            trainer = trainers[policy_name]
            result, timings = _evaluate_learned(scenario, trainer.policy, policy_name)
            audited = audit_run(scenario, result, expected_policy=policy_name)
            row, _ = _episode_row(scenario, policy_name, ENGINEERING_SEED, result, timings, scenario["scenario_id"])
            evaluation_rows.append(row)
            stem = f"{policy_name}/{scenario['scenario_id']}"
            _json_write(smoke_root / "evaluation" / "trajectories" / f"{stem}.json", result)
            _json_write(smoke_root / "evaluation" / "audits" / f"{stem}.json", audited)
            _jsonl_append(smoke_root / "evaluation" / "task_rows.jsonl", {
                "parent_id": scenario["scenario_id"], "policy": policy_name, "rows": audited["task_rows"]
            })
    _json_write(smoke_root / "evaluation" / "episode_metrics.json", {"runs": evaluation_rows})

    controlled = _controlled_failure_probe(package_root, smoke_root, supervisor, scenarios, data_hash)
    smoke_files = [path for path in smoke_root.rglob("*") if path.is_file() and path.name != "bundle_hashes.json"]
    hashes = {path.relative_to(smoke_root).as_posix(): _sha256(path) for path in sorted(smoke_files)}
    _json_write(smoke_root / "bundle_hashes.json", hashes)
    export_core = _export_bundle_core(
        package_root,
        smoke_root,
        smoke_root / "export_manifest.json",
        work_root / "resource-ledger.jsonl",
        supervisor,
        scope="engineering_smoke",
        metadata={
            "real_optimizer_updates_per_variant": 32,
            "evaluation_runs": len(evaluation_rows),
            "strict_restore_equivalence": strict_restore,
            "controlled_failure_probe": controlled,
            "runtime_admission_sha256": _sha256(work_root / "runtime_admission.json"),
        },
    )
    max_round_wall = max(round_wall_samples)
    max_round_cpu = max(round_cpu_samples)
    max_final_wall = max(final_save_wall_samples)
    max_final_cpu = max(final_save_cpu_samples)
    max_trainer_init_wall = max(trainer_init_wall_samples)
    max_trainer_init_cpu = max(trainer_init_cpu_samples)
    first_trainer_init_wall = trainer_init_wall_samples[0]
    first_trainer_init_cpu = trainer_init_cpu_samples[0]
    measured_setup_wall = float(setup_wall_through_first_round_start or 0.0)
    measured_setup_cpu = float(setup_cpu_through_first_round_start or 0.0)
    smoke_runtime_setup_wall = max(0.0, measured_setup_wall - registered_data_load_wall - paired_init_wall - first_trainer_init_wall)
    smoke_runtime_setup_cpu = max(0.0, measured_setup_cpu - registered_data_load_cpu - paired_init_cpu - first_trainer_init_cpu)
    fixed_wall = (
        _CURRENT_INVOCATION_SETUP_WALL
        + smoke_runtime_setup_wall
        + registered_data_load_wall
        + 3.0 * paired_init_wall
        + 6.0 * max_trainer_init_wall
        + 6.0 * max_final_wall
    )
    fixed_cpu = (
        _CURRENT_INVOCATION_SETUP_CPU
        + smoke_runtime_setup_cpu
        + registered_data_load_cpu
        + 3.0 * paired_init_cpu
        + 6.0 * max_trainer_init_cpu
        + 6.0 * max_final_cpu
    )
    wall_rounds = max(0, int((9000.0 / 1.5 - fixed_wall) // (6.0 * max_round_wall))) if max_round_wall > 0 else 0
    cpu_rounds = max(0, int((8400.0 / 1.5 - fixed_cpu) // (6.0 * max_round_cpu))) if max_round_cpu > 0 else 0
    common_rounds = min(32, wall_rounds, cpu_rounds)
    freeze = {
        "schema": "six-run-budget-freeze/1",
        "eligible": common_rounds >= 8,
        "common_rounds": common_rounds,
        "maximum_rounds": 32,
        "formula": "min(32, floor((9000/1.5 - measured_fixed_wall)/(6*max_observed_round_wall)), floor((8400/1.5 - measured_fixed_cpu)/(6*max_observed_round_cpu)))",
        "round_wall_samples_seconds_including_checkpoint": round_wall_samples,
        "round_cpu_samples_seconds_including_checkpoint": round_cpu_samples,
        "max_round_wall_seconds": max_round_wall,
        "max_round_cpu_seconds": max_round_cpu,
        "fixed_wall_seconds_for_smoke_runtime_import_setup_data_load_three_pair_inits_six_trainer_inits_and_six_final_saves": fixed_wall,
        "fixed_cpu_seconds_for_smoke_runtime_import_setup_data_load_three_pair_inits_six_trainer_inits_and_six_final_saves": fixed_cpu,
        "driver_invocation_setup_wall_seconds": _CURRENT_INVOCATION_SETUP_WALL,
        "driver_invocation_setup_cpu_seconds": _CURRENT_INVOCATION_SETUP_CPU,
        "smoke_setup_wall_through_first_round_start_seconds": measured_setup_wall,
        "smoke_setup_cpu_through_first_round_start_seconds": measured_setup_cpu,
        "smoke_runtime_import_setup_wall_seconds_excluding_separately_counted_components": smoke_runtime_setup_wall,
        "smoke_runtime_import_setup_cpu_seconds_excluding_separately_counted_components": smoke_runtime_setup_cpu,
        "registered_training_data_load_wall_seconds": registered_data_load_wall,
        "registered_training_data_load_cpu_seconds": registered_data_load_cpu,
        "registered_training_parent_count": len(registered_train_scenarios),
        "measured_pair_initialization_wall_seconds": paired_init_wall,
        "measured_pair_initialization_cpu_seconds": paired_init_cpu,
        "max_final_checkpoint_save_wall_seconds": max_final_wall,
        "max_final_checkpoint_save_cpu_seconds": max_final_cpu,
        "max_trainer_initialization_wall_seconds": max_trainer_init_wall,
        "max_trainer_initialization_cpu_seconds": max_trainer_init_cpu,
        "first_smoke_trainer_initialization_wall_seconds": first_trainer_init_wall,
        "first_smoke_trainer_initialization_cpu_seconds": first_trainer_init_cpu,
        "wall_feasible_rounds": wall_rounds,
        "cpu_feasible_rounds": cpu_rounds,
        "margin_factor": 1.5,
        "training_wall_budget_seconds": 9000,
        "training_cpu_budget_seconds": 8400,
        "six_new_runs": [f"{variant}-{seed}" for seed in TRAINING_SEEDS for variant in VARIANTS],
        "engineering_identity": {
            "seed": ENGINEERING_SEED,
            "fixture_sha256": fixture_hashes,
            "training_data_hash": data_hash,
            "checkpoint_weights_reused": False,
        },
        "strict_restore_equivalence": strict_restore,
        "controlled_failure_probe": controlled,
        "engineering_smoke_export_core": export_core,
        "engineering_smoke_export_manifest_sha256": export_core["manifest_sha256"],
        "target_runtime_acceptance": bool(
            current_target_runtime
            and admission.get("target_runtime_acceptance") is True
            and admission.get("status") == "accepted"
            and target_runtime_receipt_matches
        ),
        "runtime_admission_sha256": _sha256(work_root / "runtime_admission.json"),
        **identity,
        "actual_runtime": actual_runtime,
        "scenario_dataset": "registered train/development/heldout scenarios are not used by engineering smoke",
        "frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    freeze = {
        "schema": "research-training-budget-freeze/1",
        "status": "inapplicable",
        "eligible": False,
        "common_rounds": 0,
        "reason": "N01 evaluates frozen checkpoints only; no research training budget is authorized.",
    }
    _json_write(work_root / "budget_freeze.json", freeze)
    smoke_receipt = {
        "schema": "engineering-smoke-result/1",
        "status": "complete",
        "rounds_per_variant": 2,
        "optimizer_updates_per_round": 16,
        "evaluation_runs": len(evaluation_rows),
        "strict_restore_equivalence": strict_restore,
        "controlled_failure_probe": controlled,
        "target_runtime_acceptance": bool(
            current_target_runtime
            and admission.get("target_runtime_acceptance") is True
            and admission.get("status") == "accepted"
            and target_runtime_receipt_matches
        ),
        "runtime_admission_sha256": _sha256(work_root / "runtime_admission.json"),
        "actual_runtime": actual_runtime,
        "export_core": export_core,
        "training_budget_freeze_status": "inapplicable",
        **identity,
        "bundle_hashes_sha256": _sha256(smoke_root / "bundle_hashes.json"),
    }
    _json_write(smoke_root / "smoke_complete.json", smoke_receipt)
    return {"status": "complete", "freeze": freeze, "smoke": smoke_receipt}


def _controlled_failure_probe(
    package_root: Path,
    smoke_root: Path,
    supervisor: ResourceSupervisor,
    scenarios: list[dict],
    data_hash: str,
) -> dict:
    torch, _ = _load_torch_numpy()
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from graph_policy import build_policy
    from ppo_trainer import PPOTrainer

    probe_root = smoke_root / "controlled_failure"
    trainer = None

    def fail_after_real_update(stage_supervisor: ResourceSupervisor) -> dict:
        nonlocal trainer
        model = build_policy("L0", ENGINEERING_SEED + 1, device="cpu")

        def check_both_scopes() -> None:
            supervisor.check()
            stage_supervisor.check()

        trainer = PPOTrainer(
            model,
            variant="L0",
            seed=ENGINEERING_SEED + 1,
            scenarios=scenarios,
            data_hash=data_hash,
            package_root=package_root,
            run_dir=probe_root / "model",
            resource_check=check_both_scopes,
            allow_engineering_scenarios=True,
        )
        trainer.train_round()
        raise RuntimeError("controlled_failure_after_checkpoint")

    failure: str | None = None
    try:
        _execute_stage("shutdown", package_root, probe_root, fail_after_real_update)
    except RuntimeError as exc:
        failure = f"{type(exc).__name__}: {exc}"
    inventory = _checkpoint_inventory(probe_root)
    if failure != "RuntimeError: controlled_failure_after_checkpoint" or not inventory:
        raise AssertionError("controlled error path did not preserve a partial checkpoint and first error")
    receipts = sorted((probe_root / "receipts").glob("*.json"))
    ledger = ledger_summary(probe_root / "resource-ledger.jsonl")
    if len(receipts) != 1 or not ledger["entries"]:
        raise AssertionError("controlled error path did not settle a driver receipt and resource ledger")
    driver_receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    ledger_entry = ledger["entries"][0]
    if (
        driver_receipt.get("status") != "failed"
        or driver_receipt.get("first_error") != failure
        or not driver_receipt.get("partial_checkpoints")
        or ledger_entry.get("status") != "failed"
        or ledger_entry.get("first_error") != failure
    ):
        raise AssertionError("controlled error receipt or resource settlement is incomplete")
    receipt = {
        "schema": "controlled-driver-failure/1",
        "status": "expected_failure_recorded",
        "first_error": failure,
        "partial_checkpoint_inventory": inventory,
        "driver_stage_receipt": str(receipts[0].relative_to(probe_root).as_posix()),
        "driver_resource_ledger": str((probe_root / "resource-ledger.jsonl").relative_to(probe_root).as_posix()),
        "driver_receipt_status": driver_receipt["status"],
        "driver_resource_status": ledger_entry["status"],
        "resource_settlement": "inner driver failure stage records the first error and partial checkpoints; outer engineering_smoke accounts for the probe's full wall/CPU/RSS/storage use",
    }
    _json_write(probe_root / "failure_receipt.json", receipt)
    return receipt


def _run_formal_training(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    runtime_acceptance = _require_current_runtime_acceptance(package_root, work_root)
    torch, _ = _load_torch_numpy()
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from graph_policy import build_paired_policies
    from ppo_trainer import PPOTrainer, PPOConfig, load_registered_scenarios

    freeze_path = work_root / "budget_freeze.json"
    if not freeze_path.is_file():
        raise PermissionError("six-run training requires the smoke-measured budget freeze")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    common_rounds = int(freeze.get("common_rounds", 0))
    if (
        any(freeze.get(key) != value for key, value in runtime_acceptance["identity"].items())
        or freeze.get("runtime_admission_sha256") != runtime_acceptance["admission_sha256"]
    ):
        raise PermissionError("budget freeze is not bound to the accepted source/data/runtime identity")
    if freeze.get("eligible") is not True or not 8 <= common_rounds <= 32:
        _json_write(work_root / "budget_insufficient.json", {"status": "stopped_before_six_runs", "freeze": freeze})
        return {"status": "budget_insufficient", "common_rounds": common_rounds}
    registry_check = validate_registry(package_root / "registered_data")
    train_scenarios, registry = load_registered_scenarios(package_root, "train")
    if len(train_scenarios) != 56:
        raise ValueError("formal training requires all 56 preregistered training scenes")
    registry_path = package_root / "registered_data" / "input_registry.json"
    registry_hash = _sha256(registry_path)
    training_root = work_root / "formal_training"
    _prepare_fresh_attempt(training_root, "formal training")
    _json_write(training_root / "budget_freeze.json", freeze)
    run_metadata = {
        "schema": "formal-training-run/1",
        "status": "running",
        "fresh_initialization": True,
        "legacy_checkpoint_import": False,
        "seeds": list(TRAINING_SEEDS),
        "variants": list(VARIANTS),
        "common_rounds": common_rounds,
        "input_registry_sha256": registry_hash,
        "source_hashes": _source_hashes(package_root),
        "training_parent_count": len(train_scenarios),
        "training_registry_allocation": registry_check,
        "runtime_acceptance": runtime_acceptance,
    }
    _json_write(training_root / "run_metadata.json", run_metadata)
    final_entries: list[dict] = []
    for seed in TRAINING_SEEDS:
        supervisor.check()
        l0, l1, pairing = build_paired_policies(seed, device="cpu")
        _json_write(training_root / "pairing" / f"seed_{seed}.json", pairing)
        for variant, model in (("L0", l0), ("L1", l1)):
            run_id = f"{variant}-{seed}"
            run_dir = training_root / "runs" / run_id
            trainer = PPOTrainer(
                model,
                variant=variant,
                seed=seed,
                scenarios=train_scenarios,
                data_hash=registry_hash,
                package_root=package_root,
                run_dir=run_dir,
                config=PPOConfig(),
                resource_check=supervisor.check,
            )
            for round_index in range(common_rounds):
                row = trainer.train_round()
                _jsonl_append(training_root / "training_progress.jsonl", {
                    "run_id": run_id,
                    "round": round_index + 1,
                    "checkpoint_path": str(Path("runs") / run_id / "checkpoints" / f"round_{round_index + 1:04d}.pt"),
                    "round_wall_seconds_including_checkpoint": row["round_wall_seconds_including_checkpoint"],
                    "round_cpu_seconds_including_checkpoint": row["round_cpu_seconds_including_checkpoint"],
                    "mean_episode_reward": row["mean_episode_reward"],
                    "mean_weighted_on_time_delivery_rate": row["mean_weighted_on_time_delivery_rate"],
                    "actor_loss": row["actor_loss"],
                    "value_loss": row["value_loss"],
                    "entropy": row["entropy"],
                    "optimizer_updates": row["optimizer_updates"],
                })
            final_checkpoint = trainer.save_checkpoint(
                run_dir / "final.pt", training_complete=True, target_rounds=common_rounds
            )
            entry = {
                "run_id": run_id,
                "variant": variant,
                "seed": seed,
                "rounds": common_rounds,
                "path": (Path("runs") / run_id / "final.pt").as_posix(),
                "sha256": final_checkpoint["sha256"],
                "model_state_sha256": final_checkpoint["model_state_sha256"],
                "optimizer_state_sha256": final_checkpoint["optimizer_state_sha256"],
                "architecture_evidence": pairing[variant],
                "freshly_initialized": True,
            }
            final_entries.append(entry)
            _jsonl_append(training_root / "partial_final_checkpoints.jsonl", entry)
            supervisor.check()
    if len(final_entries) != 6:
        raise AssertionError(f"formal run emitted {len(final_entries)} final checkpoints")
    final_manifest = {
        "schema": "six-final-checkpoints/1",
        "training_complete": True,
        "common_rounds": common_rounds,
        "run_count": len(final_entries),
        "input_registry_sha256": registry_hash,
        "runs": final_entries,
    }
    _json_write(training_root / "final_checkpoints.json", final_manifest)
    run_metadata["status"] = "complete"
    run_metadata["final_checkpoint_manifest_sha256"] = _sha256(training_root / "final_checkpoints.json")
    _json_write(training_root / "run_metadata.json", run_metadata)
    return {"status": "complete", "common_rounds": common_rounds, "final_checkpoint_count": len(final_entries)}


def _run_evaluation(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    _require_current_runtime_acceptance(package_root, work_root)
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from evaluator import run_evaluation

    return run_evaluation(
        package_root,
        work_root / "formal_training",
        work_root / "formal_evaluation",
        resource_check=supervisor.check,
    )


def _run_export(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    acceptance = _require_current_runtime_acceptance(package_root, work_root)
    eval_root = work_root / "formal_evaluation"
    training_root = work_root / "formal_training"
    if not (eval_root / "checkpoint_barrier.json").is_file() or not (eval_root / "summary.json").is_file():
        raise PermissionError("export stage requires completed gated evaluation")
    return _export_bundle_core(
        package_root,
        work_root,
        work_root / "export_manifest.json",
        work_root / "resource-ledger.jsonl",
        supervisor,
        scope="formal_evaluation",
        metadata={
            "training_checkpoints": json.loads((training_root / "final_checkpoints.json").read_text(encoding="utf-8")),
            "evaluation_summary_sha256": _sha256(eval_root / "summary.json"),
            "runtime_acceptance": acceptance,
        },
    )


def _verify_export_manifest(artifact_root: Path, manifest: dict) -> None:
    root = artifact_root.resolve()
    for entry in manifest.get("files", []):
        path = (root / entry["path"]).resolve(strict=True)
        if root not in path.parents:
            raise ValueError(f"export path escapes artifact root: {entry['path']}")
        if path.stat().st_size != entry["size_bytes"] or _sha256(path) != entry["sha256"]:
            raise ValueError(f"export file changed after manifest generation: {entry['path']}")


def _export_bundle_core(
    package_root: Path,
    artifact_root: Path,
    manifest_path: Path,
    ledger_path: Path,
    supervisor: ResourceSupervisor,
    *,
    scope: str,
    metadata: dict,
) -> dict:
    artifact_root = artifact_root.resolve()
    manifest_path = manifest_path.resolve()
    snapshot_path = artifact_root / "resource_ledger_snapshot.json"
    ledger_cutoff = "ledger entries completed before this export stage; current stage and later shutdown are recorded in the live ledger"
    ledger_snapshot = {
        "schema": "resource-ledger-snapshot/1",
        "cutoff": ledger_cutoff,
        "summary": ledger_summary(ledger_path, package_root / CARRY_FORWARD_RECEIPT_NAME),
    }
    _json_write(snapshot_path, ledger_snapshot)
    live_ledger = ledger_path.resolve()
    files = []
    for path in artifact_root.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.resolve() == manifest_path or path.resolve() == live_ledger:
            continue
        if path.name.endswith(".tmp") or path.name == "smoke_complete.json":
            continue
        files.append(path)
    rows = []
    for path in sorted(files):
        supervisor.check()
        rows.append({
            "path": path.relative_to(artifact_root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    source_rows = [{"path": name, "sha256": digest} for name, digest in sorted(_source_hashes(package_root).items())]
    manifest = {
        "schema": "relief-graph-export/1",
        "scope": scope,
        "file_count": len(rows),
        "files": rows,
        "sources": source_rows,
        "resource_ledger_snapshot": {
            "path": snapshot_path.relative_to(artifact_root).as_posix(),
            "sha256": _sha256(snapshot_path),
            "cutoff": ledger_cutoff,
        },
        "metadata": metadata,
    }
    _json_write(manifest_path, manifest)
    supervisor.check(force_disk=True)
    _verify_export_manifest(artifact_root, manifest)
    return {
        "status": "complete",
        "scope": scope,
        "file_count": len(rows),
        "manifest_path": manifest_path.relative_to(artifact_root).as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "resource_ledger_snapshot_sha256": _sha256(snapshot_path),
    }


def _stage_receipt_path(work_root: Path, stage: str, ledger_path: Path) -> Path:
    count = len(ledger_path.read_text(encoding="utf-8").splitlines()) if ledger_path.is_file() else 0
    return work_root / "receipts" / f"{count + 1:02d}-{stage}.json"


def _execute_stage(
    stage: str,
    package_root: Path,
    work_root: Path,
    action: Callable[[ResourceSupervisor], dict],
    *,
    invocation_start: tuple[float, float] | None = None,
) -> dict:
    ledger = work_root / "resource-ledger.jsonl"
    work_root.mkdir(parents=True, exist_ok=True)
    receipt_path = _stage_receipt_path(work_root, stage, ledger)
    supervisor = None
    try:
        supervisor = ResourceSupervisor(
            stage,
            ledger,
            (package_root, work_root),
            prior_cost_path=package_root / CARRY_FORWARD_RECEIPT_NAME,
            invocation_start_wall=invocation_start[0] if invocation_start else None,
            invocation_start_cpu=invocation_start[1] if invocation_start else None,
        )
        supervisor.start_monitor()
        supervisor.check(force_disk=True)
        result = action(supervisor)
        status = result.get("status", "complete")
        receipt = {
            "schema": "driver-stage-receipt/1",
            "stage": stage,
            "status": status,
            "result": result,
            "first_error": None,
            "partial_checkpoints": [],
        }
        entry = supervisor.finish(status="complete" if status == "complete" else status, metadata={"receipt": str(receipt_path)})
        receipt["resource_entry"] = entry
        _json_write(receipt_path, receipt)
        entry = supervisor.close()
        receipt["resource_entry"] = entry
        if entry.get("status") == "failed":
            receipt["status"] = "failed"
            receipt["first_error"] = entry.get("first_error")
            receipt["partial_checkpoints"] = _checkpoint_inventory(work_root)
            _json_write(receipt_path, receipt)
            raise BudgetExceeded(entry.get("first_error") or "resource limit exceeded during stage settlement")
        _json_write(receipt_path, receipt)
        return result
    except BaseException as exc:
        if supervisor is None:
            failure_receipt = {
                "schema": "driver-stage-receipt/1",
                "stage": stage,
                "status": "failed",
                "first_error": f"{type(exc).__name__}: {exc}",
                "error_traceback": traceback.format_exc(),
                "partial_checkpoints": _checkpoint_inventory(work_root),
            }
            _json_write(receipt_path, failure_receipt)
            raise
        supervisor.record_error(exc)
        partial = _checkpoint_inventory(work_root)
        receipt = {
            "schema": "driver-stage-receipt/1",
            "stage": stage,
            "status": "failed",
            "first_error": supervisor._first_error,
            "error_traceback": traceback.format_exc(),
            "partial_checkpoints": partial,
        }
        _json_write(receipt_path, receipt)
        if supervisor._finished_row is None:
            supervisor.finish(status="failed", error=exc, metadata={"receipt": str(receipt_path)})
        entry = supervisor.close(error=exc)
        receipt["resource_entry"] = entry
        _json_write(receipt_path, receipt)
        raise


def _settle_shutdown(package_root: Path, work_root: Path, supervisor: ResourceSupervisor) -> dict:
    return {
        "status": "complete",
        "ledger": ledger_summary(
            work_root / "resource-ledger.jsonl",
            package_root / CARRY_FORWARD_RECEIPT_NAME,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    invocation_started_wall = time.monotonic()
    invocation_started_cpu = time.process_time()
    invocation_started_perf = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--engineering-smoke", action="store_true")
    # Formal N1 execution is fixed-checkpoint evaluation; research training is disabled.
    mode.add_argument("--sample-evaluate", action="store_true")
    mode.add_argument("--shutdown", action="store_true")
    mode.add_argument("--resources", action="store_true")
    parser.add_argument("--package-root", type=Path, default=HERE)
    parser.add_argument("--work-root", type=Path, default=HERE / "execution")
    parser.add_argument("--sample-manifest", type=Path)
    parser.add_argument("--scenario-root", type=Path)
    parser.add_argument("--checkpoint-root", type=Path)
    parser.add_argument("--checkpoint-manifest", type=Path)
    parser.add_argument("--rebuild-input-registry", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_guardian-token", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    package = args.package_root.resolve()
    work = args.work_root.resolve()
    if args.resources:
        print(json.dumps(
            ledger_summary(work / "resource-ledger.jsonl", package / CARRY_FORWARD_RECEIPT_NAME),
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    expected_token = os.environ.get("RELIEF_GRAPH_GUARDIAN_TOKEN")
    is_guarded_child = bool(
        args._guardian_token
        and expected_token
        and hmac.compare_digest(args._guardian_token, expected_token)
    )
    if args._guardian_token and not is_guarded_child:
        print("invalid internal process-guardian token", file=sys.stderr)
        return 2
    if not is_guarded_child and sys.platform == "linux":
        if args.preflight:
            guarded_stage = "admission"
        elif args.engineering_smoke:
            guarded_stage = "engineering_smoke"
        elif args.sample_evaluate:
            guarded_stage = "engineering_smoke"
        else:
            guarded_stage = "shutdown"
        from process_guardian import run_guarded_stage

        raw_argv = list(sys.argv[1:] if argv is None else argv)
        return run_guarded_stage(
            argv=raw_argv,
            driver_path=Path(__file__).resolve(),
            package_root=package,
            work_root=work,
            stage=guarded_stage,
            runtime_environment=REQUIRED_RUNTIME["environment"],
        )
    if args.rebuild_input_registry:
        build_registry(package / "registered_data")
    if args.preflight:
        action = lambda supervisor: _run_preflight(package, work, supervisor)
        stage = "admission"
    elif args.engineering_smoke:
        action = lambda supervisor: _run_engineering_smoke(package, work, supervisor)
        stage = "engineering_smoke"
    elif args.sample_evaluate:
        from n01_fixed_sample_evaluator import run_sample
        action = lambda supervisor: run_sample(
            package,
            args.sample_manifest or package / "n01_sample_manifest.json",
            args.scenario_root or package / "n01_scenarios",
            args.checkpoint_root or package / "fixed_checkpoints",
            args.checkpoint_manifest or package / "n01_fixed_checkpoint_manifest.json",
            work / "sample_diagnostic",
            resource_check=supervisor.check,
        )
        stage = "engineering_smoke"
    else:
        action = lambda supervisor: _settle_shutdown(package, work, supervisor)
        stage = "shutdown"
    global _CURRENT_INVOCATION_SETUP_WALL
    _CURRENT_INVOCATION_SETUP_WALL = time.perf_counter() - invocation_started_perf
    global _CURRENT_INVOCATION_SETUP_CPU
    _CURRENT_INVOCATION_SETUP_CPU = time.process_time() - invocation_started_cpu
    try:
        result = _execute_stage(
            stage,
            package,
            work,
            action,
            invocation_start=(invocation_started_wall, invocation_started_cpu),
        )
    except BaseException as exc:
        print(f"driver stage {stage} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
