from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from failure_export import write_records_atomically, write_training_failure_receipt


class FailureExportTests(unittest.TestCase):
    def test_successful_export_is_complete_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.json"
            result = write_records_atomically(
                path, [{"id": "first"}, {"id": "second"}],
                run_identity={"fixture": "synthetic"}, last_completed_update=2, checkpoint_path=None,
            )
            self.assertEqual(result["status"], "complete")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(len(payload["records"]), 2)
            self.assertFalse(path.with_suffix(".json.failure.json").exists())
            self.assertFalse(list(Path(directory).glob("*.pending")))

    def test_late_serializer_failure_preserves_first_error_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "records.json"
            checkpoint = root / "last.pt"
            checkpoint.write_bytes(b"synthetic checkpoint")

            def serializer(record):
                if record["id"] == "second":
                    raise LookupError("injected later-record serializer failure")
                return json.dumps(record)

            with self.assertRaisesRegex(LookupError, "injected later-record serializer failure"):
                write_records_atomically(
                    path, [{"id": "first"}, {"id": "second"}], serializer=serializer,
                    run_identity={"fixture": "synthetic"}, last_completed_update=7,
                    checkpoint_path=checkpoint,
                )
            self.assertFalse(path.exists())
            self.assertFalse(list(root.glob("*.pending")))
            receipt = json.loads(path.with_suffix(".json.failure.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["exception_type"], "LookupError")
            self.assertIn("injected later-record serializer failure", receipt["traceback"])
            self.assertEqual(receipt["records_serialized_before_failure"], 1)
            self.assertTrue(receipt["checkpoint_exists"])
            self.assertEqual(receipt["last_completed_update"], 7)

    def test_training_failure_receipt_keeps_failure_identity_and_original_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.pt"
            checkpoint.write_bytes(b"state")
            try:
                raise RuntimeError("injected GPPO update failure")
            except RuntimeError as error:
                receipt = write_training_failure_receipt(
                    root / "training.failure.json", run_identity={"seed": "synthetic"},
                    stage="minibatch_update", last_completed_update=3,
                    checkpoint_path=checkpoint, error=error,
                )
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["last_completed_update"], 3)
            self.assertEqual(receipt["exception_type"], "RuntimeError")
            self.assertIn("injected GPPO update failure", receipt["traceback"])

    def test_receipt_names_pending_file_when_partial_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "records.json"
            original_unlink = Path.unlink

            def fail_partial_cleanup(target, *args, **kwargs):
                if target.name.startswith("records.json.") and target.name.endswith(".pending") and "failure.json" not in target.name:
                    raise PermissionError("injected pending cleanup failure")
                return original_unlink(target, *args, **kwargs)

            def serializer(record):
                if record["id"] == "second":
                    raise LookupError("injected serializer error")
                return json.dumps(record)

            with patch.object(Path, "unlink", fail_partial_cleanup):
                with self.assertRaisesRegex(LookupError, "injected serializer error"):
                    write_records_atomically(
                        path, [{"id": "first"}, {"id": "second"}], serializer=serializer,
                        run_identity={"fixture": "synthetic"}, last_completed_update=2,
                        checkpoint_path=None,
                    )
            receipt = json.loads(path.with_suffix(".json.failure.json").read_text(encoding="utf-8"))
            pending = Path(receipt["pending_artifact"])
            self.assertEqual(receipt["pending_cleanup"], "failed")
            self.assertTrue(pending.is_file())
            original_unlink(pending)


if __name__ == "__main__":
    unittest.main()
