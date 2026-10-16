from __future__ import annotations

import hashlib
import json
import pathlib
import posixpath
import shlex
import stat
import sys
import time

import paramiko


EVIDENCE = pathlib.Path(__file__).resolve().parent
RELEASE_ROOT = EVIDENCE.parent
PACKAGE_ROOT_LOCAL = RELEASE_ROOT / "package" / "civilian"
LOCAL_DEPLOYMENT_RECEIPT = EVIDENCE / "deployment_receipt.json"
SSH_KEY = pathlib.Path(
    r"C:\Users\ASUS\AppData\Local\Temp\codex-n01-ssh-once-20261011\n01-deploy-once"
)
HOST = "172.17.27.173"
USER = "user1"
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
REMOTE_RELEASE = "/home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016"
REMOTE_PACKAGE_ROOT = REMOTE_RELEASE + "/package/civilian"
REMOTE_DEPLOYMENT_RECEIPT = (
    "/home/user1/w1-pilot/diagnostics/"
    "n02-v5-cost-repair-engineering-20261016/deployment_receipt.json"
)
RUN_ID = "n02-cost-measurement-20261016-r1"
WORK_ROOT = "/home/user1/w1-pilot/diagnostics/" + RUN_ID
UNIT_NAME = "n02-cost-repair-20261016-r1.service"
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
    if LOCAL_SUBMISSION_LOCK.exists():
        raise FileExistsError("measurement wrapper already ran; preserve its state and do not resubmit")
    if not SSH_KEY.is_file():
        raise FileNotFoundError("validated SSH key path is unavailable")
    if not LOCAL_DEPLOYMENT_RECEIPT.is_file():
        raise FileNotFoundError("local deployment receipt is missing")
    deployment = json.loads(LOCAL_DEPLOYMENT_RECEIPT.read_text(encoding="utf-8"))
    if deployment.get("status") != "preflight_pass":
        raise PermissionError("deployment receipt does not record a successful target preflight")
    sys.path.insert(0, str(RELEASE_ROOT))
    from deployment_identity import source_identity_sha256

    if source_identity_sha256(PACKAGE_ROOT_LOCAL) != deployment.get("source_identity_sha256"):
        raise PermissionError("local source identity differs from the deployed receipt")
    receipt_sha256 = hashlib.sha256(LOCAL_DEPLOYMENT_RECEIPT.read_bytes()).hexdigest()

    # The marker makes a second launch impossible from this one-use wrapper.
    with LOCAL_SUBMISSION_LOCK.open("x", encoding="utf-8") as lock:
        lock.write("measurement launch submission reserved\n")
    write_status(
        status="connecting",
        run_id=RUN_ID,
        unit_name=UNIT_NAME,
        work_root=WORK_ROOT,
        deployment_receipt_sha256=receipt_sha256,
        deployment_archive_sha256=deployment["archive_sha256"],
        source_identity_sha256=deployment["source_identity_sha256"],
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
        code, stdout, stderr = run(client, launch_argv)
        (EVIDENCE / "measurement-launch.stdout.txt").write_text(stdout, encoding="utf-8")
        (EVIDENCE / "measurement-launch.stderr.txt").write_text(stderr, encoding="utf-8")
        write_status(status="launch_returned", launch_exit_code=code)

        writer_code = None
        validator_stdout = ""
        validator_stderr = ""
        if code == 0:
            writer_argv = [
                PYTHON,
                "-B",
                REMOTE_RELEASE + "/build_prior_resource_cost.py",
                "--package-root",
                REMOTE_PACKAGE_ROOT,
                "--measurement-root",
                WORK_ROOT,
                "--run-id",
                RUN_ID,
            ]
            write_status(status="writer_submitted", writer_submissions=1)
            writer_code, writer_stdout, writer_stderr = run(client, writer_argv)
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
                write_status(status="canonical_validator_returned", canonical_validator_exit_code=validator_code)
                if validator_code != 0:
                    writer_code = validator_code

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

        if code != 0:
            write_status(status="launch_failed_first_attempt", training_started=False)
            print(json.dumps({"status": "launch_failed_first_attempt", "launch_exit_code": code}, sort_keys=True))
            return code or 1
        if writer_code != 0:
            write_status(status="writer_failed_first_attempt", training_started=False)
            print(json.dumps({"status": "writer_failed_first_attempt", "writer_exit_code": writer_code}, sort_keys=True))
            return writer_code or 1
        write_status(status="completed", canonical_receipt_validated=True)
        print(json.dumps({"status": "completed", "run_id": RUN_ID, "unit_name": UNIT_NAME}, sort_keys=True))
        return 0
    except Exception as exc:
        write_status(status="wrapper_error_no_retry", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
