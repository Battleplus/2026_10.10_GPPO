from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import n01_r2_formal_runner_repaired as runner


ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE: pathlib.Path
UNIT = "n01-full-evaluation-r2-formal-repair-v1-20261012.service"


def wsl(path: pathlib.Path) -> str:
    if os.name != "nt":
        return str(path)
    return subprocess.check_output(["wsl.exe", "wslpath", "-u", str(path)], text=True).strip()


class OfflineRunnerAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        global PACKAGE
        self.tmp = tempfile.TemporaryDirectory(prefix="n01-r2-runner-")
        self.root = pathlib.Path(self.tmp.name)
        PACKAGE = self.root / "release"
        self.materialize_release()
        self.approval = self.root / "approval.json"
        self.run_dir = self.root / "run data with spaces"
        self.diag = self.root / "diagnostics"
        self.lock = self.root / "one-shot.lock"
        self.state = self.root / "state.json"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "sleep").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.bin / "journalctl").write_text("#!/bin/sh\necho mock-journal\n", encoding="utf-8")
        fake = self.bin / "systemctl"
        fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
p=pathlib.Path(os.environ['FAKE_STATE']); s=json.loads(p.read_text()); a=sys.argv[1:]
if a[:2] == ['--user','show']:
    if 'n01-full-evaluation-r1-20261011.service' in a:
        values={'InvocationID':'7b65d35b5b4c464b810ecac918978166','ActiveState':'failed','Result':'exit-code','ExecMainStatus':'1'}
    else: values=s
    if '--value' in a:
        key=a[a.index('-p')+1]; print(values.get(key,''))
    else:
        for i,x in enumerate(a[:-1]):
            if x == '-p':
                key=a[i+1]; print(key+'='+str(values.get(key,'')))
elif a[:2] == ['--user','start']:
    s['starts']+=1; mode=os.environ.get('FAKE_START_MODE','success')
    s['InvocationID']='fixture-invocation-001'
    if mode == 'success': s.update(ActiveState='inactive',SubState='dead',Result='success',ExecMainStatus='0')
    elif mode == 'failed': s.update(ActiveState='failed',SubState='failed',Result='exit-code',ExecMainStatus='2')
    else: s.update(ActiveState='active',SubState='running',Result='success',ExecMainStatus='0')
    p.write_text(json.dumps(s));
    if mode == 'failed': raise SystemExit(7)
    print('mock-started')
else: raise SystemExit(9)
""", encoding="utf-8")
        for path in self.bin.iterdir():
            path.chmod(0o755)
        self.write_approval()

    def materialize_release(self) -> None:
        repo = ROOT.parents[3]
        overlay = json.loads((ROOT / "RELEASE_OVERLAY_INDEX.json").read_text(encoding="utf-8"))
        PACKAGE.mkdir(parents=True)
        for entry in overlay["entries"]:
            source = entry["source"]
            if source["kind"] == "existing-tracked-file":
                src = repo / source["path"]
            elif source["kind"] == "new-overlay-file":
                src = ROOT / source["path"]
            else:
                raise AssertionError(f"unsupported overlay source: {source['kind']}")
            dst = PACKAGE / entry["release_path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            self.assertEqual(runner.sha256(dst), entry["sha256"], entry["release_path"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_approval(self, status: str = "approved", identity: str | None = None,
                       reader_sha: str | None = None) -> None:
        bindings = runner.load_bindings(PACKAGE)
        obj = {
            "schema": runner.APPROVAL_SCHEMA,
            "status": status,
            "evaluation_identity": identity or runner.IDENTITY,
            "stage_budget_sha256": bindings["stage_budget_sha256"],
            "stages": {
                "admission": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
                "evaluation": {"wall_seconds": 5400.0, "cpu_seconds": 4500.0},
                "export": {"wall_seconds": 300.0, "cpu_seconds": 180.0},
                "shutdown": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
            },
            "identity_total": {"wall_seconds": 5940.0, "cpu_seconds": 4800.0},
            "approval_reference": "SYNTHETIC-OFFLINE-ONLY",
            "approved_by": "SYNTHETIC-OFFLINE-ONLY",
            "approval_body": {
                "unit": UNIT,
                "memory_max_bytes": 4294967296,
                "single_start": True,
                "failure_policy": "preserve first error; never retry",
                "excluded": ["r1 authorization reuse", "n2", "n3", "tuning"],
                "reader_sha256": reader_sha or bindings["reader_sha256"],
                "plan_sha256": bindings["plan_sha256"],
            },
        }
        self.approval.write_text(json.dumps(obj), encoding="utf-8")

    def invoke(self, *, active: str = "inactive", start_mode: str = "success",
               run_exists: bool = False, approval_status: str = "approved",
               approval_identity: str | None = None, reader_sha: str | None = None,
               diag: pathlib.Path | None = None, lock: pathlib.Path | None = None) -> tuple[subprocess.CompletedProcess, dict]:
        self.write_approval(approval_status, approval_identity, reader_sha)
        if run_exists:
            self.run_dir.mkdir(exist_ok=True)
        self.state.write_text(json.dumps({
            "LoadState": "loaded", "ActiveState": active, "SubState": "dead",
            "Result": "success", "ExecMainCode": "exited", "ExecMainStatus": "0",
            "InvocationID": "", "CPUUsageNSec": "unknown", "MemoryCurrent": "unknown",
            "MemoryPeak": "unknown", "starts": 0,
        }), encoding="utf-8")
        env = {
            **os.environ,
            "PATH": wsl(self.bin) + ":/usr/bin:/bin",
            "PKG": wsl(PACKAGE), "RUN": wsl(self.run_dir), "UNIT": UNIT,
            "APPROVAL_PATH": wsl(self.approval), "DIAG": wsl(diag or self.diag),
            "LOCK_PATH": wsl(lock or self.lock), "EXPECTED_UNIT": UNIT,
            "IDENTITY": runner.IDENTITY,
            "FAKE_STATE": wsl(self.state), "FAKE_START_MODE": start_mode,
            "POLL_LIMIT": "2",
        }
        bindings = runner.load_bindings(PACKAGE)
        env.update({
            "IDENTITY_SHA": bindings["identity_sha256"],
            "BUDGET_SHA": bindings["stage_budget_sha256"],
            "READER_SHA": bindings["reader_sha256"],
            "PLAN_SHA": bindings["plan_sha256"],
        })
        proc = subprocess.run(["bash", "-s"], input=runner.remote_script(), text=True, env=env, capture_output=True)
        return proc, json.loads(self.state.read_text())

    def test_actual_runner_shell_quoting_and_one_start(self) -> None:
        bindings = runner.load_bindings(PACKAGE)
        runner.validate_local_reader(PACKAGE / "static_plan_r2.json", bindings)
        proc, state = self.invoke()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(state["starts"], 1)
        settlement = json.loads((self.diag / "settlement.json").read_text())
        self.assertEqual(settlement["invocation_id"], "fixture-invocation-001")
        self.assertEqual(settlement["retry_count"], 0)
        self.assertFalse(settlement["formal_result_claimed"])

    def test_wrong_identity_or_not_approved_is_rejected(self) -> None:
        proc, state = self.invoke(approval_identity="old-consumed-identity")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)
        self.tmp.cleanup()
        self.setUp()
        proc, state = self.invoke(approval_status="NOT_APPROVED")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)

    def test_reader_mismatch_is_rejected(self) -> None:
        proc, state = self.invoke(reader_sha="0" * 64)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)

    def test_active_or_existing_run_is_rejected(self) -> None:
        proc, state = self.invoke(active="active")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)
        self.tmp.cleanup()
        self.setUp()
        proc, state = self.invoke(run_exists=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)

    def test_atomic_lock_rejects_repeat_submission(self) -> None:
        proc, state = self.invoke()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        second_diag = self.root / "diagnostics-second"
        proc, state = self.invoke(diag=second_diag)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state["starts"], 0)

    def test_start_failure_and_pending_write_settlement_without_retry(self) -> None:
        proc, state = self.invoke(start_mode="failed")
        self.assertNotEqual(proc.returncode, 0)
        settlement = json.loads((self.diag / "settlement.json").read_text())
        self.assertEqual(settlement["status"], "FAILED_START_COMMAND")
        self.assertEqual(settlement["start_count"], 1)
        self.assertEqual(settlement["retry_count"], 0)
        self.assertTrue((self.diag / "final-status.txt").is_file())
        self.tmp.cleanup()
        self.setUp()
        proc, state = self.invoke(start_mode="pending")
        self.assertNotEqual(proc.returncode, 0)
        settlement = json.loads((self.diag / "settlement.json").read_text())
        self.assertEqual(settlement["status"], "PENDING_TIMEOUT")
        self.assertEqual(settlement["retry_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
