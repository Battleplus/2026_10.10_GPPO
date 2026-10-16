# Graph Variant Repair Candidate

Status: review candidate only. The patch has not been applied to a package or deployed. No training, policy forward pass, or checkpoint restoration was performed.

The patch applies to `package/civilian/n2_stage_pipeline.py` with baseline SHA-256 `5063b540d72ad5df145089e6a890c2db0bd72c939bc58f6e0c5906363cb91ebd`. It changes the two graph-policy training constructors from L0 to L1, updates the paired-initialization metadata, and reconstructs L1 for strict development checkpoint loading. The training and reconstruction architectures therefore use the same variant and seed.

This candidate does not change `acceptance_harness.py`, `driver.py`, or the synthetic critic test. It does not modify any formal evidence or release package.

Checks: `git apply --check` passed against the baseline package. Two in-memory `build_policy("L1", 8201)` constructions both contained `literal_attention` and `task_update`; all 43 state entries matched exactly. These checks did not run a policy forward pass or load a checkpoint.
