# R2 Transport Repair Report

Date: 2026-10-13 (local)

Scope: local Windows to WSL transport verification only. No SSH connection,
server command, research-package execution, checkpoint load, or identity change
was performed.

## Failure and repair

The preserved attempt `attempts/formal-run-20261012-ssh1/` records the original
failure. The reviewed LF script crossed the Windows subprocess boundary in text
mode and arrived at remote `bash -s` with CRLF bytes. Bash rejected the second
line (`set: pipefail : invalid option name`) before package preflight, approval
transition, lock creation, service start, or evaluation.

`formal_transport_envelope.py` now passes `script.encode("utf-8")` as the
`subprocess.run(..., input=...)` value. The Windows boundary test asserts that
the value is `bytes` and contains no `\r`. The same bytes are then passed to a
real `wsl.exe -d Ubuntu-24.04 --exec ... bash -s` process, where the controlled
success envelope executes through approval binding and one service start.

## Local test result

Command, run from `formal_runner_repair_v1`:

```text
python -m unittest discover -v formal_transport_v1
```

Result: **5/5 passed**.

The four envelope cases are:

1. successful one-start settlement;
2. unknown shared approval preserved with zero starts;
3. R1 preflight mismatch preserved with zero starts;
4. pending result recorded without retry.

The fifth case is the Windows subprocess bytes boundary. It captures the exact
stdin, rejects CR bytes, executes those bytes with real WSL `bash -s`, and
checks `approval_bound=yes` plus one start. Every Windows test fixture root and
capture file is created under WSL `/tmp`; the non-Windows fallback also uses
`/tmp`.

## Frozen hashes

SHA-256 values below were computed after the repair and test updates:

```text
formal_transport_v1/formal_transport_envelope.py  7A837737CDA057C4FBA3E41152B316C74780C6E63AB87E89738B7E4C02B5990D
formal_transport_v1/test_formal_transport_envelope.py  D96F09F41D5EFCBCBD15F81621BDA431467B9E93669CF18F70B74D521A32A76C
formal_transport_v1/test_windows_transport_bytes.py  61EC281A726979DFCA0C8AE094B697193535D0386440905E56710660FA913A03
release/N01_FULL_EVALUATION_IDENTITY.json  E01F2444BFB75D765F9522934A581A535055990445EC0356E6DD13B6FDC6E5FE
release/n01_full_evaluation_stage_budget.json  49F2736A53E6428B3893A1AE0C81500B0E48CA766300352FB464715627EBEB5C
release/static_plan_r2.json  3EB535AA7390C0056044BA4EE5356FC3E2CEA6CA9CE8E2E6D4AD5064D919AA3D
```

The first three files are the frozen transport/test set. The last three are
recorded as package identity sentinels; they were read-only during this work.

## Review handoff

This report and the six hashes are ready for independent local review. Review
must verify the bytes boundary, the real WSL `bash -s` execution, the four
negative/positive cases, WSL `/tmp` fixture paths, and that no release or
identity file changed. No remote authorization is implied by this report.
