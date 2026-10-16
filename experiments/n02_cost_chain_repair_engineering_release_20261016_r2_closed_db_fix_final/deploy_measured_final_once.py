from __future__ import annotations

import base64
import getpass
import hashlib
import json
import pathlib
import shlex

import paramiko

from deployment_identity import build_deployment_archive, source_identity_sha256

ROOT = pathlib.Path(__file__).resolve().parent
HOST = "172.17.27.173"
USER = "user1"
RELEASE = "ch2_disaster_relief_n02_cost_repair_engineering_20261016_r2_closed_db_fix_final"
REMOTE_ROOT = "/home/user1/w1-pilot"
STAGE = f"{REMOTE_ROOT}/staging/{RELEASE}"
PUBLISH = f"{REMOTE_ROOT}/packages/{RELEASE}"
REMOTE_ARCHIVE = f"{STAGE}.deployment-package.zip"
DIAG = f"{REMOTE_ROOT}/diagnostics/n02-v5-cost-repair-engineering-20261016-r2-closed-db-fix-final"
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
KNOWN_HOSTS = pathlib.Path.home() / ".ssh" / "known_hosts"
METADATA = ("V4_RELEASE_MANIFEST.json", "V4_RELEASE_SHA256SUMS.txt", "V4_HASH_BUNDLE.json", "V4_STATIC_REQUEST_IDENTITY.json", "V4_STATIC_ATTEMPT_IDENTITY.json", "engineering_cost_bootstrap.py", "build_prior_resource_cost.py")

REMOTE_VERIFY = r'''
from pathlib import Path
import hashlib,json,os,sys
stage=Path(sys.argv[1]); pub=Path(sys.argv[2]); archive=Path(sys.argv[3]); expected_archive_sha=sys.argv[4]; expected_metadata=json.loads(sys.argv[5])
if pub.exists(): raise RuntimeError("PUBLISH_TARGET_EXISTS")
if archive.is_symlink() or not archive.is_file(): raise RuntimeError("ARCHIVE_INVALID")
actual_archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
if actual_archive_sha != expected_archive_sha: raise RuntimeError("ARCHIVE_SHA_MISMATCH")
m=json.loads((stage/"V4_RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
rows={x["path"]:x for x in m["files"]}
for rel,row in rows.items():
 p=stage/rel
 if not p.is_file() or p.is_symlink(): raise RuntimeError("FILE_INVALID:"+rel)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=row["sha256"]: raise RuntimeError("SHA_MISMATCH:"+rel)
for rel,expected_sha in expected_metadata.items():
 p=stage/rel
 if not p.is_file() or p.is_symlink(): raise RuntimeError("METADATA_INVALID:"+rel)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=expected_sha: raise RuntimeError("METADATA_SHA_MISMATCH:"+rel)
for p in stage.rglob("*"):
 if p.is_symlink() or (p.is_file() and (p.suffix in (".pyc",".pyo") or "__pycache__" in p.parts)): raise RuntimeError("BYTECODE_OR_SYMLINK")
expected=set(rows)|set(expected_metadata)
observed={p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
if observed!=expected: raise RuntimeError("FILE_SET_MISMATCH")
archive.unlink()
os.rename(stage,pub)
print(json.dumps({"status":"published","release":str(pub),"files":len(observed),"archive_sha256":actual_archive_sha},sort_keys=True))
'''


def run(client: paramiko.SSHClient, argv: list[str], timeout: float = 300.0) -> tuple[int, str, str]:
    _, out, err = client.exec_command(shlex.join(argv), get_pty=False, timeout=timeout)
    channel = out.channel
    stdout = bytearray()
    stderr = bytearray()
    while not channel.exit_status_ready():
        if channel.recv_ready(): stdout.extend(channel.recv(65536))
        if channel.recv_stderr_ready(): stderr.extend(channel.recv_stderr(65536))
    while channel.recv_ready(): stdout.extend(channel.recv(65536))
    while channel.recv_stderr_ready(): stderr.extend(channel.recv_stderr(65536))
    return channel.recv_exit_status(), stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


def mkdirs(sftp: paramiko.SFTPClient, path: str) -> None:
    current = ""
    for part in pathlib.PurePosixPath(path).parts:
        current = current + "/" + part if current else part
        try: sftp.stat(current)
        except FileNotFoundError: sftp.mkdir(current, mode=0o700)


def main() -> int:
    evidence = ROOT / "measured-final-deployment-evidence"
    evidence.mkdir(exist_ok=False)
    manifest = json.loads((ROOT / "V4_RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    package_files = [ROOT / row["path"] for row in manifest["files"]]
    for path in package_files:
        if not path.is_file() or path.is_symlink(): raise RuntimeError(f"LOCAL_FILE_INVALID:{path}")
    metadata_files = [ROOT / name for name in METADATA]
    metadata_hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in zip(METADATA, metadata_files)
    }
    deployment_archive = evidence / "deployment-package.zip"
    archive_sha = build_deployment_archive(ROOT, [*package_files, *metadata_files], deployment_archive)
    archive_bytes = deployment_archive.read_bytes()
    if hashlib.sha256(archive_bytes).hexdigest() != archive_sha:
        raise IOError("LOCAL_ARCHIVE_CHANGED_AFTER_BUILD")
    source_sha = source_identity_sha256(ROOT / "package" / "civilian")
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(KNOWN_HOSTS))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    password = getpass.getpass("SSH password (hidden input): ")
    try:
        client.connect(HOST, username=USER, password=password, allow_agent=False, look_for_keys=False, timeout=20, banner_timeout=20, auth_timeout=30)
        password = ""
        code, out, err = run(client, [PYTHON, "-B", "-c", "import getpass,socket,sys; print(socket.gethostname(),getpass.getuser(),sys.executable)"])
        (evidence / "identity.txt").write_text(out + err, encoding="utf-8")
        if code != 0: raise RuntimeError("REMOTE_IDENTITY_FAILED")
        sftp = client.open_sftp()
        for base in (f"{REMOTE_ROOT}/staging", f"{REMOTE_ROOT}/packages", f"{REMOTE_ROOT}/diagnostics"):
            sftp.stat(base)
        try: sftp.stat(STAGE); raise RuntimeError("STAGE_ALREADY_EXISTS")
        except FileNotFoundError: pass
        try: sftp.stat(PUBLISH); raise RuntimeError("PUBLISH_ALREADY_EXISTS")
        except FileNotFoundError: pass
        try: sftp.stat(REMOTE_ARCHIVE); raise RuntimeError("ARCHIVE_TARGET_EXISTS")
        except FileNotFoundError: pass
        sftp.mkdir(STAGE, mode=0o700)
        for path in package_files:
            rel = path.relative_to(ROOT).as_posix()
            remote = f"{STAGE}/{rel}"
            mkdirs(sftp, str(pathlib.PurePosixPath(remote).parent))
            with path.open("rb") as src, sftp.file(remote, "wx") as dst:
                while block := src.read(1024 * 1024): dst.write(block)
        for name in METADATA:
            with (ROOT / name).open("rb") as src, sftp.file(f"{STAGE}/{name}", "wx") as dst:
                while block := src.read(1024 * 1024): dst.write(block)
        with sftp.file(REMOTE_ARCHIVE, "wx") as destination:
            destination.write(archive_bytes)
        sftp.close()
        encoded = base64.b64encode(REMOTE_VERIFY.encode()).decode()
        metadata_json = json.dumps(metadata_hashes, sort_keys=True, separators=(",", ":"))
        verify = [PYTHON, "-B", "-c", "import base64;exec(base64.b64decode(" + repr(encoded) + "))", STAGE, PUBLISH, REMOTE_ARCHIVE, archive_sha, metadata_json]
        code, out, err = run(client, verify)
        (evidence / "publish.txt").write_text(out + err, encoding="utf-8")
        if code != 0: raise RuntimeError("REMOTE_PUBLISH_FAILED")
        preflight = ["/usr/bin/timeout", "--signal=TERM", "--kill-after=10s", "270s", "/usr/bin/env", "CUDA_VISIBLE_DEVICES=", "OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1", "PYTHONDONTWRITEBYTECODE=1", "/usr/bin/taskset", "-c", "0", PYTHON, "-B", f"{PUBLISH}/package/civilian/driver.py", "--preflight", "--work-root", DIAG]
        code, out, err = run(client, preflight, 330)
        (evidence / "preflight.txt").write_text(out + err, encoding="utf-8")
        if code != 0: raise RuntimeError(f"PREFLIGHT_FAILED:{code}")
        receipt = {
            "status": "preflight_pass",
            "release": RELEASE,
            "publish": PUBLISH,
            "preflight_exit": code,
            "source_identity_sha256": source_sha,
            "archive_sha256": archive_sha,
            "archive_filename": deployment_archive.name,
        }
        receipt_path = evidence / "deployment_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        remote_receipt = f"{DIAG}/deployment_receipt.json"
        sftp = client.open_sftp()
        try:
            with sftp.file(remote_receipt, "wx") as destination:
                destination.write(receipt_path.read_bytes())
        finally:
            sftp.close()
        print(json.dumps({**receipt, "evidence": str(evidence), "remote_receipt": remote_receipt}, ensure_ascii=False))
        return 0
    finally:
        password = ""
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
