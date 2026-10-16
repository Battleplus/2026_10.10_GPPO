from __future__ import annotations

import getpass
import hashlib
import json
import pathlib
import shlex
import stat
import sys
import time

import paramiko

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "package" / "civilian"))
from execution_gate import AUTHORIZATION_SCHEMA, load_release_binding, validate_authorization_document

HOST = "172.17.27.173"
USER = "user1"
RELEASE = "ch2_disaster_relief_n02_formal_auth_binding_v5"
REMOTE_ROOT = "/home/user1/w1-pilot"
PUBLISH = f"{REMOTE_ROOT}/packages/{RELEASE}"
AUTH_ROOT = f"{REMOTE_ROOT}/authorizations"
AUTH_ID = "n02-v5-formal-auth-binding-once"
AUTH_REMOTE = f"{AUTH_ROOT}/{AUTH_ID}.json"
PREFLIGHT_ID = "n02-v5-preflight-formal-auth-binding"
PREFLIGHT_REMOTE = f"{REMOTE_ROOT}/diagnostics/{PREFLIGHT_ID}/preflight_receipt.json"
RUN_REMOTE = f"{REMOTE_ROOT}/runs/{AUTH_ID}"
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
KNOWN_HOSTS = pathlib.Path.home() / ".ssh" / "known_hosts"


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(client: paramiko.SSHClient, argv: list[str], timeout: float = 300.0) -> tuple[int, str, str]:
    _, out, err = client.exec_command(shlex.join(argv), get_pty=False, timeout=timeout)
    channel = out.channel
    stdout = bytearray(); stderr = bytearray()
    started = time.monotonic()
    while not channel.exit_status_ready():
        if channel.recv_ready(): stdout.extend(channel.recv(65536))
        if channel.recv_stderr_ready(): stderr.extend(channel.recv_stderr(65536))
        if time.monotonic() - started > timeout:
            channel.close(); raise TimeoutError("REMOTE_COMMAND_TIMEOUT")
        time.sleep(0.05)
    while channel.recv_ready(): stdout.extend(channel.recv(65536))
    while channel.recv_stderr_ready(): stderr.extend(channel.recv_stderr(65536))
    return channel.recv_exit_status(), stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


def make_auth(binding: dict, preflight_sha: str) -> dict:
    contract = json.loads((ROOT / "FORMAL_AUTHORIZATION_CONTRACT.json").read_text(encoding="utf-8"))
    static = contract["static_candidate"]
    for key in (
        "candidate_request_identity_sha256",
        "candidate_attempt_identity_sha256",
        "release_manifest_sha256",
        "hash_bundle_sha256",
    ):
        if binding.get(key) != static.get(key):
            raise ValueError(f"static candidate mismatch: {key}")
    upgrade = dict(contract["formal_upgrade"])
    upgrade.update({
        "candidate_request_identity_sha256": static["candidate_request_identity_sha256"],
        "candidate_attempt_identity_sha256": static["candidate_attempt_identity_sha256"],
        "release_manifest_sha256": static["release_manifest_sha256"],
        "hash_bundle_sha256": static["hash_bundle_sha256"],
    })
    scope = upgrade["scope"]; budget = upgrade["budget"]
    attempt_body = {
        "attempt_id": AUTH_ID,
        "candidate_attempt_identity_sha256": static["candidate_attempt_identity_sha256"],
        "candidate_request_identity_sha256": static["candidate_request_identity_sha256"],
        "release_manifest_sha256": static["release_manifest_sha256"],
        "hash_bundle_sha256": static["hash_bundle_sha256"],
    }
    attempt = {
        "id": AUTH_ID,
        "candidate_identity_sha256": static["candidate_attempt_identity_sha256"],
        "identity_sha256": digest(attempt_body),
    }
    authorization = {
        "schema": AUTHORIZATION_SCHEMA,
        "state": "authorized",
        "one_time": True,
        "release_manifest_sha256": static["release_manifest_sha256"],
        "hash_bundle_sha256": static["hash_bundle_sha256"],
        "scope": scope,
        "budget": budget,
        "attempt": attempt,
        "request": {"identity_sha256": static["candidate_request_identity_sha256"], "scope": scope, "budget": budget},
        "formal_upgrade": upgrade,
        "preflight": {"engineering_id": PREFLIGHT_ID, "path": PREFLIGHT_REMOTE, "sha256": preflight_sha},
    }
    authorization["authorization_sha256"] = digest(authorization)
    return authorization


def main() -> int:
    evidence = ROOT / "v5-formal-run-evidence"
    evidence.mkdir(exist_ok=False)
    binding = load_release_binding(ROOT / "package" / "civilian")
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(KNOWN_HOSTS))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    password = getpass.getpass("SSH password (hidden input): ")
    try:
        client.connect(HOST, username=USER, password=password, allow_agent=False, look_for_keys=False, timeout=20, banner_timeout=20, auth_timeout=30)
        password = ""
        sftp = client.open_sftp()
        with sftp.file(PREFLIGHT_REMOTE, "rb") as stream: preflight_bytes = stream.read()
        (evidence / "preflight_receipt.json").write_bytes(preflight_bytes)
        preflight = json.loads(preflight_bytes.decode("utf-8"))
        if preflight.get("status") != "accepted": raise RuntimeError("PREFLIGHT_NOT_ACCEPTED")
        auth = make_auth(binding, sha256_bytes(preflight_bytes))
        authorization_binding = validate_authorization_document(auth, binding)
        (evidence / "authorization-validation.json").write_text(
            json.dumps(authorization_binding, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        auth_bytes = canonical(auth)
        (evidence / "authorization.json").write_bytes(auth_bytes)
        for remote_path in (AUTH_REMOTE, RUN_REMOTE):
            try:
                sftp.stat(remote_path)
            except FileNotFoundError:
                pass
            else:
                raise RuntimeError(f"ONE_SHOT_PATH_ALREADY_EXISTS:{remote_path}")
        with sftp.file(AUTH_REMOTE, "wx") as stream: stream.write(auth_bytes)
        sftp.close()
        command = [PYTHON, "-B", f"{PUBLISH}/package/civilian/driver.py", "--run", "--authorization", AUTH_REMOTE]
        unit = f"n02-v4-{AUTH_ID}.service"
        handoff = None
        submission_error = None
        try:
            code, out, err = run(client, command, 120)
            (evidence / "submission.txt").write_text(out + err, encoding="utf-8")
            if code != 0:
                submission_error = f"FORMAL_SUBMISSION_FAILED:{code}"
            else:
                handoff = json.loads(out.strip().splitlines()[-1])
                unit = handoff.get("unit_name") or unit
                (evidence / "handoff.json").write_text(json.dumps(handoff, indent=2), encoding="utf-8")
        except Exception as exc:
            submission_error = f"{type(exc).__name__}: {exc}"
            (evidence / "submission-error.txt").write_text(submission_error, encoding="utf-8")

        deadline = time.monotonic() + 1900
        last = ""
        terminal_fields = {}
        while time.monotonic() < deadline:
            status, show, showerr = run(client, ["systemctl", "--user", "show", unit, "--property=LoadState", "--property=InvocationID", "--property=ActiveState", "--property=SubState", "--property=Result", "--property=MainPID", "--property=ExecMainStatus", "--property=CPUUsageNSec", "--property=MemoryPeak", "--property=ControlGroup"], 30)
            snapshot = show + showerr
            if snapshot != last:
                (evidence / "latest-systemd-show.txt").write_text(snapshot, encoding="utf-8")
                last = snapshot
            fields = dict(line.split("=", 1) for line in show.splitlines() if "=" in line)
            if fields.get("LoadState") == "not-found" or (
                fields.get("ActiveState") in {"inactive", "failed"}
                and fields.get("SubState") in {"dead", "failed"}
            ):
                terminal_fields = fields
                break
            time.sleep(5)
        else:
            raise TimeoutError("FORMAL_RUN_MONITOR_TIMEOUT")
        (evidence / "systemd-terminal.json").write_text(
            json.dumps({"unit": unit, "properties": terminal_fields, "submission_error": submission_error}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _, journal, journal_err = run(
            client, ["journalctl", "--user", "-u", unit, "--no-pager", "-o", "short-iso-precise"], 60
        )
        (evidence / "journal.txt").write_text(journal, encoding="utf-8")
        (evidence / "journal.stderr.txt").write_text(journal_err, encoding="utf-8")

        def download_tree(remote: str, local: pathlib.Path) -> None:
            local.mkdir(parents=True, exist_ok=True)
            for item in sftp.listdir_attr(remote):
                r = remote + "/" + item.filename; p = local / item.filename
                if stat.S_ISDIR(item.st_mode): download_tree(r, p)
                else:
                    with sftp.file(r, "rb") as src: p.write_bytes(src.read())
        sftp = client.open_sftp()
        try:
            download_tree(RUN_REMOTE, evidence / "run-once")
        except FileNotFoundError:
            (evidence / "run-tree-missing.txt").write_text("remote run root is absent\n", encoding="utf-8")
        sftp.close()
        result = terminal_fields.get("Result")
        state = terminal_fields.get("ActiveState")
        status = "formal_run_terminal" if state in {"inactive", "failed"} else "formal_submission_unconfirmed"
        print(json.dumps({"status":status,"unit":unit,"active_state":state,"result":result,"submission_error":submission_error,"evidence":str(evidence)}, ensure_ascii=False))
        return 0 if status == "formal_run_terminal" and result == "success" else 1
    finally:
        password = ""
        client.close()


if __name__ == "__main__": raise SystemExit(main())
