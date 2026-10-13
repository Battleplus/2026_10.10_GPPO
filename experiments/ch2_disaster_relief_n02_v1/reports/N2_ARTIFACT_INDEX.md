# N2 Source and Artifact Index

This index describes the public archive contents and source closure. The original independently reviewed package manifest digest was `47C6ED5B74027E157A4F259AF63D778E1B3B905885CED7EF771FE3036DB524BA`. The public archive corrects the preparation README chronology and its file hash; its revised package manifest digest is `4BBA81400B575F6D6C928DE2D6FB4CC7AFB5136DB993BD29A24A1793B9285051`. The revised local manifest is not a new Linux acceptance or target authorization.

## Source Closure

The Linux package source closure contains 23 manifest-listed files plus the manifest:

- N2 engineering implementation, runner, package builder, smoke driver, and five unit-test modules under `development/ch2_disaster_relief_n2_v1/engineering/`.
- Civilian graph-v2 runtime dependencies under `development/ch2_disaster_relief_graph_v2/`: `relief_env.py`, `baselines.py`, `scenario_schema.py`, `graph_policy.py`, `ppo_trainer.py`, `chapter1_adapter.py`, `stable_identity.py`, `literal_graph_ops.py`, and `dataset_protocol.py`.
- The synthetic `fixtures/control.json` and `development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/README.md`.
- The manifest at `development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/package-manifest.json` pins those 23 files.

The M0/M1 evidence also depends on `development/ch2_disaster_relief_n2_v1/preparation/test_branch_snapshot_contract.py`, the adjacent N2 preparation records, and inherited graph-v2 tests and source in the main project. The N2 archive includes the N2 preparation probe and its source-hash record. The local 29-test engineering suite additionally requires `development/ch2_disaster_relief_graph_v2/PRIOR_RESOURCE_COST.json` (SHA-256 `B577B88138699DCEFC8286314B64D0C41D7278F36ED3DB38ECCDAE962A5ED263`) because `ppo_trainer.source_identity()` requires it. This extra test runtime input is included in the archive reconstruction workspace but is absent from the frozen Linux package manifest.

The focused Linux runner tests are included in the package closure. Rebuilding the frozen 23-file package reproduced its manifest digest, but running the full 29-test suite from that package yielded 28 passes and one error for the missing `PRIOR_RESOURCE_COST.json`. The candidate package therefore needs a separately reviewed identity update before future target execution. The earlier M0/M1 inherited-regression command additionally used graph-v2 files `independent_audit.py`, `tests/test_chapter1_adapter.py`, `tests/test_relief_env.py`, `tests/test_independent_audit.py`, and `tests/test_step_api.py`; these are not inputs to the N2 Linux package manifest.

## Evidence Files

| File | Evidence scope |
|---|---|
| `reports/M0_M1_ENGINEERING_NOTE.md` | Reuse map, engineering gaps, local probe limits |
| `reports/M0_M1_LOCAL_RESULTS.json` | Recorded environment and M0/M1 test counts |
| `reports/N2_PROTOCOL_DRAFT.md` | Proposed future collection and critic-only protocol; draft only |
| `reports/N2_INTERFACE_IMPLEMENTATION_CONTRACT.md` | Engineering interface requirements and open gates |
| `reports/N2_GATE_RECOMMENDATION.md` | Development-only gate recommendation; not run |
| `reports/N2_ENGINEERING_NODE_REPORT.json` | Local synthetic PPO smoke receipt |
| `reports/INDEPENDENT_REVIEW.md` | Independent review of scope, source identities, package, and stopped preflight |
| `reports/N2_LINUX_PREFLIGHT_STOP_SUMMARY_ZH.md` | Public summary of the single failed target preflight |
| `reports/n2-linux-preflight-stop-settlement.json` | Public, sanitized stop counts and transcript digest only |
| `reports/ARCHIVE_REBUILD_VALIDATION.md` | Rebuild, package-gap, and local smoke verification for this archive |

The original local stop report and settlement record remain private execution evidence. Their public copy contains no workstation path, SSH endpoint, key path, authorization text, script, or raw transcript. The public settlement records one connection, zero uploaded files/bytes, zero remote root creations, zero service submissions, and zero research/training/prediction/PPO operations. The original transcript SHA-256 is retained only as an evidence digest; its raw bytes are excluded.

The latest local archive smoke receipt reports 57.329 seconds wall, 54.563 seconds process CPU, and 720 combined transitions/48 updates across the continuous and restored comparison paths. Its runtime and timings belong to the recorded Windows-local environment only; generated checkpoints, rollouts, and exports are excluded.
