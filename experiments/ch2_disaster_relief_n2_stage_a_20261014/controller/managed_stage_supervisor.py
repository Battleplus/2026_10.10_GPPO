from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import pathlib
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import threading
from collections.abc import Callable, Mapping

_VENDOR_ROOT = pathlib.Path(__file__).resolve().parent / "vendor"
if str(_VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ROOT))


class ManagedStageError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class GuardLimits:
    wall_seconds: float
    wall_settlement_reserve_seconds: float
    total_cpu_seconds: float
    cpu_settlement_reserve_seconds: float
    memory_max_bytes: int
    memory_reserve_bytes: int
    storage_max_bytes: int
    sample_interval_seconds: float = 0.1
    stop_grace_seconds: float = 20.0

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "GuardLimits":
        keys = {
            "wall_seconds": "wall_seconds_total_including_settlement",
            "wall_settlement_reserve_seconds": "settlement_reserve_seconds",
            "total_cpu_seconds": "complete_process_cpu_seconds_total_including_descendants_and_settlement",
            "cpu_settlement_reserve_seconds": "settlement_cpu_reserve_seconds",
            "memory_max_bytes": "cgroup_memory_max_bytes",
            "memory_reserve_bytes": "memory_settlement_reserve_bytes",
            "storage_max_bytes": "combined_working_plus_export_peak_bytes_max",
        }
        normalized = {}
        for field, source in keys.items():
            number = value.get(source)
            byte_limit = field in {"memory_max_bytes", "memory_reserve_bytes", "storage_max_bytes"}
            valid_type = type(number) is int if byte_limit else type(number) in (int, float)
            if (not valid_type or number <= 0
                    or (type(number) is float and not math.isfinite(number))):
                raise ManagedStageError("GUARD_BUDGET_FIELD_INVALID:" + source)
            normalized[field] = number
        normalized["sample_interval_seconds"] = value.get("sample_interval_seconds", 0.1)
        normalized["stop_grace_seconds"] = value.get("stop_grace_seconds", 20.0)
        for number in (normalized["sample_interval_seconds"], normalized["stop_grace_seconds"]):
            if (type(number) not in (int, float) or number <= 0
                    or (type(number) is float and not math.isfinite(number))):
                raise ManagedStageError("GUARD_INTERVAL_INVALID")
        result = cls(**normalized)
        if result.wall_settlement_reserve_seconds >= result.wall_seconds:
            raise ManagedStageError("WALL_SETTLEMENT_RESERVE_INVALID")
        if result.cpu_settlement_reserve_seconds >= result.total_cpu_seconds:
            raise ManagedStageError("CPU_SETTLEMENT_RESERVE_INVALID")
        if result.memory_reserve_bytes >= result.memory_max_bytes:
            raise ManagedStageError("MEMORY_SETTLEMENT_RESERVE_INVALID")
        return result

    @property
    def work_wall_seconds(self) -> float:
        return self.wall_seconds - self.wall_settlement_reserve_seconds

    @property
    def work_cpu_seconds(self) -> float:
        return self.total_cpu_seconds - self.cpu_settlement_reserve_seconds

    @property
    def work_memory_bytes(self) -> int:
        return self.memory_max_bytes - self.memory_reserve_bytes


class ServiceCgroup:
    def __init__(self, *, cgroup_root: pathlib.Path = pathlib.Path("/sys/fs/cgroup"),
                 proc_cgroup: pathlib.Path = pathlib.Path("/proc/self/cgroup"),
                 unit: str, expected_memory_max: int, max_cpu_quota_percent: int):
        if os.name != "posix" or not pathlib.Path("/proc").is_dir():
            raise ManagedStageError("LINUX_CGROUP_V2_REQUIRED")
        rows = [line.partition("::")[2] for line in proc_cgroup.read_text(encoding="ascii").splitlines()
                if line.startswith("0::")]
        if len(rows) != 1:
            raise ManagedStageError("UNIFIED_CGROUP_PATH_INVALID")
        root = cgroup_root.resolve(strict=True)
        path = (root / rows[0].lstrip("/")).resolve(strict=True)
        if root not in path.parents or path.name != unit:
            raise ManagedStageError("SYSTEMD_UNIT_CGROUP_IDENTITY_MISMATCH")
        self.path = path
        self.unit = unit
        self.expected_memory_max = expected_memory_max
        self.max_cpu_quota_percent = max_cpu_quota_percent
        self.configuration = self._validate_configuration()

    def _read_int(self, name: str) -> int:
        value = (self.path / name).read_text(encoding="ascii").strip()
        if value == "max" or not value.isdigit():
            raise ManagedStageError("CGROUP_COUNTER_INVALID:" + name)
        return int(value)

    def _validate_configuration(self) -> dict[str, object]:
        cpus = (self.path / "cpuset.cpus.effective").read_text(encoding="ascii").strip()
        if not cpus:
            raise ManagedStageError("UNIT_CPUSET_EMPTY")
        effective = parse_cpu_list(cpus)
        affinity = sorted(os.sched_getaffinity(0))
        if not affinity or not set(affinity).issubset(effective):
            raise ManagedStageError("UNIT_AFFINITY_OUTSIDE_CGROUP_CPUSET")
        quota, period = (self.path / "cpu.max").read_text(encoding="ascii").split()
        if quota == "max" or int(period) <= 0:
            raise ManagedStageError("UNIT_CPU_QUOTA_MISSING")
        quota_percent = int(quota) * 100 / int(period)
        if quota_percent > self.max_cpu_quota_percent + 1e-9:
            raise ManagedStageError("UNIT_CPU_QUOTA_ABOVE_BUDGET")
        memory_max = self._read_int("memory.max")
        if memory_max > self.expected_memory_max:
            raise ManagedStageError("UNIT_MEMORY_MAX_ABOVE_BUDGET")
        if os.getpid() not in {int(value) for value in (self.path / "cgroup.procs").read_text().split()}:
            raise ManagedStageError("SUPERVISOR_NOT_IN_UNIT_CGROUP")
        return {"path": str(self.path), "cpuset_effective": effective,
                "sched_affinity": affinity, "cpu_quota_percent": quota_percent,
                "memory_max_bytes": memory_max}

    def snapshot(self) -> dict[str, object]:
        cpu = {}
        for line in (self.path / "cpu.stat").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(" ")
            if value.isdigit():
                cpu[key] = int(value)
        if "usage_usec" not in cpu:
            raise ManagedStageError("CGROUP_CPU_USAGE_MISSING")
        events = {}
        for line in (self.path / "memory.events").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(" ")
            if value.isdigit():
                events[key] = int(value)
        return {
            "cpu_usage_usec": cpu["usage_usec"],
            "memory_current_bytes": self._read_int("memory.current"),
            "memory_peak_bytes": self._read_int("memory.peak"),
            "memory_events": events,
            "pids": sorted(int(value) for value in (self.path / "cgroup.procs").read_text().split()),
        }


def parse_cpu_list(raw: str) -> list[int]:
    values = set()
    for segment in raw.split(","):
        parts = segment.split("-")
        if len(parts) == 1 and parts[0].isdigit():
            values.add(int(parts[0]))
        elif len(parts) == 2 and all(part.isdigit() for part in parts):
            first, last = map(int, parts)
            if first > last or last - first > 65535:
                raise ManagedStageError("CPUSET_RANGE_INVALID")
            values.update(range(first, last + 1))
        else:
            raise ManagedStageError("CPUSET_SYNTAX_INVALID")
    if not values:
        raise ManagedStageError("CPUSET_EMPTY")
    return sorted(values)


def tree_bytes(*roots: pathlib.Path) -> int:
    total = 0
    for root in roots:
        if not root.exists():
            continue
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [name for name in dirnames if not (pathlib.Path(directory) / name).is_symlink()]
            for name in filenames:
                path = pathlib.Path(directory) / name
                try:
                    if not path.is_symlink() and path.is_file():
                        total += path.stat().st_size
                except FileNotFoundError:
                    continue
    return total


def _atomic_json(path: pathlib.Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _first_error(path: pathlib.Path, error: BaseException) -> dict[str, object]:
    value = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc(),
             "recorded_monotonic": time.monotonic()}
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        return value
    except FileExistsError:
        return json.loads(path.read_text(encoding="utf-8"))


class ManagedStageSupervisor:
    def __init__(self, *, config: Mapping[str, object], cgroup,
                 stage_server_factory: Callable, worker_launcher: Callable,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.config = config
        self.cgroup = cgroup
        self.stage_server_factory = stage_server_factory
        self.worker_launcher = worker_launcher
        self.monotonic = monotonic
        self.sleep = sleep
        self._stop_requested = threading.Event()

    def run(self) -> int:
        work_root = pathlib.Path(self.config["work_root"])
        package_root = pathlib.Path(self.config["package_root"])
        export_root = pathlib.Path(self.config["export_root"])
        resource_request = self.config["resource_request"]
        limits = GuardLimits.from_mapping(self.config["guard_limits"])
        if not isinstance(resource_request, dict) or not resource_request.get("stage_order"):
            raise ManagedStageError("RESOURCE_REQUEST_STAGE_ORDER_REQUIRED")
        started = self.monotonic()
        work_deadline = started + limits.work_wall_seconds
        total_deadline = started + limits.wall_seconds
        cgroup_start = self.cgroup.snapshot()
        stage_server = None
        worker = None
        first_error = None
        last_snapshot = cgroup_start
        stage_rows = []
        peak_storage = 0
        worker_returncode = None
        cleanup = "NOT_REQUIRED"
        receipt_failed = False
        previous_handlers = {}
        if threading.current_thread() is threading.main_thread():
            def request_stop(signum, _frame):
                self._stop_requested.set()
                raise ManagedStageError("SUPERVISOR_SIGNAL:" + str(signum))
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous_handlers[signum] = signal.signal(signum, request_stop)
        try:
            stage_server = self.stage_server_factory(resource_request, started)
            worker = self.worker_launcher(work_root, stage_server)
            while worker.poll() is None:
                if self._stop_requested.is_set():
                    raise ManagedStageError("SUPERVISOR_STOP_REQUESTED")
                now = self.monotonic()
                if now >= work_deadline:
                    raise TimeoutError("MONOTONIC_WALL_GUARD")
                pending = stage_server.process_pending(worker.pid)
                if pending:
                    stage_rows.extend(pending)
                last_snapshot = self.cgroup.snapshot()
                cpu_seconds = last_snapshot["cpu_usage_usec"] / 1_000_000
                storage = tree_bytes(package_root, work_root, export_root)
                peak_storage = max(peak_storage, storage)
                if cpu_seconds >= limits.work_cpu_seconds:
                    raise ManagedStageError("CGROUP_TOTAL_CPU_GUARD")
                if last_snapshot["memory_peak_bytes"] >= limits.work_memory_bytes:
                    raise ManagedStageError("CGROUP_MEMORY_GUARD")
                if storage >= limits.storage_max_bytes:
                    raise ManagedStageError("ACTIVE_STORAGE_GUARD")
                self.sleep(min(limits.sample_interval_seconds, max(0, work_deadline - self.monotonic())))
            worker_returncode = worker.wait()
            if worker_returncode != 0:
                raise ManagedStageError("WORKER_EXIT_STATUS:" + str(worker_returncode))
            if stage_server.stage != resource_request["stage_order"][-1]:
                raise ManagedStageError("STAGE_SERVER_FINAL_STAGE_MISMATCH")
            worker_receipt = json.loads((work_root / "managed-worker-receipt.json").read_text(encoding="utf-8"))
            if (worker_receipt.get("status") != "complete"
                    or worker_receipt.get("settlement") != "complete"
                    or worker_receipt.get("export_status") not in ("complete", "not_requested")
                    or worker_receipt.get("ledger", {}).get("pending_calls") != 0
                    or worker_receipt.get("ledger", {}).get("failed_calls") != 0):
                raise ManagedStageError("WORKER_SETTLEMENT_RECEIPT_INVALID")
            if not worker_receipt.get("stage_server_socket_present") or not stage_server:
                raise ManagedStageError("STAGE_SERVER_NOT_USED_BY_WORKER")
        except BaseException as exc:
            first_error = _first_error(work_root / "managed-first-error.json", exc)
            if worker is not None and worker.poll() is None:
                cleanup = self._stop_worker(worker, total_deadline, limits.stop_grace_seconds)
            if cleanup != "STOPPED" and worker is not None and worker.poll() is None:
                cleanup = "UNKNOWN_WORKER_STILL_RUNNING"
        finally:
            if worker is not None and worker_returncode is None:
                try:
                    worker_returncode = worker.wait(timeout=max(0.0, total_deadline - self.monotonic()))
                except BaseException:
                    cleanup = "UNKNOWN_WORKER_STILL_RUNNING"
            if stage_server is not None:
                try:
                    stage_server.close()
                except BaseException as close_error:
                    if first_error is None:
                        first_error = _first_error(work_root / "managed-first-error.json", close_error)
            try:
                last_snapshot = self.cgroup.snapshot()
            except BaseException:
                cleanup = "UNKNOWN_CGROUP_FINAL_SNAPSHOT"
            final_cpu = last_snapshot["cpu_usage_usec"] / 1_000_000
            final_storage = tree_bytes(package_root, work_root, export_root)
            peak_storage = max(peak_storage, final_storage)
            if last_snapshot.get("pids") != [os.getpid()]:
                if cleanup == "NOT_REQUIRED" or cleanup == "STOPPED":
                    cleanup = "UNKNOWN_CGROUP_HAS_LINGERING_PIDS"
            if any(last_snapshot.get("memory_events", {}).get(key, 0)
                   > cgroup_start.get("memory_events", {}).get(key, 0)
                   for key in ("oom", "oom_kill", "oom_group_kill")):
                if first_error is None:
                    first_error = _first_error(
                        work_root / "managed-first-error.json",
                        ManagedStageError("CGROUP_MEMORY_OOM_EVENT"),
                    )
            if final_cpu >= limits.total_cpu_seconds:
                if first_error is None:
                    first_error = _first_error(work_root / "managed-first-error.json",
                                               ManagedStageError("CGROUP_TOTAL_CPU_SETTLEMENT_GUARD"))
            if last_snapshot.get("memory_peak_bytes", 0) >= limits.memory_max_bytes:
                if first_error is None:
                    first_error = _first_error(work_root / "managed-first-error.json",
                                               ManagedStageError("CGROUP_MEMORY_SETTLEMENT_GUARD"))
            if self.monotonic() - started > limits.wall_seconds:
                if first_error is None:
                    first_error = _first_error(work_root / "managed-first-error.json",
                                               TimeoutError("MONOTONIC_TOTAL_WALL_GUARD"))
            failed = first_error is not None or cleanup.startswith("UNKNOWN")
            status = {
                "schema": "n2-managed-stage-supervisor/1",
                "status": "failed" if failed else "complete",
                "controller_bundle_sha256": self.config.get("controller_bundle_sha256"),
                "systemd_invocation_id": os.environ.get("INVOCATION_ID"),
                "supervisor_pid": os.getpid(),
                "cgroup_configuration": getattr(self.cgroup, "configuration", None),
                "first_error": first_error,
                "cleanup_status": cleanup,
                "worker_returncode": worker_returncode,
                "stage_server_final_stage": getattr(stage_server, "stage", None),
                "stage_server_rows": stage_rows,
                "cgroup_baseline": cgroup_start,
                "cgroup_final": last_snapshot,
                "cgroup_cpu_seconds_total": final_cpu,
                "peak_package_work_export_bytes": peak_storage,
                "wall_seconds_total": self.monotonic() - started,
                "guard_limits": dataclasses.asdict(limits),
                "sampling_interval_seconds": limits.sample_interval_seconds,
                "automatic_retry": False,
            }
            if final_cpu >= limits.total_cpu_seconds or peak_storage >= limits.storage_max_bytes:
                status["status"] = "failed"
                status["resource_limit_status"] = "exceeded_at_settlement"
            try:
                _atomic_json(work_root / "managed-supervisor-receipt.json", status)
            except BaseException as receipt_error:
                receipt_failed = True
                if first_error is None:
                    _first_error(work_root / "managed-first-error.json", receipt_error)
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
        return 0 if status["status"] == "complete" and not receipt_failed else 1

    def _stop_worker(self, worker, deadline: float, grace: float) -> str:
        try:
            os.killpg(worker.pid, signal.SIGTERM)
        except ProcessLookupError:
            return "STOPPED"
        stop_deadline = min(deadline, self.monotonic() + grace)
        while worker.poll() is None and self.monotonic() < stop_deadline:
            self.sleep(min(0.05, stop_deadline - self.monotonic()))
        if worker.poll() is None:
            try:
                os.killpg(worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            worker.wait(timeout=max(0.0, deadline - self.monotonic()))
        except BaseException:
            return "UNKNOWN"
        return "STOPPED"


def validate_resource_request(request: Mapping[str, object]) -> None:
    order = request.get("stage_order")
    stages, totals = request.get("stages"), request.get("totals")
    if (not isinstance(order, list) or not order or len(order) != len(set(order))
            or not isinstance(stages, dict) or set(order) != set(stages) or not isinstance(totals, dict)):
        raise ManagedStageError("RESOURCE_REQUEST_SCHEMA_INVALID")
    if any(not isinstance(stage, str) or not stage for stage in order):
        raise ManagedStageError("RESOURCE_REQUEST_STAGE_INVALID")
    from stage_contract import STAGE_ORDER
    if tuple(order) != tuple(STAGE_ORDER):
        raise ManagedStageError("RESOURCE_REQUEST_W7_STAGE_ORDER_MISMATCH")
    totals = request.get("totals", {})
    stages = request.get("stages", {})
    for resource, amount in totals.items():
        if not isinstance(resource, str) or type(amount) is not int or amount < 0:
            raise ManagedStageError("RESOURCE_REQUEST_TOTAL_INVALID")
    for stage in order:
        for resource, amount in stages[stage].items():
            if (resource not in totals or type(amount) is not int or amount < 0
                    or amount > totals[resource]):
                raise ManagedStageError("RESOURCE_REQUEST_STAGE_CAP_INVALID:" + stage)


def resource_request_from_engineering_profile(profile: Mapping[str, object]) -> dict[str, object]:
    """Build provisional W7 call counters from the local-only engineering profile."""
    runtime = profile.get("runtime")
    caps = profile.get("work_caps")
    if not isinstance(runtime, Mapping) or not isinstance(caps, Mapping):
        raise ManagedStageError("ENGINEERING_PROFILE_SCHEMA_INVALID")
    source_fields = {
        "base_rollout_episodes": (caps, "base_rollout_episodes_max"),
        "episode_constructions": (caps, "episode_constructions_max"),
        "branch_count": (caps, "branch_count_max"),
        "ppo_rollout_episodes": (caps, "ppo_rollout_episodes_max"),
        "environment_steps": (caps, "total_environment_steps_max"),
        "wm_optimizer_steps": (caps, "wm_optimizer_steps_max"),
        "ppo_optimizer_steps": (caps, "ppo_optimizer_steps_max"),
        "world_model_forwards": (caps, "world_model_forwards_max"),
        "world_model_candidate_sample_evaluations": (caps, "world_model_candidate_sample_evaluations_max"),
        "checkpoint_io": (runtime, "checkpoint_reads_and_writes_max"),
        "output_write_operations": (runtime, "output_write_operations_max"),
        "verified_exports": (runtime, "exports_max"),
    }
    totals = {}
    for resource, (source, key) in source_fields.items():
        value = source.get(key)
        if type(value) is not int or value < 0:
            raise ManagedStageError("ENGINEERING_PROFILE_CAP_INVALID:" + key)
        totals[resource] = value

    from stage_contract import STAGE_ORDER
    order = tuple(STAGE_ORDER)
    stages = {stage: {} for stage in order}
    base = totals["base_rollout_episodes"]
    branches = totals["branch_count"]
    catalog_cap = caps.get("candidate_catalog_cap_including_noop")
    if type(catalog_cap) is not int or catalog_cap < 1:
        raise ManagedStageError("ENGINEERING_PROFILE_CAP_INVALID:candidate_catalog_cap_including_noop")
    if caps.get("candidate_truncation_allowed") is not False:
        raise ManagedStageError("CANDIDATE_TRUNCATION_MUST_BE_FORBIDDEN")
    steps_first = totals["environment_steps"] // 2
    wm_forwards_first = totals["world_model_forwards"] // 2
    sample_rows_first = totals["world_model_candidate_sample_evaluations"] // 2
    offline_sample_rows = min(
        catalog_cap,
        totals["world_model_candidate_sample_evaluations"] - sample_rows_first,
    )
    checkpoint_first = totals["checkpoint_io"] // 2
    paired_constructions = max(
        0, totals["episode_constructions"] - 1 - totals["ppo_rollout_episodes"]
    )
    paired_output_writes = min(1, totals["output_write_operations"])
    output_quarter = (totals["output_write_operations"] - paired_output_writes) // 4
    stages["input_admission"]["episode_constructions"] = 1
    stages["paired_collection"].update({
        "base_rollout_episodes": base,
        "branch_count": branches,
        "episode_constructions": paired_constructions,
        "environment_steps": steps_first,
        "output_write_operations": paired_output_writes,
    })
    stages["world_training_and_restore"].update({
        "wm_optimizer_steps": totals["wm_optimizer_steps"],
        "world_model_forwards": wm_forwards_first,
        "world_model_candidate_sample_evaluations": sample_rows_first,
        "checkpoint_io": checkpoint_first,
        "output_write_operations": output_quarter,
    })
    stages["offline_prediction"].update({
        "world_model_forwards": min(1, totals["world_model_forwards"] - wm_forwards_first),
        "world_model_candidate_sample_evaluations": offline_sample_rows,
    })
    stages["conditional_policy_training"].update({
        "ppo_rollout_episodes": totals["ppo_rollout_episodes"],
        "episode_constructions": totals["ppo_rollout_episodes"],
        "environment_steps": totals["environment_steps"] - steps_first,
        "ppo_optimizer_steps": totals["ppo_optimizer_steps"],
        "world_model_forwards": totals["world_model_forwards"] - wm_forwards_first
        - stages["offline_prediction"]["world_model_forwards"],
        "world_model_candidate_sample_evaluations": totals["world_model_candidate_sample_evaluations"] - sample_rows_first - offline_sample_rows,
        "checkpoint_io": totals["checkpoint_io"] - checkpoint_first,
        "output_write_operations": output_quarter,
    })
    stages["analysis_and_settlement"]["output_write_operations"] = (
        totals["output_write_operations"] - paired_output_writes - 2 * output_quarter
    )
    stages["settlement_and_verified_export"]["verified_exports"] = totals["verified_exports"]
    request = {
        "stage_order": list(order),
        "stages": stages,
        "totals": totals,
        "admission_guards": {
            "candidate_catalog_size_including_noop_max": caps.get("candidate_catalog_cap_including_noop"),
            "candidate_truncation_allowed": caps.get("candidate_truncation_allowed"),
        },
        "status": "PROVISIONAL_LOCAL_ENGINEERING_ONLY",
    }
    validate_resource_request(request)
    for resource, total in totals.items():
        if sum(stage.get(resource, 0) for stage in stages.values()) > total:
            raise ManagedStageError("ENGINEERING_STAGE_ALLOCATION_EXCEEDS_TOTAL:" + resource)
    return request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Linux managed N2 stage supervisor")
    parser.add_argument("--config", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    request = config["resource_request"]
    validate_resource_request(request)
    package_root = pathlib.Path(config["package_root"]).resolve(strict=True)
    work_root = pathlib.Path(config["work_root"]).resolve(strict=True)
    export_root = pathlib.Path(config["export_root"])
    controller_root = pathlib.Path(config["controller_root"]).resolve(strict=True)
    vendor_root = controller_root / "vendor"
    sys.path[:0] = [str(vendor_root), str(controller_root)]
    import linux_process_scope
    from phase_handshake import StageServer
    request_path = work_root / "RESOURCE_REQUEST.json"
    _atomic_json(request_path, request)
    worker_config = {
        "worker_path": str(pathlib.Path(config["worker_path"]).resolve(strict=True)),
        "worker_sha256": config["worker_sha256"],
        "worker_callable": config.get("worker_callable", "managed_worker"),
        "work_root": str(work_root),
        "export_root": str(export_root),
        "resource_request_path": str(request_path),
        "w7_infrastructure": str(vendor_root),
    }
    worker_config_path = work_root / "managed-worker-config.json"
    _atomic_json(worker_config_path, worker_config)
    linux_process_scope.enable_subreaper()
    controller_root.mkdir(parents=True, exist_ok=True)
    clock_ticks = int(os.sysconf("SC_CLK_TCK"))
    if clock_ticks <= 0:
        raise ManagedStageError("CPU_CLOCK_TICKS_INVALID")
    started = time.monotonic()

    def stage_server_factory(req, wall):
        origin = linux_process_scope.tree_cpu_ticks(
            linux_process_scope.proc_tree(os.getpid())
        ) / clock_ticks
        return StageServer(
            work_root / ".phase-accounting.sock", req,
            tree_reader=linux_process_scope.proc_tree,
            cpu_origin_seconds=origin, wall_origin_monotonic=wall,
            journal_path=work_root / "supervisor-phase-protocol.jsonl",
        )

    def launch_worker(root, server):
        environment = {
            **os.environ,
            "W1_PHASE_ACCOUNTING_SOCKET": str(server.path),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        with (root / "managed-worker.log").open("xb") as log:
            return subprocess.Popen(
                [sys.executable, "-B", str(controller_root / "managed_worker_entry.py"),
                 "--supervisor-pid", str(os.getpid()), "--config", str(worker_config_path)],
                cwd=root, env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True,
            )

    unit = str(config["systemd_unit"])
    runtime = config["guard_limits"]
    cgroup = ServiceCgroup(unit=unit, expected_memory_max=int(runtime["cgroup_memory_max_bytes"]),
                           max_cpu_quota_percent=int(runtime["cpu_quota_percent"]))
    initial = cgroup._validate_configuration()
    return ManagedStageSupervisor(config=config, cgroup=cgroup,
                                  stage_server_factory=stage_server_factory,
                                  worker_launcher=launch_worker).run()


if __name__ == "__main__":
    raise SystemExit(main())
