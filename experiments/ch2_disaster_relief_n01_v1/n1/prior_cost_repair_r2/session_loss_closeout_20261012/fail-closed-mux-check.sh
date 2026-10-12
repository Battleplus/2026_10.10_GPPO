#!/usr/bin/env bash
set -euo pipefail

test_socket="/tmp/codex-n01-no-master-$PPID"
test ! -e "$test_socket"

set +e
output=$(ssh -vv -S "$test_socket" \
  -o ControlMaster=no \
  -o ProxyCommand=/bin/false \
  -o BatchMode=yes \
  -p 1 mux-test@127.0.0.1 true 2>&1)
status=$?
set -e

printf '%s\n' "$output"
test "$status" -ne 0
grep -Fq 'Executing proxy command: exec /bin/false' <<<"$output"
if grep -Fq 'Connecting to 127.0.0.1' <<<"$output"; then
  echo "FAIL: direct TCP fallback occurred" >&2
  exit 1
fi
echo "PASS: missing mux uses /bin/false and does not open direct TCP"
