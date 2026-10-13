"""Fail-fast, metered runner for one bounded N2 Linux engineering acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:
    resource = None


STAGE_CAPS = {
    "runtime_admission": (120.0, 60.0),
    "unit_suite": (600.0, 480.0),
    "ppo_smoke": (900.0, 600.0),
    "shutdown_receipt": (120.0, 60.0),
}
TOTAL_WALL_CAP = 1740.0
TOTAL_CPU_CAP = 1200.0
RSS_CAP_BYTES = 4 * 1024**3
DISK_CAP_BYTES = 8 * 1024**3
MANIFEST_PATH = Path("preparation/linux_acceptance/package-manifest.json")
THREAD_ENV = {
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}
RUNTIME_CHECK_NAMES = (
    "host", "user", "platform", "python_executable", "python_version", "torch_version",
    "numpy_version", "cuda_visible_devices", "cuda_initialized", "torch_threads",
    "torch_interop_threads", "cpu_affinity_after_runner_pin",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".pending", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_package(
    package_root: Path, expected_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, str], str]:
    manifest_file = package_root / MANIFEST_PATH
    manifest_sha256 = _sha256(manifest_file)
    if manifest_sha256 != expected_manifest_sha256.upper():
        raise ValueError("PACKAGE_MANIFEST_SHA256_MISMATCH")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("identity") != "n2-local-synthetic-engineering-linux-acceptance-r2":
        raise ValueError("PACKAGE_IDENTITY_MISMATCH")
    hashes: dict[str, str] = {}
    expected_paths = {str(relative).replace("\\", "/") for relative in manifest["files"]}
    expected_paths.add(MANIFEST_PATH.as_posix())
    observed_paths = set()
    for path in package_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"PACKAGE_SYMLINK_FORBIDDEN:{path.relative_to(package_root)}")
        if path.is_file():
            observed_paths.add(path.relative_to(package_root).as_posix())
    if observed_paths != expected_paths:
        raise ValueError("PACKAGE_INVENTORY_MISMATCH")
    for relative in manifest["files"]:
        path = (package_root / relative).resolve()
        if package_root.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"PACKAGE_FILE_MISSING_OR_ESCAPE:{relative}")
        hashes[relative] = _sha256(path)
    expected_hashes = manifest.get("hashing", {}).get("file_sha256", {})
    if set(expected_hashes) != set(hashes) or expected_hashes != hashes:
        raise ValueError("PACKAGE_FILE_SHA256_MISMATCH")
    return manifest, hashes, manifest_sha256


def _proc_group_metrics(pgid: int) -> tuple[float, int]:
    ticks = os.sysconf("SC_CLK_TCK")
    cpu_seconds = 0.0
    rss_bytes = 0
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="ascii")
            tail = stat[stat.rfind(")") + 2:].split()
            if int(tail[2]) != pgid:
                continue
            cpu_seconds += (int(tail[11]) + int(tail[12])) / ticks
            for line in (entry / "status").read_text(encoding="ascii").splitlines():
                if line.startswith("VmRSS:"):
                    rss_bytes += int(line.split()[1]) * 1024
                    break
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
            continue
    return cpu_seconds, rss_bytes


def _current_cgroup_path(expected_unit: str) -> Path:
    if not expected_unit.endswith(".service") or "/" in expected_unit:
        raise ValueError("EXPECTED_UNIT_MUST_BE_A_SERVICE_BASENAME")
    invocation_id = os.environ.get("INVOCATION_ID", "")
    if len(invocation_id) != 32 or any(ch not in "0123456789abcdefABCDEF" for ch in invocation_id):
        raise RuntimeError("SYSTEMD_INVOCATION_ID_MISSING_OR_INVALID")
    entries = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    unified = next((line.partition("::")[2] for line in entries if line.startswith("0::")), None)
    if not unified:
        raise RuntimeError("CGROUP_V2_MEMBERSHIP_UNAVAILABLE")
    members = Path(unified)
    if expected_unit not in members.parts:
        raise RuntimeError("EXPECTED_SYSTEMD_UNIT_MISMATCH")
    cgroup_path = (Path("/sys/fs/cgroup") / members.relative_to("/")).resolve(strict=True)
    cgroup_root = Path("/sys/fs/cgroup").resolve(strict=True)
    if cgroup_root not in cgroup_path.parents or not (cgroup_path / "cpu.stat").is_file():
        raise RuntimeError("CGROUP_V2_PATH_INVALID")
    return cgroup_path


def _read_cgroup(path: Path) -> dict[str, int]:
    cpu_values = {}
    for line in (path / "cpu.stat").read_text(encoding="ascii").splitlines():
        key, value = line.split()
        cpu_values[key] = int(value)
    if "usage_usec" not in cpu_values:
        raise RuntimeError("CGROUP_CPU_USAGE_UNAVAILABLE")
    memory_peak_file = path / "memory.peak"
    if memory_peak_file.is_file():
        memory_peak = int(memory_peak_file.read_text(encoding="ascii").strip())
    else:
        raise RuntimeError("CGROUP_MEMORY_PEAK_UNAVAILABLE")
    return {"cpu_usage_usec": cpu_values["usage_usec"], "memory_peak_bytes": memory_peak}


def _tree_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _smoke_report_error(work: Path) -> str | None:
    report_path = work / "smoke-output/N2_ENGINEERING_NODE_REPORT.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        ppo = report["ppo"]
        if ppo["total_environment_transitions_per_continuous_or_resumed_path"] != 480:
            return "SMOKE_PER_PATH_TRANSITION_COUNT_MISMATCH"
        if ppo["total_optimizer_updates_per_continuous_or_resumed_path"] != 32:
            return "SMOKE_PER_PATH_UPDATE_COUNT_MISMATCH"
        if ppo["combined_environment_transitions_across_comparison_paths"] != 720:
            return "SMOKE_COMBINED_TRANSITION_COUNT_MISMATCH"
        if ppo["combined_optimizer_updates_across_comparison_paths"] != 48:
            return "SMOKE_COMBINED_UPDATE_COUNT_MISMATCH"
        if ppo["next_round_strict_restore"].get("equivalent") is not True:
            return "SMOKE_STRICT_RESTORE_CHECK_FAILED"
        if report["exports"]["normal"].get("status") != "complete":
            return "SMOKE_NORMAL_EXPORT_FAILED"
        failure_receipt = work / "smoke-output/failed_export.json.failure.json"
        if not failure_receipt.is_file():
            return "SMOKE_FAILURE_EXPORT_RECEIPT_MISSING"
        failure = json.loads(failure_receipt.read_text(encoding="utf-8"))
        if failure.get("status") != "failed" or failure.get("exception_type") != "RuntimeError":
            return "SMOKE_FAILURE_EXPORT_RECEIPT_INVALID"
    except (OSError, ValueError, KeyError, TypeError) as error:
        return f"SMOKE_REPORT_INVALID:{type(error).__name__}:{error}"
    return None


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def _kill_group(process: subprocess.Popen, grace_seconds: float = 5.0) -> None:
    if process.poll() is not None and not _group_exists(process.pid):
        process.wait()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            process.wait()
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.wait()
    deadline = time.monotonic() + grace_seconds
    while _group_exists(process.pid) and time.monotonic() < deadline:
        process.poll()
        time.sleep(0.05)
    if _group_exists(process.pid):
        raise RuntimeError("PROCESS_GROUP_NOT_SETTLED")


def _runtime_probe(python: Path, cpu: int, expected_host: str, expected_user: str) -> list[str]:
    source = f'''import json, os, pwd, socket, sys, torch, numpy
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
checks = [
    {{"name": "host", "actual": socket.gethostname(), "expected": {expected_host!r}}},
    {{"name": "user", "actual": pwd.getpwuid(os.geteuid()).pw_name, "expected": {expected_user!r}}},
    {{"name": "platform", "actual": sys.platform, "expected": "linux"}},
    {{"name": "python_executable", "actual": os.path.realpath(sys.executable), "expected": {str(python)!r}}},
    {{"name": "python_version", "actual": ".".join(map(str, sys.version_info[:3])), "expected": "3.11.16"}},
    {{"name": "torch_version", "actual": torch.__version__, "expected": "2.7.0+cu128"}},
    {{"name": "numpy_version", "actual": numpy.__version__, "expected": "1.26.0"}},
    {{"name": "cuda_visible_devices", "actual": os.environ.get("CUDA_VISIBLE_DEVICES"), "expected": ""}},
    {{"name": "cuda_initialized", "actual": torch.cuda.is_initialized(), "expected": False}},
    {{"name": "torch_threads", "actual": torch.get_num_threads(), "expected": 1}},
    {{"name": "torch_interop_threads", "actual": torch.get_num_interop_threads(), "expected": 1}},
    {{"name": "cpu_affinity_after_runner_pin", "actual": sorted(os.sched_getaffinity(0)), "expected": [{cpu}],
     "enforcement": "runner-called-sched_setaffinity-before-stage"}},
]
for check in checks:
    check["passed"] = check["actual"] == check["expected"]
print(json.dumps({{"schema": "n2-runtime-admission-checks/1", "checks": checks}}, sort_keys=True))
sys.exit(0 if all(check["passed"] for check in checks) else 1)
'''
    return [str(python), "-B", "-c", source]


def _runtime_checks(stdout_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        report = json.loads(stdout_path.read_text(encoding="utf-8"))
        if report.get("schema") != "n2-runtime-admission-checks/1":
            return [], "RUNTIME_CHECK_REPORT_SCHEMA_INVALID"
        checks = report["checks"]
        if not isinstance(checks, list) or not checks:
            return [], "RUNTIME_CHECK_REPORT_EMPTY"
        names = [check.get("name") if isinstance(check, dict) else None for check in checks]
        if len(names) != len(set(names)) or set(names) != set(RUNTIME_CHECK_NAMES):
            return checks, "RUNTIME_CHECK_REPORT_NAMES_MISMATCH"
        for check in checks:
            if not isinstance(check, dict) or not {"name", "actual", "expected", "passed"} <= set(check):
                return checks, "RUNTIME_CHECK_REPORT_ENTRY_INVALID"
            if check["passed"] is not (check["actual"] == check["expected"]):
                return checks, "RUNTIME_CHECK_REPORT_RESULT_INCONSISTENT"
        if not all(check["passed"] for check in checks):
            return checks, "RUNTIME_CHECK_FAILED"
        return checks, None
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [], f"RUNTIME_CHECK_REPORT_INVALID:{type(error).__name__}:{error}"


def _stage_commands(python: Path, package: Path, work: Path, cpu: int,
                    expected_host: str, expected_user: str) -> dict[str, list[str]]:
    tests = package / "development/ch2_disaster_relief_n2_v1/engineering/tests"
    smoke = package / "development/ch2_disaster_relief_n2_v1/engineering/run_ppo_integration_smoke.py"
    unit_bootstrap = (
        "import runpy,sys,torch; torch.set_num_threads(1); torch.set_num_interop_threads(1); "
        f"sys.argv=['unittest','discover','-s',{str(tests)!r},'-v']; "
        "runpy.run_module('unittest',run_name='__main__')"
    )
    smoke_bootstrap = (
        "import runpy,sys,torch; torch.set_num_threads(1); torch.set_num_interop_threads(1); "
        f"sys.argv=[{str(smoke)!r},'--output-root',{str(work / 'smoke-output')!r}]; "
        f"runpy.run_path({str(smoke)!r},run_name='__main__')"
    )
    return {
        "runtime_admission": _runtime_probe(python, cpu, expected_host, expected_user),
        "unit_suite": [str(python), "-B", "-c", unit_bootstrap],
        "ppo_smoke": [str(python), "-B", "-c", smoke_bootstrap],
    }


def _parse_cpu_list(value: str) -> list[int]:
    try:
        cpus = sorted({int(part) for part in value.split(",")})
    except ValueError as error:
        raise argparse.ArgumentTypeError("CPU affinity must be a comma-separated list of integers") from error
    if not cpus or any(cpu < 0 for cpu in cpus):
        raise argparse.ArgumentTypeError("CPU affinity must contain non-negative CPU indexes")
    return cpus


def run(package_root: Path, work_root: Path, python: Path, cpu: int,
        expected_manifest_sha256: str, expected_unit: str,
        expected_host: str = "ru-server-MS-1", expected_user: str = "user1",
        observed_ssh_affinity: list[int] | None = None) -> int:
    if sys.platform != "linux":
        raise RuntimeError("N2_LINUX_RUNNER_REQUIRES_LINUX")
    if resource is None:
        raise RuntimeError("RESOURCE_ACCOUNTING_UNAVAILABLE")
    cgroup_path = _current_cgroup_path(expected_unit)
    cgroup_before = _read_cgroup(cgroup_path)
    package_root = package_root.resolve(strict=True)
    work_root = work_root.resolve()
    python = python.resolve(strict=True)
    if package_root == work_root or package_root in work_root.parents or work_root in package_root.parents:
        raise ValueError("PACKAGE_AND_WORK_ROOT_MUST_BE_DISJOINT")
    if work_root.exists() and any(work_root.iterdir()):
        raise ValueError("WORK_ROOT_NOT_EMPTY")
    work_root.mkdir(parents=True, exist_ok=True)
    if observed_ssh_affinity is None:
        raise ValueError("OBSERVED_SSH_AFFINITY_REQUIRED")
    runner_affinity_before_pin = sorted(os.sched_getaffinity(0))
    if cpu not in runner_affinity_before_pin:
        raise RuntimeError("APPROVED_CPU_NOT_AVAILABLE")
    os.sched_setaffinity(0, {cpu})
    manifest, source_hashes, manifest_sha256 = _load_package(package_root, expected_manifest_sha256)
    environment = os.environ.copy()
    environment.update(THREAD_ENV)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    run_wall_start = time.monotonic()
    run_utc_start = datetime.now(timezone.utc).isoformat()
    stage_rows: list[dict[str, Any]] = []
    first_error: str | None = None
    pending: list[str] = []
    commands = _stage_commands(python, package_root, work_root, cpu, expected_host, expected_user)
    active_process: subprocess.Popen | None = None

    def stop_on_signal(signum: int, _frame: Any) -> None:
        if active_process is not None:
            _kill_group(active_process)
        raise InterruptedError(f"SIGNAL_{signum}")

    previous_handlers = {sig: signal.signal(sig, stop_on_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for name, command in commands.items():
            stage_wall_cap, stage_cpu_cap = STAGE_CAPS[name]
            stdout_path = work_root / f"{name}.stdout.log"
            stderr_path = work_root / f"{name}.stderr.log"
            wall_start = time.monotonic()
            children_before = resource.getrusage(resource.RUSAGE_CHILDREN)
            peak_group_rss = 0
            limit_reason = None
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    command, cwd=package_root, env=environment, stdout=stdout, stderr=stderr,
                    start_new_session=True, preexec_fn=lambda: os.sched_setaffinity(0, {cpu}),
                )
                active_process = process
                while process.poll() is None:
                    elapsed = time.monotonic() - wall_start
                    group_cpu, group_rss = _proc_group_metrics(process.pid)
                    peak_group_rss = max(peak_group_rss, group_rss)
                    used_disk = _tree_bytes(package_root) + _tree_bytes(work_root)
                    if elapsed > stage_wall_cap:
                        limit_reason = "STAGE_WALL_CAP"
                    elif group_cpu > stage_cpu_cap:
                        limit_reason = "STAGE_CPU_CAP"
                    elif max(peak_group_rss, _read_cgroup(cgroup_path)["memory_peak_bytes"]) > RSS_CAP_BYTES:
                        limit_reason = "RSS_CAP"
                    elif used_disk > DISK_CAP_BYTES:
                        limit_reason = "PACKAGE_WORK_EXPORT_STORAGE_CAP"
                    elif time.monotonic() - run_wall_start > TOTAL_WALL_CAP:
                        limit_reason = "TOTAL_WALL_CAP"
                    else:
                        cgroup_now = _read_cgroup(cgroup_path)
                        cgroup_cpu_now = max(0.0, (cgroup_now["cpu_usage_usec"] - cgroup_before["cpu_usage_usec"]) / 1_000_000.0)
                        if cgroup_cpu_now > TOTAL_CPU_CAP:
                            limit_reason = "TOTAL_CGROUP_CPU_CAP"
                    if limit_reason:
                        _kill_group(process)
                        break
                    time.sleep(0.25)
                exit_code = process.wait()
                if _group_exists(process.pid):
                    _kill_group(process)
                    limit_reason = "PROCESS_GROUP_CHILD_SURVIVED"
                active_process = None
            if name == "ppo_smoke" and exit_code == 0:
                limit_reason = _smoke_report_error(work_root)
            runtime_checks: list[dict[str, Any]] | None = None
            if name == "runtime_admission":
                runtime_checks, runtime_check_error = _runtime_checks(stdout_path)
                if limit_reason is None and exit_code == 0 and runtime_check_error:
                    limit_reason = runtime_check_error
            wall_seconds = time.monotonic() - wall_start
            children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu_seconds = ((children_after.ru_utime + children_after.ru_stime)
                           - (children_before.ru_utime + children_before.ru_stime))
            if limit_reason is None and wall_seconds > stage_wall_cap:
                limit_reason = "STAGE_WALL_CAP"
            if limit_reason is None and cpu_seconds > stage_cpu_cap:
                limit_reason = "STAGE_CPU_CAP"
            row = {
                "stage": name, "command": command, "exit_code": exit_code,
                "wall_seconds": wall_seconds, "cpu_seconds": cpu_seconds,
                "peak_sampled_process_group_rss_bytes": peak_group_rss,
                "stdout_bytes": stdout_path.stat().st_size,
                "stderr_bytes": stderr_path.stat().st_size,
                "cgroup_cpu_seconds_at_stage_end": max(
                    0.0, (_read_cgroup(cgroup_path)["cpu_usage_usec"] - cgroup_before["cpu_usage_usec"]) / 1_000_000.0,
                ),
                "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
                "stdout_sha256": _sha256(stdout_path), "stderr_sha256": _sha256(stderr_path),
                "limit_reason": limit_reason,
            }
            if runtime_checks is not None:
                row["checks"] = runtime_checks
            stage_rows.append(row)
            _atomic_json(work_root / f"{name}.receipt.json", row)
            if limit_reason or exit_code != 0:
                first_error = limit_reason or f"STAGE_EXIT_{exit_code}:{name}"
                pending.extend(str(path) for path in work_root.rglob("*.pending"))
                break
    except BaseException as error:
        first_error = first_error or f"{type(error).__name__}:{error}"
        pending.extend(str(path) for path in work_root.rglob("*.pending"))
    finally:
        shutdown_wall_start = time.monotonic()
        shutdown_cpu_start = resource.getrusage(resource.RUSAGE_SELF)
        if active_process is not None:
            try:
                _kill_group(active_process)
            except BaseException as cleanup_error:
                first_error = first_error or f"CHILD_CLEANUP_FAILED:{cleanup_error}"
            finally:
                active_process = None
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        children_after_all = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_total = ((children_after_all.ru_utime + children_after_all.ru_stime)
                     - (before.ru_utime + before.ru_stime))
        try:
            manifest_after, source_hashes_after, manifest_after_sha = _load_package(package_root, expected_manifest_sha256)
            if source_hashes_after != source_hashes or manifest_after_sha != manifest_sha256:
                first_error = first_error or "PACKAGE_CHANGED_DURING_RUN"
        except BaseException as error:
            first_error = first_error or f"FINAL_IDENTITY_READ_FAILED:{error}"
        try:
            cgroup_after = _read_cgroup(cgroup_path)
            cgroup_cpu_seconds: float | None = max(
                0.0, (cgroup_after["cpu_usage_usec"] - cgroup_before["cpu_usage_usec"]) / 1_000_000.0,
            )
            if cgroup_cpu_seconds > TOTAL_CPU_CAP:
                first_error = first_error or "TOTAL_CGROUP_CPU_CAP"
        except BaseException as error:
            cgroup_after = cgroup_before
            cgroup_cpu_seconds = None
            first_error = first_error or f"CGROUP_SETTLEMENT_READ_FAILED:{error}"
        stage_rows.append({
            "stage": "shutdown_receipt",
            "wall_seconds_before_receipt_write": None,
            "cpu_seconds_before_receipt_write": None,
            "wall_cap_seconds": STAGE_CAPS["shutdown_receipt"][0],
            "cpu_cap_seconds": STAGE_CAPS["shutdown_receipt"][1],
        })
        receipt = {
            "schema": "n2-linux-engineering-acceptance-receipt/1",
            "identity": manifest["identity"],
            "status": "complete" if first_error is None and len(stage_rows) == len(commands) else "failed",
            "scope": "bounded local-synthetic engineering acceptance only",
            "started_utc": run_utc_start,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "runtime": {"python_path": str(python), "cpu_affinity_after_runner_pin": [cpu],
                        "platform": platform.platform(), "expected_host": expected_host,
                        "expected_user": expected_user,
                        "runner_affinity_before_pin": runner_affinity_before_pin},
            "ordinary_ssh_affinity_observation": {
                "actual": observed_ssh_affinity,
                "source": "caller-recorded ordinary SSH shell before systemd launch",
                "enforcement": "observational-only",
            },
            "package_manifest_sha256": manifest_sha256,
            "source_sha256": source_hashes,
            "stages": stage_rows,
            "total_wall_seconds_before_final_receipt_commit": None,
            "total_child_cpu_seconds": cpu_total,
            "cgroup_cpu_seconds_at_receipt_prepare": cgroup_cpu_seconds,
            "cgroup_memory_peak_bytes": cgroup_after["memory_peak_bytes"],
            "cgroup_path": str(cgroup_path),
            "systemd_invocation_id": os.environ.get("INVOCATION_ID"),
            "expected_systemd_unit": expected_unit,
            "total_wall_seconds_at_receipt_prepare": None,
            "peak_sampled_process_group_rss_bytes": max(
                (row["peak_sampled_process_group_rss_bytes"] for row in stage_rows), default=0,
            ),
            "package_work_export_storage_bytes_at_settlement": _tree_bytes(package_root) + _tree_bytes(work_root),
            "first_error": first_error,
            "pending_paths": pending,
            "last_completed_stage": next((
                row["stage"] for row in reversed(stage_rows[:-1])
                if row.get("exit_code") == 0 and row.get("limit_reason") is None
            ), None),
            "active_checkpoint_paths": [str(path) for path in work_root.rglob("*.pt")],
            "limits": {"wall_seconds": TOTAL_WALL_CAP, "cpu_seconds": TOTAL_CPU_CAP,
                       "rss_bytes": RSS_CAP_BYTES, "package_work_export_storage_bytes": DISK_CAP_BYTES,
                       "stages": STAGE_CAPS},
            "measurement_limitations": [
                "process-group RSS is sampled and can miss short peaks",
                "disk measure is package plus work tree at samples and settlement, not host-wide I/O accounting",
                "the runner records wall time through process cleanup and before final receipt commit; the final atomic write tail is unknown and must be bounded from same-invocation systemd/cgroup evidence",
                "systemd/cgroup service memory and CPU readings are independent evidence; service cgroup CPU is sampled during stages and at settlement",
            ],
        }
        shutdown_wall = time.monotonic() - shutdown_wall_start
        shutdown_cpu_now = resource.getrusage(resource.RUSAGE_SELF)
        shutdown_cpu = ((shutdown_cpu_now.ru_utime + shutdown_cpu_now.ru_stime)
                        - (shutdown_cpu_start.ru_utime + shutdown_cpu_start.ru_stime))
        if shutdown_wall > STAGE_CAPS["shutdown_receipt"][0]:
            first_error = first_error or "SHUTDOWN_WALL_CAP"
        if shutdown_cpu > STAGE_CAPS["shutdown_receipt"][1]:
            first_error = first_error or "SHUTDOWN_CPU_CAP"
        wall_before_commit = time.monotonic() - run_wall_start
        if wall_before_commit > TOTAL_WALL_CAP:
            first_error = first_error or "TOTAL_WALL_CAP"
        stage_rows[-1]["wall_seconds_before_receipt_write"] = shutdown_wall
        stage_rows[-1]["cpu_seconds_before_receipt_write"] = shutdown_cpu
        receipt["stages"] = stage_rows
        receipt["total_wall_seconds_before_final_receipt_commit"] = wall_before_commit
        receipt["total_wall_seconds_at_receipt_prepare"] = wall_before_commit
        receipt["status"] = "complete" if first_error is None and len(stage_rows) == len(commands) else "failed"
        receipt["first_error"] = first_error
        try:
            _atomic_json(work_root / "final-receipt.json", receipt)
            receipt_commit_seconds = time.monotonic() - run_wall_start - wall_before_commit
            settled_wall = wall_before_commit + receipt_commit_seconds
            receipt["final_receipt_commit_seconds"] = receipt_commit_seconds
            receipt["total_wall_seconds_at_first_receipt_commit"] = settled_wall
            receipt["receipt_measurement_boundary"] = (
                "wall is measured through cleanup and receipt preparation; the final atomic receipt write tail is unknown, "
                "so use same-invocation systemd/cgroup end evidence for the outer bound"
            )
            if settled_wall > TOTAL_WALL_CAP:
                receipt["status"] = "failed"
                receipt["first_error"] = receipt["first_error"] or "TOTAL_WALL_CAP"
            _atomic_json(work_root / "final-receipt.json", receipt)
        except BaseException as error:
            print(f"FINAL_RECEIPT_WRITE_FAILED:{error}", file=sys.stderr)
            return_code = 2
        else:
            return_code = 0 if receipt["status"] == "complete" else 1
    return return_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument(
        "--python", type=Path, required=True,
    )
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-unit", required=True)
    parser.add_argument("--expected-host", default="ru-server-MS-1")
    parser.add_argument("--expected-user", default="user1")
    parser.add_argument("--observed-ssh-affinity", type=_parse_cpu_list, required=True)
    args = parser.parse_args(argv)
    return run(args.package_root, args.work_root, args.python, args.cpu,
               args.expected_manifest_sha256, args.expected_unit, args.expected_host, args.expected_user,
               args.observed_ssh_affinity)


if __name__ == "__main__":
    raise SystemExit(main())
