from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from managed_stage_supervisor import GuardLimits, ManagedStageError, ManagedStageSupervisor
from vendor.stage_contract import STAGE_ORDER


class FakeCgroup:
    def __init__(self, snapshots):
        self.snapshots = iter(snapshots)
        self.last = None

    def snapshot(self):
        try:
            self.last = next(self.snapshots)
        except StopIteration:
            pass
        return dict(self.last)


class FakeStageServer:
    stage = STAGE_ORDER[-1]

    def process_pending(self, _worker_pid):
        return []

    def close(self):
        pass


class FakeWorker:
    pid = 765432

    def __init__(self, work_root):
        self.work_root = work_root
        self.returncode = None
        self.poll_count = 0

    def poll(self):
        self.poll_count += 1
        if self.poll_count == 2 and self.returncode is None:
            receipt = {
                "status": "complete",
                "settlement": "complete",
                "export_status": "not_requested",
                "stage_server_socket_present": True,
                "ledger": {"pending_calls": 0, "failed_calls": 0},
            }
            (self.work_root / "managed-worker-receipt.json").write_text(
                json.dumps(receipt), encoding="utf-8"
            )
            self.returncode = 0
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = -15
        return self.returncode


class ManagedStageSupervisorContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.work = self.root / "work"
        self.package = self.root / "package"
        self.export = self.root / "export"
        for path in (self.work, self.package, self.export):
            path.mkdir()
        self.config = {
            "work_root": str(self.work),
            "package_root": str(self.package),
            "export_root": str(self.export),
            "resource_request": {"stage_order": list(STAGE_ORDER),
                                 "stages": {stage: {} for stage in STAGE_ORDER}, "totals": {}},
            "guard_limits": {
                "wall_seconds_total_including_settlement": 10,
                "settlement_reserve_seconds": 2,
                "complete_process_cpu_seconds_total_including_descendants_and_settlement": 5,
                "settlement_cpu_reserve_seconds": 1,
                "cgroup_memory_max_bytes": 1000,
                "memory_settlement_reserve_bytes": 100,
                "combined_working_plus_export_peak_bytes_max": 10000,
                "sample_interval_seconds": 0.001,
                "stop_grace_seconds": 0.01,
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_supervisor(self, cpu_values):
        worker = FakeWorker(self.work)
        cgroup = FakeCgroup([
            {"cpu_usage_usec": cpu_values[0], "memory_peak_bytes": 100,
             "memory_events": {}, "pids": [__import__("os").getpid()]},
            {"cpu_usage_usec": cpu_values[1], "memory_peak_bytes": 100,
             "memory_events": {}, "pids": [__import__("os").getpid()]},
            {"cpu_usage_usec": cpu_values[2], "memory_peak_bytes": 100,
             "memory_events": {}, "pids": [__import__("os").getpid()]},
        ])
        supervisor = ManagedStageSupervisor(
            config=self.config,
            cgroup=cgroup,
            stage_server_factory=lambda *_: FakeStageServer(),
            worker_launcher=lambda *_: worker,
            sleep=lambda _seconds: None,
        )
        return supervisor.run(), worker

    def test_fake_worker_settlement_is_recorded_as_contract_only(self):
        code, _worker = self.run_supervisor((10, 20, 30))
        receipt = json.loads((self.work / "managed-supervisor-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0, (self.work / "managed-supervisor-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["stage_server_final_stage"], STAGE_ORDER[-1])
        self.assertEqual(receipt["cgroup_cpu_seconds_total"], 0.00003)

    def test_fake_cgroup_cpu_guard_stops_and_records_first_error(self):
        worker = FakeWorker(self.work)
        cgroup = FakeCgroup([
            {"cpu_usage_usec": 0, "memory_peak_bytes": 100, "memory_events": {},
             "pids": [__import__("os").getpid()]},
            {"cpu_usage_usec": 4_000_000, "memory_peak_bytes": 100, "memory_events": {},
             "pids": [__import__("os").getpid()]},
            {"cpu_usage_usec": 4_000_000, "memory_peak_bytes": 100, "memory_events": {},
             "pids": [__import__("os").getpid()]},
        ])
        supervisor = ManagedStageSupervisor(
            config=self.config,
            cgroup=cgroup,
            stage_server_factory=lambda *_: FakeStageServer(),
            worker_launcher=lambda *_: worker,
            sleep=lambda _seconds: None,
        )
        with patch("managed_stage_supervisor.os.killpg", create=True):
            code = supervisor.run()
        receipt = json.loads((self.work / "managed-supervisor-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["status"], "failed")
        first_error = json.loads((self.work / "managed-first-error.json").read_text(encoding="utf-8"))
        self.assertEqual(first_error["message"], "CGROUP_TOTAL_CPU_GUARD")

    def test_guard_limits_reject_nonfinite_values_and_noninteger_byte_caps(self):
        baseline = dict(self.config["guard_limits"])
        invalid = (
            ("wall_seconds_total_including_settlement", float("nan")),
            ("complete_process_cpu_seconds_total_including_descendants_and_settlement", float("inf")),
            ("cgroup_memory_max_bytes", 1000.0),
            ("combined_working_plus_export_peak_bytes_max", 10000.5),
        )
        for field, value in invalid:
            with self.subTest(field=field):
                with self.assertRaises(ManagedStageError):
                    GuardLimits.from_mapping({**baseline, field: value})


if __name__ == "__main__":
    unittest.main()
