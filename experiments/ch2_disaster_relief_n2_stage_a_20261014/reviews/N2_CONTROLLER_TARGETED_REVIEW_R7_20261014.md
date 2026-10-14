# N2 controller targeted independent review R7 — final closure

Date: 2026-10-14. Verdict: **TARGETED IMPLEMENTED CONTRACTS VERIFIED; NO MANAGED ACCEPTANCE OR EXECUTION AUTHORIZATION.** All concrete defects identified in this review are closed. No SSH, remote command, systemd service, real Linux cgroup, managed worker, model forward, optimizer or environment simulation was run by this review.

## Reviewed identity

Executor-reported source-package identity: `CF0F4D6F864EF23D2271AA4EEB196A89A90E40B70D46CF53F836E35ECC37323D`; standalone entry/auth binding: `994C1B50DF383D54401BFE9BCD6E1B1F262D35F485A6F54BA7D8D8EDFD6EBF44`. These aggregate identities were not independently reconstructed. Historical snapshot `controller/revisions/r7-frozen/` has executor-reported canonical hash `83C5E66F99A2DD027061DA7FD6FC195C0C2D0BC40611BC4D6E795E823F27B9B3`.

Independently recomputed final individual SHA-256:

| File | SHA-256 |
| --- | --- |
| n2_controller.py | 57034297008E9CBC31D381C25B93F1867E84090C50FFB3E61CF74A61C1E372B4 |
| managed_stage_supervisor.py | 7E4A8CF78F9D09246A3878DB60D09D3AD1AC219BE43E2A907333BBE8E425511F |
| managed_runtime.py | 94EB6796BE523122F51A567A7F4A8E846C0D6F3ABAB43A215FAC2529053D406B |
| managed_worker_entry.py | 4756459C9E3552B9A8E221ACE36D40D46C413440DE4312EE7901513D4697A696 |
| standalone_controller.py | 4C6E78A0E4E1943016813B1CF13D9B12B0BD6CF49B4C0E00DF62DAE3B6F96B7F |
| exact_record_authorization.py | E1517CF516388064863C28DC47A58E4DCEB3467B9522CE910EDC9AEE60F58441 |
| test_standalone_controller.py | F4F4CA7F493A2B8B97EE8F5B30465CED148EBB88C30CF1BC7153322EDF8859DD |
| controller_config.template.json | DB038A1C1DC1504903C8CE968586D5F65793813EBF51F0213E5F7B823651D358 |

The independent probe recomputed bundle `A265DE1455368433C9B2B38AED3B8EB8CE372B763B0AB2792BD0406FDAD11AD2`. Its source inventory predates the final standalone overflow repair; the standalone hash above supersedes its older entry.

## Repairs closed

- Undefined subreaper resolves through `linux_process_scope.enable_subreaper()`.
- Guard limits reject NaN/infinite duration, invalid interval and fractional byte caps. Independent NaN CPU, Inf CPU, float bytes and NaN interval probes all rejected.
- Mapper includes offline candidate rows and paired evidence writes. Independent one-forward/seven-row and one-write operations were admitted before effect, each effect exactly once.
- Paired constructions now1011/global1024, leaving room for restore/replay under the total cap.
- Fresh-unit CPU uses absolute cgroup `usage_usec`, including startup, without subtracting the baseline.
- Pre-launch ownership and known InvocationID checks precede stop; unknown invocation leaves UNKNOWN and never stops an unidentified unit.
- Collector rejects non-finite quota/CPU and invalid counters, and checks receipt identities/schema/cgroup/settlement/export. Independent fake valid receipts passed; NaN quota and CPU rejected.
- SFTP uses remaining monotonic deadline timeout and checks around transfer.
- Strict JSON rejects duplicate keys, non-finite constants and exponent overflow `1e400`.

Independent final command `python -B -m unittest -v test_n2_controller test_managed_stage_supervisor test_managed_runtime test_standalone_controller`: **18 tests,0.397s,exit0**. Saved full output: `controller_r7_final_tests.txt`. Independent probes: `audit_controller_targets_r7.py` and `audit_controller_targets_r7_output.json`. Tests use local fakes/mocks; no production connector or learning was executed. CPU was not separately metered; these checks are separate from the immutable first run's receipt.

## Authorization and measurement boundaries

The standalone CLI requires explicit config/authorization, strict exact fields and bound identities/full budget/worker/target/unit/claim root before claim/connect. NOT_APPROVED template rejects before effects. One-time exact-record claim precedes connection. Known-host verification rejects unknown hosts. Reviewer never inspected keys or actual private authorization/token contents.

Approver names are record metadata; no cryptographic provenance/signature provider exists. Exact JSON validation and a one-time claim do not establish human approval. Future execution needs actual fresh out-of-band human authorization for the exact reviewed run; consumed identities cannot be reused.

Actual `managed_worker(runtime)` and real managed Linux evidence remain absent as already acknowledged. This report does not claim StageServer/BudgetLedger/systemd/cgroup acceptance, server passed or research readiness. No further generic review round is necessary to close the implemented contracts above.

Nested export/work roots can be conservatively double-counted by tree-byte accounting. Final supervisor receipt/exit tail is outside its last CPU sample; collector does not independently reconcile absolute final systemd CPU with the cap. Keep these limits explicit in future settlement evidence.

The Windows first learning run remains under R6. R7 does not approve the erroneous old node packet, change STOP, grant remote execution or reuse consumed authorization.
