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
from execution_gate import (
    AUTHORIZATION_SCHEMA,
    FORMAL_BUDGET,
    FORMAL_SCOPE,
    FORMAL_UPGRADE_SCHEMA,
    load_release_binding,
    validate_authorization_document,
    validate_preflight_receipt,
)

HOST = "172.17.27.173"
USER = "user1"
RELEASE = "ch2_disaster_relief_n02_cost_repair_engineering_20261016_r2_closed_db_fix_final"
REMOTE_ROOT = "/home/user1/w1-pilot"
PUBLISH = f"{REMOTE_ROOT}/packages/{RELEASE}"
AUTH_ROOT = f"{REMOTE_ROOT}/authorizations"
AUTH_ID = "n02-v5-formal-auth-binding-closed-db-fix-final-once"
AUTH_REMOTE = f"{AUTH_ROOT}/{AUTH_ID}.json"
PREFLIGHT_ID = "n02-v5-cost-repair-engineering-20261016-r2-closed-db-fix-final"
PREFLIGHT_REMOTE = f"{REMOTE_ROOT}/diagnostics/{PREFLIGHT_ID}/preflight_receipt.json"
RUN_REMOTE = f"{REMOTE_ROOT}/runs/{AUTH_ID}"
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
KNOWN_HOSTS = pathlib.Path.home() / ".ssh" / "known_hosts"
CONTRACT_PATH = ROOT / "FINAL_FORMAL_AUTHORIZATION_CONTRACT.json"
MEASUREMENT_RECORD = ROOT / "package" / "civilian" / "PRIOR_RESOURCE_COST.json"
MEASUREMENT_EVIDENCE = ROOT / "package" / "civilian" / "resource_cost_evidence" / "n02-cost-measurement-20261016-r2-closed-db-fix"
MEASUREMENT_DEPLOYMENT = MEASUREMENT_EVIDENCE / "deployment_receipt.json"
MEASUREMENT_STAGE_RECEIPT = MEASUREMENT_EVIDENCE / "receipts" / "01-input_admission.json"
FINAL_DEPLOYMENT = ROOT / "measured-final-deployment-evidence" / "deployment_receipt.json"


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


def build_contract(binding: dict, preflight_sha: str) -> dict:
    measured = json.loads(MEASUREMENT_RECORD.read_text(encoding="utf-8"))
    measurement_deployment = json.loads(MEASUREMENT_DEPLOYMENT.read_text(encoding="utf-8"))
    measurement_stage = json.loads(MEASUREMENT_STAGE_RECEIPT.read_text(encoding="utf-8"))
    final_deployment = json.loads(FINAL_DEPLOYMENT.read_text(encoding="utf-8"))
    receipt_sha = sha256_bytes(MEASUREMENT_RECORD.read_bytes())
    measurement_deployment_sha = sha256_bytes(MEASUREMENT_DEPLOYMENT.read_bytes())
    final_deployment_sha = sha256_bytes(FINAL_DEPLOYMENT.read_bytes())
    if (
        measured.get("status") != "measured_single_stage_bootstrap"
        or measurement_stage.get("status") != "accepted"
        or measurement_stage.get("first_error") is not None
        or measured.get("stage_coverage") != ["input_admission"]
        or measured.get("total_wall_seconds", 10**9) > FORMAL_BUDGET["server_wall_seconds"]
        or measured.get("total_cpu_seconds", 10**9) > FORMAL_BUDGET["server_cpu_seconds"]
        or measurement_deployment.get("status") != "preflight_pass"
        or measurement_deployment.get("source_identity_sha256") != measured.get("source_identity_sha256")
        or measurement_deployment.get("archive_sha256") != measured.get("deployed_package_archive_sha256")
        or final_deployment.get("status") != "preflight_pass"
    ):
        raise ValueError("measured or final deployment evidence is invalid")
    static = {
        "authorized": False,
        "request_frozen": False,
        "request_scope": binding["request_scope"],
        "budget": None,
        "candidate_request_identity_sha256": binding["candidate_request_identity_sha256"],
        "candidate_attempt_identity_sha256": binding["candidate_attempt_identity_sha256"],
        "release_manifest_sha256": binding["release_manifest_sha256"],
        "hash_bundle_sha256": binding["hash_bundle_sha256"],
    }
    upgrade = {
        "schema": FORMAL_UPGRADE_SCHEMA,
        "state": "approved",
        "authorized": True,
        "request_frozen": True,
        "scope": FORMAL_SCOPE,
        "budget": FORMAL_BUDGET,
        "candidate_request_identity_sha256": static["candidate_request_identity_sha256"],
        "candidate_attempt_identity_sha256": static["candidate_attempt_identity_sha256"],
        "release_manifest_sha256": static["release_manifest_sha256"],
        "hash_bundle_sha256": static["hash_bundle_sha256"],
    }
    contract = {
        "schema": "n02-v5-formal-authorization-contract/1",
        "package_release": binding["package_release"],
        "static_candidate": static,
        "formal_upgrade": upgrade,
        "measurement": {
            "status": measured["status"],
            "receipt_sha256": receipt_sha,
            "deployment_receipt_sha256": measurement_deployment_sha,
            "source_identity_sha256": measured["source_identity_sha256"],
            "deployed_package_archive_sha256": measured["deployed_package_archive_sha256"],
            "unit_name": "n02-cost-repair-20261016-r2-closed-db-fix.service",
            "systemd_invocation_id": measured["systemd_invocation_id"],
            "systemd_wall_seconds": measured["total_wall_seconds"],
            "systemd_cpu_seconds": measured["total_cpu_seconds"],
            "stage_coverage": measured["stage_coverage"],
            "execution_allowed": True,
        },
        "final_deployment": {
            "status": final_deployment["status"],
            "receipt_sha256": final_deployment_sha,
            "source_identity_sha256": final_deployment["source_identity_sha256"],
            "archive_sha256": final_deployment["archive_sha256"],
            "engineering_id": PREFLIGHT_ID,
            "preflight_receipt_sha256": preflight_sha,
        },
        "rules": [
            "The package sidecars remain candidate-only and are never rewritten after preflight.",
            "The external one-time envelope binds all four static digests exactly.",
            "The external request, attempt, and formal_upgrade carry the same formal scope and budget.",
            "Any digest, scope, budget, state, or candidate flag mismatch is rejected before systemd submission.",
        ],
    }
    CONTRACT_PATH.write_bytes(canonical(contract))
    return contract


def make_auth(binding: dict, preflight_sha: str) -> dict:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
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
    measurement = contract.get("measurement")
    if not isinstance(measurement, dict):
        raise ValueError("formal authorization contract is missing measured receipt binding")
    measured = json.loads(MEASUREMENT_RECORD.read_text(encoding="utf-8"))
    measured_receipt_sha256 = hashlib.sha256(MEASUREMENT_RECORD.read_bytes()).hexdigest()
    if (
        measured.get("status") != "measured_single_stage_bootstrap"
        or measured_receipt_sha256 != measurement.get("receipt_sha256")
        or measured.get("source_identity_sha256") != measurement.get("source_identity_sha256")
        or measured.get("deployed_package_archive_sha256") != measurement.get("deployed_package_archive_sha256")
        or measured.get("stage_coverage") != measurement.get("stage_coverage")
        or measured.get("total_wall_seconds", 10**9) > FORMAL_BUDGET["server_wall_seconds"]
        or measured.get("total_cpu_seconds", 10**9) > FORMAL_BUDGET["server_cpu_seconds"]
        or measurement.get("deployment_receipt_sha256") != hashlib.sha256(MEASUREMENT_DEPLOYMENT.read_bytes()).hexdigest()
        or measurement.get("unit_name") != "n02-cost-repair-20261016-r2-closed-db-fix.service"
    ):
        raise ValueError("formal authorization measurement binding is invalid")
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
        "measurement": measurement,
    }
    authorization["authorization_sha256"] = digest(authorization)
    return authorization


def main() -> int:
    evidence = ROOT / "final-formal-run-evidence"
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
        local_preflight_root = evidence / "diagnostics"
        local_preflight_dir = local_preflight_root / PREFLIGHT_ID
        local_preflight_dir.mkdir(parents=True, exist_ok=False)
        local_preflight_path = local_preflight_dir / "preflight_receipt.json"
        local_preflight_path.write_bytes(preflight_bytes)
        (evidence / "preflight_receipt.json").write_bytes(preflight_bytes)
        preflight = json.loads(preflight_bytes.decode("utf-8"))
        preflight_sha = sha256_bytes(preflight_bytes)
        if (
            preflight.get("status") != "accepted"
            or preflight.get("engineering_id") != PREFLIGHT_ID
            or preflight.get("release_manifest_sha256") != binding["release_manifest_sha256"]
            or preflight.get("hash_bundle_sha256") != binding["hash_bundle_sha256"]
            or preflight.get("candidate_request_identity_sha256") != binding["candidate_request_identity_sha256"]
            or preflight.get("candidate_attempt_identity_sha256") != binding["candidate_attempt_identity_sha256"]
        ):
            raise RuntimeError("PREFLIGHT_BINDING_MISMATCH")
        local_preflight_binding = {
            "engineering_id": PREFLIGHT_ID,
            "path": str(local_preflight_path),
            "sha256": preflight_sha,
        }
        validate_preflight_receipt(
            local_preflight_path,
            local_preflight_binding,
            binding,
            diagnostics_root=local_preflight_root,
        )
        build_contract(binding, preflight_sha)
        (evidence / "FINAL_FORMAL_AUTHORIZATION_CONTRACT.json").write_bytes(CONTRACT_PATH.read_bytes())
        auth = make_auth(binding, preflight_sha)
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
