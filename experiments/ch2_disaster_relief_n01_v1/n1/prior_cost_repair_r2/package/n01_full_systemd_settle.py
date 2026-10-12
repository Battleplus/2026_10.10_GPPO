"""Persist final systemd invocation and cgroup evidence for one N01 unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SHOW_PROPERTIES = (
    "Id", "Names", "LoadState", "ActiveState", "SubState", "Result",
    "ExecMainCode", "ExecMainStatus", "ExecMainStartTimestampMonotonic",
    "ExecMainExitTimestampMonotonic", "InvocationID", "CPUUsageNSec",
    "MemoryPeak", "MemoryCurrent", "MemoryMax", "MemoryAccounting",
        "CPUAccounting", "CPUAffinity", "CPUQuotaPerSecUSec", "RuntimeMaxUSec",
    "TimeoutStopUSec", "Type", "KillMode", "ControlGroup", "FragmentPath",
)
CGROUP_FILES = (
    "cpu.stat", "cpu.max", "memory.peak", "memory.current", "memory.max",
    "memory.events", "cpuset.cpus.effective",
)
CONTRACTS = {
    "evaluation": {
        "Type": "exec", "KillMode": "control-group", "MemoryAccounting": "yes",
        "MemoryMax": "4294967296", "CPUAccounting": "yes", "CPUAffinity": "0",
        "RuntimeMaxUSec": "1h 38min 20s",
        "TimeoutStopUSec": "40s", "memory.max": "4294967296",
    },
    "probe": {
        "Type": "exec", "KillMode": "control-group", "MemoryAccounting": "yes",
        "MemoryMax": "268435456", "CPUAccounting": "yes", "CPUAffinity": "0",
        "RuntimeMaxUSec": "20s",
        "TimeoutStopUSec": "15s", "memory.max": "268435456",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    return result.returncode, result.stdout


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit-name", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--evaluation-identity", required=True)
    parser.add_argument("--contract-profile", choices=tuple(CONTRACTS), required=True)
    args = parser.parse_args()

    show_code, show_text = _run([
        "systemctl", "--user", "show", args.unit_name,
        *[f"--property={name}" for name in SHOW_PROPERTIES],
    ])
    properties = {
        key: value
        for line in show_text.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    cat_code, effective_config = _run(["systemctl", "--user", "cat", args.unit_name, "--no-pager"])
    control_group = properties.get("ControlGroup", "")
    cgroup_path = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    cgroup_values = {}
    if cgroup_path.is_dir():
        for name in CGROUP_FILES:
            path = cgroup_path / name
            if path.is_file():
                try:
                    cgroup_values[name] = path.read_text(encoding="ascii").strip()
                except OSError as exc:
                    cgroup_values[name] = f"unavailable: {type(exc).__name__}: {exc}"
    expected_contract = CONTRACTS[args.contract_profile]
    contract_mismatches = [
        f"{name}: expected {expected!r}, observed {properties.get(name)!r}"
        for name, expected in expected_contract.items()
        if name != "memory.max" and properties.get(name) != expected
    ]
    expected_memory_max = expected_contract["memory.max"]
    if cgroup_values.get("memory.max") != expected_memory_max:
        contract_mismatches.append(
            f"cgroup memory.max: expected {expected_memory_max!r}, observed {cgroup_values.get('memory.max')!r}"
        )
    if "usage_usec" not in cgroup_values.get("cpu.stat", ""):
        contract_mismatches.append("cgroup cpu.stat usage_usec is missing")
    if not properties.get("ControlGroup") or not cgroup_path.is_dir():
        contract_mismatches.append("systemd ControlGroup or live cgroup directory is missing")
    contract_status = "complete" if not contract_mismatches else "failed"
    fragment = Path(properties.get("FragmentPath", ""))
    identity_path = args.package_root / "N01_FULL_EVALUATION_IDENTITY.json"
    ledger = args.work_root / "resource-ledger.jsonl"
    receipt = {
        "schema": "n01-systemd-settlement/1",
        "evaluation_identity": args.evaluation_identity,
        "contract_profile": args.contract_profile,
        "contract_status": contract_status,
        "contract_mismatches": contract_mismatches,
        "kernel_cpu_quota_status": "enforced-readback" if cgroup_values.get("cpu.max", "").split()[:1] not in ([], ["max"]) else "unavailable",
        "kernel_cpu_quota_readback": cgroup_values.get("cpu.max"),
        "identity_manifest_sha256": _sha256(identity_path) if identity_path.is_file() else None,
        "unit_name": args.unit_name,
        "invocation_id": properties.get("InvocationID") or os.environ.get("INVOCATION_ID"),
        "service_result": os.environ.get("SERVICE_RESULT"),
        "exit_code": os.environ.get("EXIT_CODE"),
        "exit_status": os.environ.get("EXIT_STATUS"),
        "settlement_status": "complete" if (
            properties.get("Result") == "success"
            and properties.get("ExecMainCode") == "1"
            and properties.get("ExecMainStatus") == "0"
            and os.environ.get("SERVICE_RESULT", "success") == "success"
            and os.environ.get("EXIT_STATUS", "0") == "0"
            and bool(properties.get("InvocationID") or os.environ.get("INVOCATION_ID"))
            and properties.get("CPUUsageNSec", "").isdigit()
            and "usage_usec" in cgroup_values.get("cpu.stat", "")
            and contract_status == "complete"
        ) else "failed",
        "settled_at_utc": datetime.now(timezone.utc).isoformat(),
        "systemctl_show_returncode": show_code,
        "systemd_properties": properties,
        "systemd_show_raw": show_text,
        "effective_unit_config_returncode": cat_code,
        "effective_unit_config": effective_config,
        "effective_unit_config_sha256": hashlib.sha256(effective_config.encode("utf-8")).hexdigest() if cat_code == 0 else None,
        "unit_fragment_sha256": _sha256(fragment) if fragment.is_file() else None,
        "cgroup_path": str(cgroup_path),
        "cgroup_snapshot": cgroup_values,
        "resource_ledger_sha256": _sha256(ledger) if ledger.is_file() else None,
        "resource_receipts": sorted(path.relative_to(args.work_root).as_posix() for path in args.work_root.glob("receipts/*.json")) if args.work_root.is_dir() else [],
        "guardian_receipts": sorted(path.relative_to(args.work_root).as_posix() for path in args.work_root.glob("guardians/*.json")) if args.work_root.is_dir() else [],
        "settlement_evidence_limit": "cgroup values are sampled during ExecStopPost; systemd properties and invocation ID are persisted for post-exit audit; no kernel CPU quota is claimed when cpu.max is absent; stage guardians enforce cumulative limits from cgroup cpu.stat with early-stop reserves and sampled termination overshoot",
        "settlement_wait_monotonic": time.monotonic(),
    }
    _write_json(args.work_root / "systemd-settlement.json", receipt)
    return 0 if receipt["settlement_status"] == "complete" and show_code == 0 and cat_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
