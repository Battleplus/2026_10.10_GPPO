# N2 Controller Revision Report

Date: 2026-10-14

## Status

**NOT_READY for managed execution.** The local controller and supervisor contract tests pass, but they use fake SSH/SFTP/systemd/cgroup and worker adapters. No network connection, remote command, systemd unit, Linux cgroup, or managed worker was run. The executor adapter is still pending and no `managed_worker(runtime)` callable is currently available. This report does not authorize execution and does not change the latest STOP or consume any old authorization.

## Delivered

- `n2_controller.py` exposes a single `run_controller` entry point. Remote commands go through keyword-only `command(..., *, label, text, ...)`, preventing the old positional label/text swap.
- `standalone_controller.py` is the executable one-shot entry point. It reads a strict config JSON and a separate exact authorization JSON, rejects duplicate JSON keys/non-finite constants, binds package, run, target, unit, worker, controller bundle, standalone source, full budget, and consumption root, then invokes the existing controller API. The authorization record must contain explicit approval metadata and match the complete expected field set.
- Before evidence writes or connection, local validation checks the approved budget schema, worker/package identity, package manifest and file hashes, path constraints, controller source and bundle hashes, standalone source hash, full canonical budget hash, worker entry/arguments, remote root, and fixed consumption-root reference. The sample [controller_config.template.json](E:\10.14\n2-development\controller\controller_config.template.json) is deliberately `NOT_APPROVED` and is rejected before connection or writes.
- After validation, the controller atomically claims the authorization ID/run identity in the configured persistent consumption directory. Changing the evidence directory does not release the claim. Duplicate claims fail before a connection.
- Preflight accepts one structured JSON record only. It reads the SSH command process's actual cgroup `cpuset.cpus.effective`, intersects that with `sched_getaffinity`, and constructs `CPUAffinity` from the result; there is no fixed CPU 0 assumption.
- The command plan includes remote roots, SFTP transfer, per-file remote SHA-256 verification, a pre-submission check that the systemd unit does not already exist, one `Type=exec` submission with `RuntimeMaxSec`, `CPUQuota`, and `MemoryMax`, same-connection invocation observation, and result collection. Local monotonic work and total deadlines are separate so the settlement reserve remains available.
- On a failure after submission is attempted, the controller preserves `FIRST_ERROR`. It stops the unit only after capturing its invocation ID and confirming that ID still belongs to the unit, then calls the worker settlement/evidence adapter. If the invocation is unknown, it does not stop an unidentified unit and records cleanup as unknown. It never reconnects or submits again.
- Success requires a same-invocation systemd success record and a collected receipt reporting a complete managed supervisor, matching controller-bundle hash, complete StageServer, BudgetLedger, settlement, export, and verified cgroup evidence. The default collector fetches worker/supervisor receipts and declared exports over SFTP with a monotonic deadline applied to each transfer.
- The transferred package now includes a controller bundle (`managed_stage_supervisor.py`, `managed_runtime.py`, `managed_worker_entry.py`, vendored W7 modules, and provenance) and launches the bundle supervisor as the `Type=exec` service entry. Authorization binds the controller bundle hash. Package validation requires an identity-bound `managed_runtime` manifest section containing the W7 stage request and guard limits matching the budget.
- The controller exposes a provisional local-engineering resource-request mapper from the local profile. Its stage allocations now include offline-prediction candidate rows, paired-collection output writes, and the remaining construction allowance after admission and PPO. It remains `PROVISIONAL_LOCAL_ENGINEERING_ONLY`; it is not an approved research budget.
- Runtime admission rejects candidate catalog truncation and enforces the complete W7 stage order. Export uses an atomic copy plus SHA-256 verification and refuses to leave a destination on mismatch. Guard parsing rejects non-finite durations and non-integer byte caps. Receipt validation rejects non-finite CPU/quota values and invalid or negative cgroup counters; receipt and export SFTP transfers use the remaining monotonic deadline as their socket timeout. Supervisor CPU guards and receipts use the fresh unit cgroup's absolute `usage_usec`, including startup and settlement; settlement also checks pending ledger calls, memory OOM events, memory/storage limits, signal cleanup, and lingering cgroup PIDs.
- The exact authorization JSON is consumed by an atomic one-time claim. Paramiko is used from the existing runtime, with the supplied known-hosts file loaded and unknown hosts rejected; key and known-host references are not printed. Failure settlement verifies the captured invocation before collecting failure artifacts and reports unknown when the invocation is unavailable.

The standalone invocation form is:

```text
python E:\\10.14\\n2-development\\controller\\standalone_controller.py --config E:\\10.14\\n2-development\\controller\\controller_config.json --authorization E:\\10.14\\n2-development\\controller\\approved-authorization.json
```

The template itself is not executable because its budget is `NOT_APPROVED`; the two runtime JSON paths must be created from an approved run configuration and a separately approved exact record.

## Verification

Command run: `python -m unittest -v test_standalone_controller test_n2_controller test_managed_stage_supervisor test_managed_runtime`

Result: exit code 0, 18 tests passed. Complete stdout/stderr is saved in [local-tests.txt](E:\10.14\n2-development\controller\verification\local-tests.txt), SHA-256 `4463DC653DD0FAD8EF9983CF93A614CF7172EA7A88448C96390A4E7451923315`. Coverage includes strict CLI JSON parsing including exponent overflow, rejection of the `NOT_APPROVED` template before connect/write, exact authorization success through a mocked connector, authorization mismatch before claim/connect, fake command text/order and pre-existing-unit protection, timeout and failed-channel handling, one-time authorization replay rejection, same-connection stop/settlement with first-error preservation, refusal to stop a unit when its invocation ID is unknown, fake cgroup CPU-guard failure and absolute CPU accounting, guard rejection of NaN/infinity and non-integer byte caps, collector rejection of NaN quota/CPU and negative PID/memory counters, fake settlement receipt, profile-to-W7 allocation totals, catalog admission, and wrong export hash cleanup. These tests demonstrate code contracts only; they are not a managed acceptance PASS.

## Hashes

- Controller bundle SHA-256: `A265DE1455368433C9B2B38AED3B8EB8CE372B763B0AB2792BD0406FDAD11AD2`
- Controller source-package SHA-256: `CF0F4D6F864EF23D2271AA4EEB196A89A90E40B70D46CF53F836E35ECC37323D`
- Standalone entry/auth source SHA-256: `994C1B50DF383D54401BFE9BCD6E1B1F262D35F485A6F54BA7D8D8EDFD6EBF44`
- `n2_controller.py`: `57034297008E9CBC31D381C25B93F1867E84090C50FFB3E61CF74A61C1E372B4`
- `managed_stage_supervisor.py`: `7E4A8CF78F9D09246A3878DB60D09D3AD1AC219BE43E2A907333BBE8E425511F`
- `managed_runtime.py`: `94EB6796BE523122F51A567A7F4A8E846C0D6F3ABAB43A215FAC2529053D406B`
- `managed_worker_entry.py`: `4756459C9E3552B9A8E221ACE36D40D46C413440DE4312EE7901513D4697A696`
- `standalone_controller.py`: `4C6E78A0E4E1943016813B1CF13D9B12B0BD6CF49B4C0E00DF62DAE3B6F96B7F`; `exact_record_authorization.py`: `E1517CF516388064863C28DC47A58E4DCEB3467B9522CE910EDC9AEE60F58441`
- Config template SHA-256: `DB038A1C1DC1504903C8CE968586D5F65793813EBF51F0213E5F7B823651D358`
- Tests: `test_n2_controller.py` `7CD47BA4C2B85A4D3AB4A2B0E0BD40D3826DECB583789723ED9105D6006232C6`; `test_managed_stage_supervisor.py` `E63F6E060F39E7DD50A68B37E1DC58283B95631D6646CEEAF49C9DCC7CAB1BC7`; `test_managed_runtime.py` `C1C8B6FC800F97C9D691674628B78E7652F2C0786377F6F0CB79F1E94D06FBBF`; `test_standalone_controller.py` `F4F4CA7F493A2B8B97EE8F5B30465CED148EBB88C30CF1BC7153322EDF8859DD`
- W7 vendor hashes and missing-`infra_io` compatibility provenance: `vendor/PROVENANCE.json` SHA-256 `CB180D74F8C330A065F93DB3DA3738D4D5E9A86290E7EAD35970385038B39E1F`. The four supplied W7 files match their reference hashes; `infra_io.py` is local compatibility code, not copied source.

## Not Verified / Required Before Readiness

- No cryptographic signature provider is configured. The standalone entry verifies the exact out-of-band approved JSON record and all bound local hashes; the named approver fields are record metadata, not proof of approver identity or a digital signature.
- The actual transient unit cgroup has not been inspected. The preflight cpuset is from the SSH command's cgroup, while the controller requires the worker receipt adapter to report unit-level cgroup verification. There is no independent production validation of unit cpuset, CPU counters, memory peak, or process-tree RSS here.
- StageServer, BudgetLedger, shutdown settlement, export, and SFTP collection are exercised only through fakes in local tests. The real worker adapter (`managed_worker(runtime)`) remains pending; no managed execution or real Linux cgroup validation has occurred.
- The immutable local engineering receipt (`runs/local-1791969402746190800/artifacts/LOCAL_ENGINEERING_RECEIPT.json`) reports local Windows-only work, 57 episode constructions, 1,384 environment steps, 12 WM and 48 PPO optimizer steps, and unavailable cgroup metrics. It is separate local engineering evidence and does not establish managed acceptance or research results.
- The current engineering budget remains draft. No new run identity, approved authorization record, production worker adapter, or remote execution was created.
- The old launcher and all prior STOP evidence remain untouched.
- The reviewed R7 controller source snapshot is preserved at `revisions/r7-frozen/`; its canonical copied-file SHA-256 is `83C5E66F99A2DD027061DA7FD6FC195C0C2D0BC40611BC4D6E795E823F27B9B3`, retaining the previous controller bundle hash `A265DE1455368433C9B2B38AED3B8EB8CE372B763B0AB2792BD0406FDAD11AD2`.
