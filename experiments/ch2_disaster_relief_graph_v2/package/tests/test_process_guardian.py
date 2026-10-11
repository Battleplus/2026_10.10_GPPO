from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import process_guardian
from process_guardian import _ProcRSSMissing, _ProcZombie, _process_started_at, _proc_metrics, run_guarded_stage


NO_PRIOR_COST = {
    "stage_costs": {},
    "total_wall_seconds": 0.0,
    "total_cpu_seconds": 0.0,
    "receipt_sha256": None,
}


def _proc_stat(*, user_ticks: int = 300, system_ticks: int = 200, start_ticks: int = 9500, state: str = "S") -> str:
    fields = [state] + ["0"] * 20
    fields[11] = str(user_ticks)
    fields[12] = str(system_ticks)
    fields[19] = str(start_ticks)
    return f"4242 (python worker) {' '.join(fields)}"


def _ledger_row(stage: str, receipt: str, *, first_error: str | None = None) -> dict:
    return {
        "schema": "resource-ledger-entry/1",
        "stage": stage,
        "status": "failed" if first_error else "complete",
        "started_wall_monotonic": 99.0,
        "finished_wall_monotonic": 99.5,
        "wall_seconds": 0.5,
        "cpu_seconds": 0.02,
        "first_error": first_error,
        "metadata": {"receipt": receipt},
    }


class ProcessGuardianTests(unittest.TestCase):
    def test_process_start_conversion_uses_monotonic_epoch(self) -> None:
        uptime = "1000.00 42.00\n"
        stat = _proc_stat()

        def read_text(path: Path, encoding: str = "utf-8") -> str:
            if path.as_posix() == "/proc/uptime":
                return uptime
            if path.as_posix() == "/proc/self/stat":
                return stat
            raise AssertionError(path)

        with (
            patch.object(Path, "read_text", read_text),
            patch("process_guardian.os.sysconf", return_value=100, create=True),
            patch("process_guardian.time.monotonic", return_value=2500.0),
            patch("process_guardian.time.process_time", return_value=20.0),
        ):
            started_wall, started_cpu = _process_started_at()

        self.assertAlmostEqual(started_wall, 1595.0)
        self.assertAlmostEqual(started_cpu, 15.0)

    def test_proc_zombie_without_rss_is_distinguished_from_malformed_status(self) -> None:
        stat = _proc_stat()

        def read_text(path: Path, encoding: str = "utf-8") -> str:
            if path.as_posix() == "/proc/4242/status":
                return "Name:\tpython\nState:\tZ (zombie)\n"
            if path.as_posix() == "/proc/4242/stat":
                return _proc_stat(state="S")
            raise AssertionError(path)

        with patch.object(Path, "read_text", read_text), patch("process_guardian.os.sysconf", return_value=100, create=True):
            with self.assertRaises(_ProcZombie) as caught:
                _proc_metrics(4242)
            self.assertAlmostEqual(caught.exception.cpu_seconds, 5.0)

        def malformed_read(path: Path, encoding: str = "utf-8") -> str:
            if path.as_posix() == "/proc/4242/status":
                return "Name:\tpython\nState:\tR (running)\n"
            if path.as_posix() == "/proc/4242/stat":
                return stat
            raise AssertionError(path)

        with patch.object(Path, "read_text", malformed_read), patch("process_guardian.os.sysconf", return_value=100, create=True):
            with self.assertRaisesRegex(RuntimeError, "RSS fields missing"):
                _proc_metrics(4242)

    def test_non_zombie_status_followed_by_zombie_stat_is_an_exit_race(self) -> None:
        def read_text(path: Path, encoding: str = "utf-8") -> str:
            if path.as_posix() == "/proc/4242/status":
                return "Name:\tpython\nState:\tR (running)\n"
            if path.as_posix() == "/proc/4242/stat":
                return _proc_stat(state="Z")
            raise AssertionError(path)

        with patch.object(Path, "read_text", read_text), patch("process_guardian.os.sysconf", return_value=100, create=True):
            with self.assertRaises(_ProcZombie) as caught:
                _proc_metrics(4242)
        self.assertEqual(caught.exception.state, "R")
        self.assertAlmostEqual(caught.exception.cpu_seconds, 5.0)

    def test_wait4_confirms_exit_after_non_zombie_rss_missing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            work = root / "work"
            package.mkdir()
            work.mkdir()
            child_pid = 4242
            receipt_path = work / "receipts" / "01-shutdown.json"
            receipt_path.parent.mkdir()
            receipt_path.write_text('{"schema":"driver-stage-receipt/1","stage":"shutdown","status":"complete","first_error":null}\n', encoding="utf-8")
            row = _ledger_row("shutdown", "receipts/01-shutdown.json")
            ledger_path = work / "resource-ledger.jsonl"
            process = types.SimpleNamespace(pid=child_pid, returncode=None)
            usage = types.SimpleNamespace(ru_utime=0.01, ru_stime=0.01, ru_maxrss=4)
            wait_results = [(0, 0, None), (0, 0, None), (child_pid, 0, usage)]

            def start_child(*_args, **_kwargs):
                receipt_path.write_text('{"schema":"driver-stage-receipt/1","stage":"shutdown","status":"complete","first_error":null}\n', encoding="utf-8")
                ledger_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                return process

            def proc_metrics(pid: int) -> dict[str, int]:
                if pid == child_pid:
                    raise _ProcRSSMissing(child_pid, "R", 0.05)
                return {"rss_bytes": 100, "rss_hwm_bytes": 120, "cpu_seconds": 0}

            with (
                patch("process_guardian.sys.platform", "linux"),
                patch("process_guardian._process_started_at", return_value=(100.0, 0.0)),
                patch("process_guardian._read_prior_resource_cost", return_value=NO_PRIOR_COST),
                patch("process_guardian.subprocess.Popen", side_effect=start_child),
                patch("process_guardian.os.wait4", side_effect=wait_results, create=True) as wait4,
                patch("process_guardian.os.WNOHANG", 1, create=True),
                patch("process_guardian.os.waitstatus_to_exitcode", return_value=0),
                patch("process_guardian._proc_metrics", side_effect=proc_metrics),
                patch("process_guardian.time.monotonic", return_value=100.2),
                patch("process_guardian.time.process_time", return_value=0.1),
                patch("process_guardian.time.sleep"),
            ):
                status = run_guarded_stage(
                    argv=["--shutdown", "--package-root", str(package), "--work-root", str(work)],
                    driver_path=package / "driver.py",
                    package_root=package,
                    work_root=work,
                    stage="shutdown",
                    runtime_environment={},
                )

            self.assertEqual(status, 0)
            self.assertEqual(wait4.call_count, 3)
            guardian = json.loads(next((work / "guardians").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(guardian["status"], "complete")
            self.assertEqual(guardian["child_returncode"], 0)
            row = json.loads((work / "resource-ledger.jsonl").read_text(encoding="utf-8"))
            self.assertAlmostEqual(row["wall_seconds"], row["finished_wall_monotonic"] - row["started_wall_monotonic"])
            self.assertGreaterEqual(row["peak_rss_bytes"], usage.ru_maxrss * 1024 + 100)

    def test_live_child_missing_rss_is_failed_and_reaped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            work = root / "work"
            package.mkdir()
            work.mkdir()
            child_pid = 4242
            process = types.SimpleNamespace(pid=child_pid, returncode=None)
            usage = types.SimpleNamespace(ru_utime=0.02, ru_stime=0.01, ru_maxrss=8)
            receipt_path = work / "receipts" / "01-shutdown.json"
            receipt_path.parent.mkdir()
            row = _ledger_row("shutdown", "receipts/01-shutdown.json")
            waits = {"nonblocking": 0}

            def wait4(_pid: int, options: int):
                if options:
                    waits["nonblocking"] += 1
                    return 0, 0, None
                return child_pid, 9, usage

            def start_child(*_args, **_kwargs):
                receipt_path.write_text(json.dumps({
                    "schema": "driver-stage-receipt/1",
                    "stage": "shutdown",
                    "status": "complete",
                    "first_error": None,
                }) + "\n", encoding="utf-8")
                (work / "resource-ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
                return process

            def proc_metrics(pid: int) -> dict[str, int]:
                if pid == child_pid:
                    raise _ProcRSSMissing(child_pid, "R", 0.05)
                return {"rss_bytes": 100, "rss_hwm_bytes": 120, "cpu_seconds": 0}

            with (
                patch("process_guardian.sys.platform", "linux"),
                patch("process_guardian._process_started_at", return_value=(100.0, 0.0)),
                patch("process_guardian._read_prior_resource_cost", return_value=NO_PRIOR_COST),
                patch("process_guardian.subprocess.Popen", side_effect=start_child),
                patch("process_guardian.os.wait4", side_effect=wait4, create=True) as wait4_mock,
                patch("process_guardian.os.WNOHANG", 1, create=True),
                patch("process_guardian.os.waitstatus_to_exitcode", return_value=-9),
                patch("process_guardian.os.kill", create=True),
                patch("process_guardian.signal.SIGKILL", 9, create=True),
                patch("process_guardian._proc_metrics", side_effect=proc_metrics),
                patch("process_guardian.time.monotonic", return_value=100.2),
                patch("process_guardian.time.process_time", return_value=0.1),
                patch("process_guardian.time.sleep") as sleep,
            ):
                status = run_guarded_stage(
                    argv=["--shutdown"],
                    driver_path=package / "driver.py",
                    package_root=package,
                    work_root=work,
                    stage="shutdown",
                    runtime_environment={},
                )

            guardian = json.loads(next((work / "guardians").glob("*.json")).read_text(encoding="utf-8"))
            self.assertNotEqual(status, 0)
            self.assertEqual(waits["nonblocking"], 1 + 11)
            self.assertEqual(wait4_mock.call_count, 13)
            self.assertEqual(sleep.call_count, 10)
            self.assertEqual(guardian["status"], "failed")
            self.assertIn("RSS fields missing", guardian["first_error"])
            self.assertEqual(guardian["child_returncode"], -9)
            self.assertGreaterEqual(guardian["peak_process_group_rss_bytes"], usage.ru_maxrss * 1024 + 100)

    def test_guardian_rss_failure_is_not_accepted_when_child_is_reapable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            work = root / "work"
            package.mkdir()
            work.mkdir()
            child_pid = 4242
            guardian_pid = os.getpid()
            process = types.SimpleNamespace(pid=child_pid, returncode=None)
            usage = types.SimpleNamespace(ru_utime=0.01, ru_stime=0.01, ru_maxrss=4)
            receipt_path = work / "receipts" / "01-shutdown.json"
            receipt_path.parent.mkdir()
            row = _ledger_row("shutdown", "receipts/01-shutdown.json")
            wait_results = [(0, 0, None), (child_pid, 0, usage)]
            samples = {"guardian": 0}

            def start_child(*_args, **_kwargs):
                receipt_path.write_text(json.dumps({
                    "schema": "driver-stage-receipt/1",
                    "stage": "shutdown",
                    "status": "complete",
                    "first_error": None,
                }) + "\n", encoding="utf-8")
                (work / "resource-ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
                return process

            def proc_metrics(pid: int) -> dict[str, int]:
                if pid == guardian_pid:
                    samples["guardian"] += 1
                    if samples["guardian"] == 2:
                        raise _ProcRSSMissing(pid, "R", 0.03)
                return {"rss_bytes": 100, "rss_hwm_bytes": 120, "cpu_seconds": 0}

            with (
                patch("process_guardian.sys.platform", "linux"),
                patch("process_guardian._process_started_at", return_value=(100.0, 0.0)),
                patch("process_guardian._read_prior_resource_cost", return_value=NO_PRIOR_COST),
                patch("process_guardian.subprocess.Popen", side_effect=start_child),
                patch("process_guardian.os.wait4", side_effect=wait_results, create=True),
                patch("process_guardian.os.WNOHANG", 1, create=True),
                patch("process_guardian.os.waitstatus_to_exitcode", return_value=0),
                patch("process_guardian.os.kill", create=True),
                patch("process_guardian.signal.SIGKILL", 9, create=True),
                patch("process_guardian._proc_metrics", side_effect=proc_metrics),
                patch("process_guardian.time.monotonic", return_value=100.2),
                patch("process_guardian.time.process_time", return_value=0.1),
            ):
                status = run_guarded_stage(
                    argv=["--shutdown"],
                    driver_path=package / "driver.py",
                    package_root=package,
                    work_root=work,
                    stage="shutdown",
                    runtime_environment={},
                )

            guardian = json.loads(next((work / "guardians").glob("*.json")).read_text(encoding="utf-8"))
            self.assertNotEqual(status, 0)
            self.assertEqual(guardian["status"], "failed")
            self.assertIn("RSS fields missing", guardian["first_error"])
            self.assertEqual(guardian["child_returncode"], 0)

    def test_missing_child_settlement_gets_a_receipt_without_overwriting_empty_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            work = root / "work"
            package.mkdir()
            work.mkdir()
            child_pid = 4242
            process = types.SimpleNamespace(pid=child_pid, returncode=None)
            usage = types.SimpleNamespace(ru_utime=0.0, ru_stime=0.0, ru_maxrss=1)

            with (
                patch("process_guardian.sys.platform", "linux"),
                patch("process_guardian._process_started_at", return_value=(100.0, 0.0)),
                patch("process_guardian._read_prior_resource_cost", return_value=NO_PRIOR_COST),
                patch("process_guardian.subprocess.Popen", return_value=process),
                patch("process_guardian.os.wait4", return_value=(child_pid, 256, usage), create=True),
                patch("process_guardian.os.WNOHANG", 1, create=True),
                patch("process_guardian.os.waitstatus_to_exitcode", return_value=1),
                patch("process_guardian._proc_metrics", return_value={"rss_bytes": 100, "rss_hwm_bytes": 120, "cpu_seconds": 0}),
                patch("process_guardian.time.monotonic", return_value=100.2),
                patch("process_guardian.time.process_time", return_value=0.1),
            ):
                status = run_guarded_stage(
                    argv=["--shutdown"],
                    driver_path=package / "driver.py",
                    package_root=package,
                    work_root=work,
                    stage="shutdown",
                    runtime_environment={},
                )

            receipt = json.loads((work / "receipts" / "01-shutdown.json").read_text(encoding="utf-8"))
            self.assertNotEqual(status, 0)
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("no settled child stage entry", receipt["first_error"])

    def test_child_first_error_survives_later_outer_guard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            work = root / "work"
            package.mkdir()
            work.mkdir()
            child_pid = 4242
            child_error = "RuntimeError: child primary"
            receipt_path = work / "receipts" / "01-shutdown.json"
            receipt_path.parent.mkdir()
            row = _ledger_row("shutdown", "receipts/01-shutdown.json", first_error=child_error)
            process = types.SimpleNamespace(pid=child_pid, returncode=None)
            usage = types.SimpleNamespace(ru_utime=0.0, ru_stime=0.0, ru_maxrss=1)
            wait_results = [(0, 0, None), (child_pid, 9, usage)]

            def start_child(*_args, **_kwargs):
                receipt_path.write_text(json.dumps({
                    "schema": "driver-stage-receipt/1",
                    "stage": "shutdown",
                    "status": "failed",
                    "first_error": child_error,
                }) + "\n", encoding="utf-8")
                (work / "resource-ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
                return process

            with (
                patch("process_guardian.sys.platform", "linux"),
                patch("process_guardian._process_started_at", return_value=(100.0, 0.0)),
                patch("process_guardian._read_prior_resource_cost", return_value=NO_PRIOR_COST),
                patch("process_guardian.subprocess.Popen", side_effect=start_child),
                patch("process_guardian.os.wait4", side_effect=wait_results, create=True),
                patch("process_guardian.os.WNOHANG", 1, create=True),
                patch("process_guardian.os.waitstatus_to_exitcode", return_value=-9),
                patch("process_guardian.os.kill", create=True),
                patch("process_guardian.signal.SIGKILL", 9, create=True),
                patch("process_guardian._proc_metrics", return_value={"rss_bytes": 100, "rss_hwm_bytes": 120, "cpu_seconds": 0}),
                patch("process_guardian.time.monotonic", return_value=100.2),
                patch("process_guardian.time.process_time", return_value=0.1),
                patch("process_guardian.RSS_LIMIT_BYTES", 0),
            ):
                status = run_guarded_stage(
                    argv=["--shutdown"],
                    driver_path=package / "driver.py",
                    package_root=package,
                    work_root=work,
                    stage="shutdown",
                    runtime_environment={},
                )

            settled = json.loads((work / "receipts" / "01-shutdown.json").read_text(encoding="utf-8"))
            guardian = json.loads(next((work / "guardians").glob("*.json")).read_text(encoding="utf-8"))
            self.assertNotEqual(status, 0)
            self.assertEqual(settled["first_error"], child_error)
            self.assertIn("RSS", guardian["outer_guardian_kill_reason"])
            self.assertEqual(guardian["first_error"], child_error)

    def test_partial_trailing_ledger_line_is_ignored_during_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.jsonl"
            path.write_text(json.dumps(_ledger_row("shutdown", "receipt.json")) + "\n{" , encoding="utf-8")
            rows = process_guardian._read_ledger_tolerating_partial_tail(path)
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
