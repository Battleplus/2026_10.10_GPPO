from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import time
import unittest
from dataclasses import replace

from n2_controller import (AFFINITY_MARKER, ControllerConfig, Evidence, canonical_sha256,
                           collect_managed_receipts, command, controller_bundle_sha256,
                           run_controller, sha256)
from vendor.stage_contract import STAGE_ORDER


INVOCATION = "0123456789abcdef0123456789abcdef"


class FakeChannel:
    def __init__(self, output: bytes = b"", status: int = 0):
        self.output = output
        self.status = status
        self.sent = False

    def recv_ready(self):
        return not self.sent and bool(self.output)

    def recv(self, _size):
        self.sent = True
        return self.output

    def recv_stderr_ready(self):
        return False

    def recv_stderr(self, _size):
        return b""

    def exit_status_ready(self):
        return self.sent or not self.output

    def recv_exit_status(self):
        return self.status

    def close(self):
        pass


class FakeStdout:
    def __init__(self, channel):
        self.channel = channel


class FakeSftp:
    def __init__(self, events):
        self.events = events

    def mkdir(self, path, mode=0o700):
        self.events.append(("transfer_mkdir", path, mode))

    def stat(self, _path):
        return object()

    def put(self, local, remote, confirm=True):
        self.events.append(("transfer_file", pathlib.Path(local).name, remote, confirm))

    def close(self):
        self.events.append(("transfer_close",))


class FakeClient:
    def __init__(self, events):
        self.events = events
        self.commands = []
        self.submit_output_override = None
        self.submit_status_override = 0

    def exec_command(self, text, *, get_pty, timeout):
        self.commands.append((text, get_pty, timeout))
        channel_status = 0
        if "N2_PREFLIGHT_JSON=" in text:
            output = (AFFINITY_MARKER + json.dumps({
                "hostname": "unit-test-host",
                "user": "unit-test-user",
                "sched_affinity": [2, 4, 6],
                "cpuset_effective": [4, 5, 6],
            }) + "\n").encode()
            phase = "preflight"
        elif "mkdir -m 700 -p" in text:
            output, phase = b"", "mkdir"
        elif "PACKAGE_HASHES_VERIFIED" in text:
            output, phase = b"PACKAGE_HASHES_VERIFIED\n", "verify"
        elif "systemctl --user stop" in text:
            output = ("InvocationID=" + INVOCATION + "\nActiveState=inactive\nResult=success\n").encode()
            output, phase = output, "stop"
        elif "systemd-run --user" in text:
            output = (
                "N2_INVOCATION_ID=" + INVOCATION + "\n"
                "InvocationID=" + INVOCATION + "\n"
                "ControlGroup=/user.slice/test.service\n"
                "ActiveState=inactive\nResult=success\nExecMainStatus=0\n"
                "CPUUsageNSec=1000\nMemoryPeak=4096\n"
            ).encode()
            if self.submit_output_override is not None:
                output = self.submit_output_override
                channel_status = self.submit_status_override
            output, phase = output, "submit"
        elif "systemctl --user show" in text:
            output = ("InvocationID=" + INVOCATION + "\nControlGroup=/user.slice/test.service\n"
                      "CPUUsageNSec=1000\nMemoryPeak=4096\n").encode()
            output, phase = output, "result"
        else:
            raise AssertionError("Unexpected command text: " + text)
        self.events.append(("command", phase, text))
        return None, FakeStdout(FakeChannel(output, status=channel_status)), None

    def open_sftp(self):
        self.events.append(("transfer_begin",))
        return FakeSftp(self.events)

    def close(self):
        self.events.append(("connection_close",))


class ControllerTest(unittest.TestCase):
    def make_config(self, root: pathlib.Path) -> ControllerConfig:
        package = root / "package"
        package.mkdir()
        (package / "worker.py").write_text("# worker entry\n", encoding="utf-8")
        worker_hash = hashlib.sha256((package / "worker.py").read_bytes()).hexdigest().upper()
        manifest = {
            "identity": "n2-engineering-test-r3",
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
        key_file, known_hosts = root / "ssh-key-ref", root / "known-hosts-ref"
        key_file.write_text("private reference fixture", encoding="utf-8")
        known_hosts.write_text("host key fixture", encoding="utf-8")
        run_id = "n2-controller-contract-test-once"
        unit = run_id + ".service"
        budget = {
            "status": "APPROVED",
            "wall_seconds_total_including_settlement": 180,
            "settlement_reserve_seconds": 30,
            "systemd_runtime_max_seconds": 180,
            "cpu_quota_percent": 100,
            "cgroup_memory_max_bytes": 1073741824,
        }
        authorization = {
            "approval_status": "APPROVED",
            "one_time_execution": True,
            "identity": "n2-engineering-test-r3",
            "run_identity": run_id,
            "target_host": "unit-test-host",
            "target_user": "unit-test-user",
            "connect_host": "127.0.0.1",
            "package_sha256": manifest_hash,
            "systemd_unit": unit,
            "controller_sha256": sha256(pathlib.Path(__file__).with_name("n2_controller.py")),
            "controller_bundle_sha256": controller_bundle_sha256(),
            "budget_sha256": canonical_sha256(budget),
            "worker_entry": "worker.py",
            "worker_args": [],
            "remote_root": "/tmp/n2-controller-contract-test-once",
            "consumption_root": str((root / "consumed").resolve()),
            "authorization_id": "test-only-authorization",
            "approved_at": "test-only",
        }
        return ControllerConfig(
            package_root=package,
            manifest_rel="manifest.json",
            package_sha256=manifest_hash,
            expected_identity="n2-engineering-test-r3",
            run_identity=run_id,
            unit=unit,
            target_host="unit-test-host",
            target_user="unit-test-user",
            connect_host="127.0.0.1",
            remote_root="/tmp/n2-controller-contract-test-once",
            python="/usr/bin/python3",
            worker_entry="worker.py",
            worker_args=(),
            ssh_key_file=key_file,
            known_hosts=known_hosts,
            evidence_root=root / "evidence",
            budget=budget,
            authorization=authorization,
            consumption_root=root / "consumed",
        )

    def test_success_path_records_real_command_text_and_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            config = self.make_config(root)
            events = []
            client = FakeClient(events)
            connect_calls = []

            def connect(**kwargs):
                connect_calls.append(kwargs)
                events.append(("connect",))
                return client

            def collect(client_arg, source, destination):
                self.assertIs(client_arg, client)
                events.append(("collect", source, str(destination)))
                return {
                    "invocation_id": INVOCATION,
                    "status": "complete",
                    "managed_supervisor": "complete",
                    "controller_bundle_sha256": controller_bundle_sha256(),
                    "stage_server": "complete",
                    "budget_ledger": "complete",
                    "settlement": "complete",
                    "export": "complete",
                    "cgroup": "verified",
                }

            invocation = run_controller(
                config, connect=connect, collect=collect,
                settle_failure=lambda *_: "STOPPED_SETTLED_AND_COLLECTED",
                verify_authorization=lambda _record: True,
            )
            self.assertEqual(invocation, INVOCATION)
            self.assertEqual(len(connect_calls), 1)
            self.assertEqual(client.commands[0][1], False)

            transcript = (config.evidence_root / "controller-transcript.txt").read_text(encoding="utf-8")
            command_labels = []
            lines = transcript.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("COMMAND_BEGIN label="):
                    command_labels.append(line.partition("label=")[2])
            command_records = list(zip(command_labels, (command[0] for command in client.commands)))
            labels = [label for label, _ in command_records]
            self.assertEqual(labels, [
                "preflight_identity_and_cpu_json",
                "create_remote_roots",
                "verify_transferred_package",
                "submit_once_and_observe",
                "collect_same_invocation_result",
            ])

            mkdir_label, mkdir_text = command_records[1]
            self.assertEqual(mkdir_label, "create_remote_roots")
            self.assertIn("mkdir -m 700 -p /tmp/n2-controller-contract-test-once/package", mkdir_text)
            self.assertIn("/tmp/n2-controller-contract-test-once/work", mkdir_text)
            preflight_label, preflight_text = command_records[0]
            self.assertEqual(preflight_label, "preflight_identity_and_cpu_json")
            self.assertIn(AFFINITY_MARKER, preflight_text)
            self.assertIn("cpuset.cpus.effective", preflight_text)

            submit_label, submit_text = command_records[3]
            self.assertEqual(submit_label, "submit_once_and_observe")
            self.assertIn("--property=Type=exec", submit_text)
            self.assertIn("--property=RuntimeMaxSec=180s", submit_text)
            self.assertIn("LoadState --value --no-pager)\" = not-found", submit_text)
            self.assertIn("time.monotonic()+180", submit_text)
            self.assertIn("ActiveState", submit_text)
            self.assertIn("--property=CPUQuota=100%", submit_text)
            self.assertIn("--property=MemoryMax=1073741824", submit_text)
            self.assertIn("--property=CPUAffinity=4,6", submit_text)
            self.assertIn("worker.py", submit_text)
            self.assertIn("managed-controller/managed_stage_supervisor.py", submit_text)
            self.assertIn("managed-supervisor-config.json", submit_text)

            phase_order = [event[1] for event in events if event[0] == "command"]
            self.assertEqual(phase_order, ["preflight", "mkdir", "verify", "submit", "result"])
            event_kinds = [event[0] for event in events]
            self.assertLess(event_kinds.index("command"), event_kinds.index("transfer_begin"))
            self.assertLess(event_kinds.index("transfer_close"),
                            event_kinds.index("command", event_kinds.index("transfer_close")))
            self.assertLess(event_kinds.index("submit") if "submit" in event_kinds else event_kinds.index("command", 3), event_kinds.index("collect"))
            self.assertEqual(event_kinds.count("connect"), 1)
            retry_config = replace(config, evidence_root=root / "different-evidence")
            retry_connects = []
            with self.assertRaisesRegex(ValueError, "AUTHORIZATION_ALREADY_CONSUMED"):
                run_controller(
                    retry_config,
                    connect=lambda **kwargs: retry_connects.append(kwargs),
                    collect=collect,
                    settle_failure=lambda *_: "UNKNOWN",
                    verify_authorization=lambda _record: True,
                )
            self.assertEqual(retry_connects, [])
            self.assertFalse(retry_config.evidence_root.exists())

    def test_channel_timeout_closes_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Evidence(pathlib.Path(temp) / "evidence")
            self.addCleanup(evidence.close)

            class NoResponseChannel:
                closed = False

                def recv_ready(self):
                    return False

                def recv_stderr_ready(self):
                    return False

                def exit_status_ready(self):
                    return False

                def close(self):
                    self.closed = True

            channel = NoResponseChannel()

            class Client:
                calls = 0

                def exec_command(self, _text, *, get_pty, timeout):
                    self.calls += 1
                    return None, FakeStdout(channel), None

            times = iter((0.0, 0.1, 0.2, 2.0))
            with self.assertRaisesRegex(TimeoutError, "REMOTE_COMMAND_TIMEOUT"):
                command(Client(), evidence, label="timeout", text="true", timeout=1,
                        deadline=10, now=lambda: next(times))
            self.assertTrue(channel.closed)
            evidence.close()

    def test_nonzero_channel_exit_is_a_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = Evidence(pathlib.Path(temp) / "evidence")
            self.addCleanup(evidence.close)
            channel = FakeChannel(output=b"", status=17)

            class Client:
                calls = 0

                def exec_command(self, _text, *, get_pty, timeout):
                    self.calls += 1
                    return None, FakeStdout(channel), None

            with self.assertRaisesRegex(RuntimeError, "REMOTE_COMMAND_FAILED:failed:17"):
                command(Client(), evidence, label="failed", text="false", timeout=5,
                        deadline=10, now=lambda: 0.0)
            evidence.close()

    def test_default_collector_checks_json_receipts_cgroup_and_export_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            export = b"verified-output"
            export_hash = hashlib.sha256(export).hexdigest().upper()
            worker = {
                "schema": "n2-managed-worker-receipt/1",
                "status": "complete",
                "settlement": "complete",
                "stage_server_socket_present": True,
                "ledger": {"pending_calls": 0, "failed_calls": 0},
                "export_status": "complete",
                "exports": [{"path": "result.bin", "bytes": len(export), "sha256": export_hash}],
            }
            supervisor = {
                "schema": "n2-managed-stage-supervisor/1",
                "status": "complete",
                "systemd_invocation_id": INVOCATION,
                "controller_bundle_sha256": "A" * 64,
                "stage_server_final_stage": "settlement_and_verified_export",
                "supervisor_pid": 123,
                "cgroup_configuration": {
                    "path": "/sys/fs/cgroup/user.slice/test.service",
                    "cpuset_effective": [2], "sched_affinity": [2],
                    "cpu_quota_percent": 100, "memory_max_bytes": 1000,
                },
                "cgroup_final": {
                    "pids": [123], "memory_peak_bytes": 500,
                },
                "cgroup_cpu_seconds_total": 1.0,
            }
            remote_files = {
                "/remote/work/managed-worker-receipt.json": json.dumps(worker).encode(),
                "/remote/work/managed-supervisor-receipt.json": json.dumps(supervisor).encode(),
                "/remote/work/export/result.bin": export,
            }

            class Sftp:
                class Channel:
                    def settimeout(self, _timeout):
                        pass

                def get_channel(self):
                    return self.Channel()

                def get(self, remote, local):
                    pathlib.Path(local).write_bytes(remote_files[remote])

                def close(self):
                    pass

            class Client:
                def open_sftp(self):
                    return Sftp()

            receipt = collect_managed_receipts(
                Client(), "/remote/work", root / "collected", invocation=INVOCATION,
                control_group="/user.slice/test.service", bundle_sha256="A" * 64,
                guard_limits={
                    "cpu_quota_percent": 100,
                    "cgroup_memory_max_bytes": 1000,
                    "complete_process_cpu_seconds_total_including_descendants_and_settlement": 5,
                },
                final_stage="settlement_and_verified_export",
                deadline=time.monotonic() + 10,
            )
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual(receipt["cgroup"], "verified")
            self.assertEqual((root / "collected" / "exports" / "result.bin").read_bytes(), export)

            invalid_cases = (
                ("quota_nan", lambda value: value["cgroup_configuration"].__setitem__("cpu_quota_percent", float("nan"))),
                ("cpu_nan", lambda value: value.__setitem__("cgroup_cpu_seconds_total", float("nan"))),
                ("negative_pid", lambda value: value["cgroup_final"].__setitem__("pids", [-1])),
                ("negative_peak", lambda value: value["cgroup_final"].__setitem__("memory_peak_bytes", -1)),
            )
            for name, corrupt in invalid_cases:
                malformed = json.loads(json.dumps(supervisor))
                corrupt(malformed)
                remote_files["/remote/work/managed-supervisor-receipt.json"] = json.dumps(malformed).encode()
                with self.subTest(case=name), self.assertRaises(ValueError):
                    collect_managed_receipts(
                        Client(), "/remote/work", root / ("collected-" + name),
                        invocation=INVOCATION, control_group="/user.slice/test.service",
                        bundle_sha256="A" * 64,
                        guard_limits={
                            "cpu_quota_percent": 100,
                            "cgroup_memory_max_bytes": 1000,
                            "complete_process_cpu_seconds_total_including_descendants_and_settlement": 5,
                        },
                        final_stage="settlement_and_verified_export",
                        deadline=time.monotonic() + 10,
                    )

    def test_post_submission_failure_stops_same_unit_and_preserves_first_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            config = self.make_config(root)
            events = []
            client = FakeClient(events)
            settled = []

            def incomplete_collect(_client, _source, _destination):
                return {"invocation_id": INVOCATION, "status": "failed"}

            def settle(client_arg, unit, invocation, first_error, evidence_root, deadline):
                self.assertIs(client_arg, client)
                self.assertEqual(unit, config.unit)
                self.assertEqual(invocation, INVOCATION)
                settled.append(type(first_error).__name__)
                events.append(("settlement",))
                return "STOPPED_SETTLED_AND_COLLECTED"

            with self.assertRaisesRegex(RuntimeError, "WORKER_RECEIPT_OR_SETTLEMENT_NOT_VERIFIED"):
                run_controller(
                    config,
                    connect=lambda **kwargs: (events.append(("connect",)) or client),
                    collect=incomplete_collect,
                    settle_failure=settle,
                    verify_authorization=lambda _record: True,
                )
            event_kinds = [event[0] for event in events]
            self.assertEqual(event_kinds.count("connect"), 1)
            self.assertEqual(sum(1 for event in events if event[0] == "command" and event[1] == "submit"), 1)
            self.assertEqual(sum(1 for event in events if event[0] == "command" and event[1] == "stop"), 1)
            self.assertEqual(settled, ["RuntimeError"])
            transcript = (config.evidence_root / "controller-transcript.txt").read_text(encoding="utf-8")
            self.assertIn("FIRST_ERROR type=RuntimeError detail=WORKER_RECEIPT_OR_SETTLEMENT_NOT_VERIFIED", transcript)
            self.assertIn("FAILURE_CLEANUP status=STOPPED_SETTLED_AND_COLLECTED", transcript)

    def test_unknown_invocation_does_not_stop_an_unidentified_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            config = self.make_config(root)
            events = []
            client = FakeClient(events)
            client.submit_output_override = b""
            client.submit_status_override = 1
            settled = []

            with self.assertRaisesRegex(RuntimeError, "SUBMISSION_OR_INVOCATION_EVIDENCE_INVALID"):
                run_controller(
                    config,
                    connect=lambda **kwargs: (events.append(("connect",)) or client),
                    collect=lambda *_: None,
                    settle_failure=lambda client_arg, unit, invocation, *_: (
                        settled.append(invocation) or "UNKNOWN"
                    ),
                    verify_authorization=lambda _record: True,
                )
            self.assertEqual(settled, [None])
            self.assertFalse(any(event[0] == "command" and event[1] == "stop" for event in events))

    def test_preflight_rejections_happen_before_write_or_connect(self):
        cases = ("budget", "authorization", "package_hash", "controller_bundle", "identity", "file_hash", "signature")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = pathlib.Path(temp)
                config = self.make_config(root)
                if case == "budget":
                    object.__setattr__(config, "budget", {**config.budget, "status": "DRAFT"})
                elif case == "authorization":
                    object.__setattr__(config, "authorization", {**config.authorization, "approval_status": "PENDING"})
                else:
                    if case == "package_hash":
                        object.__setattr__(config, "package_sha256", "0" * 64)
                    elif case == "controller_bundle":
                        object.__setattr__(config, "authorization", {
                            **config.authorization, "controller_bundle_sha256": "0" * 64,
                        })
                    elif case == "identity":
                        object.__setattr__(config, "expected_identity", "wrong-identity")
                    elif case == "file_hash":
                        (config.package_root / "worker.py").write_text("tampered\n", encoding="utf-8")
                connect_calls = []
                with self.assertRaises(ValueError):
                    run_controller(config, connect=lambda **kwargs: connect_calls.append(kwargs), collect=lambda *_: None,
                                   settle_failure=lambda *_: "UNKNOWN",
                                   verify_authorization=lambda _record: case != "signature")
                self.assertEqual(connect_calls, [])
                self.assertFalse(config.evidence_root.exists())


if __name__ == "__main__":
    unittest.main()
