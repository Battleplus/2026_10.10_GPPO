from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

from exact_record_authorization import expected_authorization
from standalone_controller import load_json_object, run_standalone
from vendor.stage_contract import STAGE_ORDER


class StandaloneControllerTests(unittest.TestCase):
    def _fixture(self, root: pathlib.Path):
        package = root / "package"
        package.mkdir()
        worker = package / "worker.py"
        worker.write_text("def managed_worker(runtime):\n    return {}\n", encoding="utf-8")
        worker_hash = hashlib.sha256(worker.read_bytes()).hexdigest().upper()
        budget = {
            "status": "APPROVED",
            "wall_seconds_total_including_settlement": 180,
            "settlement_reserve_seconds": 30,
            "systemd_runtime_max_seconds": 180,
            "cpu_quota_percent": 100,
            "cgroup_memory_max_bytes": 1073741824,
        }
        manifest = {
            "identity": "n2-standalone-test-r1",
            "files": ["worker.py"],
            "file_sha256": {"worker.py": worker_hash},
            "managed_runtime": {
                "resource_request": {
                    "stage_order": list(STAGE_ORDER),
                    "stages": {stage: {} for stage in STAGE_ORDER},
                    "totals": {},
                },
                "guard_limits": {
                    "wall_seconds_total_including_settlement": 180,
                    "settlement_reserve_seconds": 30,
                    "complete_process_cpu_seconds_total_including_descendants_and_settlement": 90,
                    "settlement_cpu_reserve_seconds": 10,
                    "cgroup_memory_max_bytes": 1073741824,
                    "memory_settlement_reserve_bytes": 1048576,
                    "combined_working_plus_export_peak_bytes_max": 10485760,
                    "cpu_quota_percent": 100,
                },
            },
        }
        manifest_path = package / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
        key = root / "private-key-reference"
        known_hosts = root / "known-hosts-reference"
        key.write_text("private key reference only", encoding="utf-8")
        known_hosts.write_text("host key reference", encoding="utf-8")
        raw = {
            "package_root": str(package),
            "manifest_rel": "manifest.json",
            "package_sha256": manifest_hash,
            "expected_identity": manifest["identity"],
            "run_identity": "n2-standalone-test-once",
            "unit": "n2-standalone-test-once.service",
            "target_host": "approved-host",
            "target_user": "approved-user",
            "connect_host": "127.0.0.1",
            "remote_root": "/tmp/n2-standalone-test-once",
            "python": "/usr/bin/python3",
            "worker_entry": "worker.py",
            "worker_args": [],
            "ssh_key_file": str(key),
            "known_hosts": str(known_hosts),
            "evidence_root": str(root / "evidence"),
            "budget": budget,
            "consumption_root": str(root / "consumed"),
        }
        return raw

    def _write_pair(self, root: pathlib.Path, raw: dict[str, object]):
        config_path = root / "controller-config.json"
        authorization_path = root / "approved-authorization.json"
        provisional = {
            "approval_status": "APPROVED",
            "one_time_execution": True,
            "authorization_id": "test-auth-id",
            "approved_at": "2026-10-14T10:00:00+08:00",
            "approved_by": "test-coordinator",
        }
        from standalone_controller import build_config

        config = build_config(raw, provisional)
        authorization = {
            **expected_authorization(config),
            **provisional,
        }
        config_path.write_text(json.dumps(raw), encoding="utf-8")
        authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
        return config_path, authorization_path, authorization

    def test_not_approved_template_rejects_before_connect_or_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            template = load_json_object(
                pathlib.Path(__file__).with_name("controller_config.template.json")
            )
            authorization = root / "authorization.json"
            authorization.write_text("{}", encoding="utf-8")
            calls = []
            with self.assertRaisesRegex(ValueError, "BUDGET_NOT_APPROVED"):
                run_standalone(
                    pathlib.Path(__file__).with_name("controller_config.template.json"),
                    authorization,
                    connect_factory=lambda **kwargs: calls.append(kwargs),
                )
            self.assertEqual(template["budget"]["status"], "NOT_APPROVED")
            self.assertEqual(calls, [])

    def test_exact_existing_authorization_reaches_only_the_mock_connector(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            config_path, authorization_path, _ = self._write_pair(root, self._fixture(root))
            calls = []

            class ConnectReached(RuntimeError):
                pass

            def connect(**kwargs):
                calls.append(kwargs)
                raise ConnectReached("mocked connector reached")

            with self.assertRaisesRegex(ConnectReached, "mocked connector reached"):
                run_standalone(config_path, authorization_path, connect_factory=connect)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["hostname"], "127.0.0.1")
            self.assertTrue((root / "consumed").is_dir())
            self.assertTrue((root / "evidence").is_dir())

    def test_authorization_mismatch_rejects_before_claim_or_connector(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            config_path, authorization_path, authorization = self._write_pair(root, self._fixture(root))
            authorization["worker_entry"] = "other.py"
            authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
            calls = []
            with self.assertRaisesRegex(ValueError, "AUTHORIZATION_MISMATCH:worker_entry"):
                run_standalone(config_path, authorization_path, connect_factory=lambda **kwargs: calls.append(kwargs))
            self.assertEqual(calls, [])
            self.assertFalse((root / "consumed").exists())
            self.assertFalse((root / "evidence").exists())

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "duplicate.json"
            path.write_text('{"status":"APPROVED","status":"NOT_APPROVED"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON_INPUT_INVALID"):
                load_json_object(path)

    def test_float_exponent_overflow_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "overflow.json"
            path.write_text('{"wall_seconds":1e400}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON_INPUT_INVALID"):
                load_json_object(path)


if __name__ == "__main__":
    unittest.main()
