import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from driver import (
    REQUIRED_RUNTIME,
    _execute_stage,
    _export_bundle_core,
    _json_write,
    _require_current_runtime_acceptance,
    _runtime_identity,
    _sha256,
    _verify_export_manifest,
    _prepare_fresh_attempt,
)
from driver import _load_torch_numpy
from resource_supervisor import BudgetExceeded, ResourceSupervisor, _disk_bytes


class DriverFailureSettlementTests(unittest.TestCase):
    def test_torch_thread_configuration_is_idempotent(self):
        first_torch, first_numpy = _load_torch_numpy()
        second_torch, second_numpy = _load_torch_numpy()
        self.assertIs(first_torch, second_torch)
        self.assertIs(first_numpy, second_numpy)
        self.assertEqual(second_torch.get_num_threads(), 1)
        self.assertEqual(second_torch.get_num_interop_threads(), 1)

    def test_failed_stage_records_first_error_and_partial_checkpoint(self):
        package_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory:
            work_root = Path(temporary_directory) / "failure-probe"

            def fail_after_checkpoint(supervisor):
                checkpoint = work_root / "runs" / "partial.pt"
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                checkpoint.write_bytes(b"partial-checkpoint")
                supervisor.check()
                raise RuntimeError("controlled_test_failure")

            with self.assertRaisesRegex(RuntimeError, "controlled_test_failure"):
                _execute_stage("shutdown", package_root, work_root, fail_after_checkpoint)

            receipt_path = work_root / "receipts" / "01-shutdown.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            ledger = json.loads((work_root / "resource-ledger.jsonl").read_text(encoding="utf-8"))

            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["first_error"], "RuntimeError: controlled_test_failure")
            self.assertEqual(receipt["resource_entry"]["status"], "failed")
            self.assertEqual(receipt["partial_checkpoints"][0]["path"], "runs/partial.pt")
            self.assertEqual(ledger["status"], "failed")
            self.assertEqual(ledger["first_error"], "RuntimeError: controlled_test_failure")

    def test_final_budget_overrun_rewrites_success_receipt_as_failure(self):
        package_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory:
            work_root = Path(temporary_directory) / "late-overrun"

            class TightDiskSupervisor(ResourceSupervisor):
                def __init__(self, stage, ledger_path, storage_roots, **kwargs):
                    roots = tuple(Path(root) for root in storage_roots)
                    super().__init__(
                        stage,
                        ledger_path,
                        roots,
                        disk_limit_bytes=_disk_bytes(roots) + 256,
                        **kwargs,
                    )

            def finish_over_limit(supervisor):
                (work_root / "late-output.bin").write_bytes(b"x" * 4096)
                return {"status": "complete"}

            with patch("driver.ResourceSupervisor", TightDiskSupervisor):
                with self.assertRaises(BudgetExceeded):
                    _execute_stage("shutdown", package_root, work_root, finish_over_limit)

            receipt = json.loads((work_root / "receipts" / "01-shutdown.json").read_text(encoding="utf-8"))
            ledger = json.loads((work_root / "resource-ledger.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertIn("work/export storage", receipt["first_error"])
            self.assertEqual(receipt["resource_entry"]["status"], "failed")
            self.assertEqual(ledger["status"], "failed")

    def test_export_core_freezes_a_stable_ledger_snapshot_and_rechecks_files(self):
        package_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            artifact_root = Path(temporary) / "artifacts"
            artifact_root.mkdir()
            ledger_path = artifact_root / "resource-ledger.jsonl"
            evidence_path = artifact_root / "evidence.json"
            evidence_path.write_text('{"complete":true}\n', encoding="utf-8")
            supervisor = ResourceSupervisor("export", ledger_path, (artifact_root,))

            exported = _export_bundle_core(
                package_root,
                artifact_root,
                artifact_root / "export_manifest.json",
                ledger_path,
                supervisor,
                scope="test",
                metadata={"accepted": True},
            )
            supervisor.finish(status="complete")
            supervisor.close()
            manifest = json.loads((artifact_root / "export_manifest.json").read_text(encoding="utf-8"))
            _verify_export_manifest(artifact_root, manifest)

            self.assertEqual(exported["status"], "complete")
            self.assertNotIn("resource-ledger.jsonl", {entry["path"] for entry in manifest["files"]})
            self.assertIn("resource_ledger_snapshot.json", {entry["path"] for entry in manifest["files"]})
            self.assertEqual(
                manifest["resource_ledger_snapshot"]["sha256"],
                _sha256(artifact_root / "resource_ledger_snapshot.json"),
            )

    def test_formal_runtime_gate_requires_same_work_root_bound_receipts(self):
        package_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            work_root = Path(temporary) / "accepted"
            work_root.mkdir()
            identity = _runtime_identity(package_root, work_root)
            actual = {
                "python": REQUIRED_RUNTIME["python"],
                "torch": REQUIRED_RUNTIME["torch"],
                "numpy": REQUIRED_RUNTIME["numpy"],
                "device": "cpu",
                "affinity": [0],
                "affinity_error": None,
                "torch_threads": 1,
                "torch_interop_threads": 1,
                "environment": dict(REQUIRED_RUNTIME["environment"]),
                "cuda_is_initialized": False,
            }
            admission_path = work_root / "runtime_admission.json"
            admission = {
                "schema": "runtime-admission/1",
                "runtime_spec_sha256": _sha256(package_root / "runtime-spec.json"),
                "status": "accepted",
                "target_runtime_acceptance": True,
                "actual": {**actual, "cuda_is_initialized_before_witness": False},
                "kernel_witness": {"cuda_initialized_after_witness": False},
                **identity,
            }
            _json_write(admission_path, admission)
            smoke_root = work_root / "engineering_smoke"
            smoke_root.mkdir()
            strict_restore = {"L0": {"equivalent": True}, "L1": {"equivalent": True}}
            controlled_failure = {"status": "expected_failure_recorded"}
            _json_write(smoke_root / "strict_restore.json", strict_restore)
            controlled_failure_path = smoke_root / "controlled_failure" / "failure_receipt.json"
            _json_write(controlled_failure_path, controlled_failure)
            smoke_manifest = {
                "schema": "relief-graph-export/1",
                "files": [
                    {
                        "path": relative,
                        "size_bytes": (smoke_root / relative).stat().st_size,
                        "sha256": _sha256(smoke_root / relative),
                    }
                    for relative in ("strict_restore.json", "controlled_failure/failure_receipt.json")
                ],
                "sources": [
                    {"path": name, "sha256": digest}
                    for name, digest in sorted(identity["source_hashes"].items())
                ],
            }
            manifest_path = smoke_root / "export_manifest.json"
            _json_write(manifest_path, smoke_manifest)
            export_core = {"status": "complete", "manifest_sha256": _sha256(manifest_path)}
            freeze = {
                "target_runtime_acceptance": True,
                "engineering_smoke_export_manifest_sha256": export_core["manifest_sha256"],
                "runtime_admission_sha256": _sha256(admission_path),
                **identity,
            }
            freeze_path = work_root / "budget_freeze.json"
            _json_write(freeze_path, freeze)
            _json_write(smoke_root / "smoke_complete.json", {
                "schema": "engineering-smoke-result/1",
                "status": "complete",
                "target_runtime_acceptance": True,
                "runtime_admission_sha256": _sha256(admission_path),
                "actual_runtime": actual,
                "export_core": export_core,
                "strict_restore_equivalence": strict_restore,
                "controlled_failure_probe": controlled_failure,
                "budget_freeze_sha256": _sha256(freeze_path),
                **identity,
            })

            settled_rows = []
            for index, (stage, status) in enumerate((("admission", "accepted"), ("engineering_smoke", "complete")), 1):
                receipt_path = work_root / "receipts" / f"{index:02d}-{stage}.json"
                guardian_path = work_root / "guardians" / f"{index:02d}-{stage}.json"
                entry = {
                    "schema": "resource-ledger-entry/1",
                    "stage": stage,
                    "status": status,
                    "first_error": None,
                    "outer_guardian_error": None,
                    "outer_guardian_kill_reason": None,
                    "wall_seconds": 1.0,
                    "cpu_seconds": 1.0,
                    "metadata": {
                        "receipt": receipt_path.as_posix(),
                        "outer_guardian_receipt": guardian_path.as_posix(),
                    },
                }
                _json_write(guardian_path, {
                    "schema": "outer-process-guardian/1",
                    "stage": stage,
                    "status": "complete",
                    "first_error": None,
                    "outer_guardian_error": None,
                    "outer_guardian_kill_reason": None,
                    "child_returncode": 0,
                    "resource_entry": entry,
                })
                _json_write(receipt_path, {
                    "schema": "driver-stage-receipt/1",
                    "stage": stage,
                    "status": status,
                    "first_error": None,
                    "resource_entry": entry,
                    "outer_guardian_receipt": guardian_path.as_posix(),
                })
                settled_rows.append(entry)
            (work_root / "resource-ledger.jsonl").write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in settled_rows),
                encoding="utf-8",
            )

            with patch("driver._establish_current_runtime", return_value=(actual, True)):
                accepted = _require_current_runtime_acceptance(package_root, work_root)
                with self.assertRaisesRegex(PermissionError, "missing from this work root"):
                    _require_current_runtime_acceptance(package_root, Path(temporary) / "other")

            self.assertEqual(accepted["identity"], identity)
            self.assertEqual(accepted["admission_sha256"], _sha256(admission_path))
            self.assertEqual(set(accepted["settled_prerequisite_stages"]), {"admission", "engineering_smoke"})

            ledger_path = work_root / "resource-ledger.jsonl"
            settled_rows[1]["status"] = "failed"
            settled_rows[1]["first_error"] = "outer guardian: engineering_smoke wall 901>900s"
            settled_rows[1]["outer_guardian_error"] = settled_rows[1]["first_error"]
            settled_rows[1]["stage_wall_used_including_this"] = 901.0
            ledger_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in settled_rows),
                encoding="utf-8",
            )
            smoke_receipt_path = work_root / "receipts" / "02-engineering_smoke.json"
            smoke_receipt = json.loads(smoke_receipt_path.read_text(encoding="utf-8"))
            smoke_receipt.update({
                "status": "failed",
                "first_error": settled_rows[1]["first_error"],
                "resource_entry": settled_rows[1],
            })
            _json_write(smoke_receipt_path, smoke_receipt)
            guardian_path = work_root / "guardians" / "02-engineering_smoke.json"
            guardian_receipt = json.loads(guardian_path.read_text(encoding="utf-8"))
            guardian_receipt.update({
                "status": "failed",
                "first_error": settled_rows[1]["first_error"],
                "outer_guardian_error": settled_rows[1]["first_error"],
                "resource_entry": settled_rows[1],
            })
            _json_write(guardian_path, guardian_receipt)
            self.assertEqual(json.loads((smoke_root / "smoke_complete.json").read_text(encoding="utf-8"))["status"], "complete")
            with patch("driver._establish_current_runtime", return_value=(actual, True)):
                with self.assertRaisesRegex(PermissionError, "main resource-ledger settlement did not succeed"):
                    _require_current_runtime_acceptance(package_root, work_root)

    def test_attempt_directory_preserves_existing_failed_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "formal_training"
            root.mkdir()
            (root / "run_metadata.json").write_text('{"status":"running"}\n', encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "preserve it"):
                _prepare_fresh_attempt(root, "formal training")

            empty = Path(temporary) / "new_identity"
            _prepare_fresh_attempt(empty, "formal training")
            self.assertTrue(empty.is_dir())


if __name__ == "__main__":
    unittest.main()
