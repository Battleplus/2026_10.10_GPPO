from __future__ import annotations

"""Single-session R2 runner repair.

The remote program is sent as stdin to ``bash -s``.  It contains no nested
``bash -c`` and no Python source assembled inside shell quotes.  This module
does not ship an approval record and defaults to an offline fixture.
"""

import argparse
import hashlib
import json
import os
import pathlib
import subprocess

IDENTITY = "ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012"
IDENTITY_SHA = ""
BUDGET_SHA = ""
READER_SHA = ""
PLAN_SHA = ""
APPROVAL_SCHEMA = "n01-stage-budget-approval/1"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bindings(package: pathlib.Path) -> dict:
    path = pathlib.Path(__file__).with_name("FROZEN_BINDINGS.json")
    bindings = json.loads(path.read_text(encoding="utf-8"))
    if bindings.get("evaluation_identity") != IDENTITY:
        raise RuntimeError("repair identity binding mismatch")
    if sha256(package / "static_plan_r2.json") != bindings.get("reader_sha256"):
        raise RuntimeError("frozen reader SHA-256 mismatch")
    if sha256(package / "N01_FULL_EVALUATION_IDENTITY.json") != bindings.get("identity_sha256"):
        raise RuntimeError("identity manifest SHA-256 mismatch")
    if sha256(package / "n01_full_evaluation_stage_budget.json") != bindings.get("stage_budget_sha256"):
        raise RuntimeError("stage budget SHA-256 mismatch")
    identity = json.loads((package / "N01_FULL_EVALUATION_IDENTITY.json").read_text(encoding="utf-8"))
    actual = {name: sha256(package / name) for name in identity["current_source_hashes"]}
    if actual != identity["current_source_hashes"] or actual != bindings["package_source_hashes"]:
        raise RuntimeError("release source inventory mismatch")
    return bindings


def validate_local_reader(reader: pathlib.Path, bindings: dict) -> None:
    if sha256(reader) != bindings["reader_sha256"]:
        raise RuntimeError("frozen reader SHA-256 mismatch")
    obj = json.loads(reader.read_text(encoding="utf-8"))
    expected = {
        "evaluation_identity": IDENTITY,
        "identity_sha256": bindings["identity_sha256"],
        "plan_sha256": bindings["plan_sha256"],
    }
    if any(obj.get(k) != v for k, v in expected.items()):
        raise RuntimeError("frozen reader binding mismatch")
    plan = dict(obj)
    recorded = plan.pop("plan_sha256", None)
    actual = hashlib.sha256(json.dumps(plan, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()
    if recorded != actual:
        raise RuntimeError("reader canonical plan hash mismatch")


def remote_script() -> str:
    # All values arrive as environment variables.  Python receives file paths
    # as argv, so neither JSON keys nor identity strings pass through shell
    # quoting.
    return r'''#!/usr/bin/env bash
set -Eeuo pipefail
: "${PKG:?PKG is required}" "${RUN:?RUN is required}" "${UNIT:?UNIT is required}"
: "${APPROVAL_PATH:?APPROVAL_PATH is required}" "${DIAG:?DIAG is required}" "${LOCK_PATH:?LOCK_PATH is required}"
test "$UNIT" = "$EXPECTED_UNIT"
test ! -e "$DIAG"
mkdir "$DIAG"
exec > >(tee -a "$DIAG/session.stdout") 2> >(tee -a "$DIAG/session.stderr" >&2)
printf 'session_started=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
test -d "$PKG"
test "$(sha256sum "$PKG/N01_FULL_EVALUATION_IDENTITY.json" | cut -d' ' -f1)" = "$IDENTITY_SHA"
test "$(sha256sum "$PKG/n01_full_evaluation_stage_budget.json" | cut -d' ' -f1)" = "$BUDGET_SHA"
test "$(sha256sum "$PKG/static_plan_r2.json" | cut -d' ' -f1)" = "$READER_SHA"
python3 - "$PKG/N01_FULL_EVALUATION_IDENTITY.json" "$PKG" <<'PY'
import hashlib, json, pathlib, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
root = pathlib.Path(sys.argv[2])
for rel, expected in manifest["current_source_hashes"].items():
    path = (root / rel).resolve(strict=True)
    if root.resolve() not in path.parents:
        raise SystemExit("source path escapes package")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("source hash mismatch: " + rel)
print("source_set_bound=yes")
PY
python3 - "$PKG/static_plan_r2.json" "$IDENTITY" "$IDENTITY_SHA" "$PLAN_SHA" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
if obj.get("evaluation_identity") != sys.argv[2]:
    raise SystemExit("reader identity mismatch")
if obj.get("identity_sha256") != sys.argv[3]:
    raise SystemExit("reader identity sha mismatch")
if obj.get("plan_sha256") != sys.argv[4]:
    raise SystemExit("reader plan sha mismatch")
print("reader_bound=yes")
PY
test "$(systemctl --user show "$UNIT" -p LoadState --value --no-pager)" = loaded
R1=$(systemctl --user show n01-full-evaluation-r1-20261011.service -p InvocationID -p ActiveState -p Result -p ExecMainStatus --no-pager)
grep -qx 'InvocationID=7b65d35b5b4c464b810ecac918978166' <<<"$R1"
grep -qx 'ActiveState=failed' <<<"$R1"
grep -qx 'Result=exit-code' <<<"$R1"
grep -qx 'ExecMainStatus=1' <<<"$R1"
test "$(systemctl --user show "$UNIT" -p ActiveState --value --no-pager)" = inactive
test -z "$(systemctl --user show "$UNIT" -p InvocationID --value --no-pager)"
test ! -e "$RUN"
test -f "$APPROVAL_PATH"
python3 - "$APPROVAL_PATH" "$IDENTITY" "$BUDGET_SHA" "$READER_SHA" "$PLAN_SHA" "$EXPECTED_UNIT" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
checks = {
    "schema": "n01-stage-budget-approval/1",
    "status": "approved",
    "evaluation_identity": sys.argv[2],
    "stage_budget_sha256": sys.argv[3],
}
for key, value in checks.items():
    if obj.get(key) != value:
        raise SystemExit("approval mismatch: " + key)
if obj.get("identity_total") != {"wall_seconds": 5940.0, "cpu_seconds": 4800.0}:
    raise SystemExit("approval total mismatch")
stages = {
    "admission": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
    "evaluation": {"wall_seconds": 5400.0, "cpu_seconds": 4500.0},
    "export": {"wall_seconds": 300.0, "cpu_seconds": 180.0},
    "shutdown": {"wall_seconds": 120.0, "cpu_seconds": 60.0},
}
if obj.get("stages") != stages:
    raise SystemExit("approval stage caps mismatch")
body = obj.get("approval_body", {})
if body.get("reader_sha256") != sys.argv[4] or body.get("plan_sha256") != sys.argv[5]:
    raise SystemExit("approval reader/plan binding mismatch")
if body.get("single_start") is not True or body.get("failure_policy") != "preserve first error; never retry":
    raise SystemExit("approval launch/failure policy mismatch")
if body.get("unit") != sys.argv[6] or body.get("memory_max_bytes") != 4294967296:
    raise SystemExit("approval runtime binding mismatch")
if "r1 authorization reuse" not in body.get("excluded", []) or "n2" not in body.get("excluded", []) or "n3" not in body.get("excluded", []):
    raise SystemExit("approval exclusion binding mismatch")
if not obj.get("approval_reference") or not obj.get("approved_by"):
    raise SystemExit("approval provenance missing")
print("approval_bound=yes")
PY
# Atomic lock prevents concurrent or repeated launch attempts across sessions.
mkdir "$LOCK_PATH"
printf 'start_intent=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DIAG/start-intent.txt"
START_RC=0
systemctl --user start "$UNIT" || START_RC=$?
INVOCATION=$(systemctl --user show "$UNIT" -p InvocationID --value --no-pager || printf unknown)
if [ -z "$INVOCATION" ]; then INVOCATION=unknown; fi
printf 'formal_start=one unit=%s invocation_id=%s\n' "$UNIT" "$INVOCATION"
TERMINAL=no
for i in $(seq 1 "${POLL_LIMIT:-480}"); do
  ACTIVE=$(systemctl --user show "$UNIT" -p ActiveState --value --no-pager || printf unknown)
  SUB=$(systemctl --user show "$UNIT" -p SubState --value --no-pager || printf unknown)
  RESULT=$(systemctl --user show "$UNIT" -p Result --value --no-pager || printf unknown)
  printf 'observe poll=%s invocation_id=%s active=%s sub=%s result=%s utc=%s\n' "$i" "$INVOCATION" "$ACTIVE" "$SUB" "$RESULT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ "$ACTIVE" = inactive ] || [ "$ACTIVE" = failed ]; then TERMINAL=yes; break; fi
  sleep 15
done
systemctl --user show "$UNIT" --no-pager -p LoadState -p ActiveState -p SubState -p Result -p ExecMainCode -p ExecMainStatus -p InvocationID -p CPUUsageNSec -p MemoryCurrent -p MemoryPeak > "$DIAG/final-status.txt" || true
journalctl --user -u "$UNIT" --no-pager -o short-iso > "$DIAG/journal.txt" 2>&1 || true
if [ -d "$RUN" ]; then find "$RUN" -type f -printf '%P\t%s\n' | sort > "$DIAG/run-files.tsv"; else : > "$DIAG/run-files.tsv"; fi
ACTIVE=$(systemctl --user show "$UNIT" -p ActiveState --value --no-pager || printf unknown)
RESULT=$(systemctl --user show "$UNIT" -p Result --value --no-pager || printf unknown)
FINAL_INVOCATION=$(systemctl --user show "$UNIT" -p InvocationID --value --no-pager || printf unknown)
if [ "$START_RC" != 0 ]; then SETTLEMENT=FAILED_START_COMMAND
elif [ "$INVOCATION" = unknown ]; then SETTLEMENT=UNKNOWN_MISSING_INVOCATION
elif [ "$FINAL_INVOCATION" != "$INVOCATION" ]; then SETTLEMENT=UNKNOWN_INVOCATION_MISMATCH
elif [ "$TERMINAL" != yes ]; then SETTLEMENT=PENDING_TIMEOUT
elif [ "$ACTIVE" = failed ] || [ "$RESULT" != success ]; then SETTLEMENT=FAILED_PRESERVE_FIRST_ERROR
elif [ ! -s "$DIAG/run-files.tsv" ]; then SETTLEMENT=UNKNOWN_MISSING_RUN_EVIDENCE
else SETTLEMENT=TERMINAL_SUCCESS_REQUIRES_INDEPENDENT_AUDIT
fi
printf '{"schema":"n01-formal-run-settlement/1","status":"%s","invocation_id":"%s","active_state":"%s","result":"%s","start_exit":%s,"start_count":1,"retry_count":0,"run_files_index":"run-files.tsv","journal":"journal.txt","resource_status":"see final-status.txt; preserve unknown fields","formal_result_claimed":false}\n' "$SETTLEMENT" "$INVOCATION" "$ACTIVE" "$RESULT" "$START_RC" > "$DIAG/settlement.json"
cat "$DIAG/settlement.json"
test "$FINAL_INVOCATION" = "$INVOCATION"
test "$TERMINAL" = yes
test "$ACTIVE" = inactive
test "$RESULT" = success
'''


def run(args: argparse.Namespace) -> int:
    reader = pathlib.Path(args.reader)
    package = pathlib.Path(args.pkg)
    bindings = load_bindings(package)
    validate_local_reader(reader, bindings)
    env_bindings = {
        "IDENTITY": IDENTITY,
        "IDENTITY_SHA": bindings["identity_sha256"],
        "BUDGET_SHA": bindings["stage_budget_sha256"],
        "READER_SHA": bindings["reader_sha256"],
        "PLAN_SHA": bindings["plan_sha256"],
    }
    env = {
        "PKG": args.pkg,
        "RUN": args.run,
        "UNIT": args.unit,
        "APPROVAL_PATH": args.approval_path,
        "DIAG": args.diag,
        "LOCK_PATH": args.lock_path,
        "EXPECTED_UNIT": bindings["unit_name"],
        **env_bindings,
    }
    script = remote_script()
    if args.offline_fixture:
        proc = subprocess.run(["bash", "-s"], input=script, text=True, env={**os.environ, **args.environ, **env})
    else:
        if not args.key:
            raise ValueError("--key is required for the SSH path")
        target = f"{args.user}@{args.host}"
        cmd = ["ssh", "-i", args.key, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "PasswordAuthentication=no",
               "-o", "KbdInteractiveAuthentication=no",
               "-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "ProxyJump=none",
               "-o", "ProxyCommand=none", "-o", "ConnectionAttempts=1", target, "bash", "-s"]
        proc = subprocess.run(cmd, input=script, text=True, env={**os.environ, **args.environ, **env})
    return proc.returncode


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--reader", required=True)
    p.add_argument("--pkg", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--approval-path", required=True)
    p.add_argument("--diag", required=True)
    p.add_argument("--lock-path", required=True)
    p.add_argument("--offline-fixture", action="store_true")
    p.add_argument("--host", default="172.17.27.173")
    p.add_argument("--user", default="user1")
    p.add_argument("--key", default="")
    p.set_defaults(environ={})
    return p


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
