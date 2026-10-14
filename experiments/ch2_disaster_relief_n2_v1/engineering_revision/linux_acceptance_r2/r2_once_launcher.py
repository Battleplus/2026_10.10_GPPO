from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import posixpath
import shlex
import stat
import sys
import time

import paramiko

IDENTITY = "n2-local-synthetic-engineering-linux-acceptance-r2"
MANIFEST_REL = "preparation/linux_acceptance/package-manifest.json"
MANIFEST_SHA256 = "C90FA16A70158E77FBF1EF56C35D9E511F4579F8CE926F35B9458963AAF5ACCA"
HOST, USER = "ru-server-MS-1", "user1"
RUN_ID = "n2-engineering-acceptance-r2-20261013-once"
UNIT = RUN_ID + ".service"
REMOTE = "/home/user1/" + RUN_ID
PYTHON = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"
SCOPE = "runtime admission, N2 engineering unit suite, and local synthetic PPO integration smoke only"
EXCLUDED_SCOPE = [
    "registered research data processing",
    "40-epoch world-model fitting",
    "development prediction gate",
    "G versus G-WM policy comparison",
    "formal training or publication claims",
]


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def check_package(root: pathlib.Path) -> list[tuple[str, pathlib.Path, str]]:
    mp = root / MANIFEST_REL
    if digest(mp) != MANIFEST_SHA256:
        raise RuntimeError("LOCAL_MANIFEST_SHA256_MISMATCH")
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    files, hashes = manifest["files"], manifest["hashing"]["file_sha256"]
    if manifest.get("identity") != IDENTITY or manifest.get("status") != "prepared_not_authorized_for_execution":
        raise RuntimeError("LOCAL_PACKAGE_IDENTITY_OR_STATUS_MISMATCH")
    if len(files) != 25 or len(set(files)) != 25 or set(files) != set(hashes):
        raise RuntimeError("LOCAL_MANIFEST_FILE_TABLE_INVALID")
    expected = set(files) | {MANIFEST_REL}
    observed = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("LOCAL_PACKAGE_SYMLINK_FORBIDDEN")
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
    if observed != expected:
        raise RuntimeError("LOCAL_PACKAGE_INVENTORY_MISMATCH")
    rows = []
    for rel in sorted(expected):
        if rel != MANIFEST_REL and (".." in pathlib.PurePosixPath(rel).parts or rel.startswith("/")):
            raise RuntimeError("UNSAFE_MANIFEST_PATH")
        path = root.joinpath(*rel.split("/"))
        sha = digest(path)
        if rel != MANIFEST_REL and sha != hashes[rel].upper():
            raise RuntimeError("LOCAL_PACKAGE_FILE_HASH_MISMATCH:" + rel)
        rows.append((rel, path, sha))
    return rows


def check_authorization(path: pathlib.Path, connect_host: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema": "n2-linux-one-shot-authorization/1", "approval_status": "APPROVED",
        "identity": IDENTITY, "target_host": HOST, "target_user": USER,
        "connect_host": connect_host, "manifest_sha256": MANIFEST_SHA256,
        "run_identity": RUN_ID, "systemd_unit": UNIT, "one_time_execution": True,
        "scope": SCOPE, "excluded_scope": EXCLUDED_SCOPE,
    }
    for name, value in required.items():
        if record.get(name) != value:
            raise RuntimeError("AUTHORIZATION_MISMATCH:" + name)
    if not record.get("authorization_id") or not record.get("approved_at"):
        raise RuntimeError("AUTHORIZATION_ID_AND_TIMESTAMP_REQUIRED")
    return record


def parse_affinity(value: str) -> str:
    try:
        cpus = sorted({int(part) for part in value.split(",")})
    except ValueError as exc:
        raise argparse.ArgumentTypeError("affinity must be comma-separated non-negative CPU indexes") from exc
    if not cpus or any(cpu < 0 for cpu in cpus):
        raise argparse.ArgumentTypeError("affinity must contain non-negative CPU indexes")
    return ",".join(str(cpu) for cpu in cpus)


class Evidence:
    def __init__(self, root: pathlib.Path):
        root.mkdir(parents=True, exist_ok=False)
        self.root = root
        self.stream = (root / "transport-transcript.txt").open("x", encoding="utf-8", newline="\n")

    def write(self, text: str):
        self.stream.write(text)
        self.stream.flush()
        print(text, end="", flush=True)


def command(client, evidence, label: str, text: str, timeout: float, allow_nonzero: bool = False, on_output=None):
    evidence.write(f"\nCOMMAND_BEGIN label={label} utc={utc()}\n{text}\n")
    started = time.monotonic()
    try:
        _stdin, stdout, _stderr = client.exec_command(text, get_pty=False, timeout=timeout)
    except BaseException as exc:
        evidence.write(f"\nCOMMAND_OPEN_FAILED label={label} error={type(exc).__name__} no_retry=true\n")
        raise
    channel, out, err = stdout.channel, bytearray(), bytearray()
    while True:
        received = False
        if channel.recv_ready():
            block = channel.recv(65536)
            out.extend(block)
            decoded = block.decode("utf-8", "replace")
            evidence.write(decoded)
            if on_output:
                on_output(decoded)
            received = True
        if channel.recv_stderr_ready():
            block = channel.recv_stderr(65536)
            err.extend(block)
            evidence.write(block.decode("utf-8", "replace"))
            received = True
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
        if time.monotonic() - started > timeout:
            channel.close()
            evidence.write(f"\nCOMMAND_TIMEOUT label={label} no_retry=true\n")
            raise TimeoutError("REMOTE_COMMAND_TIMEOUT:" + label + ":no reconnect or resubmission")
        if not received:
            time.sleep(0.1)
    status = channel.recv_exit_status()
    evidence.write(f"\nCOMMAND_END label={label} utc={utc()} exit={status}\n")
    if status and not allow_nonzero:
        raise RuntimeError(f"REMOTE_COMMAND_FAILED:{label}:{status}:{err.decode('utf-8','replace')[-1200:]}")
    return status, out.decode("utf-8", "replace")


def transfer(rows, client, evidence, target: str):
    sftp = client.open_sftp()
    try:
        for rel, local, sha in rows:
            dest = posixpath.join(target, *rel.split("/"))
            parent, current = posixpath.dirname(dest), ""
            for part in parent.strip("/").split("/"):
                current += "/" + part
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    sftp.mkdir(current, mode=0o700)
            sftp.put(str(local), dest, confirm=True)
            if sftp.stat(dest).st_size != local.stat().st_size:
                raise RuntimeError("SFTP_SIZE_MISMATCH:" + rel)
            evidence.write(f"SFTP_FILE path={rel} bytes={local.stat().st_size} sha256={sha}\n")
    finally:
        sftp.close()


def collect(client, evidence, source: str, dest: pathlib.Path):
    sftp = client.open_sftp()
    try:
        def visit(remote_dir: str, local_dir: pathlib.Path):
            local_dir.mkdir(parents=True, exist_ok=True)
            for item in sftp.listdir_attr(remote_dir):
                remote_path = posixpath.join(remote_dir, item.filename)
                local_path = local_dir / item.filename
                if stat.S_ISDIR(item.st_mode):
                    visit(remote_path, local_path)
                elif stat.S_ISREG(item.st_mode):
                    sftp.get(remote_path, str(local_path))
                    evidence.write(f"EVIDENCE_FILE path={remote_path} bytes={local_path.stat().st_size} sha256={digest(local_path)}\n")
        visit(source, dest)
    finally:
        sftp.close()


def run(args):
    package = args.package_root.resolve(strict=True)
    rows = check_package(package)
    auth = check_authorization(args.authorization_record, args.connect_host)
    key_file, known_hosts = args.ssh_key_file.resolve(strict=True), args.known_hosts.resolve(strict=True)
    evidence = Evidence(args.evidence_root.resolve())
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(known_hosts))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    invocation = "unknown"
    invocation_box = ["unknown"]
    try:
        evidence.write(f"RUN_BEGIN utc={utc()} run_identity={auth['run_identity']} host={HOST} user={USER} connect_host={args.connect_host} manifest_sha256={MANIFEST_SHA256} files=25 transport_sessions=1\n")
        key = paramiko.PKey.from_path(str(key_file))
        evidence.write(f"SSH_CONNECT_BEGIN utc={utc()} single_transport=true\n")
        client.connect(hostname=args.connect_host, port=22, username=USER, pkey=key,
                       allow_agent=False, look_for_keys=False, password=None,
                       timeout=20, banner_timeout=20, auth_timeout=30)
        transport = client.get_transport()
        if transport is None or not transport.is_active():
            raise RuntimeError("SSH_TRANSPORT_NOT_ACTIVE")
        evidence.write(f"SSH_AUTHENTICATED host_key={transport.get_remote_server_key().fingerprint}\n")
        pkg, work = REMOTE + "/package", REMOTE + "/work"
        preflight = f"""set -eu
test "$(hostname)" = {shlex.quote(HOST)}
test "$(id -un)" = {shlex.quote(USER)}
test -x {shlex.quote(PYTHON)}
test ! -e {shlex.quote(REMOTE)}
systemctl --user show {shlex.quote(UNIT)} --property=LoadState --value --no-pager | grep -qx not-found
taskset -pc $$
printf 'PREFLIGHT_OK host=%s user=%s\n' "$(hostname)" "$(id -un)"
"""
        command(client, evidence, "preflight", preflight, 120)
        command(client, evidence, f"mkdir -m 700 -p {shlex.quote(pkg)} {shlex.quote(work)}; test -z \"$(find {shlex.quote(work)} -mindepth 1 -print -quit)\"", "create_roots", 60)
        transfer(rows, client, evidence, pkg)
        verify = f"""set -eu
{shlex.quote(PYTHON)} -B - <<'PYCODE'
import hashlib,json,pathlib
p=pathlib.Path({pkg!r}); m=p/{MANIFEST_REL!r}
h=lambda x:hashlib.sha256(x.read_bytes()).hexdigest().upper()
d=json.loads(m.read_text(encoding='utf-8'))
assert h(m)=={MANIFEST_SHA256!r}
expected=set(d['files'])|{{{MANIFEST_REL!r}}}
seen={{x.relative_to(p).as_posix() for x in p.rglob('*') if x.is_file()}}
assert seen==expected and len(d['files'])==25
assert all(h(p/r)==d['hashing']['file_sha256'][r] for r in d['files'])
print('REMOTE_PACKAGE_VERIFIED files=25 manifest_sha256='+h(m))
PYCODE
test -z "$(find {shlex.quote(work)} -mindepth 1 -print -quit)"
"""
        command(client, evidence, "verify_package", verify, 120)
        submit = f"""set -eu
systemd-run --user --unit={shlex.quote(UNIT)} \\
 --property=Restart=no --property=KillMode=control-group --property=CPUAffinity=0 \\
 --property=CPUQuota=100% --property=MemoryMax=4G --property=MemoryAccounting=yes \\
 --property=CPUAccounting=yes --property=RuntimeMaxSec=1800s \\
 --property=WorkingDirectory={shlex.quote(pkg)} \\
 --setenv=CUDA_VISIBLE_DEVICES= --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 \\
 --setenv=OPENBLAS_NUM_THREADS=1 --setenv=NUMEXPR_NUM_THREADS=1 --setenv=PYTHONDONTWRITEBYTECODE=1 \\
 {shlex.quote(PYTHON)} -B {shlex.quote(pkg + '/development/ch2_disaster_relief_n2_v1/engineering/n2_linux_runner.py')} \\
 --package-root {shlex.quote(pkg)} --work-root {shlex.quote(work)} --python {shlex.quote(PYTHON)} \\
 --cpu 0 --expected-manifest-sha256 {shlex.quote(MANIFEST_SHA256)} --expected-unit {shlex.quote(UNIT)} \\
 --expected-host {shlex.quote(HOST)} --expected-user {shlex.quote(USER)} \\
 --observed-ssh-affinity {shlex.quote(args.observed_ssh_affinity)}
invocation=$(systemctl --user show {shlex.quote(UNIT)} -p InvocationID --value --no-pager)
test "${{#invocation}}" -eq 32
printf 'INVOCATION_ID=%s\n' "$invocation"
deadline=$((SECONDS + 1805))
while :; do
 state=$(systemctl --user show {shlex.quote(UNIT)} -p ActiveState --value --no-pager)
 case "$state" in inactive|failed) break;; esac
 if [ "$SECONDS" -ge "$deadline" ]; then echo "OBSERVATION_TIMEOUT no_retry=true"; exit 124; fi
 sleep 2
done
systemctl --user show {shlex.quote(UNIT)} --no-pager -p InvocationID -p ControlGroup -p ActiveState -p SubState -p Result -p ExecMainStatus -p ExecMainCode -p ExecMainStartTimestamp -p ExecMainExitTimestamp -p CPUUsageNSec -p MemoryPeak
"""
        capture_buffer = [""]

        def capture_invocation(text: str):
            capture_buffer[0] += text
            lines = capture_buffer[0].splitlines(keepends=True)
            capture_buffer[0] = ""
            if lines and not lines[-1].endswith(("\n", "\r")):
                capture_buffer[0] = lines.pop()
            for line in lines:
                if line.startswith("INVOCATION_ID="):
                    value = line.partition("=")[2].strip()
                    if len(value) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in value):
                        invocation_box[0] = value

        submit_status, output = command(
            client, evidence, "submit_once_and_observe_same_connection", submit, 1820,
            allow_nonzero=True, on_output=capture_invocation,
        )
        found = [line.partition("=")[2].strip() for line in output.splitlines() if line.startswith("INVOCATION_ID=")]
        if len(found) != 1 or len(found[0]) != 32:
            raise RuntimeError("INVOCATION_ID_MISSING:no reconnect or resubmission")
        invocation = found[0]
        invocation_box[0] = invocation
        if submit_status:
            raise RuntimeError(f"SUBMIT_OR_OBSERVE_EXIT_{submit_status}:no reconnect or resubmission")
        final = f"""set -eu
test "$(systemctl --user show {shlex.quote(UNIT)} -p InvocationID --value --no-pager)" = {shlex.quote(invocation)}
systemctl --user show {shlex.quote(UNIT)} --no-pager -p InvocationID -p ControlGroup -p ActiveState -p SubState -p Result -p ExecMainStatus -p ExecMainCode -p ExecMainStartTimestamp -p ExecMainExitTimestamp -p CPUUsageNSec -p MemoryPeak -p TasksCurrent
journalctl --user -u {shlex.quote(UNIT)} --no-pager --output=short-iso-precise
cg=$(systemctl --user show {shlex.quote(UNIT)} -p ControlGroup --value --no-pager)
for f in cpu.stat memory.current memory.peak memory.max; do if [ -r "/sys/fs/cgroup$cg/$f" ]; then printf '%s=' "$f"; cat "/sys/fs/cgroup$cg/$f"; fi; done
find {shlex.quote(work)} -type f -printf '%P\\t%s\\t%T@\\n' | sort
find {shlex.quote(work)} -type f -print0 | sort -z | xargs -0 -r sha256sum
"""
        final_status, final_output = command(
            client, evidence, "same_invocation_final_evidence", final, 120, allow_nonzero=True,
        )
        collect(client, evidence, work, evidence.root / "work")
        properties = dict(
            line.split("=", 1) for line in final_output.splitlines() if "=" in line and not line.startswith(" ")
        )
        receipt_path = evidence.root / "work" / "final-receipt.json"
        report_path = evidence.root / "work" / "smoke-output" / "N2_ENGINEERING_NODE_REPORT.json"
        failure_path = evidence.root / "work" / "smoke-output" / "failed_export.json.failure.json"
        if final_status != 0:
            raise RuntimeError(f"FINAL_SYSTEMD_EVIDENCE_FAILED:{final_status}")
        if properties.get("InvocationID") != invocation:
            raise RuntimeError("FINAL_SYSTEMD_INVOCATION_MISMATCH")
        if properties.get("Result") != "success" or properties.get("ExecMainStatus") != "0":
            raise RuntimeError("SYSTEMD_RESULT_OR_EXIT_STATUS_FAILED")
        if not receipt_path.is_file() or not report_path.is_file() or not failure_path.is_file():
            raise RuntimeError("ACCEPTANCE_RECEIPT_OR_EXPORT_EVIDENCE_MISSING")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if receipt.get("identity") != IDENTITY or receipt.get("status") != "complete":
            raise RuntimeError("RUNNER_RECEIPT_INCOMPLETE")
        if receipt.get("first_error") is not None or receipt.get("pending_paths"):
            raise RuntimeError("RUNNER_RECEIPT_HAS_ERROR_OR_PENDING_PATHS")
        if receipt.get("systemd_invocation_id") != invocation:
            raise RuntimeError("RUNNER_RECEIPT_INVOCATION_MISMATCH")
        if receipt.get("package_manifest_sha256") != MANIFEST_SHA256:
            raise RuntimeError("RUNNER_RECEIPT_MANIFEST_MISMATCH")
        if receipt.get("total_wall_seconds_at_first_receipt_commit", float("inf")) > 1740:
            raise RuntimeError("RUNNER_WALL_CAP_EXCEEDED")
        if receipt.get("total_child_cpu_seconds", float("inf")) > 1200:
            raise RuntimeError("RUNNER_CPU_CAP_EXCEEDED")
        if receipt.get("cgroup_cpu_seconds_at_receipt_prepare", float("inf")) > 1200:
            raise RuntimeError("CGROUP_CPU_CAP_EXCEEDED")
        if receipt.get("cgroup_memory_peak_bytes", float("inf")) > 4 * 1024**3:
            raise RuntimeError("CGROUP_MEMORY_CAP_EXCEEDED")
        if receipt.get("peak_sampled_process_group_rss_bytes", float("inf")) > 4 * 1024**3:
            raise RuntimeError("RUNNER_RSS_CAP_EXCEEDED")
        if receipt.get("package_work_export_storage_bytes_at_settlement", float("inf")) > 8 * 1024**3:
            raise RuntimeError("RUNNER_STORAGE_CAP_EXCEEDED")
        if report.get("exports", {}).get("normal", {}).get("status") != "complete":
            raise RuntimeError("NORMAL_EXPORT_EVIDENCE_INVALID")
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        if failure.get("status") != "failed" or failure.get("exception_type") != "RuntimeError":
            raise RuntimeError("INJECTED_FAILURE_EXPORT_EVIDENCE_INVALID")
        evidence.write(f"RUN_COMPLETE utc={utc()} invocation_id={invocation} reconnects=0 systemd_run_submissions=1\n")
        return 0
    except BaseException as exc:
        invocation = invocation_box[0]
        evidence.write(f"RUN_STOP utc={utc()} error={type(exc).__name__}:{exc} invocation_id={invocation} no_retry=true reconnects=0\n")
        raise
    finally:
        client.close()
        evidence.write(f"TRANSPORT_CLOSED utc={utc()}\n")
        evidence.stream.close()


def main():
    parser = argparse.ArgumentParser(description="One-shot N2 r2 launcher; exact separate authorization required.")
    parser.add_argument("--authorization-record", type=pathlib.Path, required=True)
    parser.add_argument("--connect-host", required=True)
    parser.add_argument("--package-root", type=pathlib.Path, required=True)
    parser.add_argument("--evidence-root", type=pathlib.Path, required=True)
    parser.add_argument("--ssh-key-file", type=pathlib.Path, required=True)
    parser.add_argument("--known-hosts", type=pathlib.Path, required=True)
    parser.add_argument("--observed-ssh-affinity", type=parse_affinity, required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        print(f"LOCAL_FATAL utc={utc()} type={type(exc).__name__} detail={exc}", file=sys.stderr, flush=True)
        raise
