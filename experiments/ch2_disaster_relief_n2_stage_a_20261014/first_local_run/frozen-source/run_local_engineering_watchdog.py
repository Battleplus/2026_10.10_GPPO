from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import ctypes
from ctypes import wintypes

import psutil


ROOT = Path(__file__).resolve().parent
PROFILE = json.loads((ROOT / "LOCAL_ENGINEERING_BUDGET.json").read_text(encoding="utf-8"))


def tree_files(root: Path):
    return [path for path in root.rglob("*") if path.is_file()]


def terminate_tree(process: psutil.Process) -> None:
    try:
        children = process.children(recursive=True)
    except psutil.Error:
        children = []
    for child in reversed(children):
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        process.kill()
    except psutil.Error:
        pass


def windows_process_cpu_seconds(process: subprocess.Popen) -> float:
    if os.name != "nt":
        try:
            times = psutil.Process(process.pid).cpu_times()
            return times.user + times.system
        except psutil.Error:
            return 0.0

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
    get_process_times = ctypes.windll.kernel32.GetProcessTimes
    get_process_times.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
                                  ctypes.POINTER(FileTime), ctypes.POINTER(FileTime)]
    get_process_times.restype = wintypes.BOOL
    ok = get_process_times(
        wintypes.HANDLE(process._handle), ctypes.byref(created), ctypes.byref(exited),
        ctypes.byref(kernel), ctypes.byref(user),
    )
    if not ok:
        raise OSError("GetProcessTimes failed")
    ticks = lambda item: (item.high << 32) | item.low
    return (ticks(kernel) + ticks(user)) / 10_000_000


def main() -> int:
    run_id = str(time.time_ns())
    output = ROOT / "runs" / f"local-{run_id}"
    output.mkdir(parents=True, exist_ok=False)
    stdout_path = output / "worker.stdout.log"
    command = [sys.executable, str(ROOT / "run_local_engineering.py"), "--output-root", str(output / "artifacts")]
    profile_path = ROOT / "LOCAL_ENGINEERING_BUDGET.json"
    profile_hash_start = hashlib.sha256(profile_path.read_bytes()).hexdigest().upper()
    source_paths = [
        ROOT / "n2_contracts.py", ROOT / "run_local_engineering.py",
        ROOT / "references" / "existing_n2" / "branching.py",
        ROOT / "references" / "existing_n2" / "world_model.py",
        ROOT / "references" / "civil" / "relief_env.py",
        ROOT / "references" / "civil" / "baselines.py",
        ROOT / "references" / "civil" / "scenario_schema.py",
        ROOT / "references" / "civil" / "fixtures" / "control.json",
        ROOT / "references" / "existing_n2" / "ppo_integration.py",
        ROOT / "references" / "existing_n2" / "tests" / "test_branching.py",
        ROOT / "run_local_engineering_watchdog.py",
        ROOT / "references" / "civil" / "graph_policy.py",
        ROOT / "references" / "civil" / "ppo_trainer.py",
    ]
    source_hashes_start = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest().upper()
                           for path in source_paths}
    started = time.monotonic()
    cpu_peak = 0.0
    rss_peak = 0
    output_peak = 0
    samples = 0
    violation = None
    descendants_seen: list[tuple[int, float]] = []
    child = None
    cleanup_verified = False
    supervisor_write_operations = 2
    try:
        with stdout_path.open("w", encoding="utf-8", newline="\n") as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            worker = psutil.Process(child.pid)
            while child.poll() is None:
                elapsed = time.monotonic() - started
                parent_cpu = time.process_time()
                try:
                    descendants = worker.children(recursive=True)
                    if descendants:
                        violation = "UNEXPECTED_WORKER_DESCENDANT"
                        descendants_seen.extend((desc.pid, desc.create_time()) for desc in descendants)
                        for descendant in reversed(descendants):
                            try:
                                descendant.kill()
                            except psutil.Error:
                                pass
                    cpu_now = parent_cpu + sum(p.cpu_times().user + p.cpu_times().system for p in [worker] if p.is_running())
                    rss_now = psutil.Process(os.getpid()).memory_info().rss + sum(p.memory_info().rss for p in [worker] if p.is_running())
                except psutil.Error:
                    violation = violation or "RESOURCE_SAMPLE_UNKNOWN"
                    cpu_now, rss_now = cpu_peak, rss_peak
                cpu_peak, rss_peak = max(cpu_peak, cpu_now), max(rss_peak, rss_now)
                files = tree_files(output)
                output_now = sum(path.stat().st_size for path in files)
                output_peak = max(output_peak, output_now)
                samples += 1
                if elapsed >= PROFILE["runtime"]["wall_work_deadline_seconds"]:
                    violation = violation or "WALL_WORK_DEADLINE"
                elif cpu_peak >= PROFILE["runtime"]["process_tree_cpu_seconds_work_limit"]:
                    violation = violation or "PROCESS_TREE_CPU_WORK_LIMIT"
                elif rss_peak >= PROFILE["runtime"]["rss_tree_bytes_max"]:
                    violation = violation or "PROCESS_TREE_RSS_LIMIT"
                elif output_peak >= PROFILE["runtime"]["output_tree_bytes_max"]:
                    violation = violation or "OUTPUT_TREE_SIZE_LIMIT"
                if violation:
                    terminate_tree(worker)
                    break
                time.sleep(0.25)
    except BaseException as error:
        violation = violation or f"WATCHDOG_EXCEPTION:{type(error).__name__}"
    finally:
        if child is not None and child.poll() is None:
            try:
                terminate_tree(psutil.Process(child.pid))
                child.wait(timeout=10)
            except BaseException:
                violation = violation or "WORKER_KILL_OR_WAIT_FAILED"
        cleanup_verified = child is not None and child.poll() is not None and not descendants_seen
    try:
        files = tree_files(output)
        output_bytes = sum(path.stat().st_size for path in files)
        if stdout_path.exists():
            with stdout_path.open("rb") as stream:
                stream.seek(max(0, stdout_path.stat().st_size - 48 * 1024))
                worker_log = stream.read(48 * 1024).decode("utf-8", errors="replace")
        else:
            worker_log = ""
    except BaseException:
        files, output_bytes, worker_log = [], -1, ""
        violation = violation or "OUTPUT_SETTLEMENT_UNKNOWN"
    profile_hash_end = hashlib.sha256(profile_path.read_bytes()).hexdigest().upper()
    source_hashes_end = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest().upper()
                         for path in source_paths}
    if profile_hash_start != profile_hash_end or source_hashes_start != source_hashes_end:
        violation = violation or "PROFILE_OR_SOURCE_CHANGED"
    elapsed = time.monotonic() - started
    cpu_final = time.process_time()
    if child is not None:
        try:
            cpu_final += windows_process_cpu_seconds(child)
        except BaseException:
            violation = violation or "FINAL_WORKER_CPU_UNKNOWN"
    cpu_peak = max(cpu_peak, cpu_final)
    try:
        rss_tail = psutil.Process(os.getpid()).memory_info().rss
        if child is not None and child.poll() is None:
            rss_tail += psutil.Process(child.pid).memory_info().rss
        files = tree_files(output)
        output_bytes = sum(path.stat().st_size for path in files)
        output_peak = max(output_peak, output_bytes)
    except BaseException:
        rss_tail = -1
        violation = violation or "FINAL_RESOURCE_SAMPLE_UNKNOWN"
    rss_peak = max(rss_peak, rss_tail)
    if elapsed > PROFILE["runtime"]["wall_seconds_total_including_settlement"]:
        violation = violation or "TOTAL_WALL_LIMIT"
    if cpu_final > PROFILE["runtime"]["process_tree_cpu_seconds_total_including_settlement"]:
        violation = violation or "TOTAL_CPU_LIMIT"
    if rss_tail < 0 or rss_tail > PROFILE["runtime"]["rss_tree_bytes_max"]:
        violation = violation or "FINAL_RSS_LIMIT"
    if output_bytes > PROFILE["runtime"]["output_tree_bytes_max"]:
        violation = violation or "FINAL_OUTPUT_SIZE_LIMIT"
    receipt = {
        "schema": "n2-local-engineering-watchdog/1",
        "profile_sha256": profile_hash_start,
        "source_sha256": source_hashes_start,
        "command": command,
        "exit_code": child.returncode if child is not None else None,
        "violation": violation,
        "wall_seconds": elapsed,
        "process_tree_cpu_seconds_peak_sample": cpu_peak,
        "process_tree_rss_bytes_peak_sample": rss_peak,
        "output_tree_bytes_peak_sample": output_peak,
        "output_tree_bytes_final": output_bytes,
        "output_file_count_final": len(files),
        "sample_interval_seconds": 0.25,
        "resource_samples": samples,
        "final_process_tree_cpu_seconds": cpu_final,
        "windows_cgroup_metrics": "unavailable",
        "stdout_tail": worker_log[-12000:],
        "supervisor_output_write_operations": supervisor_write_operations,
        "worker_cleanup_verified": cleanup_verified,
        "unexpected_descendants_seen": descendants_seen,
        "final_rss_bytes_including_worker": rss_tail,
        "settlement": "worker handle exited and was polled; resource limits rechecked after log/hash/output inspection; no remote or systemd action",
        "settlement_measurement_limit": "The final watchdog receipt write and stdout emission occur after the last resource sample; their CPU/RSS is not measured. The 45s wall and 30s CPU reserves include settlement headroom, but their consumption is unverified.",
        "receipt_write_operations_planned": 1,
    }
    receipt_path = output / "WATCHDOG_RECEIPT.json"
    receipt["receipt_write_bytes_planned"] = 0
    serialized = json.dumps(receipt, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    receipt["receipt_write_bytes_planned"] = len(serialized.encode("utf-8"))
    serialized = json.dumps(receipt, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    planned_total = output_bytes + len(serialized.encode("utf-8"))
    if planned_total > PROFILE["runtime"]["output_tree_bytes_max"]:
        receipt["violation"] = receipt["violation"] or "RECEIPT_OUTPUT_TREE_SIZE_LIMIT"
    receipt["output_tree_bytes_planned_including_receipt"] = planned_total
    serialized = json.dumps(receipt, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    receipt["receipt_write_bytes_planned"] = len(serialized.encode("utf-8"))
    serialized = json.dumps(receipt, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    receipt_path.write_text(serialized, encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in (
        "exit_code", "violation", "wall_seconds", "process_tree_cpu_seconds_peak_sample",
        "process_tree_rss_bytes_peak_sample", "output_tree_bytes_final", "output_file_count_final",
        "resource_samples", "stdout_tail",
    )}, sort_keys=True))
    return 0 if child is not None and child.returncode == 0 and violation is None and cleanup_verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
