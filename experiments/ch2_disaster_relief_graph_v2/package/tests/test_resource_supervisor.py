from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resource_supervisor import (
    BudgetExceeded,
    CARRY_FORWARD_RECEIPT_NAME,
    STAGE_LIMITS,
    TOTAL_CPU_LIMIT,
    TOTAL_WALL_LIMIT,
    ResourceSupervisor,
    _read_prior_resource_cost,
    ledger_summary,
)
from driver import _execute_stage


class ResourceSupervisorTests(unittest.TestCase):
    def test_stage_and_pilot_limits_match_frozen_allocation(self) -> None:
        self.assertEqual(sum(wall for wall, _ in STAGE_LIMITS.values()), TOTAL_WALL_LIMIT)
        self.assertEqual(sum(cpu for _, cpu in STAGE_LIMITS.values()), TOTAL_CPU_LIMIT)

    def test_entries_accumulate_across_invocations_and_keep_first_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger.jsonl"
            first = ResourceSupervisor("admission", ledger, (root,))
            first.check()
            first_row = first.finish(status="failed", error="injected first failure")
            self.assertEqual(first_row["first_error"], "injected first failure")

            second = ResourceSupervisor("engineering_smoke", ledger, (root,))
            second.check()
            second_row = second.finish(status="complete")
            self.assertGreaterEqual(second_row["pilot_cpu_used_including_this"], first_row["cpu_seconds"])

            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["stage"] for row in rows], ["admission", "engineering_smoke"])
            summary = ledger_summary(ledger)
            self.assertEqual(summary["entries"], rows)
            self.assertFalse(summary["all_successful"])

    def test_accepted_admission_counts_as_successful(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supervisor = ResourceSupervisor("admission", root / "ledger.jsonl", (root,))
            supervisor.finish(status="accepted")
            supervisor.close()
            self.assertTrue(ledger_summary(root / "ledger.jsonl")["all_successful"])

    def test_prior_cost_receipt_is_verified_and_debited_by_stage_and_pilot(self) -> None:
        receipt_path = Path(__file__).resolve().parents[1] / CARRY_FORWARD_RECEIPT_NAME
        prior = _read_prior_resource_cost(receipt_path, required=True)
        self.assertAlmostEqual(prior["stage_costs"]["admission"]["wall_seconds"], 5.357756602210641)
        self.assertAlmostEqual(prior["stage_costs"]["admission"]["cpu_seconds"], 2.771441418)
        self.assertAlmostEqual(prior["stage_costs"]["shutdown"]["wall_seconds"], 0.3769723977893591)
        self.assertAlmostEqual(prior["total_wall_seconds"], 5.734729)
        self.assertAlmostEqual(prior["total_cpu_seconds"], 2.914629)
        self.assertIsNotNone(prior["receipt_sha256"])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "resource-ledger.jsonl"
            summary = ledger_summary(ledger, receipt_path)
            self.assertAlmostEqual(summary["stage_wall_seconds"]["admission"], 5.357756602210641)
            self.assertAlmostEqual(summary["stage_cpu_seconds"]["shutdown"], 0.143187582)
            self.assertAlmostEqual(summary["total_wall_seconds"], 5.734729)
            self.assertAlmostEqual(summary["total_cpu_seconds"], 2.914629)
            supervisor = ResourceSupervisor(
                "shutdown",
                ledger,
                (root,),
                interrupt_on_violation=False,
                prior_cost_path=receipt_path,
            )
            row = supervisor.finish(status="failed", error="accounting test")
            supervisor.close()
            self.assertGreaterEqual(row["stage_wall_used_including_this"], 0.3769723977893591)
            self.assertGreaterEqual(row["pilot_cpu_used_including_this"], 2.914629)
            self.assertEqual(row["metadata"]["prior_resource_cost_sha256"], prior["receipt_sha256"])

    def test_explicit_missing_prior_cost_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / CARRY_FORWARD_RECEIPT_NAME
            with self.assertRaisesRegex(FileNotFoundError, "required prior resource-cost receipt"):
                _read_prior_resource_cost(missing, required=True)
            with self.assertRaisesRegex(FileNotFoundError, "required prior resource-cost receipt"):
                ResourceSupervisor("admission", Path(temporary) / "ledger.jsonl", (), prior_cost_path=missing)

    def test_tampered_prior_evidence_is_rejected(self) -> None:
        source_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            package.mkdir()
            shutil.copy2(source_root / CARRY_FORWARD_RECEIPT_NAME, package / CARRY_FORWARD_RECEIPT_NAME)
            (package / "diagnostics").mkdir()
            shutil.copytree(source_root / "diagnostics" / "prior-v1", package / "diagnostics" / "prior-v1")
            receipt_path = package / CARRY_FORWARD_RECEIPT_NAME
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            tampered = package / receipt["evidence_roles"]["resource_ledger"]
            with tampered.open("ab") as handle:
                handle.write(b"tampered\n")
            with self.assertRaisesRegex(ValueError, "evidence hash mismatch"):
                _read_prior_resource_cost(receipt_path, required=True)

    def test_carried_stage_costs_accumulate_across_invocations(self) -> None:
        receipt_path = Path(__file__).resolve().parents[1] / CARRY_FORWARD_RECEIPT_NAME
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "resource-ledger.jsonl"
            first = ResourceSupervisor(
                "admission",
                ledger,
                (root,),
                interrupt_on_violation=False,
                prior_cost_path=receipt_path,
            )
            first_row = first.finish(status="failed", error="first invocation")
            first.close()
            stored_first = json.loads(ledger.read_text(encoding="utf-8"))

            second = ResourceSupervisor(
                "admission",
                ledger,
                (root,),
                interrupt_on_violation=False,
                prior_cost_path=receipt_path,
            )
            self.assertAlmostEqual(
                second._prior_stage_wall,
                5.357756602210641 + stored_first["wall_seconds"],
            )
            second_row = second.finish(status="failed", error="second invocation")
            second.close()
            self.assertGreaterEqual(
                second_row["stage_wall_used_including_this"],
                5.357756602210641 + stored_first["wall_seconds"],
            )
            self.assertGreaterEqual(
                second_row["pilot_cpu_used_including_this"],
                2.914629 + stored_first["cpu_seconds"],
            )
            self.assertGreater(first_row["wall_seconds"], 0.0)

    def test_invalid_stage_is_rejected_before_any_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                ResourceSupervisor("unknown", root / "ledger.jsonl", (root,))
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_finish_forces_a_final_disk_check_before_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supervisor = ResourceSupervisor(
                "shutdown", root / "ledger.jsonl", (root,), disk_limit_bytes=0
            )
            (root / "late-output.bin").write_bytes(b"over limit")

            with self.assertRaisesRegex(BudgetExceeded, "work/export storage") as caught:
                supervisor.finish(status="complete")

            row = supervisor.finish(status="failed", error=caught.exception)
            self.assertEqual(row["status"], "failed")
            self.assertIn("work/export storage", row["first_error"])

    def test_initial_rss_excess_is_settled_as_a_failed_stage(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            work_root = Path(temporary) / "initial-rss-over-limit"

            class ZeroRSSLimitSupervisor(ResourceSupervisor):
                def __init__(self, stage, ledger_path, storage_roots, **kwargs):
                    super().__init__(
                        stage,
                        ledger_path,
                        storage_roots,
                        rss_limit_bytes=0,
                        interrupt_on_violation=False,
                        **kwargs,
                    )

            action_called = False

            def action(_supervisor):
                nonlocal action_called
                action_called = True
                return {"status": "complete"}

            with patch("driver.ResourceSupervisor", ZeroRSSLimitSupervisor):
                with self.assertRaisesRegex(BudgetExceeded, "RSS"):
                    _execute_stage("shutdown", package_root, work_root, action)

            receipt = json.loads((work_root / "receipts" / "01-shutdown.json").read_text(encoding="utf-8"))
            ledger = json.loads((work_root / "resource-ledger.jsonl").read_text(encoding="utf-8"))
            self.assertFalse(action_called)
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("RSS", receipt["first_error"])
            self.assertEqual(ledger["status"], "failed")
            self.assertIn("VmHWM" if Path("/proc/self/status").is_file() else "high-water", ledger["rss_high_water_source"])

    def test_monitor_polls_high_water_rss_between_explicit_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "ledger.jsonl"
            reads = {"count": 0}

            def fake_rss_metrics():
                reads["count"] += 1
                high_water = 200 if reads["count"] >= 3 else 100
                return 100, high_water

            with patch("resource_supervisor._read_rss_metrics", side_effect=fake_rss_metrics):
                supervisor = ResourceSupervisor(
                    "shutdown",
                    ledger,
                    (root,),
                    rss_limit_bytes=150,
                    monitor_interval_seconds=0.01,
                    interrupt_on_violation=False,
                )
                supervisor.start_monitor()
                self.assertTrue(supervisor._monitor_violation.wait(1.0))
                self.assertIn("RSS", supervisor._first_error or "")
                self.assertEqual(supervisor._peak_rss, 200)
                supervisor.finish(status="failed", error=supervisor._first_error)
                row = supervisor.close()

            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["peak_rss_bytes"], 200)


if __name__ == "__main__":
    unittest.main()
