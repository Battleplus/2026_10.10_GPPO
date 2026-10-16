"""Build a v5 /2 carry-forward receipt from completed, hash-bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any


STAGE_PROTOCOL_ID = "n02-integration-smoke-v4-100x100/seven-stage"
RESOURCE_COST_SCHEMA = "resource-cost-carry-forward/2"
REQUIRED_EVIDENCE = (
    "resource-ledger.jsonl",
    "systemd-show.txt",
    "deployment_receipt.json",
    "measurement-context.json",
    "systemd-terminal.json",
    "receipts/01-input_admission.json",
    "guardians/01-input_admission.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _systemd_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"deployment receipt has no valid {name}")
    return value


def build(package_root: Path, measurement_root: Path, run_id: str) -> dict[str, Any]:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", run_id) is None:
        raise ValueError("run id must be a simple path component")
    package_root = package_root.resolve(strict=True)
    measurement_root = measurement_root.resolve(strict=True)
    if not package_root.is_dir() or not measurement_root.is_dir():
        raise NotADirectoryError("package root and completed measurement root must be directories")
    if package_root == measurement_root or package_root in measurement_root.parents:
        raise ValueError("measurement input must remain outside the candidate package")

    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    import resource_supervisor

    if resource_supervisor.STAGE_PROTOCOL_ID != STAGE_PROTOCOL_ID:
        raise PermissionError("candidate package does not use the repaired 100x100 stage protocol")
    prior_path = package_root / resource_supervisor.CARRY_FORWARD_RECEIPT_NAME
    pending = resource_supervisor._read_prior_resource_cost(prior_path, required=True)
    if pending.get("measurement_status") != "pending" or pending.get("execution_allowed") is not False:
        raise PermissionError("receipt builder only replaces a validated pending status")

    for relative in REQUIRED_EVIDENCE:
        source = measurement_root / relative
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(f"completed measurement evidence is missing or unsafe: {relative}")

    context = _json_read(measurement_root / "measurement-context.json")
    terminal = _json_read(measurement_root / "systemd-terminal.json")
    deployment = _json_read(measurement_root / "deployment_receipt.json")
    driver_stage = _json_read(measurement_root / "receipts" / "01-input_admission.json")
    guardian = _json_read(measurement_root / "guardians" / "01-input_admission.json")
    show = _systemd_values(measurement_root / "systemd-show.txt")

    invocation_id = show.get("InvocationID", "")
    if (
        terminal.get("schema") != "n02-engineering-cost-measurement/1"
        or terminal.get("status") != "completed"
        or terminal.get("systemd_invocation_id") != invocation_id
        or context.get("schema") != "n02-engineering-cost-measurement/1"
        or context.get("status") != "completed"
        or context.get("systemd_invocation_id") != invocation_id.lower()
        or context.get("preflight_only") is not True
        or context.get("measured_stage_scope") != ["input_admission"]
        or context.get("stage_protocol") != STAGE_PROTOCOL_ID
        or context.get("training_started") is not False
        or context.get("authorization_created") is not False
        or context.get("formal_attempt_created") is not False
        or terminal.get("formal_attempt_created") is not False
        or terminal.get("training_started") is not False
    ):
        raise PermissionError("measurement context does not prove a completed preflight-only systemd run")
    if (
        show.get("LoadState") != "loaded"
        or show.get("ActiveState") != "inactive"
        or show.get("SubState") != "dead"
        or show.get("Result") != "success"
        or show.get("ExecMainStatus") != "0"
        or show.get("Restart") != "no"
        or show.get("KillMode") != "control-group"
        or show.get("CPUAccounting") != "yes"
        or show.get("MemoryAccounting") != "yes"
        or show.get("MemoryMax") != str(4 * 1024**3)
        or show.get("TasksMax") != "64"
        or show.get("CPUQuotaPerSecUSec") != "360ms"
        or not re.fullmatch(r"[0-9a-fA-F]{32}", invocation_id)
    ):
        raise PermissionError("terminal systemd properties do not match the engineering measurement contract")
    try:
        systemd_wall = (
            int(show["ExecMainExitTimestampMonotonic"])
            - int(show["ExecMainStartTimestampMonotonic"])
        ) / 1_000_000
        systemd_cpu = int(show["CPUUsageNSec"]) / 1_000_000_000
    except (KeyError, ValueError) as exc:
        raise ValueError("terminal systemd time or CPU accounting fields are invalid") from exc
    if systemd_wall < 0 or systemd_wall > 270 or systemd_cpu < 0 or systemd_cpu > 100:
        raise ValueError("measured systemd totals exceed the proposed 270s wall / 100s CPU budget")

    rows = resource_supervisor._read_ledger(measurement_root / "resource-ledger.jsonl")
    if len(rows) != 1:
        raise ValueError("preflight-only bootstrap must produce exactly one real ledger row")
    row = rows[0]
    if (
        row.get("stage_protocol") != STAGE_PROTOCOL_ID
        or row.get("stage") != "input_admission"
        or row.get("status") != "accepted"
        or row.get("first_error") is not None
        or row.get("runtime_identity_sha256") != context.get("runtime_identity_sha256")
    ):
        raise PermissionError("resource ledger does not contain one accepted input_admission measurement")
    if (
        driver_stage.get("stage_protocol") != STAGE_PROTOCOL_ID
        or driver_stage.get("stage") != "input_admission"
        or driver_stage.get("status") != "accepted"
        or driver_stage.get("first_error") is not None
        or driver_stage.get("resource_entry") != row
        or not isinstance(driver_stage.get("result"), dict)
        or driver_stage["result"].get("schema") != "runtime-admission/2"
        or driver_stage["result"].get("status") != "accepted"
        or driver_stage["result"].get("target_runtime_acceptance") is not True
        or guardian.get("stage_protocol") != STAGE_PROTOCOL_ID
        or guardian.get("stage") != "input_admission"
        or guardian.get("status") != "complete"
        or guardian.get("child_returncode") != 0
        or guardian.get("first_error") is not None
        or guardian.get("resource_entry") != row
    ):
        raise PermissionError("worker and guardian receipts do not match the measured ledger row")

    source_identity_sha256 = _require_sha(deployment.get("source_identity_sha256"), "source_identity_sha256")
    archive_sha256 = _require_sha(deployment.get("archive_sha256"), "archive_sha256")
    ledger_stage_costs: dict[str, dict[str, float]] = {
        "input_admission": {
            "wall_seconds": float(row["wall_seconds"]),
            "cpu_seconds": float(row["cpu_seconds"]),
        }
    }
    ledger_wall = ledger_stage_costs["input_admission"]["wall_seconds"]
    ledger_cpu = ledger_stage_costs["input_admission"]["cpu_seconds"]
    wall_overhead = systemd_wall - ledger_wall
    cpu_overhead = systemd_cpu - ledger_cpu
    if wall_overhead < -1e-9 or cpu_overhead < -1e-9:
        raise ValueError("same-unit systemd totals are below the guardian ledger totals")
    stage_costs = {
        "input_admission": {
            "wall_seconds": ledger_wall + max(0.0, wall_overhead),
            "cpu_seconds": ledger_cpu + max(0.0, cpu_overhead),
        }
    }

    evidence_root = package_root / "resource_cost_evidence" / run_id
    if evidence_root.exists():
        raise FileExistsError("evidence destination already exists; preserve it and use a fresh run id")
    evidence_root.mkdir(parents=True, exist_ok=False)
    relative_paths = {}
    evidence_files = []
    for relative in REQUIRED_EVIDENCE:
        source = measurement_root / relative
        destination = evidence_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        digest = _sha256(destination)
        if digest != _sha256(source):
            raise IOError(f"evidence copy hash mismatch: {relative}")
        package_relative = destination.relative_to(package_root).as_posix()
        relative_paths[relative] = package_relative
        evidence_files.append({"path": package_relative, "sha256": digest})

    receipt = {
        "schema": RESOURCE_COST_SCHEMA,
        "status": "measured_single_stage_bootstrap",
        "stage_protocol": STAGE_PROTOCOL_ID,
        "stage_coverage": ["input_admission"],
        "measurement_scope": "target-runtime input_admission plus same-unit systemd process shutdown tail",
        "source_identity_sha256": source_identity_sha256,
        "deployed_package_archive_sha256": archive_sha256,
        "systemd_invocation_id": invocation_id,
        "systemd_total_wall_seconds": systemd_wall,
        "systemd_total_cpu_seconds": systemd_cpu,
        "ledger_stage_costs": ledger_stage_costs,
        "systemd_wrapper_overhead_assigned_to_input_admission": {
            "wall_seconds": max(0.0, wall_overhead),
            "cpu_seconds": max(0.0, cpu_overhead),
        },
        "stage_costs": stage_costs,
        "total_wall_seconds": stage_costs["input_admission"]["wall_seconds"],
        "total_cpu_seconds": stage_costs["input_admission"]["cpu_seconds"],
        "evidence_roles": {
            "resource_ledger": relative_paths["resource-ledger.jsonl"],
            "systemd_show": relative_paths["systemd-show.txt"],
            "deployment_receipt": relative_paths["deployment_receipt.json"],
            "measurement_context": relative_paths["measurement-context.json"],
            "systemd_terminal": relative_paths["systemd-terminal.json"],
            "driver_stage_receipt": relative_paths["receipts/01-input_admission.json"],
            "outer_guardian_receipt": relative_paths["guardians/01-input_admission.json"],
        },
        "evidence_files": evidence_files,
        "hash_scope_note": (
            "Source identity and archive SHA-256 refer to the separately deployed measurement package. "
            "The final release hashes this receipt and copied evidence afterward; its full manifest is not embedded here."
        ),
    }
    temporary = prior_path.with_name(prior_path.name + ".candidate.tmp")
    if temporary.exists():
        raise FileExistsError("receipt temp path already exists; preserve it")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, prior_path)
    validated = resource_supervisor._read_prior_resource_cost(prior_path, required=True)
    if not validated.get("execution_allowed") or validated.get("measurement_status") != "measured":
        raise PermissionError("v5 validator did not accept the generated measured receipt")
    return {
        "status": "receipt_validated",
        "receipt_sha256": validated["receipt_sha256"],
        "measurement_status": validated["measurement_status"],
        "measured_stage_coverage": ["input_admission"],
        "systemd_wall_seconds": systemd_wall,
        "systemd_cpu_seconds": systemd_cpu,
        "total_wall_seconds": validated["total_wall_seconds"],
        "total_cpu_seconds": validated["total_cpu_seconds"],
        "note": "This receipt does not claim seven-stage measurement coverage.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--measurement-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = build(args.package_root, args.measurement_root, args.run_id)
    except Exception as exc:
        print(json.dumps({"status": "receipt_rejected", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
