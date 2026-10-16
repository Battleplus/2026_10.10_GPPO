"""Bounded, preflight-only systemd measurement for a repaired N02 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


STAGE_PROTOCOL_ID = "n02-integration-smoke-v4-100x100/seven-stage"
MEASUREMENT_SCHEMA = "n02-engineering-cost-measurement/1"
WALL_BUDGET_SECONDS = 270
CPU_BUDGET_SECONDS = 100
CPU_QUOTA_PERCENT = 36
SYSTEMD_SHOW_PROPERTIES = (
    "Id",
    "LoadState",
    "InvocationID",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainStatus",
    "ExecMainStartTimestampMonotonic",
    "ExecMainExitTimestampMonotonic",
    "CPUUsageNSec",
    "Restart",
    "RemainAfterExit",
    "KillMode",
    "CPUAccounting",
    "MemoryAccounting",
    "MemoryMax",
    "TasksMax",
    "CPUQuotaPerSecUSec",
)


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _json_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_modules(package_root: Path):
    package_root = package_root.resolve(strict=True)
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    import driver
    import resource_supervisor

    if resource_supervisor.STAGE_PROTOCOL_ID != STAGE_PROTOCOL_ID:
        raise PermissionError("package stage protocol is not the repaired 100x100 protocol")
    return driver, resource_supervisor


def _require_pending(package_root: Path, resource_supervisor) -> dict[str, Any]:
    prior_path = package_root / resource_supervisor.CARRY_FORWARD_RECEIPT_NAME
    prior = resource_supervisor._read_prior_resource_cost(prior_path, required=True)
    if (
        prior.get("measurement_status") != "pending"
        or prior.get("execution_allowed") is not False
        or prior.get("preflight_allowed") is not True
    ):
        raise PermissionError("engineering measurement requires the current pending-only cost state")
    return prior


def _diagnostics_root(execution_gate) -> Path:
    return Path(execution_gate.DIAGNOSTICS_ROOT).resolve()


def _validate_work_root(work_root: Path, execution_gate) -> Path:
    work_root = work_root.resolve(strict=False)
    expected = execution_gate.diagnostic_path(work_root.name).resolve(strict=False)
    if work_root != expected:
        raise PermissionError("measurement work root must be a direct child of the fixed diagnostics root")
    return work_root


def worker(package_root: Path, work_root: Path, unit_name: str) -> int:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("engineering cost measurement requires the target Linux runtime")
    package_root = package_root.resolve(strict=True)
    work_root = work_root.resolve(strict=True)
    driver, resource_supervisor = _package_modules(package_root)
    import execution_gate
    from process_guardian import run_guarded_pipeline

    _validate_work_root(work_root, execution_gate)
    prior = _require_pending(package_root, resource_supervisor)
    invocation_id = os.environ.get("INVOCATION_ID", "")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", invocation_id):
        raise PermissionError("worker is not running inside a systemd unit with an InvocationID")
    expected_python = Path(driver.TARGET_PYTHON_PATH).resolve(strict=True)
    actual_python = Path(sys.executable).resolve(strict=True)
    if actual_python != expected_python:
        raise PermissionError("worker interpreter differs from the fixed target Python")
    if tuple(resource_supervisor.STAGE_ORDER)[0] != "input_admission":
        raise RuntimeError("the target package has no input_admission bootstrap stage")

    identity = driver._runtime_identity(package_root, work_root)
    context_path = work_root / "measurement-context.json"
    context = {
        "schema": MEASUREMENT_SCHEMA,
        "status": "running",
        "package_release": driver.PACKAGE_RELEASE_ID,
        "stage_protocol": STAGE_PROTOCOL_ID,
        "mode": "controlled_preflight_only",
        "unit_name": unit_name,
        "systemd_invocation_id": invocation_id.lower(),
        "runtime_identity_sha256": identity["runtime_identity_sha256"],
        "pending_status_sha256": prior["status_sha256"],
        "preflight_only": True,
        "measured_stage_scope": ["input_admission"],
        "training_started": False,
        "authorization_created": False,
        "formal_attempt_created": False,
    }
    _json_write(context_path, context)

    code = run_guarded_pipeline(
        argv=[
            "--preflight",
            "--package-root",
            str(package_root),
            "--work-root",
            str(work_root),
        ],
        driver_path=package_root / "driver.py",
        package_root=package_root,
        work_root=work_root,
        runtime_identity_sha256=identity["runtime_identity_sha256"],
        runtime_environment=driver.REQUIRED_RUNTIME["environment"],
        preflight_only=True,
    )
    context["status"] = "completed" if code == 0 else "failed"
    context["run_guarded_pipeline_exit_code"] = int(code)
    _json_write(context_path, context)
    return int(code)


def _show_unit(unit_name: str) -> tuple[str, dict[str, str]]:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit_name,
            *[f"--property={key}" for key in SYSTEMD_SHOW_PROPERTIES],
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"systemctl show failed: {result.stderr.strip()}")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return result.stdout, fields


def _stop_unit(unit_name: str) -> None:
    subprocess.run(
        ["systemctl", "--user", "stop", unit_name],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def launch(
    package_root: Path,
    work_root: Path,
    deployment_receipt: Path,
    unit_name: str,
) -> dict[str, Any]:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("engineering cost measurement launcher requires Linux")
    package_root = package_root.resolve(strict=True)
    deployment_receipt = deployment_receipt.resolve(strict=True)
    work_root = work_root.resolve(strict=False)
    driver, resource_supervisor = _package_modules(package_root)
    import execution_gate

    _validate_work_root(work_root, execution_gate)
    prior = _require_pending(package_root, resource_supervisor)
    deploy = _json_read(deployment_receipt)
    for key in ("source_identity_sha256", "archive_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(deploy.get(key, ""))):
            raise ValueError(f"deployment receipt is missing a valid {key}")
    if work_root.exists():
        raise FileExistsError("measurement work root already exists; preserve it and choose a fresh id")
    if not re.fullmatch(r"[A-Za-z0-9_.@:-]+\.service", unit_name):
        raise ValueError("unit name must be an explicit service name")

    properties, existing = _show_unit(unit_name)
    if existing.get("LoadState") != "not-found":
        raise FileExistsError(f"systemd unit already exists: {unit_name}")

    work_root.mkdir(parents=True, exist_ok=False)
    (work_root / "deployment_receipt.json").write_bytes(deployment_receipt.read_bytes())
    request = {
        "schema": MEASUREMENT_SCHEMA,
        "status": "requested_pending_authorized_engineering_measurement",
        "package_release": driver.PACKAGE_RELEASE_ID,
        "stage_protocol": STAGE_PROTOCOL_ID,
        "work_root": str(work_root),
        "unit_name": unit_name,
        "prior_status_sha256": prior["status_sha256"],
        "deployment_receipt_sha256": _sha256(work_root / "deployment_receipt.json"),
        "measurement_scope": ["input_admission", "same-unit systemd shutdown tail"],
        "training_started": False,
        "authorization_created": False,
        "formal_attempt_created": False,
        "budget_proposal": {
            "wall_seconds": WALL_BUDGET_SECONDS,
            "cpu_seconds": CPU_BUDGET_SECONDS,
            "systemd_runtime_max_seconds": WALL_BUDGET_SECONDS,
            "systemd_timeout_start_seconds": WALL_BUDGET_SECONDS,
            "systemd_cpu_quota_percent": CPU_QUOTA_PERCENT,
            "systemd_cpu_quota_period_seconds": 0.1,
            "rss_bytes": 4 * 1024**3,
        },
        "budget_source": "v5 target-runtime preflight plan; fresh engineering authorization required",
    }
    _json_write(work_root / "measurement-request.json", request)

    script_path = Path(__file__).resolve(strict=True)
    python_path = Path(driver.TARGET_PYTHON_PATH)
    if not python_path.is_file():
        raise FileNotFoundError("fixed target Python path is unavailable")
    command = [
        "systemd-run",
        "--user",
        f"--unit={unit_name}",
        "--service-type=oneshot",
        "--no-block",
        "--property=Restart=no",
        "--property=RemainAfterExit=yes",
        "--property=KillMode=control-group",
        "--property=CPUAccounting=yes",
        "--property=MemoryAccounting=yes",
        "--property=MemoryMax=4G",
        "--property=TasksMax=64",
        f"--property=RuntimeMaxSec={WALL_BUDGET_SECONDS}s",
        f"--property=TimeoutStartSec={WALL_BUDGET_SECONDS}s",
        f"--property=CPUQuota={CPU_QUOTA_PERCENT}%",
        "--property=CPUQuotaPeriodSec=100ms",
        f"--property=WorkingDirectory={package_root}",
    ]
    for key, value in sorted(driver.REQUIRED_RUNTIME["environment"].items()):
        command.append(f"--setenv={key}={value}")
    command.extend(
        [
            "--setenv=PYTHONUNBUFFERED=1",
            "--quiet",
            "--",
            str(python_path),
            "-B",
            str(script_path),
            "--worker",
            "--package-root",
            str(package_root),
            "--work-root",
            str(work_root),
            "--unit-name",
            unit_name,
        ]
    )
    submitted_at = time.monotonic()
    submit = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if submit.returncode != 0:
        result = {
            "schema": MEASUREMENT_SCHEMA,
            "status": "systemd_submission_failed",
            "unit_name": unit_name,
            "stdout": submit.stdout,
            "stderr": submit.stderr,
            "systemd_submission_attempted": True,
            "formal_attempt_created": False,
            "training_started": False,
        }
        _json_write(work_root / "systemd-terminal.json", result)
        return result

    deadline = time.monotonic() + WALL_BUDGET_SECONDS + 30
    invocation_id = ""
    budget_exceeded = False
    terminal_text = ""
    terminal_fields: dict[str, str] = {}
    while time.monotonic() < deadline:
        terminal_text, terminal_fields = _show_unit(unit_name)
        invocation_id = terminal_fields.get("InvocationID", "")
        active_state = terminal_fields.get("ActiveState")
        active = active_state in {"active", "activating"}
        retained_terminal = (
            terminal_fields.get("ActiveState") == "active"
            and terminal_fields.get("SubState") == "exited"
        )
        terminal = terminal_fields.get("LoadState") == "loaded" and (
            terminal_fields.get("ActiveState") in {"inactive", "failed"}
            or retained_terminal
        )
        if terminal:
            break
        start_us = int(terminal_fields.get("ExecMainStartTimestampMonotonic", "0") or 0)
        cpu_ns = int(terminal_fields.get("CPUUsageNSec", "0") or 0)
        now_us = time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 1000
        elapsed_wall_us = (
            now_us - start_us
            if start_us
            else int((time.monotonic() - submitted_at) * 1_000_000)
        )
        if active and (
            cpu_ns >= CPU_BUDGET_SECONDS * 1_000_000_000
            or elapsed_wall_us >= WALL_BUDGET_SECONDS * 1_000_000
        ):
            budget_exceeded = True
            _stop_unit(unit_name)
        if not invocation_id:
            time.sleep(0.5)
            continue
        time.sleep(1.0)
    else:
        budget_exceeded = True
        _stop_unit(unit_name)
        terminal_text, terminal_fields = _show_unit(unit_name)

    (work_root / "systemd-show.txt").write_text(terminal_text, encoding="utf-8")
    start_us = int(terminal_fields.get("ExecMainStartTimestampMonotonic", "0") or 0)
    exit_us = int(terminal_fields.get("ExecMainExitTimestampMonotonic", "0") or 0)
    cpu_ns = int(terminal_fields.get("CPUUsageNSec", "0") or 0)
    measured_wall = max(0.0, (exit_us - start_us) / 1_000_000) if exit_us >= start_us else None
    measured_cpu = cpu_ns / 1_000_000_000
    within_budget = (
        measured_wall is not None
        and measured_wall <= WALL_BUDGET_SECONDS
        and measured_cpu <= CPU_BUDGET_SECONDS
    )
    if not within_budget:
        budget_exceeded = True
    invocation_id = terminal_fields.get("InvocationID", "")
    succeeded = (
        not budget_exceeded
        and terminal_fields.get("Result") == "success"
        and terminal_fields.get("ExecMainStatus") == "0"
        and terminal_fields.get("ActiveState") == "active"
        and terminal_fields.get("SubState") == "exited"
        and terminal_fields.get("RemainAfterExit") == "yes"
        and terminal_fields.get("Id") == unit_name
        and bool(invocation_id)
    )
    result = {
        "schema": MEASUREMENT_SCHEMA,
        "status": "completed" if succeeded else ("budget_exceeded" if budget_exceeded else "failed"),
        "unit_name": unit_name,
        "systemd_invocation_id": invocation_id,
        "systemd_properties": terminal_fields,
        "systemd_wall_seconds": measured_wall,
        "systemd_cpu_seconds": measured_cpu,
        "budget_proposal": request["budget_proposal"],
        "measurement_scope": request["measurement_scope"],
        "stage_protocol": STAGE_PROTOCOL_ID,
        "formal_attempt_created": False,
        "training_started": False,
    }
    _json_write(work_root / "systemd-terminal.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--worker", action="store_true")
    mode.add_argument("--launch", action="store_true")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("--deployment-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            return worker(args.package_root, args.work_root, args.unit_name)
        if args.deployment_receipt is None:
            raise ValueError("--launch requires the deployment receipt for the measured package archive")
        result = launch(args.package_root, args.work_root, args.deployment_receipt, args.unit_name)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "completed" else 1
    except Exception as exc:
        print(json.dumps({"status": "blocked_or_failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
