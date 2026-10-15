# Independent R10 snapshot metadata addendum

Reviewer: GPT-6.1 Sol, high reasoning. Date: 2026-10-15.

Verdict: **PASS — the identified change is metadata only. User approval scope does not change.** The original R10 source/configuration review remains applicable; this addendum binds the current snapshot metadata. Execution remains unapproved and hosted managed acceptance remains NOT RUN.

## Exact delta and timing

The original review and machine output recorded snapshot metadata SHA-256:

`5215D07FA2A7AFF21AEDCDA088E014C0A4269EDFAB185FE344B332E5339DA07B`

The current `E:/10.14/n2-development/controller-password-r10-SNAPSHOT_SHA256.json` hashes to:

`B6D0AFEF6672868079B4008A43FF769FDDD0E610E797077760FCCB7BEF077C6C`

The independent check loaded the current JSON, removed exactly the top-level `read_only_r10_preflight` block, and encoded `json.dumps(object, indent=2) + "\n"` as UTF-8. Those reconstructed bytes hash **exactly** to the original `5215…` value. This is a reconstruction checked against the previously recorded digest, not a newly discovered original snapshot file.

The added block records the already-reviewed exact R10 preflight receipt path/hash, READ_ONLY_PREFLIGHT_MATCH status, CPU intersection 0–31, effective cpuset source `/sys/fs/cgroup/user.slice`, and false upload/training/authorization-consumption/credential-persistence flags. Its assertions match the unchanged receipt. No other field differs from the original metadata bytes represented by the recorded digest.

The original audit output's local modification time is 2026-10-15 00:13:16.337425 UTC; the current metadata file's is 00:13:18.921886 UTC. These times are consistent with the executor's disclosed append occurring immediately after the original audit output. The byte reconstruction supplies the stronger evidence of the precise delta. The earlier report was correct for the metadata version it observed; the later request/archive included the appended version. That timing discrepancy is preserved here, without rewriting the original report or output.

## Current bindings independently rechecked

- All **17 R10 files** match both the prior independent machine output and the current snapshot's file-hash table. Canonical source mapping remains `C7A451A43B693690AA2D4B6F59FD74930888B15304410C95C4482752589DB60E`.
- All **54 worker-package files** match their manifest table, with no extra/missing inventory files. Package manifest remains `661C80171B56DA0C45A072AA6699EE9D21032C2B3BB63D639286894D5655B05E`.
- Proposed config remains `9C812ECFC8CF9DDF24A33380890E89A52F0A2174A3F7955EBC9A429295827FF3`; budget remains NOT_APPROVED, password mode and null key reference unchanged.
- Test log remains `3737A8CE1D6B279BDA34E01FEA51AEA9F602AEA9497EA77312B3CADBF846B1CD`; exact actual read-only receipt remains `DC9D3DAFA0E935FC7B94FF54774C9A1303BCCC71F2CD1BB826502A038ACEACA9`.
- Current authorization request hashes to `ED2358C66EE82C1B7AFDE581B557D884CF706FFD37E9A6CF28A39A3F87B1D851` and correctly binds the current `B6D…` metadata, unchanged configuration, source mappings and preflight receipt.
- The preserved full archive hashes to `4CDA29C94405505278E3B6D2D1F0B490CDE596EAA4CD560A98580A468ADC5727`; the preserved public-source archive hashes to `DF3F2A146E34BE5B03DD23148838D031D9CFDDDBE086ED3B7D52ACFAD09DBC42`. Both contain the current `B6D…` snapshot and the original independent machine output unchanged.

Original independent report SHA-256 remains `B923351ADEC8CD9FC2BB425568B090439449F602DC80790395CEBEF45D4BB048`; original output remains `802A0455B4D0205BA514C9239FDF7F46E9CA8CFF6247430C787607E7DD4508DF`. Neither was overwritten. Existing archive ZIPs and publication commit were not modified by this review.

## Approval and acceptance implications

This addition changes no executable source, target, run/unit identity, worker package, password-authentication mode, resource limits, operation caps or requested one-attempt scope. It adds a pointer to evidence the original review already examined. **No new or expanded user approval scope arises from this metadata-only delta.** The evidence version in any subsequent approval/request must transparently refer to the current metadata and this addendum; the addendum itself grants no approval.

The request still has `execution_authorized: false`, requests one bounded Stage A managed engineering acceptance attempt and excludes formal research. The existing need for a genuine fresh exact one-time approval, live systemd/StageServer/BudgetLedger settlement, verified raw export and wider research-budget readiness remains. Original sampled-storage and other R10 review limitations remain in force; Stage A remains incomplete.

The new same-prefix `.py` and `.json` files record the reconstruction and every current source digest. One bounded read-only local check produced the result. No implementation, SSH, password prompt, experiment, training, authorization creation or authorization consumption occurred.
