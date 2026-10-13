from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import threading
import time
from typing import BinaryIO


IDENTITY = "ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012"
INVOCATION_ID = "fbdad1589e894466b62cf1785df0de47"
UNIT = "n01-full-evaluation-r2-formal-repair-v1-20261012.service"
RUN = "/home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-once"
DIAG = "/home/user1/w1-pilot/diagnostics/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-formal-run-20261012"
REQUIRED_DIAG_RECEIPTS = ("final-status.txt", "journal.txt", "run-files.tsv", "settlement.json")
MAGIC = b"N01-RO-EVIDENCE/1\n"
CHUNK_SIZE = 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def write_record(stream: BinaryIO, record: dict) -> None:
    data = json_bytes(record)
    stream.write(struct.pack(">I", len(data)))
    stream.write(data)
    stream.flush()


def frame_chunks(stream: BinaryIO, chunks) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    for chunk in chunks:
        if not chunk:
            continue
        for offset in range(0, len(chunk), CHUNK_SIZE):
            part = chunk[offset : offset + CHUNK_SIZE]
            stream.write(struct.pack(">I", len(part)))
            stream.write(part)
            digest.update(part)
            total += len(part)
    stream.write(struct.pack(">I", 0))
    stream.flush()
    return total, digest.hexdigest()


def parse_systemd_properties(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def stable_terminal_state(properties: dict[str, str]) -> tuple[bool, str]:
    if properties.get("InvocationID") != INVOCATION_ID:
        return False, "invocation_id_mismatch"
    if properties.get("ActiveState") not in {"inactive", "failed"}:
        return False, "unit_not_terminal"
    return True, "terminal_invocation_match"


REMOTE_PYTHON = r'''from __future__ import annotations
import hashlib, json, os, stat, struct, subprocess, sys, time

EXPECTED_ID = "fbdad1589e894466b62cf1785df0de47"
UNIT = "n01-full-evaluation-r2-formal-repair-v1-20261012.service"
RUN = "/home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-once"
DIAG = "/home/user1/w1-pilot/diagnostics/ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012-formal-run-20261012"
REQUIRED_DIAG_RECEIPTS = ("final-status.txt", "journal.txt", "run-files.tsv", "settlement.json")
MAGIC = b"N01-RO-EVIDENCE/1\n"
CHUNK = 1024 * 1024
LIMIT = 2 * 1024 * 1024 * 1024
out = sys.stdout.buffer

def emit(obj):
    b = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    out.write(struct.pack(">I", len(b))); out.write(b); out.flush()

def chunks(data):
    for pos in range(0, len(data), CHUNK):
        yield data[pos:pos + CHUNK]

def emit_bytes(data):
    h = hashlib.sha256(); n = 0
    for part in chunks(data):
        out.write(struct.pack(">I", len(part))); out.write(part); h.update(part); n += len(part)
    out.write(struct.pack(">I", 0)); out.flush()
    return n, h.hexdigest()

def emit_blob(name, data):
    emit({"type": "blob_start", "path": "commands/" + name})
    n, h = emit_bytes(data)
    emit({"type": "blob_end", "path": "commands/" + name, "status": "ok", "bytes": n, "sha256": h})
    return n, h

def command(argv):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return {"argv": argv, "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except Exception as e:
        return {"argv": argv, "exit_code": None, "stdout": b"", "stderr": (type(e).__name__ + ": " + str(e)).encode("utf-8", "replace")}

def same_stat(a, b):
    return (a.st_dev, a.st_ino, a.st_mode, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (b.st_dev, b.st_ino, b.st_mode, b.st_size, b.st_mtime_ns, b.st_ctime_ns)

def open_root(path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current = os.open("/", flags)
    try:
        for part in path.strip("/").split("/"):
            if not part:
                continue
            child = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise

def walk_dir(root_fd, prefix, budget, inventory):
    try:
        names = sorted(os.listdir(root_fd))
    except Exception as e:
        inventory.append({"path": prefix, "status": "list_error", "error": type(e).__name__ + ": " + str(e)})
        return
    for name in names:
        try:
            name.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            inventory.append({"path": prefix, "status": "filename_not_utf8_skipped", "name_bytes_hex": os.fsencode(name).hex()})
            continue
        rel = prefix + "/" + name
        try:
            st = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except Exception as e:
            inventory.append({"path": rel, "status": "stat_error", "error": type(e).__name__ + ": " + str(e)})
            continue
        if stat.S_ISLNK(st.st_mode):
            inventory.append({"path": rel, "status": "symlink_skipped"})
            continue
        if stat.S_ISDIR(st.st_mode):
            try:
                child = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
                try:
                    now = os.fstat(child)
                    if not same_stat(st, now):
                        inventory.append({"path": rel, "status": "directory_changed_before_walk"})
                    else:
                        walk_dir(child, rel, budget, inventory)
                finally:
                    os.close(child)
            except Exception as e:
                inventory.append({"path": rel, "status": "directory_open_error", "error": type(e).__name__ + ": " + str(e)})
            continue
        if not stat.S_ISREG(st.st_mode):
            inventory.append({"path": rel, "status": "non_regular_skipped"})
            continue
        if st.st_size < 0 or budget[0] + st.st_size > LIMIT:
            inventory.append({"path": rel, "status": "size_limit_skipped", "size": st.st_size})
            continue
        entry = {"path": rel, "status": "reading", "initial_size": st.st_size}
        emit({"type": "file_start", **entry})
        count = 0
        digest = hashlib.sha256()
        status = "ok"
        error = None
        fd = None
        try:
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or not same_stat(st, before):
                status = "changed_before_read"
            else:
                remaining = before.st_size
                while remaining:
                    part = os.read(fd, min(CHUNK, remaining))
                    if not part:
                        status = "short_read"
                        break
                    out.write(struct.pack(">I", len(part))); out.write(part)
                    digest.update(part); count += len(part); remaining -= len(part); budget[0] += len(part)
                if status == "ok":
                    extra = os.read(fd, 1)
                    after = os.fstat(fd)
                    if extra or not same_stat(before, after):
                        status = "changed_during_read"
        except Exception as e:
            status = "read_error"
            error = type(e).__name__ + ": " + str(e)
        finally:
            if fd is not None:
                os.close(fd)
        out.write(struct.pack(">I", 0)); out.flush()
        item = {"type": "file_end", "path": rel, "status": status, "bytes": count, "sha256": digest.hexdigest()}
        if error:
            item["error"] = error
        inventory.append(item)
        emit(item)

out.write(MAGIC); out.flush()
started = time.time_ns()
props_argv = ["systemctl", "--user", "show", UNIT, "--no-pager", "-p", "LoadState", "-p", "ActiveState", "-p", "SubState", "-p", "Result", "-p", "ExecMainCode", "-p", "ExecMainStatus", "-p", "InvocationID", "-p", "ExecMainStartTimestamp", "-p", "ExecMainExitTimestamp", "-p", "CPUUsageNSec", "-p", "MemoryCurrent", "-p", "MemoryPeak"]
'''.replace("\n+", "\n") + r'''
props = command(props_argv)
emit({"type": "command_start", "name": "systemd_before", "argv": props_argv})
n, h = emit_blob("systemd_before.stdout", props["stdout"])
en, eh = emit_blob("systemd_before.stderr", props["stderr"])
emit({"type": "command_end", "name": "systemd_before", "exit_code": props["exit_code"], "stdout_bytes": n, "stdout_sha256": h, "stderr_bytes": en, "stderr_sha256": eh})
properties = {}
for line in props["stdout"].decode("utf-8", "replace").splitlines():
    if "=" in line:
        k, v = line.split("=", 1); properties[k] = v
matched = properties.get("InvocationID") == EXPECTED_ID
terminal = properties.get("ActiveState") in ("inactive", "failed")
stable = matched and terminal and props["exit_code"] == 0
reason = "terminal_invocation_match" if stable else ("invocation_id_mismatch" if not matched else "unit_not_terminal" if not terminal else "systemctl_error")
emit({"type": "gate", "stable_terminal_invocation": stable, "reason": reason, "expected_invocation_id": EXPECTED_ID, "observed_invocation_id": properties.get("InvocationID"), "active_state": properties.get("ActiveState")})

journal_argv = ["journalctl", "--user", "-u", UNIT, "--no-pager", "-o", "short-iso", "_SYSTEMD_INVOCATION_ID=" + EXPECTED_ID]
journal = command(journal_argv)
emit({"type": "command_start", "name": "journal", "argv": journal_argv})
n, h = emit_blob("journal.stdout", journal["stdout"])
en, eh = emit_blob("journal.stderr", journal["stderr"])
emit({"type": "command_end", "name": "journal", "exit_code": journal["exit_code"], "stdout_bytes": n, "stdout_sha256": h, "stderr_bytes": en, "stderr_sha256": eh})

inventory = []
budget = [0]
if stable:
    for label, path in (("diag", DIAG), ("run", RUN)):
        try:
            root_fd = open_root(path)
        except FileNotFoundError:
            inventory.append({"path": label, "status": "directory_missing"})
        except Exception as e:
            inventory.append({"path": label, "status": "directory_open_error", "error": type(e).__name__ + ": " + str(e)})
        else:
            try:
                before_count = len(inventory)
                walk_dir(root_fd, label, budget, inventory)
                if len(inventory) == before_count:
                    inventory.append({"path": label, "status": "empty_evidence"})
            finally:
                os.close(root_fd)
    for name in REQUIRED_DIAG_RECEIPTS:
        rel = "diag/" + name
        if not any(item.get("path") == rel and item.get("status") == "ok" for item in inventory):
            if not any(item.get("path") == rel and item.get("status") != "ok" for item in inventory):
                inventory.append({"path": rel, "status": "required_file_missing"})
else:
    inventory.append({"path": "run+diag", "status": "not_scanned_unstable_unit", "reason": reason})

props_after = command(props_argv)
emit({"type": "command_start", "name": "systemd_after", "argv": props_argv})
after_n, after_h = emit_blob("systemd_after.stdout", props_after["stdout"])
after_en, after_eh = emit_blob("systemd_after.stderr", props_after["stderr"])
emit({"type": "command_end", "name": "systemd_after", "exit_code": props_after["exit_code"], "stdout_bytes": after_n, "stdout_sha256": after_h, "stderr_bytes": after_en, "stderr_sha256": after_eh})
after = {}
for line in props_after["stdout"].decode("utf-8", "replace").splitlines():
    if "=" in line:
        k, v = line.split("=", 1); after[k] = v
changed = {k: [properties.get(k), after.get(k)] for k in ("InvocationID", "ActiveState", "SubState", "Result") if properties.get(k) != after.get(k)}
stable_at_end = props_after["exit_code"] == 0 and not changed and after.get("InvocationID") == EXPECTED_ID and after.get("ActiveState") in ("inactive", "failed") and stable
emit({"type": "systemd_after", "exit_code": props_after["exit_code"], "properties": after, "changed_fields": changed, "service_state_stable_at_end": stable_at_end})
emit({"type": "manifest", "identity": "ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012", "expected_invocation_id": EXPECTED_ID, "started_unix_ns": started, "finished_unix_ns": time.time_ns(), "service_state_stable": stable, "gate_reason": reason, "inventory": inventory, "remote_writes": False})
'''


def read_record(stream: BinaryIO) -> dict | None:
    size_bytes = stream.read(4)
    if not size_bytes:
        return None
    if len(size_bytes) != 4:
        raise ValueError("truncated record length")
    size = struct.unpack(">I", size_bytes)[0]
    if size > 16 * 1024 * 1024:
        raise ValueError("record header too large")
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("truncated record header")
    return json.loads(data.decode("ascii"))


def safe_local_file(root: pathlib.Path, rel: str) -> pathlib.Path:
    p = pathlib.PurePosixPath(rel)
    if p.is_absolute() or "\\" in rel or "\x00" in rel or any(part in {"", ".", ".."} for part in p.parts):
        raise ValueError("unsafe archive path")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if any(":" in part or part.rstrip(" .") != part or part.split(".", 1)[0].upper() in reserved for part in p.parts):
        raise ValueError("path component is not portable to the local filesystem")
    dest = root.joinpath(*p.parts)
    parent = root
    for part in p.parts[:-1]:
        parent = parent / part
        if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
            raise ValueError("unsafe local parent path")
        parent.mkdir(exist_ok=True)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    return dest


def decode_stream(raw_path: pathlib.Path, extract_root: pathlib.Path) -> dict:
    records = []
    with raw_path.open("rb") as src:
        if src.read(len(MAGIC)) != MAGIC:
            raise ValueError("bad evidence stream magic")
        while (record := read_record(src)) is not None:
            kind = record.get("type")
            if kind in {"file_start", "blob_start"}:
                rel = record["path"]
                dest = safe_local_file(extract_root, rel)
                digest = hashlib.sha256()
                count = 0
                with dest.open("xb") as out:
                    while True:
                        size_bytes = src.read(4)
                        if len(size_bytes) != 4:
                            raise ValueError("truncated file frame")
                        size = struct.unpack(">I", size_bytes)[0]
                        if size == 0:
                            break
                        if size > CHUNK_SIZE:
                            raise ValueError("chunk too large")
                        data = src.read(size)
                        if len(data) != size:
                            raise ValueError("truncated file bytes")
                        out.write(data); digest.update(data); count += size
                end = read_record(src)
                expected_end = "file_end" if kind == "file_start" else "blob_end"
                if not end or end.get("type") != expected_end or end.get("path") != rel:
                    raise ValueError("missing/mismatched file end record")
                end["local_bytes"] = count
                end["local_sha256"] = digest.hexdigest()
                end["local_matches_stream"] = count == end.get("bytes") and digest.hexdigest() == end.get("sha256")
                records.append({"start": record, "end": end})
            else:
                records.append(record)
    return {"schema": "n01-readonly-capture-decoded/1", "records": records}


def assess_capture(exit_code: int | None, local_errors: list[str], framing_status: str, decoded: dict | None) -> tuple[str, list[str]]:
    if framing_status != "decoded" or decoded is None:
        return "unknown", ["framing_unavailable"]
    records = decoded.get("records", [])
    manifests = [r for r in records if r.get("type") == "manifest"]
    if not manifests:
        return "unknown", ["manifest_missing"]

    reasons = []
    if exit_code != 0:
        reasons.append("ssh_exit_nonzero")
    if local_errors:
        reasons.append("local_pipe_error")
    blob_paths = set()
    for record in records:
        if "start" in record and "end" in record:
            end = record["end"]
            if not end.get("local_matches_stream"):
                reasons.append("frame_hash_mismatch")
            if end.get("status") != "ok":
                reasons.append("frame_read_incomplete")
            if record["start"].get("type") == "blob_start" and end.get("local_matches_stream") and end.get("status") == "ok":
                blob_paths.add(record["start"].get("path"))

    for command in ("systemd_before", "journal", "systemd_after"):
        for stream in ("stdout", "stderr"):
            if "commands/" + command + "." + stream not in blob_paths:
                reasons.append("required_command_blob_missing:" + command + ":" + stream)

    commands = {r.get("name"): r for r in records if r.get("type") == "command_end"}
    for name in ("systemd_before", "journal", "systemd_after"):
        if name not in commands or commands[name].get("exit_code") != 0:
            reasons.append("required_command_failed:" + name)
    gates = [r for r in records if r.get("type") == "gate"]
    if not gates or not gates[-1].get("stable_terminal_invocation"):
        reasons.append("service_state_not_stable_terminal")
    after = [r for r in records if r.get("type") == "systemd_after"]
    if not after or not after[-1].get("service_state_stable_at_end"):
        reasons.append("service_state_readback_mismatch")

    manifest = manifests[-1]
    inventory = manifest.get("inventory")
    if not isinstance(inventory, list):
        reasons.append("inventory_missing")
    else:
        for item in inventory:
            if item.get("status") != "ok":
                reasons.append("inventory_incomplete:" + str(item.get("path", "unknown")) + ":" + str(item.get("status", "unknown")))
        inventory_by_path = {item.get("path"): item for item in inventory}
        for name in REQUIRED_DIAG_RECEIPTS:
            path = "diag/" + name
            item = inventory_by_path.get(path)
            if item is None:
                reasons.append("required_receipt_missing:" + path)
            elif item.get("status") != "ok":
                reasons.append("required_receipt_incomplete:" + path)
    if not manifest.get("service_state_stable"):
        reasons.append("manifest_service_state_not_stable")

    return ("complete" if not reasons else "partial"), sorted(set(reasons))


def copy_pipe(src: BinaryIO, dest: pathlib.Path, errors: list[str], label: str) -> None:
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(src, out, length=CHUNK_SIZE)
    except Exception as e:
        errors.append(label + ": " + type(e).__name__ + ": " + str(e))


def safe_write_json(path: pathlib.Path, obj: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def ssh_argv(args: argparse.Namespace) -> list[str]:
    target = args.user + "@" + args.host
    return [
        "ssh", "-i", args.key,
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no", "-o", "ControlMaster=no",
        "-o", "ControlPath=none", "-o", "ProxyJump=none", "-o", "ProxyCommand=none",
        "-o", "ConnectionAttempts=1", target, "python3", "-B", "-",
    ]


def capture(args: argparse.Namespace) -> int:
    outdir = pathlib.Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    marker = outdir / "capture-once.lock"
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    key = pathlib.Path(args.key)
    if not key.is_file():
        safe_write_json(outdir / "session-record.json", {"schema": "n01-readonly-capture/1", "status": "local_key_path_missing", "capture_status": "unknown", "capture_status_reasons": ["ssh_not_started"], "python_capture_read_key_contents": False, "finished_utc": utc_now()})
        return 2
    cmd = ssh_argv(args)
    started = utc_now()
    errors: list[str] = []
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except Exception as e:
        safe_write_json(outdir / "session-record.json", {"schema": "n01-readonly-capture/1", "status": "local_ssh_process_error", "capture_status": "unknown", "capture_status_reasons": ["ssh_not_started"], "error": type(e).__name__ + ": " + str(e), "started_utc": started, "finished_utc": utc_now(), "ssh_invocation_count": 0, "python_capture_read_key_contents": False})
        return 2
    stdout_thread = threading.Thread(target=copy_pipe, args=(proc.stdout, outdir / "stdout.raw", errors, "stdout"), daemon=True)
    stderr_thread = threading.Thread(target=copy_pipe, args=(proc.stderr, outdir / "stderr.raw", errors, "stderr"), daemon=True)
    stdout_thread.start(); stderr_thread.start()
    try:
        proc.stdin.write(REMOTE_PYTHON.encode("utf-8"))
        proc.stdin.close()
    except Exception as e:
        errors.append("stdin: " + type(e).__name__ + ": " + str(e))
        try:
            proc.stdin.close()
        except Exception:
            pass
    code = proc.wait()
    stdout_thread.join(); stderr_thread.join()
    stdout_path = outdir / "stdout.raw"
    decoded_root = outdir / "decoded"
    framing_status = "invalid_or_empty_stream"
    framing_error = None
    decoded_sha256 = None
    decoded = None
    try:
        decoded_root.mkdir()
        decoded = decode_stream(stdout_path, decoded_root)
        manifest_path = decoded_root / "manifest.json"
        safe_write_json(manifest_path, decoded)
        dig = hashlib.sha256()
        with manifest_path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                dig.update(chunk)
        decoded_sha256 = dig.hexdigest()
        framing_status = "decoded"
    except Exception as e:
        framing_error = type(e).__name__ + ": " + str(e)
    hashes = {}
    for name in ("stdout.raw", "stderr.raw"):
        path = outdir / name
        if not path.is_file():
            hashes[name] = {"bytes": None, "sha256": None, "status": "missing_after_pipe_error"}
            continue
        dig = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                dig.update(chunk); size += len(chunk)
        hashes[name] = {"bytes": size, "sha256": dig.hexdigest()}
    capture_status, capture_reasons = assess_capture(code, errors, framing_status, decoded)
    record = {
        "schema": "n01-readonly-capture/1",
        "identity": IDENTITY,
        "expected_invocation_id": INVOCATION_ID,
        "unit": UNIT,
        "run_path": RUN,
        "diagnostics_path": DIAG,
        "started_utc": started,
        "finished_utc": utc_now(),
        "ssh_invocation_count": 1,
        "ssh_command_redacted": ["ssh", "-i", "[KEY PATH OMITTED]", "...", args.user + "@" + args.host, "python3", "-B", "-"],
        "exit_code": code,
        "python_capture_read_key_contents": False,
        "remote_writes": False,
        "local_capture_errors": errors,
        "framing_status": framing_status,
        "framing_error": framing_error,
        "capture_status": capture_status,
        "capture_status_reasons": capture_reasons,
        "decoded_manifest_sha256": decoded_sha256,
        "raw_streams": hashes,
    }
    safe_write_json(outdir / "session-record.json", record)
    sum_lines = []
    for name in ("stdout.raw", "stderr.raw", "session-record.json"):
        path = outdir / name
        if not path.is_file():
            continue
        dig = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(CHUNK_SIZE):
                dig.update(chunk)
        sum_lines.append(dig.hexdigest() + "  " + name)
    sums_tmp = outdir / "SHA256SUMS.txt.tmp"
    with sums_tmp.open("x", encoding="ascii", newline="\n") as stream:
        stream.write("\n".join(sum_lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(sums_tmp, outdir / "SHA256SUMS.txt")
    return code


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="172.17.27.173")
    p.add_argument("--user", default="user1")
    p.add_argument("--key", required=True, help="key path only; key content is never read by this program")
    p.add_argument("--out", required=True, help="new local output directory; must not already exist")
    return p


if __name__ == "__main__":
    raise SystemExit(capture(parser().parse_args()))
