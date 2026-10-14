# N2 Integration Smoke v1 Handoff

Status: initial archival snapshot; implementation and target-runtime measurement are in progress.

This package is a new, independent development line for the user task book in `TASKBOOK.md`. It has not been deployed, trained, or authorized for a formal smoke run. No experiment identity, authorization, acceptance receipt, or server result has been created.

## Scope and boundaries

- All trajectory collection, counterfactual branching, world-model training, graph PPO training, and evaluation must run on `ru-server-MS-1`.
- Local work is limited to source inspection/development, static checks, package planning, and reading returned evidence. No local training, model forward pass, synthetic replacement result, SSH connection, service submission, or authorization reuse is permitted.
- The required local development root is `E:/Z博士/development/ch2_disaster_relief_n02_integration_smoke_v1/`.
- Existing N1, N2 v1, graph v2, r2 acceptance, and archived evidence are read-only inputs. This version must not overwrite them.
- Old military data/checkpoints and old world-model weights are excluded.

## Current progress

- The complete user task book was read from the supplied attachment and is being copied verbatim to `TASKBOOK.md`.
- Source inventory has been checked against `development/ch2_disaster_relief_graph_v2/`, `development/ch2_disaster_relief_n2_v1/engineering/`, and the N1 feasibility findings. The static action/time/reward audit is complete; target-runtime measurement, dynamic snapshot implementation, and new-package acceptance remain open.
- The configured archive destination is `https://github.com/Battleplus/2026_10.10_GPPO`. The initial snapshot uses the isolated worktree `E:/Z博士/.codex-tmp/n2-integration-archive-20261014` on branch `archive/ch2-n02-integration-smoke-v1-20261014`, created from the verified remote `origin/main` at `4c1ffe1e7832e2b3570d754a7db0e7462e432cb4`. The unrelated N1 local ahead commit and untracked files in the release checkout were not included.
- The task-book SHA-256 is `347aef850c3a4ebcb6da37e82ac871eb83a6054089e4e0953adebec496fdc2a3`.
- The configured target-runtime Python path, service handshake, complete submission wrapper, engineering measurements, identity, authorization, and final acceptance remain unverified.

## Current stop point

No server connection or workload has been started. The next gates are: produce an executable static package plan; review the complete structured submission command flow offline; then prepare a bounded target-runtime engineering measurement plan. Freeze a new Request/identity only after those measurements and the required engineering acceptance are complete.
