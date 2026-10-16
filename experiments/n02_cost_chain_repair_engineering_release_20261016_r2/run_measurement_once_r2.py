from __future__ import annotations

import hashlib
import json
import pathlib
import posixpath
import shlex
import stat
import sys
import time
import zipfile

import paramiko


ROOT = pathlib.Path(__file__).resolve().parent
EVIDENCE = ROOT / "r2-measurement-evidence"
DEPLOY_EVIDENCE = ROOT / "v5-deploy-preflight-evidence"
PACKAGE_ROOT_LOCAL = ROOT / "package" / "civilian"
LOCAL_DEPLOYMENT_RECEIPT = DEPLOY_EVIDENCE / "deployment_receipt.json"
SSH_KEY = pathlib.Path(
    r"C:\Users\ASUS\AppData\Local\Temp\codex-n01-ssh-once-20261011\n01-deploy-once"
)
HOST = "172.17.27.173"
USER = "user1"
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
REMOTE_RELEASE = "/home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016_r2"
REMOTE_PACKAGE_ROOT = REMOTE_RELEASE + "/package/civilian"
REMOTE_DEPLOYMENT_RECEIPT = (
    "/home/user1/w1-pilot/diagnostics/"
    "n02-v5-cost-repair-engineering-20261016-r2/deployment_receipt.json"
)
RUN_ID = "n02-cost-measurement-20261016-r2"
WORK_ROOT = "/home/user1/w1-pilot/diagnostics/" + RUN_ID
UNIT_NAME = "n02-cost-repair-20261016-r2.service"
LOCAL_MEASUREMENT = EVIDENCE / RUN_ID
LOCAL_COST_EVIDENCE = EVIDENCE / "resource_cost_evidence" / RUN_ID
LOCAL_SUBMISSION_LOCK = EVIDENCE / "measurement-submission.lock"
LOCAL_STATUS = EVIDENCE / "measurement-execution.json"


def write_status(**fields: object) -> None:
    current = {}
    if LOCAL_STATUS.exists():
        current = json.loads(LOCAL_STATUS.read_text(encoding="utf-8"))
    current.update(fields)
    LOCAL_STATUS.write_text(
        json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def run(client: paramiko.SSHClient, argv: list[str], timeout: float = 420.0):
    _, stdout, stderr = client.exec_command(shlex.join(argv), get_pty=False, timeout=timeout)
    channel = stdout.channel
    out = bytearray()
    err = bytearray()
    while not channel.exit_status_ready():
        if channel.recv_ready():
            out.extend(channel.recv(65536))
        if channel.recv_stderr_ready():
            err.extend(channel.recv_stderr(65536))
        time.sleep(0.05)
    while channel.recv_ready():
        out.extend(channel.recv(65536))
    while channel.recv_stderr_ready():
        err.extend(channel.recv_stderr(65536))
    return channel.recv_exit_status(), out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def download_tree(sftp: paramiko.SFTPClient, remote: str, local: pathlib.Path) -> None:
    local.mkdir(parents=True, exist_ok=True)
    for entry in sftp.listdir_attr(remote):
        remote_child = posixpath.join(remote, entry.filename)
        local_child = local / entry.filename
        if stat.S_ISDIR(entry.st_mode):
            download_tree(sftp, remote_child, local_child)
        elif stat.S_ISREG(entry.st_mode):
            sftp.get(remote_child, str(local_child))
        else:
            raise RuntimeError(f"unexpected non-regular remote evidence: {remote_child}")


def main() -> int:
    if EVIDENCE.exists() or LOCAL_SUBMISSION_LOCK.exists():
        raise FileExistsError("r2 measurement wrapper already has state; do not resubmit")
    if not SSH_KEY.is_file():
        raise FileNotFoundError("validated SSH key path is unavailable")
    if not LOCAL_DEPLOYMENT_RECEIPT.is_file():
        raise FileNotFoundError("r2 deployment receipt is missing")
    deployment_bytes = LOCAL_DEPLOYMENT_RECEIPT.read_bytes()
    deployment = json.loads(deployment_bytes)
    if deployment.get("status") != "preflight_pass" or deployment.get("release") != pathlib.Path(REMOTE_RELEASE).name:
        raise PermissionError("r2 deployment receipt does not identify a successful matching preflight")
    archive_path = DEPLOY_EVIDENCE / "deployment-package.zip"
    archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if archive_sha != deployment.get("archive_sha256"):
        raise PermissionError("local r2 archive differs from the deployment receipt")
    with zipfile.ZipFile(archive_path) as archive:
        helper_bytes = archive.read("engineering_cost_bootstrap.py")
    helper_sha = hashlib.sha256(helper_bytes).hexdigest()
    if helper_sha != hashlib.sha256((ROOT / "engineering_cost_bootstrap.py").read_bytes()).hexdigest():
        raise PermissionError("r2 deployment archive does not contain the approved helper bytes")

    sys.path.insert(0, str(PACKAGE_ROOT_LOCAL))
    import resource_supervisor

    prior = resource_supervisor._read_prior_resource_cost(
        PACKAGE_ROOT_LOCAL / resource_supervisor.CARRY_FORWARD_RECEIPT_NAME,
        required=True,
    )
    if (
        prior.get("measurement_status") != "pending"
        or prior.get("execution_allowed") is not False
        or prior.get("preflight_allowed") is not True
    ):
        raise PermissionError("local r2 package is not in the pending-only measurement state")

    EVIDENCE.mkdir(parents=True, exist_ok=False)
    with LOCAL_SUBMISSION_LOCK.open("x", encoding="utf-8") as lock:
        lock.write("r2 measurement launch submission reserved\n")
    write_status(
        status="connecting",
        run_id=RUN_ID,
        unit_name=UNIT_NAME,
        work_root=WORK_ROOT,
        source_identity_sha256=deployment["source_identity_sha256"],
        archive_sha256=deployment["archive_sha256"],
        helper_sha256=helper_sha,
        prior_status_sha256=prior["status_sha256"],
        training_started=False,
        formal_attempt_created=False,
        authorization_created=False,
    )

    client = paramiko.SSHClient()
    client.load_system_host_keys(str(pathlib.Path.home() / ".ssh" / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            HOST,
            username=USER,
            password=None,
            key_filename=str(SSH_KEY),
            allow_agent=False,
            look_for_keys=False,
            timeout=20,
            banner_timeout=20,
            auth_timeout=30,
        )
        write_status(status="connected", host=HOST, user=USER)

        sftp = client.open_sftp()
        try:
            with sftp.file(REMOTE_DEPLOYMENT_RECEIPT, "rb") as remote_receipt_file:
                remote_receipt_bytes = remote_receipt_file.read()
        finally:
            sftp.close()
        if hashlib.sha256(remote_receipt_bytes).hexdigest() != hashlib.sha256(deployment_bytes).hexdigest():
            raise PermissionError("remote r2 deployment receipt differs from the local verified receipt")
        write_status(remote_receipt_sha256=hashlib.sha256(remote_receipt_bytes).hexdigest())

        hash_code, hash_out, hash_err = run(
            client,
            ["/usr/bin/sha256sum", REMOTE_RELEASE + "/engineering_cost_bootstrap.py"],
        )
        (EVIDENCE / "remote-helper-hash.stdout.txt").write_text(hash_out, encoding="utf-8")
        (EVIDENCE / "remote-helper-hash.stderr.txt").write_text(hash_err, encoding="utf-8")
        remote_helper_sha = hash_out.split()[0] if hash_out.split() else ""
        if hash_code != 0 or remote_helper_sha != helper_sha:
            raise PermissionError("remote r2 helper hash differs from the approved archive helper")
        write_status(remote_helper_sha256=remote_helper_sha, remote_helper_hash_verified=True)

        launch_argv = [
            PYTHON,
            "-B",
            REMOTE_RELEASE + "/engineering_cost_bootstrap.py",
            "--launch",
            "--package-root",
            REMOTE_PACKAGE_ROOT,
            "--work-root",
            WORK_ROOT,
            "--unit-name",
            UNIT_NAME,
            "--deployment-receipt",
            REMOTE_DEPLOYMENT_RECEIPT,
        ]
        write_status(status="launch_submitted", launch_submissions=1)
        launch_code, launch_stdout, launch_stderr = run(client, launch_argv)
        (EVIDENCE / "measurement-launch.stdout.txt").write_text(launch_stdout, encoding="utf-8")
        (EVIDENCE / "measurement-launch.stderr.txt").write_text(launch_stderr, encoding="utf-8")
        write_status(status="launch_returned", launch_exit_code=launch_code)

        writer_code = None
        if launch_code == 0:
            writer_code, writer_stdout, writer_stderr = run(
                client,
                [
                    PYTHON,
                    "-B",
                    REMOTE_RELEASE + "/build_prior_resource_cost.py",
                    "--package-root",
                    REMOTE_PACKAGE_ROOT,
                    "--measurement-root",
                    WORK_ROOT,
                    "--run-id",
                    RUN_ID,
                ],
            )
            (EVIDENCE / "measurement-writer.stdout.txt").write_text(writer_stdout, encoding="utf-8")
            (EVIDENCE / "measurement-writer.stderr.txt").write_text(writer_stderr, encoding="utf-8")
            write_status(status="writer_returned", writer_exit_code=writer_code)
            if writer_code == 0:
                validator_code, validator_stdout, validator_stderr = run(
                    client,
                    [
                        PYTHON,
                        "-B",
                        "-c",
                        "import json,sys; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root)); import resource_supervisor; value=resource_supervisor._read_prior_resource_cost(root/resource_supervisor.CARRY_FORWARD_RECEIPT_NAME,required=True); print(json.dumps({k:value.get(k) for k in ('measurement_status','execution_allowed','receipt_sha256','total_wall_seconds','total_cpu_seconds','stage_coverage')},sort_keys=True))",
                        REMOTE_PACKAGE_ROOT,
                    ],
                )
                (EVIDENCE / "measurement-validator.stdout.txt").write_text(validator_stdout, encoding="utf-8")
                (EVIDENCE / "measurement-validator.stderr.txt").write_text(validator_stderr, encoding="utf-8")
                write_status(canonical_validator_exit_code=validator_code)
                if validator_code != 0:
                    writer_code = validator_code

        if launch_code != 0:
            journal_code, journal_out, journal_err = run(
                client,
                ["journalctl", "--user", "--unit=" + UNIT_NAME, "--no-pager", "--output=short-iso"],
            )
            (EVIDENCE / "measurement-journal.stdout.txt").write_text(journal_out, encoding="utf-8")
            (EVIDENCE / "measurement-journal.stderr.txt").write_text(journal_err, encoding="utf-8")
            write_status(journal_exit_code=journal_code)

        sftp = client.open_sftp()
        try:
            try:
                sftp.stat(WORK_ROOT)
            except OSError:
                write_status(remote_measurement_root_downloaded=False)
            else:
                download_tree(sftp, WORK_ROOT, LOCAL_MEASUREMENT)
                write_status(remote_measurement_root_downloaded=True)
            if writer_code == 0:
                download_tree(
                    sftp,
                    REMOTE_PACKAGE_ROOT + "/resource_cost_evidence/" + RUN_ID,
                    LOCAL_COST_EVIDENCE,
                )
                sftp.get(
                    REMOTE_PACKAGE_ROOT + "/PRIOR_RESOURCE_COST.json",
                    str(EVIDENCE / "measured-PRIOR_RESOURCE_COST.json"),
                )
                write_status(committed_receipt_and_evidence_downloaded=True)
        finally:
            sftp.close()

        if launch_code != 0:
            write_status(status="launch_failed_first_attempt")
            print(json.dumps({"status": "launch_failed_first_attempt", "launch_exit_code": launch_code}, sort_keys=True))
            return launch_code or 1
        if writer_code != 0:
            write_status(status="writer_failed_first_attempt")
            print(json.dumps({"status": "writer_failed_first_attempt", "writer_exit_code": writer_code}, sort_keys=True))
            return writer_code or 1
        write_status(status="completed", canonical_validator_exit_code=0)
        print(json.dumps({"status": "completed", "run_id": RUN_ID, "unit_name": UNIT_NAME}, sort_keys=True))
        return 0
    except Exception as exc:
        write_status(status="wrapper_error_no_retry", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
