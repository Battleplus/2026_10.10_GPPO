"""Persistent stage and whole-pilot resource accounting."""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STAGE_LIMITS: dict[str, tuple[float, float]] = {
    "admission": (120.0, 60.0),
    "engineering_smoke": (900.0, 600.0),
    "shutdown": (120.0, 60.0),
    "n01_full_admission": (120.0, 60.0),
    "n01_full_evaluation": (5400.0, 4500.0),
    "n01_full_export": (300.0, 180.0),
    "n01_full_shutdown": (120.0, 60.0),
}
TOTAL_WALL_LIMIT = 1140.0
TOTAL_CPU_LIMIT = 720.0
STAGE_STOP_RESERVES: dict[str, tuple[float, float]] = {
    "n01_full_admission": (5.0, 2.0),
    "n01_full_evaluation": (20.0, 15.0),
    "n01_full_export": (5.0, 2.0),
    "n01_full_shutdown": (10.0, 2.0),
}
TOTAL_WALL_STOP_RESERVE = 70.0
TOTAL_CPU_STOP_RESERVE = 40.0
RSS_LIMIT_BYTES = 4 * 1024**3
DISK_LIMIT_BYTES = 8 * 1024**3
CARRY_FORWARD_RECEIPT_NAME = "PRIOR_RESOURCE_COST.json"


class BudgetExceeded(RuntimeError):
    pass


def _read_rss_metrics() -> tuple[int, int]:
    proc_status = Path("/proc/self/status")
    if proc_status.is_file():
        current = None
        high_water = None
        for line in proc_status.read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                current = int(line.split()[1]) * 1024
            elif line.startswith("VmHWM:"):
                high_water = int(line.split()[1]) * 1024
        if current is None or high_water is None:
            raise RuntimeError("VmRSS or VmHWM missing from /proc/self/status")
        return current, high_water
    if sys.platform == "win32":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.argtypes = []
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        get_process_memory_info.restype = wintypes.BOOL
        ok = get_process_memory_info(get_current_process(), ctypes.byref(counters), counters.cb)
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        peak_bytes = peak if sys.platform == "darwin" else peak * 1024
        return peak_bytes, peak_bytes
    except (ImportError, AttributeError) as exc:
        raise RuntimeError("RSS measurement is unavailable on this platform") from exc


def _read_rss_bytes() -> int:
    """Return the kernel-measured high-water mark where the platform exposes it."""
    return _read_rss_metrics()[1]


def _disk_bytes(roots: tuple[Path, ...]) -> int:
    total = 0
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            try:
                resolved = path.resolve(strict=True)
                if resolved in seen or path.is_symlink() or not path.is_file():
                    continue
                seen.add(resolved)
                total += path.stat().st_size
            except FileNotFoundError:
                continue
    return total


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid resource ledger line {line_number}") from exc
            if row.get("schema") != "resource-ledger-entry/1":
                raise ValueError(f"unsupported resource ledger line {line_number}")
            rows.append(row)
    return rows


def _read_prior_resource_cost(path: str | Path | None, *, required: bool = False) -> dict[str, Any]:
    empty = {
        "stage_costs": {},
        "total_wall_seconds": 0.0,
        "total_cpu_seconds": 0.0,
        "receipt_sha256": None,
    }
    if path is None:
        if required:
            raise FileNotFoundError("required prior resource-cost receipt path was not provided")
        return empty
    receipt_path = Path(path)
    if not receipt_path.is_file():
        if required:
            raise FileNotFoundError(f"required prior resource-cost receipt is missing: {receipt_path}")
        return empty
    receipt_path = receipt_path.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") == "n01-full-evaluation-prior-cost/1":
        evidence_root = (receipt_path.parent / receipt.get("evidence_root_relative", "")).resolve(strict=True)
        evidence = receipt.get("evidence_sha256")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("full-evaluation prior-cost receipt has no evidence hashes")
        for relative, expected in evidence.items():
            evidence_path = (evidence_root / relative).resolve(strict=True)
            if evidence_root not in evidence_path.parents or not evidence_path.is_file():
                raise ValueError("full-evaluation prior-cost evidence escapes its bound root")
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if not isinstance(expected, str) or digest != expected.lower():
                raise ValueError(f"full-evaluation prior-cost evidence hash mismatch: {relative}")
        total_wall = float(receipt.get("known_total_wall_seconds", float("nan")))
        total_cpu = float(receipt.get("known_total_cpu_seconds", float("nan")))
        if not math.isfinite(total_wall) or not math.isfinite(total_cpu) or min(total_wall, total_cpu) < 0:
            raise ValueError("full-evaluation prior-cost totals are invalid")
        return {
            "stage_costs": {},
            "total_wall_seconds": total_wall,
            "total_cpu_seconds": total_cpu,
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
    if receipt.get("schema") == "n01-prior-resource-cost/1":
        evidence_files = receipt.get("evidence_files")
        if not isinstance(evidence_files, list) or not evidence_files:
            raise ValueError("N01 prior-cost receipt has no evidence files")
        root = receipt_path.parent.resolve()
        evidence_hashes: dict[str, str] = {}
        for item in evidence_files:
            relative = item.get("path") if isinstance(item, dict) else None
            expected = item.get("sha256") if isinstance(item, dict) else None
            if not isinstance(relative, str) or not relative or not isinstance(expected, str):
                raise ValueError("invalid N01 prior-cost evidence row")
            evidence_path = (root / relative).resolve(strict=True)
            if root not in evidence_path.parents or not evidence_path.is_file():
                raise ValueError("N01 prior-cost evidence escapes package or is not a file")
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if digest != expected:
                raise ValueError(f"N01 prior-cost evidence hash mismatch: {relative}")
            evidence_hashes[relative] = digest
        ledger_relative = receipt.get("ledger_path")
        if ledger_relative not in evidence_hashes:
            raise ValueError("N01 prior-cost ledger is not hash-bound")
        rows = _read_ledger(root / ledger_relative)
        for row in rows:
            metadata = row.get("metadata") or {}
            receipt_name = Path(metadata.get("receipt", "")).name
            guardian_name = Path(metadata.get("outer_guardian_receipt", "")).name
            receipt_candidates = [name for name in evidence_hashes if "/receipts/" in f"/{name}" and name.endswith(receipt_name)]
            guardian_candidates = [name for name in evidence_hashes if "/guardians/" in f"/{name}" and name.endswith(guardian_name)]
            if len(receipt_candidates) != 1 or len(guardian_candidates) != 1:
                raise ValueError("N01 prior-cost ledger is missing a unique receipt or guardian")
            driver_receipt = json.loads((root / receipt_candidates[0]).read_text(encoding="utf-8"))
            guardian_receipt = json.loads((root / guardian_candidates[0]).read_text(encoding="utf-8"))
            if (
                driver_receipt.get("resource_entry") != row
                or driver_receipt.get("status") != row.get("status")
                or driver_receipt.get("first_error") is not None
                or guardian_receipt.get("resource_entry") != row
                or guardian_receipt.get("status") != "complete"
                or guardian_receipt.get("first_error") is not None
                or guardian_receipt.get("outer_guardian_error") is not None
                or guardian_receipt.get("outer_guardian_kill_reason") is not None
                or guardian_receipt.get("child_returncode") != 0
            ):
                raise ValueError("N01 prior-cost receipt or guardian does not match source ledger")
        expected_statuses = {"admission": "accepted", "engineering_smoke": "complete"}
        stage_costs: dict[str, dict[str, float]] = {}
        for row in rows:
            stage = row["stage"]
            if stage not in expected_statuses or row.get("status") != expected_statuses[stage]:
                raise ValueError("N01 prior-cost ledger has a failed or out-of-scope stage")
            if row.get("first_error") is not None or row.get("outer_guardian_error") is not None or row.get("outer_guardian_kill_reason") is not None:
                raise ValueError("N01 prior-cost ledger contains an error")
            cost = stage_costs.setdefault(stage, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
            cost["wall_seconds"] += float(row["wall_seconds"])
            cost["cpu_seconds"] += float(row["cpu_seconds"])
        declared_costs = receipt.get("stage_costs")
        if not isinstance(declared_costs, dict) or set(declared_costs) != set(stage_costs):
            raise ValueError("N01 prior-cost stage totals are invalid")
        for stage, measured in stage_costs.items():
            for field in ("wall_seconds", "cpu_seconds"):
                if not math.isclose(measured[field], float(declared_costs[stage][field]), rel_tol=1e-12, abs_tol=1e-9):
                    raise ValueError("N01 prior-cost stage totals do not match source ledger")
        total_wall = sum(value["wall_seconds"] for value in stage_costs.values())
        total_cpu = sum(value["cpu_seconds"] for value in stage_costs.values())
        if not math.isclose(total_wall, float(receipt.get("total_wall_seconds", float("nan"))), rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("N01 prior-cost total wall does not match source ledger")
        if not math.isclose(total_cpu, float(receipt.get("total_cpu_seconds", float("nan"))), rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("N01 prior-cost total CPU does not match source ledger")
        return {
            "stage_costs": stage_costs,
            "total_wall_seconds": total_wall,
            "total_cpu_seconds": total_cpu,
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
    if receipt.get("schema") != "resource-cost-carry-forward/1":
        raise ValueError("unsupported prior resource-cost receipt")

    evidence_files = receipt.get("evidence_files")
    if not isinstance(evidence_files, list) or not evidence_files:
        raise ValueError("prior resource-cost receipt has no evidence hashes")
    evidence_hashes: dict[str, str] = {}
    root = receipt_path.parent
    for item in evidence_files:
        if not isinstance(item, dict):
            raise ValueError("invalid prior resource-cost evidence row")
        relative = item.get("path")
        expected = item.get("sha256")
        if not isinstance(relative, str) or not relative or not isinstance(expected, str):
            raise ValueError("invalid prior resource-cost evidence path or hash")
        evidence_path = (root / relative).resolve(strict=True)
        if root not in evidence_path.parents or not evidence_path.is_file():
            raise ValueError("prior resource-cost evidence escapes its package or is not a file")
        digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"prior resource-cost evidence hash mismatch: {relative}")
        evidence_hashes[relative] = digest

    roles = receipt.get("evidence_roles")
    if not isinstance(roles, dict):
        raise ValueError("prior resource-cost receipt has no evidence roles")
    required_roles = {"resource_ledger", "systemd_show", "deployment_receipt"}
    if not required_roles.issubset(roles):
        raise ValueError("prior resource-cost receipt is missing accounting evidence roles")
    if any(roles[name] not in evidence_hashes for name in required_roles):
        raise ValueError("prior resource-cost accounting evidence is not hash-bound")

    deployment = json.loads((root / roles["deployment_receipt"]).read_text(encoding="utf-8"))
    if (
        deployment.get("source_identity_sha256") != receipt.get("source_identity_sha256")
        or deployment.get("archive_sha256") != receipt.get("deployed_package_archive_sha256")
    ):
        raise ValueError("prior resource-cost receipt does not match its deployment evidence")

    ledger_rows = _read_ledger(root / roles["resource_ledger"])
    ledger_stage_costs: dict[str, dict[str, float]] = {}
    for row in ledger_rows:
        stage = row.get("stage")
        if stage not in STAGE_LIMITS:
            raise ValueError("prior resource ledger contains an unknown stage")
        cost = ledger_stage_costs.setdefault(stage, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
        cost["wall_seconds"] += float(row["wall_seconds"])
        cost["cpu_seconds"] += float(row["cpu_seconds"])
    if ledger_stage_costs != receipt.get("ledger_stage_costs"):
        for stage in set(ledger_stage_costs) | set(receipt.get("ledger_stage_costs", {})):
            measured = ledger_stage_costs.get(stage, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
            declared = receipt.get("ledger_stage_costs", {}).get(stage, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
            if any(
                not math.isclose(float(measured[key]), float(declared[key]), rel_tol=1e-12, abs_tol=1e-9)
                for key in ("wall_seconds", "cpu_seconds")
            ):
                raise ValueError("prior resource-cost ledger totals do not match the source ledger")

    systemd_text = (root / roles["systemd_show"]).read_text(encoding="utf-8")
    systemd_values = {
        key: value
        for line in systemd_text.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    invocation_id = systemd_values.get("InvocationID")
    if invocation_id != receipt.get("systemd_invocation_id"):
        raise ValueError("prior resource-cost receipt does not match the systemd invocation")
    try:
        systemd_wall = (
            int(systemd_values["ExecMainExitTimestampMonotonic"])
            - int(systemd_values["ExecMainStartTimestampMonotonic"])
        ) / 1_000_000
        systemd_cpu = int(systemd_values["CPUUsageNSec"]) / 1_000_000_000
    except (KeyError, ValueError) as exc:
        raise ValueError("prior systemd accounting fields are missing or invalid") from exc
    if not math.isclose(systemd_wall, float(receipt["systemd_total_wall_seconds"]), rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("prior resource-cost wall total does not match systemd")
    if not math.isclose(systemd_cpu, float(receipt["systemd_total_cpu_seconds"]), rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("prior resource-cost CPU total does not match systemd")

    ledger_wall = sum(cost["wall_seconds"] for cost in ledger_stage_costs.values())
    ledger_cpu = sum(cost["cpu_seconds"] for cost in ledger_stage_costs.values())
    wall_overhead = systemd_wall - ledger_wall
    cpu_overhead = systemd_cpu - ledger_cpu
    if wall_overhead < -1e-9 or cpu_overhead < -1e-9:
        raise ValueError("systemd totals are below the prior process-guardian ledger")
    declared_overhead = receipt.get("systemd_wrapper_overhead_assigned_to_admission", {})
    if any(
        not math.isclose(
            max(0.0, actual),
            float(declared_overhead.get(field, float("nan"))),
            rel_tol=1e-12,
            abs_tol=1e-9,
        )
        for actual, field in ((wall_overhead, "wall_seconds"), (cpu_overhead, "cpu_seconds"))
    ):
        raise ValueError("prior systemd wrapper overhead is not reconciled")
    expected_stage_costs = {
        stage: {"wall_seconds": cost["wall_seconds"], "cpu_seconds": cost["cpu_seconds"]}
        for stage, cost in ledger_stage_costs.items()
    }
    admission = expected_stage_costs.setdefault("admission", {"wall_seconds": 0.0, "cpu_seconds": 0.0})
    admission["wall_seconds"] += max(0.0, wall_overhead)
    admission["cpu_seconds"] += max(0.0, cpu_overhead)
    declared_stage_costs = receipt.get("stage_costs")
    if not isinstance(declared_stage_costs, dict) or set(declared_stage_costs) != set(expected_stage_costs):
        raise ValueError("prior resource-cost stage totals are invalid")
    for stage, measured in expected_stage_costs.items():
        declared = declared_stage_costs[stage]
        if any(
            not math.isclose(float(measured[key]), float(declared[key]), rel_tol=1e-12, abs_tol=1e-9)
            for key in ("wall_seconds", "cpu_seconds")
        ):
            raise ValueError("prior resource-cost stage totals do not reconcile")

    total_wall = sum(cost["wall_seconds"] for cost in declared_stage_costs.values())
    total_cpu = sum(cost["cpu_seconds"] for cost in declared_stage_costs.values())
    if not math.isclose(total_wall, systemd_wall, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("prior resource-cost wall stages do not sum to systemd")
    if not math.isclose(total_cpu, systemd_cpu, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("prior resource-cost CPU stages do not sum to systemd")
    return {
        "stage_costs": declared_stage_costs,
        "total_wall_seconds": total_wall,
        "total_cpu_seconds": total_cpu,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }


@dataclass(slots=True)
class ResourceSupervisor:
    stage: str
    ledger_path: Path
    storage_roots: tuple[Path, ...]
    rss_limit_bytes: int = RSS_LIMIT_BYTES
    disk_limit_bytes: int = DISK_LIMIT_BYTES
    monitor_interval_seconds: float = 0.25
    interrupt_on_violation: bool = True
    prior_cost_path: Path | None = None
    invocation_start_wall: float | None = None
    invocation_start_cpu: float | None = None
    _ledger_before: list[dict[str, Any]] = field(init=False, repr=False)
    _prior_cost: dict[str, Any] = field(init=False, repr=False)
    _stage_wall_limit: float = field(init=False, repr=False)
    _stage_cpu_limit: float = field(init=False, repr=False)
    _prior_stage_wall: float = field(init=False, repr=False)
    _prior_stage_cpu: float = field(init=False, repr=False)
    _prior_total_wall: float = field(init=False, repr=False)
    _prior_total_cpu: float = field(init=False, repr=False)
    _start_wall: float = field(init=False, repr=False)
    _start_cpu: float = field(init=False, repr=False)
    _peak_rss: int = field(init=False, repr=False)
    _peak_disk: int = field(init=False, repr=False)
    _last_disk_check: float = field(init=False, repr=False)
    _current_disk: int = field(init=False, repr=False)
    _first_error: str | None = field(init=False, default=None, repr=False)
    _closed: bool = field(init=False, default=False, repr=False)
    _finished_row: dict[str, Any] | None = field(init=False, default=None, repr=False)
    _monitor_thread: threading.Thread | None = field(init=False, default=None, repr=False)
    _monitor_stop: threading.Event = field(init=False, repr=False)
    _monitor_violation: threading.Event = field(init=False, repr=False)
    _interrupt_sent: bool = field(init=False, default=False, repr=False)
    _previous_signal_handler: Any = field(init=False, default=None, repr=False)
    _signal_number: int | None = field(init=False, default=None, repr=False)
    _state_lock: threading.RLock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.stage not in STAGE_LIMITS:
            raise ValueError(f"unknown budget stage: {self.stage}")
        self.ledger_path = Path(self.ledger_path)
        self.storage_roots = tuple(Path(item) for item in self.storage_roots)
        self._ledger_before = _read_ledger(self.ledger_path)
        self._prior_cost = _read_prior_resource_cost(self.prior_cost_path, required=self.prior_cost_path is not None)
        self._stage_wall_limit, self._stage_cpu_limit = STAGE_LIMITS[self.stage]
        carry_stage = self._prior_cost["stage_costs"].get(self.stage, {})
        self._prior_stage_wall = float(carry_stage.get("wall_seconds", 0.0)) + sum(row["wall_seconds"] for row in self._ledger_before if row["stage"] == self.stage)
        self._prior_stage_cpu = float(carry_stage.get("cpu_seconds", 0.0)) + sum(row["cpu_seconds"] for row in self._ledger_before if row["stage"] == self.stage)
        self._prior_total_wall = self._prior_cost["total_wall_seconds"] + sum(row["wall_seconds"] for row in self._ledger_before)
        self._prior_total_cpu = self._prior_cost["total_cpu_seconds"] + sum(row["cpu_seconds"] for row in self._ledger_before)
        self._start_wall = self.invocation_start_wall if self.invocation_start_wall is not None else time.monotonic()
        self._start_cpu = self.invocation_start_cpu if self.invocation_start_cpu is not None else time.process_time()
        self._peak_rss = _read_rss_bytes()
        self._current_disk = _disk_bytes(self.storage_roots)
        self._peak_disk = self._current_disk
        self._last_disk_check = time.monotonic()
        self._first_error: str | None = None
        self._closed = False
        self._finished_row = None
        self._monitor_thread = None
        self._monitor_stop = threading.Event()
        self._monitor_violation = threading.Event()
        self._interrupt_sent = False
        self._previous_signal_handler = None
        self._signal_number = None
        self._state_lock = threading.RLock()

    def start_monitor(self) -> None:
        if self._monitor_thread is not None:
            raise RuntimeError("resource monitor already started")
        if self.interrupt_on_violation and os.name == "posix" and threading.current_thread() is threading.main_thread():
            signal_number = getattr(signal, "SIGUSR1", None)
            if signal_number is not None:
                self._signal_number = signal_number
                self._previous_signal_handler = signal.getsignal(signal_number)
                signal.signal(signal_number, self._interrupt_handler)
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name=f"resource-watch-{self.stage}",
            daemon=True,
        )
        self._monitor_thread.start()

    def _interrupt_handler(self, _signum, _frame) -> None:
        raise BudgetExceeded(self._first_error or f"{self.stage} resource limit exceeded")

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.wait(self.monitor_interval_seconds):
            try:
                self._monitor_sample()
            except BudgetExceeded:
                self._monitor_violation.set()
                if self._signal_number is not None and not self._interrupt_sent:
                    self._interrupt_sent = True
                    try:
                        os.kill(os.getpid(), self._signal_number)
                    except OSError:
                        pass
                return
            except BaseException as exc:
                with self._state_lock:
                    self._first_error = self._first_error or f"resource monitor failed: {type(exc).__name__}: {exc}"
                self._monitor_violation.set()
                if self._signal_number is not None and not self._interrupt_sent:
                    self._interrupt_sent = True
                    try:
                        os.kill(os.getpid(), self._signal_number)
                    except OSError:
                        pass
                return

    def _sample_and_check(self, *, force_disk: bool = False, allow_finished: bool = False) -> None:
        with self._state_lock:
            if self._closed or (self._finished_row is not None and not allow_finished):
                return
            wall = self.wall_seconds
            cpu = self.cpu_seconds
            _current_rss, rss_high_water = _read_rss_metrics()
            if force_disk or time.monotonic() - self._last_disk_check >= 1.0:
                self._current_disk = _disk_bytes(self.storage_roots)
                self._last_disk_check = time.monotonic()
            self._peak_rss = max(self._peak_rss, rss_high_water)
            self._peak_disk = max(self._peak_disk, self._current_disk)
            violations = self._limit_violations(wall, cpu, self._peak_rss, self._current_disk)
            if violations:
                self._first_error = self._first_error or "; ".join(violations)
                raise BudgetExceeded(self._first_error)

    def _monitor_sample(self) -> None:
        self._sample_and_check(force_disk=time.monotonic() - self._last_disk_check >= 1.0, allow_finished=True)

    @property
    def wall_seconds(self) -> float:
        return time.monotonic() - self._start_wall

    @property
    def cpu_seconds(self) -> float:
        return time.process_time() - self._start_cpu

    def _limit_violations(self, wall: float, cpu: float, rss: int, disk: int) -> list[str]:
        stage_wall = self._prior_stage_wall + wall
        stage_cpu = self._prior_stage_cpu + cpu
        total_wall = self._prior_total_wall + wall
        total_cpu = self._prior_total_cpu + cpu
        violations = []
        if stage_wall > self._stage_wall_limit:
            violations.append(f"{self.stage} wall {stage_wall:.3f}>{self._stage_wall_limit:.0f}s")
        if stage_cpu > self._stage_cpu_limit:
            violations.append(f"{self.stage} CPU {stage_cpu:.3f}>{self._stage_cpu_limit:.0f}s")
        if total_wall > TOTAL_WALL_LIMIT:
            violations.append(f"whole-pilot wall {total_wall:.3f}>{TOTAL_WALL_LIMIT:.0f}s")
        if total_cpu > TOTAL_CPU_LIMIT:
            violations.append(f"whole-pilot CPU {total_cpu:.3f}>{TOTAL_CPU_LIMIT:.0f}s")
        if rss > self.rss_limit_bytes:
            violations.append(f"RSS {rss}>{self.rss_limit_bytes} bytes")
        if disk > self.disk_limit_bytes:
            violations.append(f"work/export storage {disk}>{self.disk_limit_bytes} bytes")
        return violations

    def check(self, *, force_disk: bool = False) -> None:
        if self._closed:
            raise RuntimeError("resource supervisor is already closed")
        self._sample_and_check(force_disk=force_disk)

    def record_error(self, error: BaseException | str) -> None:
        if self._first_error is None:
            if isinstance(error, BaseException):
                self._first_error = f"{type(error).__name__}: {error}"
            else:
                self._first_error = str(error)

    def finish(self, *, status: str, error: BaseException | str | None = None, metadata: dict | None = None) -> dict:
        if self._finished_row is not None:
            raise RuntimeError("resource supervisor has already written its stage entry")
        if error is None:
            self.check(force_disk=True)
        if error is not None:
            self.record_error(error)
        finished_wall = time.monotonic()
        finished_cpu = time.process_time()
        _current_rss, rss = _read_rss_metrics()
        self._current_disk = _disk_bytes(self.storage_roots)
        disk = self._current_disk
        self._peak_rss = max(self._peak_rss, rss)
        self._peak_disk = max(self._peak_disk, disk)
        if error is None:
            violations = self._limit_violations(finished_wall - self._start_wall, finished_cpu - self._start_cpu, rss, disk)
            if violations:
                self._first_error = self._first_error or "; ".join(violations)
                raise BudgetExceeded(self._first_error)
        row = {
            "schema": "resource-ledger-entry/1",
            "stage": self.stage,
            "status": status,
            "started_wall_monotonic": self._start_wall,
            "finished_wall_monotonic": finished_wall,
            "wall_seconds": finished_wall - self._start_wall,
            "cpu_seconds": finished_cpu - self._start_cpu,
            "peak_rss_bytes": self._peak_rss,
            "rss_high_water_source": "linux:/proc/self/status:VmHWM" if Path("/proc/self/status").is_file() else "platform process high-water API",
            "peak_work_export_bytes": self._peak_disk,
            "rss_limit_bytes": self.rss_limit_bytes,
            "work_export_limit_bytes": self.disk_limit_bytes,
            "stage_wall_used_including_this": self._prior_stage_wall + (finished_wall - self._start_wall),
            "stage_cpu_used_including_this": self._prior_stage_cpu + (finished_cpu - self._start_cpu),
            "pilot_wall_used_including_this": self._prior_total_wall + (finished_wall - self._start_wall),
            "pilot_cpu_used_including_this": self._prior_total_cpu + (finished_cpu - self._start_cpu),
            "first_error": self._first_error,
            "metadata": {
                **(metadata or {}),
                **({"prior_resource_cost_sha256": self._prior_cost["receipt_sha256"]} if self._prior_cost["receipt_sha256"] else {}),
            },
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._finished_row = row
        return dict(row)

    def close(self, *, error: BaseException | str | None = None) -> dict[str, Any]:
        if self._closed:
            if error is not None:
                return self._revise_finished_entry(error)
            return dict(self._finished_row or {})
        if error is not None:
            self.record_error(error)
        self._monitor_stop.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=max(1.0, self.monitor_interval_seconds * 4))
            if self._monitor_thread.is_alive():
                self.record_error("resource monitor did not stop")
        if self._signal_number is not None and threading.current_thread() is threading.main_thread():
            signal.signal(self._signal_number, self._previous_signal_handler)
        self._sample_final_metrics()
        if self._finished_row is None:
            raise RuntimeError("resource supervisor cannot close before writing a stage entry")
        if self._first_error is not None:
            self._finished_row["status"] = "failed"
            self._finished_row["first_error"] = self._first_error
        self._write_revised_last_entry()
        self._closed = True
        return dict(self._finished_row)

    def _sample_final_metrics(self) -> None:
        with self._state_lock:
            finished_wall = time.monotonic()
            finished_cpu = time.process_time()
            _current_rss, rss = _read_rss_metrics()
            self._current_disk = _disk_bytes(self.storage_roots)
            self._peak_rss = max(self._peak_rss, rss)
            self._peak_disk = max(self._peak_disk, self._current_disk)
            violations = self._limit_violations(
                finished_wall - self._start_wall,
                finished_cpu - self._start_cpu,
                self._peak_rss,
                self._current_disk,
            )
            if violations:
                self._first_error = self._first_error or "; ".join(violations)
            if self._finished_row is not None:
                row = self._finished_row
                row.update({
                    "finished_wall_monotonic": finished_wall,
                    "wall_seconds": finished_wall - self._start_wall,
                    "cpu_seconds": finished_cpu - self._start_cpu,
                    "peak_rss_bytes": self._peak_rss,
                    "peak_work_export_bytes": self._peak_disk,
                    "stage_wall_used_including_this": self._prior_stage_wall + (finished_wall - self._start_wall),
                    "stage_cpu_used_including_this": self._prior_stage_cpu + (finished_cpu - self._start_cpu),
                    "pilot_wall_used_including_this": self._prior_total_wall + (finished_wall - self._start_wall),
                    "pilot_cpu_used_including_this": self._prior_total_cpu + (finished_cpu - self._start_cpu),
                })

    def _revise_finished_entry(self, error: BaseException | str) -> dict[str, Any]:
        self.record_error(error)
        if self._finished_row is not None:
            self._finished_row["status"] = "failed"
            self._finished_row["first_error"] = self._first_error
            self._write_revised_last_entry()
        return dict(self._finished_row or {})

    def _write_revised_last_entry(self) -> None:
        rows = _read_ledger(self.ledger_path)
        if not rows or rows[-1].get("started_wall_monotonic") != self._start_wall:
            raise RuntimeError("resource ledger changed while the stage was active")
        rows[-1] = dict(self._finished_row or {})
        temporary = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.ledger_path)


def ledger_summary(path: str | Path, prior_cost_path: str | Path | None = None) -> dict[str, Any]:
    rows = _read_ledger(Path(path))
    prior = _read_prior_resource_cost(prior_cost_path, required=prior_cost_path is not None)
    stage_wall = {stage: sum(row["wall_seconds"] for row in rows if row["stage"] == stage) for stage in STAGE_LIMITS}
    stage_cpu = {stage: sum(row["cpu_seconds"] for row in rows if row["stage"] == stage) for stage in STAGE_LIMITS}
    for stage, cost in prior["stage_costs"].items():
        stage_wall[stage] += cost["wall_seconds"]
        stage_cpu[stage] += cost["cpu_seconds"]
    wall = prior["total_wall_seconds"] + sum(row["wall_seconds"] for row in rows)
    cpu = prior["total_cpu_seconds"] + sum(row["cpu_seconds"] for row in rows)
    return {
        "entries": rows,
        "stage_wall_seconds": stage_wall,
        "stage_cpu_seconds": stage_cpu,
        "total_wall_seconds": wall,
        "total_cpu_seconds": cpu,
        "prior_resource_cost_sha256": prior["receipt_sha256"],
        "total_wall_limit_seconds": TOTAL_WALL_LIMIT,
        "total_cpu_limit_seconds": TOTAL_CPU_LIMIT,
        "all_successful": all(row["status"] in {"complete", "accepted"} for row in rows),
    }
