from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import formal_transport_envelope as transport
import n01_r2_formal_runner_repaired as runner


PACKAGE = ROOT / "release"
UNIT = "n01-full-evaluation-r2-formal-repair-v1-20261012.service"
WSL = pathlib.Path(r"C:\Windows\System32\wsl.exe")


def bash_path(path: pathlib.Path) -> str:
    if os.name != "nt":
        return str(path)
    win_path = str(path.resolve()).replace("\\", "/")
    wsl_prefix = "//wsl.localhost/Ubuntu-24.04"
    if win_path.lower().startswith(wsl_prefix.lower() + "/"):
        return win_path[len(wsl_prefix):]
    drive, tail = win_path[:2], win_path[2:]
    if len(drive) != 2 or drive[1] != ":":
        raise ValueError("test fixture path must be on a mounted drive")
    return "/mnt/" + drive[0].lower() + tail


class TransportEnvelopeAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        if os.name == "nt":
            created = subprocess.check_output(
                [str(WSL), "-d", "Ubuntu-24.04", "--exec", "mktemp", "-d", "/tmp/n01-r2-transport-XXXXXX"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if not created.startswith("/tmp/") or "\n" in created:
                raise RuntimeError(f"unexpected WSL temporary directory: {created!r}")
            self.linux_root = created
            self.root = pathlib.Path("\\\\wsl.localhost\\Ubuntu-24.04" + created.replace("/", "\\"))
            self.bin = self.root / "bin"
        else:
            self.linux_root = None
            self.root = pathlib.Path(tempfile.mkdtemp(prefix="n01-r2-transport-", dir="/tmp"))
            self.bin = self.root / "bin"
        self.bin.mkdir()
        self.base = self.root / "pilot"
        for name in ("packages", "runs", "diagnostics"):
            (self.base / name).mkdir(parents=True)
        self.remote_pkg = self.base / "packages" / runner.IDENTITY
        shutil.copytree(PACKAGE, self.remote_pkg)
        self.approval = self.base / "packages" / transport.APPROVAL_FILENAME
        self.run_dir = self.base / "runs" / (runner.IDENTITY + "-once")
        self.diag = self.base / "diagnostics" / (runner.IDENTITY + "-formal-run-20261012")
        self.lock = self.diag / "launch.lock"
        self.capture = self.root / "ssh-stdin.bin"
        self.state = self.root / "state.json"
        self.fake_ssh = self.bin / ("ssh.cmd" if os.name == "nt" else "ssh")
        if os.name == "nt":
            fake_ssh_py = self.bin / "fake_ssh.py"
            fake_ssh_py.write_text('''import os, pathlib, subprocess, sys
data = sys.stdin.buffer.read()
pathlib.Path(os.environ["CAPTURE"]).write_bytes(data)
cmd = ["wsl.exe", "-d", "Ubuntu-24.04", "--exec", "env"]
for key in ("FAKE_STATE", "FAKE_START_MODE", "FAKE_R1_MISMATCH", "POLL_LIMIT", "WSL_BIN"):
    value = os.environ.get(key)
    if value is not None:
        cmd.append(("PATH=" if key == "WSL_BIN" else key + "=") + value if key != "WSL_BIN" else "PATH=" + value + ":/usr/bin:/bin")
cmd += ["bash", "-s"]
result = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
sys.stdout.buffer.write(result.stdout); sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
''', encoding="utf-8")
            self.fake_ssh.write_text(f'@echo off\r\npython "{fake_ssh_py}" %*\r\n', encoding="utf-8")
        else:
            self.fake_ssh.write_text(
                "#!/bin/sh\ncat > \"$CAPTURE\"\nexec bash -s < \"$CAPTURE\"\n",
                encoding="utf-8",
            )
        systemctl = self.bin / ("systemctl.cmd" if os.name == "nt" else "systemctl")
        service_source = '''import json, os, pathlib, sys
p=pathlib.Path(os.environ["FAKE_STATE"]); s=json.loads(p.read_text()); a=sys.argv[1:]
if a[:2] == ["--user", "show"]:
    if "n01-full-evaluation-r1-20261011.service" in a:
        values={"InvocationID":"bad-r1-invocation" if os.environ.get("FAKE_R1_MISMATCH") else "7b65d35b5b4c464b810ecac918978166","ActiveState":"failed","Result":"exit-code","ExecMainStatus":"1"}
    else: values=s
    if "--value" in a: print(values.get(a[a.index("-p")+1], ""))
    else:
        for i,x in enumerate(a[:-1]):
            if x == "-p": print(a[i+1]+"="+str(values.get(a[i+1], "")))
elif a[:2] == ["--user", "start"]:
    s["starts"] += 1; mode=os.environ.get("FAKE_START_MODE", "success")
    run=pathlib.Path(os.environ["RUN"]); run.mkdir(parents=True, exist_ok=True); (run/"fixture.json").write_text("{}")
    s["InvocationID"]="fixture-invocation-001"
    if mode == "success": s.update(ActiveState="inactive",SubState="dead",Result="success",ExecMainStatus="0")
    elif mode == "failed": s.update(ActiveState="failed",SubState="failed",Result="exit-code",ExecMainStatus="2")
    else: s.update(ActiveState="active",SubState="running",Result="success",ExecMainStatus="0")
    p.write_text(json.dumps(s))
    if mode == "failed": raise SystemExit(7)
    print("mock-started")
else: raise SystemExit(9)
'''
        if os.name == "nt":
            systemctl.write_text(
                "@echo off\r\npython -c \"" + service_source.replace('"', '\\"').replace("\n", ";") + "\" %*\r\n",
                encoding="utf-8",
            )
            # Windows cmd wrappers cannot reliably carry multiline source. Use a
            # Python executable shim on PATH through a tiny .cmd trampoline.
            self.service_py = self.bin / "fake_systemctl.py"
            self.service_py.write_text(service_source, encoding="utf-8")
            systemctl.write_text(f'@echo off\r\npython "{self.service_py}" %*\r\n', encoding="utf-8")
            sleep = self.bin / "sleep.cmd"
            sleep.write_text("@exit /b 0\r\n", encoding="utf-8")
            journal = self.bin / "journalctl.cmd"
            journal.write_text("@echo mock-journal\r\n", encoding="utf-8")
            self.service_py = self.bin / "fake_systemctl.py"
            self.service_py.write_text(service_source, encoding="utf-8")
            (self.bin / "systemctl").write_bytes(
                b'#!/bin/sh\nexec python3 "$FAKE_SYSTEMCTL_SOURCE" "$@"\n'
            )
            (self.bin / "sleep").write_bytes(b"#!/bin/sh\nexit 0\n")
            (self.bin / "journalctl").write_bytes(b"#!/bin/sh\necho mock-journal\n")
            subprocess.check_call([
                str(WSL), "-d", "Ubuntu-24.04", "--exec", "chmod", "+x",
                bash_path(self.bin / "systemctl"), bash_path(self.bin / "sleep"),
                bash_path(self.bin / "journalctl"),
            ])
        else:
            self.service_py = self.bin / "fake_systemctl.py"
            self.service_py.write_text(service_source, encoding="utf-8")
            systemctl.write_text("#!/bin/sh\nexec python3 \"$FAKE_SYSTEMCTL_SOURCE\" \"$@\"\n", encoding="utf-8")
            for name, content in (("sleep", "#!/bin/sh\nexit 0\n"), ("journalctl", "#!/bin/sh\necho mock-journal\n")):
                (self.bin / name).write_text(content, encoding="utf-8")
            for path in self.bin.iterdir():
                path.chmod(0o755)
        self.state.write_text(json.dumps({
            "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
            "Result": "success", "ExecMainCode": "exited", "ExecMainStatus": "0",
            "InvocationID": "", "CPUUsageNSec": "unknown", "MemoryCurrent": "unknown",
            "MemoryPeak": "unknown", "starts": 0,
        }))
        shutil.copyfile(
            ROOT.parent / "engineering_revision" / transport.APPROVAL_FILENAME,
            self.approval,
        )

    def tearDown(self) -> None:
        if self.linux_root is not None:
            subprocess.run(
                [str(WSL), "-d", "Ubuntu-24.04", "--exec", "rm", "-rf", self.linux_root],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            shutil.rmtree(self.root)

    def invoke(self, *, start_mode: str = "success", approval_mismatch: bool = False,
               r1_mismatch: bool = False) -> tuple[int, dict]:
        if approval_mismatch:
            self.approval.write_text("{}\n", encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "CAPTURE": str(self.capture),
            "FAKE_STATE": bash_path(self.state),
            "FAKE_SYSTEMCTL_SOURCE": bash_path(self.service_py),
            "FAKE_START_MODE": start_mode,
            "FAKE_R1_MISMATCH": "1" if r1_mismatch else "",
            "POLL_LIMIT": "1",
            "WSL_BIN": bash_path(self.bin),
        })
        path_key = "Path" if os.name == "nt" else "PATH"
        env[path_key] = str(self.bin) + (";" if os.name == "nt" else ":") + env.get(path_key, "")
        args = argparse_namespace(
            reader=str(PACKAGE / "static_plan_r2.json"), pkg=str(PACKAGE),
            remote_pkg=bash_path(self.remote_pkg), run=bash_path(self.run_dir), unit=UNIT,
            approval_path=bash_path(self.approval), diag=bash_path(self.diag),
            lock_path=bash_path(self.lock), key="fixture-key", host="fixture.invalid", user="fixture",
        )
        previous = os.environ.copy()
        os.environ.clear(); os.environ.update(env)
        try:
            if os.name == "nt":
                original_run = subprocess.run

                def fake_ssh(command, *, input, env):
                    self.assertEqual(command[0], "ssh")
                    self.assertIsInstance(input, bytes)
                    self.assertNotIn(b"\r", input)
                    self.capture.write_bytes(input)
                    wsl_env = [
                        "FAKE_STATE=" + env["FAKE_STATE"],
                        "FAKE_START_MODE=" + env["FAKE_START_MODE"],
                        "FAKE_R1_MISMATCH=" + env["FAKE_R1_MISMATCH"],
                        "FAKE_SYSTEMCTL_SOURCE=" + bash_path(self.service_py),
                        "POLL_LIMIT=" + env["POLL_LIMIT"],
                        "PATH=" + env["WSL_BIN"] + ":/usr/bin:/bin",
                    ]
                    remote = original_run(
                        [str(WSL), "-d", "Ubuntu-24.04", "--exec", "env", *wsl_env, "bash", "-s"],
                        input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    self.last_stdout = remote.stdout
                    self.last_stderr = remote.stderr
                    return subprocess.CompletedProcess(command, remote.returncode)

                with mock.patch.object(transport.subprocess, "run", fake_ssh):
                    code = transport.run(args)
            else:
                code = transport.run(args)
        finally:
            os.environ.clear(); os.environ.update(previous)
        return code, json.loads(self.state.read_text())

    def test_actual_ssh_stdin_is_exported_and_runs_one_start(self) -> None:
        code, state = self.invoke()
        self.assertEqual(code, 0, getattr(self, "last_stderr", b"").decode(errors="replace"))
        self.assertEqual(state["starts"], 1, getattr(self, "last_stderr", b"").decode(errors="replace"))
        payload_bytes = self.capture.read_bytes()
        self.assertNotIn(b"\r", payload_bytes)
        payload = payload_bytes.decode("utf-8")
        self.assertIn("export IDENTITY=", payload)
        self.assertIn("export APPROVAL_PATH=", payload)
        self.assertLess(payload.index("approval_bound=yes"), payload.index('systemctl --user start "$UNIT"'))
        if os.name == "nt":
            self.assertIn(b"approval_bound=yes", self.last_stdout)
        approval = json.loads(self.approval.read_text())
        self.assertEqual(approval["approval_body"]["plan_sha256"], "7e5334cd8c9691df59a63501e5ed8bbb8ad31e466ecffdb535ae45bed832fb45")
        settlement = json.loads((self.diag / "settlement.json").read_text())
        self.assertEqual(settlement["start_count"], 1)
        self.assertEqual(settlement["retry_count"], 0)
        self.assertEqual(settlement["status"], "TERMINAL_SUCCESS_REQUIRES_INDEPENDENT_AUDIT")
        self.assertLess(payload.index('test ! -e "$RUN"'), payload.index("approval_bound=yes"))
        self.assertEqual(
            (self.diag / "prior-r1-approval.json").read_bytes(),
            (ROOT.parent / "engineering_revision" / transport.APPROVAL_FILENAME).read_bytes(),
        )
        transition = json.loads((self.diag / "approval-transition.json").read_text())
        self.assertFalse(transition["automatic_restore"])

    def test_unknown_shared_approval_is_preserved_and_never_starts(self) -> None:
        code, state = self.invoke(approval_mismatch=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(state["starts"], 0)
        self.assertEqual(self.approval.read_text(), "{}\n")
        if os.name == "nt":
            self.assertNotIn(b"approval_bound=yes", self.last_stdout)

    def test_failed_r1_preflight_preserves_prior_approval(self) -> None:
        original = self.approval.read_bytes()
        code, state = self.invoke(r1_mismatch=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(state["starts"], 0)
        self.assertEqual(self.approval.read_bytes(), original)
        self.assertFalse((self.diag / "prior-r1-approval.json").exists())

    def test_pending_result_is_recorded_without_retry(self) -> None:
        code, state = self.invoke(start_mode="pending")
        self.assertNotEqual(code, 0)
        self.assertEqual(state["starts"], 1, getattr(self, "last_stderr", b"").decode(errors="replace"))
        settlement = json.loads((self.diag / "settlement.json").read_text())
        self.assertEqual(settlement["status"], "PENDING_TIMEOUT")
        self.assertEqual(settlement["retry_count"], 0)
        self.assertTrue((self.diag / "final-status.txt").is_file())


def argparse_namespace(**kwargs):
    from argparse import Namespace
    return Namespace(**kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
