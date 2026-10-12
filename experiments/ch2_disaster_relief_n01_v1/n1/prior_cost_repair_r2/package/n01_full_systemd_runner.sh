#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT=/home/user1/w1-pilot/packages/ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012
WORK_ROOT=/home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012-once
PYTHON=/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python
EXPECTED_IDENTITY=ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012

test -x "$PYTHON"
test -f "$PACKAGE_ROOT/N01_FULL_EVALUATION_IDENTITY.json"
test ! -e "$WORK_ROOT"
actual_identity=$("$PYTHON" -B -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["evaluation_identity"])' "$PACKAGE_ROOT/N01_FULL_EVALUATION_IDENTITY.json")
test "$actual_identity" = "$EXPECTED_IDENTITY"

for stage in admit evaluate export shutdown; do
    "$PYTHON" -B "$PACKAGE_ROOT/n01_full_evaluator.py" \
        --mode "$stage" \
        --package-root "$PACKAGE_ROOT" \
        --work-root "$WORK_ROOT"
done
