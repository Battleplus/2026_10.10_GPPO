from __future__ import annotations

import hashlib
import io
import json
import pathlib
import struct
import tempfile
import unittest
from unittest import mock

import capture_n01_readonly_once as capture


def emit_record(stream: io.BytesIO, value: dict) -> None:
    body = capture.json_bytes(value)
    stream.write(struct.pack(">I", len(body)))
    stream.write(body)


def emit_blob(stream: io.BytesIO, path: str, data: bytes, kind: str = "blob") -> None:
    emit_record(stream, {"type": kind + "_start", "path": path})
    stream.write(struct.pack(">I", len(data)))
    stream.write(data)
    stream.write(struct.pack(">I", 0))
    emit_record(stream, {"type": kind + "_end", "path": path, "status": "ok", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})


class ReadOnlyCaptureTests(unittest.TestCase):
    def test_binary_frames_unpack_and_hash_exactly(self) -> None:
        payload = b"journal\x00line\xff\r\n"
        stream = io.BytesIO(capture.MAGIC)
        stream.seek(0, 2)
        emit_blob(stream, "commands/journal.stdout", payload)
        emit_blob(stream, "diag/settlement.json", b"{\"status\":\"failed\"}\n", "file")
        with tempfile.TemporaryDirectory() as temp:
            raw = pathlib.Path(temp) / "stdout.raw"
            root = pathlib.Path(temp) / "decoded"
            root.mkdir()
            raw.write_bytes(stream.getvalue())
            decoded = capture.decode_stream(raw, root)
            self.assertEqual((root / "commands/journal.stdout").read_bytes(), payload)
            self.assertTrue(decoded["records"][0]["end"]["local_matches_stream"])
            self.assertEqual(decoded["records"][0]["end"]["local_sha256"], hashlib.sha256(payload).hexdigest())

    def test_missing_path_and_remote_failure_records_are_preserved(self) -> None:
        stream = io.BytesIO(capture.MAGIC)
        stream.seek(0, 2)
        emit_record(stream, {"type": "command_end", "name": "journal", "exit_code": 1, "stderr": "missing invocation journal"})
        emit_record(stream, {"type": "manifest", "inventory": [{"path": "run", "status": "directory_missing"}]})
        with tempfile.TemporaryDirectory() as temp:
            raw = pathlib.Path(temp) / "stdout.raw"
            root = pathlib.Path(temp) / "decoded"
            root.mkdir()
            raw.write_bytes(stream.getvalue())
            decoded = capture.decode_stream(raw, root)
            self.assertEqual(decoded["records"][0]["exit_code"], 1)
            self.assertEqual(decoded["records"][1]["inventory"][0]["status"], "directory_missing")

    def test_terminal_gate_rejects_mismatched_or_active_unit(self) -> None:
        ok, reason = capture.stable_terminal_state({"InvocationID": capture.INVOCATION_ID, "ActiveState": "failed"})
        self.assertTrue(ok)
        self.assertEqual(reason, "terminal_invocation_match")
        ok, reason = capture.stable_terminal_state({"InvocationID": "other", "ActiveState": "failed"})
        self.assertFalse(ok)
        self.assertEqual(reason, "invocation_id_mismatch")
        ok, reason = capture.stable_terminal_state({"InvocationID": capture.INVOCATION_ID, "ActiveState": "active"})
        self.assertFalse(ok)
        self.assertEqual(reason, "unit_not_terminal")

    def test_untrusted_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for value in ("../outside", "/absolute", "diag/../../outside", "diag\\..\\outside", "C:/outside", "diag/CON"):
                with self.assertRaises(ValueError):
                    capture.safe_local_file(root, value)

    def test_capture_preserves_binary_streams_on_ssh_failure(self) -> None:
        stdout = io.BytesIO(capture.MAGIC)
        stdout.seek(0, 2)
        emit_record(stdout, {"type": "manifest", "inventory": [{"path": "diag", "status": "directory_missing"}]})
        stdout_bytes = stdout.getvalue()
        stderr_bytes = b"ssh transport failed\x00\xff"

        class FakeProcess:
            def __init__(self) -> None:
                class RecordingInput(io.BytesIO):
                    def close(self) -> None:
                        self.closed_by_capture = True

                self.stdin = RecordingInput()
                self.stdout = io.BytesIO(stdout_bytes)
                self.stderr = io.BytesIO(stderr_bytes)

            def wait(self) -> int:
                return 255

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            key = root / "key-path-only"
            key.write_bytes(b"do-not-read-key-material")
            out = root / "capture"
            args = type("Args", (), {"out": str(out), "key": str(key), "user": "fixture", "host": "fixture.invalid"})()
            proc = FakeProcess()
            with mock.patch.object(capture.subprocess, "Popen", return_value=proc) as popen:
                self.assertEqual(capture.capture(args), 255)
            self.assertEqual(popen.call_args.args[0][-3:], ["python3", "-B", "-"])
            self.assertIn(b"systemctl", proc.stdin.getvalue())
            self.assertEqual((out / "stdout.raw").read_bytes(), stdout_bytes)
            self.assertEqual((out / "stderr.raw").read_bytes(), stderr_bytes)
            record = json.loads((out / "session-record.json").read_text(encoding="utf-8"))
            self.assertEqual(record["exit_code"], 255)
            self.assertEqual(record["raw_streams"]["stdout.raw"]["sha256"], hashlib.sha256(stdout_bytes).hexdigest())
            self.assertEqual(record["raw_streams"]["stderr.raw"]["sha256"], hashlib.sha256(stderr_bytes).hexdigest())
            self.assertEqual(record["framing_status"], "decoded")
            self.assertEqual(record["capture_status"], "partial")
            self.assertIn("ssh_exit_nonzero", record["capture_status_reasons"])
            self.assertIn("inventory_incomplete:diag:directory_missing", record["capture_status_reasons"])
            self.assertNotIn(b"do-not-read-key-material", (out / "stdout.raw").read_bytes())

    def test_capture_completeness_requires_successful_state_and_inventory(self) -> None:
        records = []
        for command in ("systemd_before", "journal", "systemd_after"):
            records.append({"type": "command_end", "name": command, "exit_code": 0})
            for stream in ("stdout", "stderr"):
                path = "commands/" + command + "." + stream
                records.append({
                    "start": {"type": "blob_start", "path": path},
                    "end": {"type": "blob_end", "path": path, "status": "ok", "local_matches_stream": True},
                })
        records.extend([
            {"type": "gate", "stable_terminal_invocation": True},
            {"type": "systemd_after", "service_state_stable_at_end": True},
            {"type": "manifest", "service_state_stable": True, "inventory": [
                {"path": "diag/" + name, "status": "ok"} for name in capture.REQUIRED_DIAG_RECEIPTS
            ] + [{"path": "run/example.bin", "status": "ok"}]},
        ])
        decoded = {"records": records}
        self.assertEqual(capture.assess_capture(0, [], "decoded", decoded), ("complete", []))

        for status in ("directory_missing", "read_error", "list_error"):
            failed = {"records": records[:-1] + [{
                "type": "manifest", "service_state_stable": True,
                "inventory": [{"path": "diag", "status": status}] + [
                    {"path": "diag/" + name, "status": "ok"} for name in capture.REQUIRED_DIAG_RECEIPTS
                ] + [{"path": "run/example.bin", "status": "ok"}],
            }]}
            capture_status, reasons = capture.assess_capture(0, [], "decoded", failed)
            self.assertEqual(capture_status, "partial")
            self.assertIn("inventory_incomplete:diag:" + status, reasons)

        empty = {"records": records[:-1] + [{
            "type": "manifest", "service_state_stable": True,
            "inventory": [{"path": "diag/" + name, "status": "ok"} for name in capture.REQUIRED_DIAG_RECEIPTS]
                + [{"path": "run", "status": "empty_evidence"}],
        }]}
        self.assertEqual(capture.assess_capture(0, [], "decoded", empty)[0], "partial")
        missing_receipt = {"records": records[:-1] + [{
            "type": "manifest", "service_state_stable": True,
            "inventory": [{"path": "diag/" + name, "status": "ok"} for name in capture.REQUIRED_DIAG_RECEIPTS[1:]]
                + [{"path": "run/example.bin", "status": "ok"}],
        }]}
        self.assertIn("required_receipt_missing:diag/final-status.txt", capture.assess_capture(0, [], "decoded", missing_receipt)[1])

        self.assertEqual(capture.assess_capture(255, [], "decoded", decoded)[0], "partial")
        self.assertEqual(capture.assess_capture(0, [], "invalid_or_empty_stream", None)[0], "unknown")

    def test_transport_is_single_read_only_python_stdin_command(self) -> None:
        args = type("Args", (), {"key": "key", "host": "host", "user": "user"})()
        argv = capture.ssh_argv(args)
        self.assertEqual(argv.count("ssh"), 1)
        self.assertEqual(argv[-3:], ["python3", "-B", "-"])
        self.assertIn("ConnectionAttempts=1", argv)
        self.assertIn("O_NOFOLLOW", capture.REMOTE_PYTHON)
        self.assertIn("systemctl", capture.REMOTE_PYTHON)
        self.assertIn("journalctl", capture.REMOTE_PYTHON)
        for forbidden in ("systemctl.*start", "systemctl.*stop", "systemctl.*restart"):
            self.assertNotIn(forbidden, capture.REMOTE_PYTHON)
        self.assertNotIn("approval_path.write", capture.REMOTE_PYTHON)


if __name__ == "__main__":
    unittest.main(verbosity=2)
