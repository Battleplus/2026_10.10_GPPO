from __future__ import annotations

"""External one-session SSH transport for the frozen R2 runner."""

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys

import n01_r2_formal_runner_repaired as runner


APPROVAL_REFERENCE = "N1-MAIN-NODE-20261012-R2-FORMAL-REPAIR-2800"
APPROVED_BY = (
    "User-confirmed R2 2800-episode evaluation scope; 2026-10-12"
)
PRIOR_APPROVAL_SHA = "e61324c215158c81d6129c8852c89fbc1200f85e28c6bff78c265cc68c4a91ff"
PRIOR_IDENTITY = "ch2-disaster-relief-n01-full-evaluation-r1-20261011"
PRIOR_BUDGET_SHA = "ebc7b2140569ad470aa1c7eb4e00cbd234e8f0092a00c0f7a2dc717e1703d572"
APPROVAL_FILENAME = "N1_FULL_EVALUATION_BUDGET_APPROVAL.json"


def approval_record(bindings: dict, unit: str) -> dict:
    return {
        "schema": runner.APPROVAL_SCHEMA,
        "status": "approved",
        "evaluation_identity": runner.IDENTITY,
        "stage_budget_sha256": bindings["stage_budget_sha256"],
        "stages": {
            "admission": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
            "evaluation": {"wall_seconds": 5400.0, "cpu_seconds": 4500.0},
            "export": {"wall_seconds": 300.0, "cpu_seconds": 180.0},
            "shutdown": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
        },
        "identity_total": {"wall_seconds": 5940.0, "cpu_seconds": 4800.0},
        "approval_reference": APPROVAL_REFERENCE,
        "approved_by": APPROVED_BY,
        "scope": "Six fixed checkpoints, 350 registered scenarios, 2800 evaluation episodes; training disabled",
        "target_gate": "Admission must pass before evaluation; preserve first error and never retry",
        "results_claim": "No result is implied by this approval",
        "approval_body": {
            "unit": unit,
            "memory_max_bytes": 4294967296,
            "single_start": True,
            "failure_policy": "preserve first error; never retry",
            "reader_sha256": bindings["reader_sha256"],
            "plan_sha256": bindings["plan_sha256"],
            "excluded": ["r1 authorization reuse", "n2", "n3", "training"],
        },
    }


def shell_prefix(env: dict[str, str], approval: dict) -> str:
    exports = "\n".join(
        f"export {name}={shlex.quote(value)}" for name, value in sorted(env.items())
    )
    approval_json = json.dumps(approval, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    approval_literal = repr(approval_json)
    prefix = f"""#!/usr/bin/env bash
set -Eeuo pipefail
{exports}
: "${{PKG:?}}" "${{RUN:?}}" "${{DIAG:?}}" "${{LOCK_PATH:?}}" "${{APPROVAL_PATH:?}}"
test -d "$PKG"
test "$(sha256sum "$PKG/N01_FULL_EVALUATION_IDENTITY.json" | cut -d' ' -f1)" = "$IDENTITY_SHA"
test "$(sha256sum "$PKG/n01_full_evaluation_stage_budget.json" | cut -d' ' -f1)" = "$BUDGET_SHA"
test "$(sha256sum "$PKG/static_plan_r2.json" | cut -d' ' -f1)" = "$READER_SHA"
test "$(basename "$APPROVAL_PATH")" = "{APPROVAL_FILENAME}"
test "$(dirname "$APPROVAL_PATH")" = "$(dirname "$PKG")"
test -f "$APPROVAL_PATH"
test "$(sha256sum "$APPROVAL_PATH" | cut -d' ' -f1)" = "{PRIOR_APPROVAL_SHA}"
python3 - "$APPROVAL_PATH" <<'PY_PRIOR'
import json, sys
old = json.load(open(sys.argv[1], encoding="utf-8"))
if old.get("evaluation_identity") != "{PRIOR_IDENTITY}" or old.get("stage_budget_sha256") != "{PRIOR_BUDGET_SHA}":
    raise SystemExit("shared approval is not the exact known R1 approval")
PY_PRIOR
test ! -e "$RUN"
test ! -e "$DIAG"
test ! -e "$LOCK_PATH"
"""
    install = f'''python3 - "$APPROVAL_PATH" "$DIAG" "$PKG" <<'PY_APPROVAL_TRANSITION'
import ctypes, errno, hashlib, json, os, pathlib, sys, tempfile
target, diag, pkg = map(pathlib.Path, sys.argv[1:])
if target != pkg.parent / {APPROVAL_FILENAME!r}:
    raise SystemExit("approval path is not evaluator's fixed sibling path")
if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != {PRIOR_APPROVAL_SHA!r}:
    raise SystemExit("shared approval changed after preflight")
old_bytes = target.read_bytes()
old_obj = json.loads(old_bytes)
if old_obj.get("evaluation_identity") != {PRIOR_IDENTITY!r} or old_obj.get("stage_budget_sha256") != {PRIOR_BUDGET_SHA!r}:
    raise SystemExit("shared approval identity/budget changed after preflight")
backup = diag / "prior-r1-approval.json"
if os.path.lexists(backup):
    raise SystemExit("prior approval backup path already exists")
fd, backup_tmp = tempfile.mkstemp(prefix=".prior-approval-", dir=str(diag))
try:
    with os.fdopen(fd, "wb") as stream:
        stream.write(old_bytes); stream.flush(); os.fsync(stream.fileno())
    os.link(backup_tmp, backup)
finally:
    try: os.unlink(backup_tmp)
    except FileNotFoundError: pass
if hashlib.sha256(backup.read_bytes()).hexdigest() != {PRIOR_APPROVAL_SHA!r}:
    raise SystemExit("prior approval backup hash mismatch")
payload = {approval_literal}.encode("ascii") + b"\\n"
fd, new_tmp = tempfile.mkstemp(prefix=".r2-approval-", dir=str(target.parent))
new_tmp_path = pathlib.Path(new_tmp)
preserve_new_tmp = False
try:
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    if target.read_bytes() != old_bytes:
        raise SystemExit("shared approval changed before atomic replacement")
    libc = ctypes.CDLL(None, use_errno=True)
    exchange = getattr(libc, "renameat2", None)
    if exchange is None:
        raise SystemExit("atomic no-clobber exchange is unavailable")
    exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    exchange.restype = ctypes.c_int
    if exchange(-100, os.fsencode(new_tmp_path), -100, os.fsencode(target), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if new_tmp_path.read_bytes() != old_bytes:
        if exchange(-100, os.fsencode(new_tmp_path), -100, os.fsencode(target), 2) != 0:
            preserve_new_tmp = True
            (diag / "approval-transition-recovery.json").write_text(json.dumps({{"status":"manual-recovery-required","unexpected_approval_preserved_at":str(new_tmp_path)}}, sort_keys=True, indent=2) + "\\n", encoding="utf-8")
            raise OSError(ctypes.get_errno(), "cannot restore concurrently changed approval path")
        raise SystemExit("shared approval changed during atomic exchange; original state restored")
    new_tmp_path.unlink()
finally:
    if not preserve_new_tmp:
        try: os.unlink(new_tmp)
        except FileNotFoundError: pass
if hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(payload).hexdigest():
    raise SystemExit("installed R2 approval hash mismatch")
transition = {{"schema":"n01-approval-transition/1","prior_sha256":{PRIOR_APPROVAL_SHA!r},"prior_identity":{PRIOR_IDENTITY!r},"prior_budget_sha256":{PRIOR_BUDGET_SHA!r},"installed_identity":{runner.IDENTITY!r},"installed_stage_budget_sha256":{approval["stage_budget_sha256"]!r},"backup":"prior-r1-approval.json","automatic_restore":False}}
(diag / "approval-transition.json").write_text(json.dumps(transition, sort_keys=True, indent=2) + "\\n", encoding="utf-8")
PY_APPROVAL_TRANSITION
'''
    marker = 'test ! -e "$RUN"\ntest -f "$APPROVAL_PATH"\n'
    if runner.remote_script().count(marker) != 1:
        raise RuntimeError("reviewed runner approval gate marker changed")
    gate = 'test ! -e "$RUN"\n' + install + 'test -f "$APPROVAL_PATH"\n'
    return prefix + runner.remote_script().replace(marker, gate, 1)


def run(args: argparse.Namespace) -> int:
    package = pathlib.Path(args.pkg)
    bindings = runner.load_bindings(package)
    runner.validate_local_reader(pathlib.Path(args.reader), bindings)
    if args.unit != bindings["unit_name"]:
        raise ValueError("unit does not match frozen runner binding")
    env = {
        "PKG": args.remote_pkg,
        "RUN": args.run,
        "UNIT": args.unit,
        "APPROVAL_PATH": args.approval_path,
        "DIAG": args.diag,
        "LOCK_PATH": args.lock_path,
        "EXPECTED_UNIT": bindings["unit_name"],
        "IDENTITY": runner.IDENTITY,
        "IDENTITY_SHA": bindings["identity_sha256"],
        "BUDGET_SHA": bindings["stage_budget_sha256"],
        "READER_SHA": bindings["reader_sha256"],
        "PLAN_SHA": bindings["plan_sha256"],
    }
    script = shell_prefix(env, approval_record(bindings, args.unit))
    target = f"{args.user}@{args.host}"
    command = [
        "ssh", "-i", args.key,
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no", "-o", "ControlMaster=no",
        "-o", "ControlPath=none", "-o", "ProxyJump=none", "-o", "ProxyCommand=none",
        "-o", "ConnectionAttempts=1", target, "bash", "-s",
    ]
    proc = subprocess.run(command, input=script.encode("utf-8"), env=os.environ.copy())
    return proc.returncode


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--reader", required=True)
    p.add_argument("--pkg", required=True)
    p.add_argument("--remote-pkg", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--approval-path", required=True)
    p.add_argument("--diag", required=True)
    p.add_argument("--lock-path", required=True)
    p.add_argument("--host", default="172.17.27.173")
    p.add_argument("--user", default="user1")
    p.add_argument("--key", required=True)
    return p


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
