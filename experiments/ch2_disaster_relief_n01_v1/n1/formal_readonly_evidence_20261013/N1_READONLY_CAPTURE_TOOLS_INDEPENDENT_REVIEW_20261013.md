# N1 Read-Only Capture Tools: Independent Review Addendum

Date: 2026-10-13 (Asia/Shanghai)

This addendum records the scope and local evidence-integrity review of the two one-shot collectors used to retrieve evidence for the N1 formal-run review. Neither script was executed by this reviewer against the server. No credentials or raw evidence are included here.

| Collector | Reviewed source SHA-256 | Review result |
|---|---|---|
| `n01_formal_readonly_capture_20261013/capture_n01_readonly_once.py` | `1e24067cf69a2d59bdfb765031b679698cded0c90be54b66f9925a4b146c0fcd` | Fixed identity/unit/run/diagnostics and InvocationID; one SSH invocation; read-only systemd/journal/file operations; no symlink following; raw binary streams retained and hashed. Offline tests passed 7/7. |
| `n01_minimal_recapture_plan_20261013/capture_n01_minimal_missing_once.py` | `a44bb01a78ef3277f6e7a0e343039cddd0419f21b5f749cdbceaecfab9f4e0d` | Fixed to ZIP and `preflight_plan.json`; component-wise no-follow reads; regular-file and stable-stat checks; archive expected-hash check; one SSH invocation; hard aggregate 70 MiB cap enforced per chunk before output. Offline `--plan` assertions passed; no server connection during review. |

The first collector's local capture decoded with zero payload hash mismatches and no local errors. Its inventory was marked partial only because the configured 2 GiB byte budget skipped 598 large files. The supplemental collector recovered the two allowlisted files; the ZIP matched the export manifest's expected size and SHA-256. Both collectors preserve their raw streams and local session records with SHA-256 inventories. These checks establish local byte integrity relative to the collectors' framed streams and the captured expected ZIP hash; they are not a cryptographic signature over the remote host.

The supplemental collector's initial draft did not enforce the aggregate cap if a file grew after its initial `fstat`. That issue was corrected by checking every read chunk against the remaining byte budget before emitting the chunk. This review inspected the corrected source and ran only its local `--plan` mode. No SSH action was run by this reviewer.
