"""Attach transient systemd service status and cgroup counters to a run receipt."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_linux_engineering import _artifact_rows, _sha256_file, _write_json


PROPERTIES = (
    "LoadState",
    "InvocationID",
    "ControlGroup",
    "ExecMainPID",
    "MainPID",
    "RemainAfterExit",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "CPUUsageNSec",
    "MemoryPeak",
    "MemoryMax",
    "TasksCurrent",
    "Restart",
    "KillMode",
    "CPUAffinity",
    "CPUQuotaPerSecUSec",
    "RuntimeMaxUSec",
)


def _parse_properties(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _valid_counter(value: str | None) -> int | None:
    if not value or not value.isdigit():
        return None
    number = int(value)
    return number if number < (2**64 - 1) else None


def _finalize(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "run-receipt.json"
    if receipt_path.is_file():
        receipt: dict[str, Any] = json.loads(receipt_path.read_text(encoding="utf-8"))
    else:
        receipt = {
            "schema_version": 1,
            "run_id": args.run_id,
            "run_kind": "linux_engineering_compatibility_not_study",
            "status": "technical_stop",
            "first_error": None,
            "stages": [],
            "formal_training": False,
            "heldout_confirmation": False,
            "six_path_study_training": False,
            "resource": {
                "scope": "systemd service launch failed before the runner produced a receipt",
                "automatic_retries": 0,
            },
        }
        receipt["first_error"] = {
            "stage": "systemd-launch",
            "type": "ServiceDidNotProduceReceipt",
            "message": f"service exit code {args.service_exit_code}; inspect systemd-run.log",
        }

    command = [
        "systemctl",
        "--user",
        "show",
        "--no-pager",
        f"--property={','.join(PROPERTIES)}",
        args.unit,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    status_path = output_dir / "systemd-status.txt"
    status_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    values = _parse_properties(result.stdout)
    service = {
        "unit": args.unit,
        "query_argv": command,
        "query_return_code": result.returncode,
        "service_exit_code_from_systemd_run": args.service_exit_code,
        "properties": values,
        "status_path": status_path.name,
        "status_sha256": _sha256_file(status_path),
    }
    receipt["systemd"] = service
    resource_row = receipt.setdefault("resource", {})
    cpu_ns = values.get("CPUUsageNSec")
    memory_peak = values.get("MemoryPeak")
    resource_row["systemd_cgroup_cpu_usage_seconds"] = (
        _valid_counter(cpu_ns) / 1_000_000_000 if _valid_counter(cpu_ns) is not None else None
    )
    resource_row["systemd_cgroup_memory_peak_bytes"] = (
        _valid_counter(memory_peak)
    )
    resource_row["systemd_cgroup_memory_max_bytes"] = (
        _valid_counter(values.get("MemoryMax"))
    )
    resource_row["systemd_cgroup_tasks_current_at_collection"] = (
        _valid_counter(values.get("TasksCurrent"))
    )
    resource_row["scope"] = (
        "runner and child commands inside the transient systemd service; excludes SSH, code deployment, and environment installation"
    )

    required = {
        "systemd query": result.returncode == 0,
        "retained loaded unit": values.get("LoadState") == "loaded",
        "invocation present": bool(values.get("InvocationID")),
        "main process exited": values.get("MainPID") == "0" and values.get("SubState") == "exited",
        "retained after exit": values.get("RemainAfterExit") == "yes",
        "source identity": receipt.get("source_identity_declared") == args.source_identity,
        "service exit": args.service_exit_code == 0,
        "service result": values.get("Result") == "success",
        "restart disabled": values.get("Restart") == "no",
        "kill mode": values.get("KillMode") == "control-group",
        "CPU affinity": values.get("CPUAffinity", "").strip() == "0",
        "one-core quota": values.get("CPUQuotaPerSecUSec") in {"1s", "1000000"},
        "runtime limit": values.get("RuntimeMaxUSec") in {"10min", "600000000"},
        "memory limit": resource_row["systemd_cgroup_memory_max_bytes"] == 4 * 1024**3,
        "CPU counter": resource_row["systemd_cgroup_cpu_usage_seconds"] is not None,
    }
    service["acceptance_checks"] = required
    service["bounded_service_checks_pass"] = all(required.values())
    service["accounting_status"] = "bounded_service_counters_only"
    service["full_system_accounting"] = False
    service["limitations"] = ["SSH, installation, deployment and finalizer are outside service counters",
                              "MemoryPeak may be unavailable on systemd 249; sampled RSS and single-child max RSS are separate"]
    if receipt.get("status") != "pass" or not all(required.values()):
        receipt["status"] = "technical_stop"
        if receipt.get("first_error") is None:
            failed = [name for name, passed in required.items() if not passed]
            receipt["first_error"] = {
                "stage": "systemd-accounting",
                "type": "SystemdAcceptanceFailure",
                "message": "systemd service/accounting checks failed: " + ", ".join(failed),
            }
    receipt["systemd_finalized_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat(timespec="seconds")

    cleanup = subprocess.run(["systemctl", "--user", "stop", args.unit], capture_output=True, text=True, check=False)
    service["cleanup_stop_exit_code"] = cleanup.returncode
    _write_json(output_dir / "unit-cleanup.json", {"command": ["systemctl", "--user", "stop", args.unit], "exit_code": cleanup.returncode, "stdout": cleanup.stdout, "stderr": cleanup.stderr})
    if cleanup.returncode != 0:
        receipt["status"] = "technical_stop"
        if receipt.get("first_error") is None:
            receipt["first_error"] = {"stage": "unit-cleanup", "type": "CleanupFailed", "message": cleanup.stderr}
    rows = _artifact_rows(output_dir)
    receipt["artifact_hashes"] = rows
    receipt["artifact_index"] = "artifact-hashes.json"
    _write_json(receipt_path, receipt)
    index = {
        "algorithm": "sha256",
        "artifacts": rows,
        "run_receipt_sha256": _sha256_file(receipt_path),
    }
    _write_json(output_dir / "artifact-hashes.json", index)
    print(json.dumps({"status": receipt["status"], "systemd": service, "resource": resource_row}, indent=2))
    return 0 if receipt["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--service-exit-code", type=int, required=True)
    parser.add_argument("--source-identity", required=True)
    return _finalize(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
