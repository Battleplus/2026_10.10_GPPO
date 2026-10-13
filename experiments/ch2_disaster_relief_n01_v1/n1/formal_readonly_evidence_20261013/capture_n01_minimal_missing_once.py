from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys


HOST = "172.17.27.173"
USER = "user1"
RUN = "/home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-once"
MAGIC = b"N01-RO-MISSING/1\n"
CHUNK = 1024 * 1024
MAX_TOTAL_BYTES = 70 * 1024 * 1024
FILES = (
    {
        "path": "export/n01-full-evaluation.zip",
        "expected_size": 66112453,
        "expected_sha256": "93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31",
    },
    {
        "path": "preflight_plan.json",
        "expected_size": 743708,
        "expected_sha256": None,
    },
)

REMOTE_PYTHON = r'''from __future__ import annotations
import hashlib, json, os, stat, struct, sys, time

RUN = "/home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-once"
MAGIC = b"N01-RO-MISSING/1\n"
CHUNK = 1024 * 1024
MAX_TOTAL_BYTES = 70 * 1024 * 1024
FILES = (
    ("export/n01-full-evaluation.zip", 66112453, "93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31"),
    ("preflight_plan.json", 743708, None),
)
out = sys.stdout.buffer

def emit(obj):
    data = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    out.write(struct.pack(">I", len(data))); out.write(data); out.flush()

def open_readonly(path):
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open("/", directory_flags)
    try:
        for part in RUN.strip("/").split("/"):
            child = os.open(part, directory_flags, dir_fd=current)
            os.close(current)
            current = child
        parts = path.split("/")
        for part in parts[:-1]:
            child = os.open(part, directory_flags, dir_fd=current)
            os.close(current)
            current = child
        fd = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=current)
        return fd
    finally:
        os.close(current)

def same_stat(a, b):
    return (a.st_dev, a.st_ino, a.st_mode, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (b.st_dev, b.st_ino, b.st_mode, b.st_size, b.st_mtime_ns, b.st_ctime_ns)

def capture_file(path, expected_size, expected_sha256, budget):
    emit({"type": "file_start", "path": "run/" + path, "expected_size": expected_size, "expected_sha256": expected_sha256})
    status = "ok"
    error = None
    total = 0
    digest = hashlib.sha256()
    fd = None
    try:
        fd = open_readonly(path)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            status = "not_regular"
        elif budget[0] + before.st_size > MAX_TOTAL_BYTES:
            status = "size_limit_rejected"
        else:
            while True:
                part = os.read(fd, CHUNK)
                if not part:
                    break
                if budget[0] + len(part) > MAX_TOTAL_BYTES:
                    status = "size_limit_rejected"
                    break
                out.write(struct.pack(">I", len(part))); out.write(part)
                digest.update(part); total += len(part)
                budget[0] += len(part)
            if status == "ok":
                after = os.fstat(fd)
                if not same_stat(before, after):
                    status = "changed_during_read"
                elif total != expected_size:
                    status = "expected_size_mismatch"
                elif expected_sha256 and digest.hexdigest() != expected_sha256:
                    status = "expected_hash_mismatch"
    except FileNotFoundError:
        status = "missing"
    except Exception as exc:
        status = "read_error"
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        if fd is not None:
            os.close(fd)
    out.write(struct.pack(">I", 0)); out.flush()
    result = {"type": "file_end", "path": "run/" + path, "status": status, "bytes": total, "sha256": digest.hexdigest()}
    if error:
        result["error"] = error
    emit(result)

out.write(MAGIC); out.flush()
emit({"type": "manifest", "started_unix_ns": time.time_ns(), "scope": ["run/export/n01-full-evaluation.zip", "run/preflight_plan.json"], "remote_writes": False})
budget = [0]
for path, expected_size, expected_sha256 in FILES:
    capture_file(path, expected_size, expected_sha256, budget)
emit({"type": "finished", "finished_unix_ns": time.time_ns()})
'''


def ssh_argv(key: str) -> list[str]:
    return [
        "ssh", "-i", key,
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no", "-o", "ControlMaster=no",
        "-o", "ControlPath=none", "-o", "ProxyJump=none", "-o", "ProxyCommand=none",
        "-o", "ConnectionAttempts=1", USER + "@" + HOST, "python3", "-B", "-",
    ]


def read_record(stream):
    size_bytes = stream.read(4)
    if not size_bytes:
        return None
    if len(size_bytes) != 4:
        raise ValueError("truncated record length")
    size = struct.unpack(">I", size_bytes)[0]
    if size > 1024 * 1024:
        raise ValueError("record header too large")
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("truncated record header")
    return json.loads(data.decode("ascii"))


def decode(raw_path: pathlib.Path, root: pathlib.Path) -> list[dict]:
    expected = {"run/" + item["path"]: item for item in FILES}
    records = []
    with raw_path.open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError("bad evidence stream magic")
        while (record := read_record(stream)) is not None:
            if record.get("type") != "file_start":
                records.append(record)
                continue
            relative = record.get("path")
            if relative not in expected:
                raise ValueError("unexpected file path in evidence stream")
            target = root.joinpath(*pathlib.PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            total = 0
            with target.open("xb") as output:
                while True:
                    size_bytes = stream.read(4)
                    if len(size_bytes) != 4:
                        raise ValueError("truncated file frame")
                    size = struct.unpack(">I", size_bytes)[0]
                    if size == 0:
                        break
                    if size > CHUNK:
                        raise ValueError("chunk too large")
                    data = stream.read(size)
                    if len(data) != size:
                        raise ValueError("truncated file bytes")
                    output.write(data); digest.update(data); total += size
            end = read_record(stream)
            if not end or end.get("type") != "file_end" or end.get("path") != relative:
                raise ValueError("missing/mismatched file end record")
            end["local_bytes"] = total
            end["local_sha256"] = digest.hexdigest()
            end["local_matches_stream"] = total == end.get("bytes") and digest.hexdigest() == end.get("sha256")
            expected_item = expected[relative]
            end["expected_size_matches"] = total == expected_item["expected_size"]
            expected_hash = expected_item["expected_sha256"]
            end["expected_hash_matches"] = None if expected_hash is None else digest.hexdigest() == expected_hash
            records.append({"start": record, "end": end})
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--plan", action="store_true", help="print the fixed command plan without connecting")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({
            "ssh_argv_redacted": ["ssh", "-i", "[KEY PATH OMITTED]", *ssh_argv(args.key)[3:]],
            "remote_scope": [{k: v for k, v in item.items()} for item in FILES],
            "max_total_payload_bytes": MAX_TOTAL_BYTES,
            "remote_script_sha256": hashlib.sha256(REMOTE_PYTHON.encode("utf-8")).hexdigest(),
            "ssh_invocations": 1,
        }, indent=2))
        return 0

    outdir = pathlib.Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    lock_fd = os.open(outdir / "capture-once.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(lock_fd)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with (outdir / "stdout.raw").open("xb") as stdout, (outdir / "stderr.raw").open("xb") as stderr:
        result = subprocess.run(ssh_argv(args.key), input=REMOTE_PYTHON.encode("utf-8"), stdout=stdout, stderr=stderr, check=False)
    raw_path = outdir / "stdout.raw"
    decoded_root = outdir / "decoded"
    decoded_root.mkdir()
    decode_error = None
    records = []
    try:
        records = decode(raw_path, decoded_root)
    except Exception as exc:
        decode_error = type(exc).__name__ + ": " + str(exc)
    payloads = [item for item in records if "start" in item and "end" in item]
    expected_paths = {"run/" + item["path"] for item in FILES}
    captured_paths = {item["start"].get("path") for item in payloads}
    manifests = [item for item in records if item.get("type") == "manifest"]
    finished = any(item.get("type") == "finished" for item in records)
    scope_matches = bool(manifests) and set(manifests[0].get("scope", [])) == expected_paths
    file_payloads_ok = len(payloads) == len(FILES) and captured_paths == expected_paths and all(
        item["end"].get("status") == "ok"
        and item["end"].get("local_matches_stream")
        and item["end"].get("expected_size_matches")
        and item["end"].get("expected_hash_matches") is not False
        for item in payloads
    )
    capture_reasons = []
    if result.returncode != 0:
        capture_reasons.append("ssh_exit_nonzero")
    if decode_error is not None:
        capture_reasons.append("framing_unavailable")
    if not scope_matches or not finished:
        capture_reasons.append("protocol_manifest_or_finish_missing")
    if not file_payloads_ok:
        capture_reasons.append("selected_file_missing_or_mismatched")
    complete = not capture_reasons
    hashes = {}
    for name in ("stdout.raw", "stderr.raw"):
        path = outdir / name
        hashes[name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    record = {
        "schema": "n01-minimal-readonly-capture/1",
        "capture_status": "complete" if complete else "partial" if decode_error is None else "unknown",
        "expected_files": list(FILES),
        "ssh_invocation_count": 1,
        "ssh_exit_code": result.returncode,
        "remote_writes": False,
        "framing_status": "decoded" if decode_error is None else "invalid_or_empty_stream",
        "framing_error": decode_error,
        "capture_status_reasons": capture_reasons,
        "decoded_records": records,
        "raw_streams": hashes,
        "started_utc": started,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    (outdir / "session-record.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [hashlib.sha256((outdir / name).read_bytes()).hexdigest() + "  " + name for name in ("stdout.raw", "stderr.raw", "session-record.json")]
    (outdir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
