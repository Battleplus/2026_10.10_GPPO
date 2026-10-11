"""Linux parent-process guard for one complete driver stage invocation."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from resource_supervisor import (
    DISK_LIMIT_BYTES,
    RSS_LIMIT_BYTES,
    STAGE_LIMITS,
    TOTAL_CPU_LIMIT,
    TOTAL_WALL_LIMIT,
    _disk_bytes,
    CARRY_FORWARD_RECEIPT_NAME,
    _read_prior_resource_cost,
    _read_ledger,
)


POLL_SECONDS = 0.25
REAP_RACE_CONFIRM_ATTEMPTS = 10
REAP_RACE_CONFIRM_INTERVAL_SECONDS = 0.005


class _ProcRSSMissing(RuntimeError):
    def __init__(self, pid: int, state: str | None, cpu_seconds: float):
        super().__init__(f"RSS fields missing for pid {pid}")
        self.pid = pid
        self.state = state
        self.cpu_seconds = cpu_seconds


class _ProcZombie(_ProcRSSMissing):
    def __init__(self, pid: int, state: str | None, cpu_seconds: float):
        super().__init__(pid, state, cpu_seconds)


def _confirm_child_reaped(child_pid: int) -> tuple[int, int, Any]:
    for attempt in range(REAP_RACE_CONFIRM_ATTEMPTS + 1):
        result = os.wait4(child_pid, os.WNOHANG)
        if result[0] == child_pid:
            return result
        if attempt < REAP_RACE_CONFIRM_ATTEMPTS:
            time.sleep(REAP_RACE_CONFIRM_INTERVAL_SECONDS)
    return 0, 0, None


def _json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _proc_metrics(pid: int) -> dict[str, int]:
    status_path = Path(f"/proc/{pid}/status")
    stat_path = Path(f"/proc/{pid}/stat")
    values: dict[str, int] = {}
    state = None
    for line in status_path.read_text(encoding="ascii").splitlines():
        if line.startswith("State:"):
            state = line.split()[1]
        elif line.startswith("VmRSS:"):
            values["rss_bytes"] = int(line.split()[1]) * 1024
        elif line.startswith("VmHWM:"):
            values["rss_hwm_bytes"] = int(line.split()[1]) * 1024
    stat = stat_path.read_text(encoding="ascii")
    fields = stat[stat.rfind(")") + 2 :].split()
    stat_state = fields[0] if fields else None
    ticks_per_second = os.sysconf("SC_CLK_TCK")
    cpu_seconds = (int(fields[11]) + int(fields[12])) / ticks_per_second
    values["cpu_seconds"] = cpu_seconds
    if "rss_bytes" not in values or "rss_hwm_bytes" not in values:
        sampled_state = state or stat_state
        if state in {"Z", "X"} or stat_state in {"Z", "X"}:
            raise _ProcZombie(pid, sampled_state, cpu_seconds)
        raise _ProcRSSMissing(pid, sampled_state, cpu_seconds)
    return values


def _process_started_at() -> tuple[float, float]:
    """Use proc start ticks so Python import and CLI setup are inside the wall bound."""
    uptime = float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
    stat = Path("/proc/self/stat").read_text(encoding="ascii")
    fields = stat[stat.rfind(")") + 2 :].split()
    ticks_per_second = os.sysconf("SC_CLK_TCK")
    elapsed_wall = uptime - int(fields[19]) / ticks_per_second
    started_wall = time.monotonic() - elapsed_wall
    started_cpu = max(0.0, time.process_time() - (int(fields[11]) + int(fields[12])) / ticks_per_second)
    return started_wall, started_cpu


def _rewrite_last_row(ledger_path: Path, row: dict[str, Any], *, replace_last: bool) -> None:
    rows = _read_ledger_tolerating_partial_tail(ledger_path)
    if replace_last and rows:
        rows[-1] = row
    else:
        rows.append(row)
    temporary = ledger_path.with_suffix(ledger_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, ledger_path)


def _read_ledger_tolerating_partial_tail(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.is_file():
        return []
    rows = []
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                break
            raise
        if row.get("schema") != "resource-ledger-entry/1":
            raise ValueError(f"unsupported resource ledger row {index + 1}")
        rows.append(row)
    return rows


def _checkpoint_inventory(work_root: Path) -> list[dict[str, Any]]:
    import hashlib

    checkpoints = []
    for path in sorted(work_root.rglob("*.pt")):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        checkpoints.append({
            "path": path.relative_to(work_root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return checkpoints


def _stage_receipt(work_root: Path, stage: str, ledger_rows: list[dict]) -> Path:
    count = len(ledger_rows) + 1
    return work_root / "receipts" / f"{count:02d}-{stage}.json"


def _update_stage_receipt(
    receipt_path: Path,
    row: dict[str, Any],
    *,
    error: str | None,
    checkpoints: list[dict[str, Any]],
    guardian_path: Path,
) -> None:
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    else:
        receipt = {
            "schema": "driver-stage-receipt/1",
            "stage": row["stage"],
            "result": None,
            "partial_checkpoints": checkpoints,
        }
    receipt["resource_entry"] = row
    receipt["outer_guardian_receipt"] = guardian_path.as_posix()
    if error is not None:
        receipt["status"] = "failed"
        receipt["first_error"] = row.get("first_error") or error
        receipt["partial_checkpoints"] = checkpoints
    _json_write(receipt_path, receipt)


def run_guarded_stage(
    *,
    argv: list[str],
    driver_path: Path,
    package_root: Path,
    work_root: Path,
    stage: str,
    runtime_environment: dict[str, str],
) -> int:
    if sys.platform != "linux":
        raise RuntimeError("full-process resource guarding requires the accepted Linux target runtime")
    if stage not in STAGE_LIMITS:
        raise ValueError(f"unknown guarded stage: {stage}")

    ledger_path = work_root / "resource-ledger.jsonl"
    work_root.mkdir(parents=True, exist_ok=True)
    previous_rows = _read_ledger(ledger_path)
    prior_cost = _read_prior_resource_cost(package_root / CARRY_FORWARD_RECEIPT_NAME, required=True)
    carried_stage = prior_cost["stage_costs"].get(stage, {})
    previous_stage_wall = float(carried_stage.get("wall_seconds", 0.0)) + sum(row["wall_seconds"] for row in previous_rows if row["stage"] == stage)
    previous_stage_cpu = float(carried_stage.get("cpu_seconds", 0.0)) + sum(row["cpu_seconds"] for row in previous_rows if row["stage"] == stage)
    previous_total_wall = prior_cost["total_wall_seconds"] + sum(row["wall_seconds"] for row in previous_rows)
    previous_total_cpu = prior_cost["total_cpu_seconds"] + sum(row["cpu_seconds"] for row in previous_rows)
    stage_wall_limit, stage_cpu_limit = STAGE_LIMITS[stage]
    started_wall, started_cpu = _process_started_at()
    guardian_cpu_start = started_cpu
    current_disk = _disk_bytes((package_root, work_root))
    peak_disk = current_disk
    peak_group_rss = _proc_metrics(os.getpid())["rss_hwm_bytes"]
    first_error: str | None = None
    outer_error: str | None = None
    kill_reason: str | None = None
    outer_error_at: float | None = None
    status_code = 1
    child_rusage = None
    child_status = 0
    child_metrics: dict[str, int] = {"cpu_seconds": 0, "rss_bytes": 0, "rss_hwm_bytes": 0}
    last_disk_sample = time.monotonic()
    guardian_path = work_root / "guardians" / f"{len(previous_rows) + 1:02d}-{stage}.json"
    token = uuid.uuid4().hex
    env = os.environ.copy()
    env.update(runtime_environment)
    env["RELIEF_GRAPH_GUARDIAN_TOKEN"] = token
    child_argv = [*argv, "--_guardian-token", token]
    command = [sys.executable, str(driver_path), *child_argv]

    try:
        if hasattr(os, "sched_setaffinity"):
            try:
                os.sched_setaffinity(0, {0})
            except OSError:
                pass
        process = subprocess.Popen(command, cwd=str(package_root), env=env, close_fds=True)
        child_pid = process.pid
        while True:
            waited_pid, child_status, child_rusage = os.wait4(child_pid, os.WNOHANG)
            if waited_pid == child_pid:
                process.returncode = os.waitstatus_to_exitcode(child_status)
                status_code = int(process.returncode)
                break
            now = time.monotonic()
            elapsed_wall = now - started_wall
            try:
                child_metrics = _proc_metrics(child_pid)
            except _ProcRSSMissing as exc:
                # A missing RSS sample is accepted only after wait4 confirms and accounts for exit.
                waited_pid, child_status, child_rusage = _confirm_child_reaped(child_pid)
                if waited_pid == child_pid:
                    process.returncode = os.waitstatus_to_exitcode(child_status)
                    status_code = int(process.returncode)
                    break
                raise RuntimeError(f"{exc}; wait4 did not confirm child exit (state={exc.state!r})") from exc
            except FileNotFoundError as exc:
                waited_pid, child_status, child_rusage = _confirm_child_reaped(child_pid)
                if waited_pid == child_pid:
                    process.returncode = os.waitstatus_to_exitcode(child_status)
                    status_code = int(process.returncode)
                    break
                raise RuntimeError(f"/proc metrics disappeared while child {child_pid} remained live") from exc
            guardian_metrics = _proc_metrics(os.getpid())
            group_rss = child_metrics["rss_bytes"] + guardian_metrics["rss_bytes"]
            peak_group_rss = max(peak_group_rss, group_rss)
            child_cpu = child_metrics["cpu_seconds"]
            elapsed_cpu = child_cpu + max(0.0, time.process_time() - guardian_cpu_start)
            if now - last_disk_sample >= POLL_SECONDS:
                current_disk = _disk_bytes((package_root, work_root))
                peak_disk = max(peak_disk, current_disk)
                last_disk_sample = now
            violations = []
            if previous_stage_wall + elapsed_wall > stage_wall_limit:
                violations.append(f"{stage} wall {previous_stage_wall + elapsed_wall:.3f}>{stage_wall_limit:.0f}s")
            if previous_stage_cpu + elapsed_cpu > stage_cpu_limit:
                violations.append(f"{stage} CPU {previous_stage_cpu + elapsed_cpu:.3f}>{stage_cpu_limit:.0f}s")
            if previous_total_wall + elapsed_wall > TOTAL_WALL_LIMIT:
                violations.append(f"whole-pilot wall {previous_total_wall + elapsed_wall:.3f}>{TOTAL_WALL_LIMIT:.0f}s")
            if previous_total_cpu + elapsed_cpu > TOTAL_CPU_LIMIT:
                violations.append(f"whole-pilot CPU {previous_total_cpu + elapsed_cpu:.3f}>{TOTAL_CPU_LIMIT:.0f}s")
            if peak_group_rss > RSS_LIMIT_BYTES:
                violations.append(f"process-group RSS {peak_group_rss}>{RSS_LIMIT_BYTES} bytes")
            if current_disk > DISK_LIMIT_BYTES:
                violations.append(f"work/export storage {current_disk}>{DISK_LIMIT_BYTES} bytes")
            if violations:
                kill_reason = "; ".join(violations)
                outer_error = outer_error or f"outer guardian: {kill_reason}"
                outer_error_at = outer_error_at or now
                os.kill(child_pid, signal.SIGKILL)
                _waited_pid, child_status, child_rusage = os.wait4(child_pid, 0)
                process.returncode = os.waitstatus_to_exitcode(child_status)
                status_code = int(process.returncode)
                break
            time.sleep(POLL_SECONDS)
    except BaseException as exc:
        outer_error = outer_error or f"{type(exc).__name__}: {exc}"
        outer_error_at = outer_error_at or time.monotonic()
        if "process" in locals():
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                _waited_pid, child_status, child_rusage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(child_status)
                status_code = int(process.returncode)
            except ChildProcessError:
                pass

    child_cpu_seconds = 0.0
    child_peak_rss = 0
    if child_rusage is not None:
        child_cpu_seconds = float(child_rusage.ru_utime + child_rusage.ru_stime)
        child_peak_rss = int(child_rusage.ru_maxrss) * 1024
    current_rows = _read_ledger_tolerating_partial_tail(ledger_path)
    has_child_entry = len(current_rows) > len(previous_rows)
    row = current_rows[-1] if has_child_entry else None
    if row is None or row.get("stage") != stage:
        outer_error = outer_error or "outer guardian found no settled child stage entry"
        outer_error_at = outer_error_at or time.monotonic()
        row = {
            "schema": "resource-ledger-entry/1",
            "stage": stage,
            "status": "failed",
            "started_wall_monotonic": started_wall,
            "metadata": {},
        }
    child_started_wall = row.get("started_wall_monotonic")

    receipt_path = Path(row.get("metadata", {}).get("receipt", ""))
    if not receipt_path.is_absolute():
        receipt_path = work_root / receipt_path
    if not receipt_path.is_file():
        receipt_path = _stage_receipt(work_root, stage, previous_rows)
    child_receipt_error = None
    if receipt_path.is_file():
        try:
            child_receipt_error = json.loads(receipt_path.read_text(encoding="utf-8")).get("first_error")
        except (json.JSONDecodeError, OSError):
            child_receipt_error = None
    child_error = row.get("first_error") or child_receipt_error
    child_error_preceded_outer = bool(
        child_error
        and (outer_error_at is None or row.get("finished_wall_monotonic", float("inf")) <= outer_error_at)
    )
    first_error = child_error if child_error_preceded_outer else outer_error
    if status_code != 0 and first_error is None:
        first_error = child_error or f"guarded child exited with status {status_code}"
    first_error = first_error or child_error

    # Include failed-checkpoint inventory hashing in the outer stage totals.
    checkpoints = _checkpoint_inventory(work_root) if first_error is not None else []
    finished_wall = time.monotonic()
    finished_cpu = time.process_time()
    wall_seconds = max(0.0, finished_wall - started_wall)
    guardian_cpu_seconds = max(0.0, finished_cpu - guardian_cpu_start)
    cpu_seconds = child_cpu_seconds + guardian_cpu_seconds
    guardian_final = _proc_metrics(os.getpid())
    peak_group_rss = max(peak_group_rss, child_peak_rss + guardian_final["rss_bytes"])
    current_disk = _disk_bytes((package_root, work_root))
    peak_disk = max(peak_disk, current_disk)
    final_violations = []
    if previous_stage_wall + wall_seconds > stage_wall_limit:
        final_violations.append(f"{stage} wall {previous_stage_wall + wall_seconds:.3f}>{stage_wall_limit:.0f}s")
    if previous_stage_cpu + cpu_seconds > stage_cpu_limit:
        final_violations.append(f"{stage} CPU {previous_stage_cpu + cpu_seconds:.3f}>{stage_cpu_limit:.0f}s")
    if previous_total_wall + wall_seconds > TOTAL_WALL_LIMIT:
        final_violations.append(f"whole-pilot wall {previous_total_wall + wall_seconds:.3f}>{TOTAL_WALL_LIMIT:.0f}s")
    if previous_total_cpu + cpu_seconds > TOTAL_CPU_LIMIT:
        final_violations.append(f"whole-pilot CPU {previous_total_cpu + cpu_seconds:.3f}>{TOTAL_CPU_LIMIT:.0f}s")
    if peak_group_rss > RSS_LIMIT_BYTES:
        final_violations.append(f"process-group RSS {peak_group_rss}>{RSS_LIMIT_BYTES} bytes")
    if peak_disk > DISK_LIMIT_BYTES:
        final_violations.append(f"work/export storage {peak_disk}>{DISK_LIMIT_BYTES} bytes")
    if final_violations:
        outer_error = outer_error or f"outer guardian: {'; '.join(final_violations)}"
        outer_error_at = outer_error_at or finished_wall
        first_error = first_error or outer_error
        if first_error is not None:
            row["status"] = "failed"
            row["first_error"] = first_error
        if not checkpoints:
            checkpoints = _checkpoint_inventory(work_root)
            finished_wall = time.monotonic()
            finished_cpu = time.process_time()
            wall_seconds = max(0.0, finished_wall - started_wall)
            guardian_cpu_seconds = max(0.0, finished_cpu - guardian_cpu_start)
            cpu_seconds = child_cpu_seconds + guardian_cpu_seconds
            current_disk = _disk_bytes((package_root, work_root))
            peak_disk = max(peak_disk, current_disk)

    if first_error is not None:
        row["status"] = "failed"
        row["first_error"] = first_error
    row.update({
        "started_wall_monotonic": started_wall,
        "finished_wall_monotonic": finished_wall,
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "peak_rss_bytes": peak_group_rss,
        "rss_high_water_source": "wait4.ru_maxrss plus /proc sampled process-group VmRSS",
        "outer_guardian_error": outer_error,
        "outer_guardian_kill_reason": kill_reason,
        "outer_guardian_error_at_wall_monotonic": outer_error_at,
        "child_error_preceded_outer_guardian": child_error_preceded_outer,
        "peak_work_export_bytes": peak_disk,
        "rss_limit_bytes": RSS_LIMIT_BYTES,
        "work_export_limit_bytes": DISK_LIMIT_BYTES,
        "stage_wall_used_including_this": previous_stage_wall + wall_seconds,
        "stage_cpu_used_including_this": previous_stage_cpu + cpu_seconds,
        "pilot_wall_used_including_this": previous_total_wall + wall_seconds,
        "pilot_cpu_used_including_this": previous_total_cpu + cpu_seconds,
    })
    row.setdefault("metadata", {})["outer_guardian_receipt"] = guardian_path.as_posix()
    row["metadata"]["outer_guardian_sampling_interval_seconds"] = POLL_SECONDS
    row["metadata"]["child_exit_race_confirmation"] = {
        "maximum_window_seconds": REAP_RACE_CONFIRM_ATTEMPTS * REAP_RACE_CONFIRM_INTERVAL_SECONDS,
        "interval_seconds": REAP_RACE_CONFIRM_INTERVAL_SECONDS,
        "accepted_only_after_wait4_reap": True,
    }
    row["metadata"]["disk_peak_sampling_method"] = "directory size scan every 0.25 seconds; short-lived growth between scans may be missed"
    if child_started_wall is not None:
        row["metadata"]["child_started_wall_monotonic"] = child_started_wall
    if prior_cost["receipt_sha256"] is not None:
        row["metadata"]["prior_resource_cost_sha256"] = prior_cost["receipt_sha256"]
    _rewrite_last_row(ledger_path, row, replace_last=has_child_entry)

    if first_error is not None:
        _update_stage_receipt(
            receipt_path,
            row,
            error=first_error,
            checkpoints=checkpoints,
            guardian_path=guardian_path,
        )
    else:
        receipt_path = Path(row.get("metadata", {}).get("receipt", ""))
        if receipt_path.is_file():
            _update_stage_receipt(receipt_path, row, error=None, checkpoints=[], guardian_path=guardian_path)

    guardian_receipt = {
        "schema": "outer-process-guardian/1",
        "stage": stage,
        "status": "failed" if first_error is not None else "complete",
        "first_error": first_error,
        "outer_guardian_error": outer_error,
        "outer_guardian_kill_reason": kill_reason,
        "outer_guardian_error_at_wall_monotonic": outer_error_at,
        "child_returncode": status_code,
        "child_pid": child_pid if "child_pid" in locals() else None,
        "prior_resource_cost_sha256": prior_cost["receipt_sha256"],
        "scope": "driver process start through child exit and failed-checkpoint inventory hashing; wait4 child CPU/RSS plus guardian CPU; final ledger and receipt writes are excluded",
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "child_cpu_seconds": child_cpu_seconds,
        "guardian_cpu_seconds": guardian_cpu_seconds,
        "peak_process_group_rss_bytes": peak_group_rss,
        "rss_measurement": "Linux wait4.ru_maxrss plus 0.25-second /proc process-group samples",
        "peak_work_export_bytes": peak_disk,
        "disk_sampling_interval_seconds": POLL_SECONDS,
        "disk_sampling_limit": "short-lived growth between directory scans may be missed",
        "stage_wall_used_including_this": previous_stage_wall + wall_seconds,
        "stage_cpu_used_including_this": previous_stage_cpu + cpu_seconds,
        "pilot_wall_used_including_this": previous_total_wall + wall_seconds,
        "pilot_cpu_used_including_this": previous_total_cpu + cpu_seconds,
        "resource_entry": row,
    }
    _json_write(guardian_path, guardian_receipt)
    return status_code if first_error is None else (status_code if status_code != 0 else 1)
