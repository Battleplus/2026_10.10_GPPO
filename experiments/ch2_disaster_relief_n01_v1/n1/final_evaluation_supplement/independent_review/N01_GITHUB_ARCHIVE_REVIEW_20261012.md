# N01 GitHub Archive Candidate Review

Review date: 2026-10-12 (Asia/Shanghai)

## Decision

**Exact assembled candidate: PASS for publication review. Publication: not authorized by this review. Target execution readiness: NOT_READY.** The review is bound to the candidate archive SHA-256 below. It does not authorize training or evaluation and does not claim that the 2,800-episode evaluation was executed.

## Bound Artifacts

- Candidate archive: `received/n01_github_archive_candidate_identity_3667872d.tar.gz`
- Candidate SHA-256: `3910174846bb818fe84b3f1c90266e98ab413ed21aa001f361c733f000bd2da8`
- Candidate size and file count: 13,353,942 bytes; 557 files
- Candidate sidecar: `received/N01_GITHUB_ARCHIVE_CANDIDATE_MANIFEST.json`
- Candidate sidecar SHA-256 at review: `ce297c0f1b166cfb9ab87a4facfcb7d46af2b4d873448f8038856e05866d9c9d`
- Evaluation identity: `ch2-disaster-relief-n01-full-evaluation-r1-20261011`
- Identity SHA-256: `3667872dc04bcabbc6c5bbe77cabf169e8344c5e8cb337376c164a24c5d9bdb6`
- Canonical static plan SHA-256: `84e37c9816ba27aa780d07ddf31b19fe4609977532825f19a8d7976918cfd78d`
- Embedded deployment archive SHA-256: `329c30853c380290d13710236809ab085af85b7bc8f697e300febaaa56c831a1`

## Findings

The candidate archive's actual SHA-256, byte size, and 557 file members match the external candidate manifest. Every member matches its declared path, size, and SHA-256; there are no missing, extra, or mismatched members. The assembled candidate directory on disk matches the archive and manifest.

The embedded deployment archive matches its 540-entry sidecar manifest, with no missing, extra, or mismatched files. The candidate's 540-file `source/` tree matches the deployment archive byte for byte. The identity file hashes to the bound identity SHA-256; all 28 identity source hashes match. The preregistered protocol is present and identity-bound. The scenario manifest covers five conditions with 70 scenarios each; all 350 scenario files match their canonical JSON hashes. All six fixed checkpoint files match the checkpoint manifest and identity.

The candidate index and reports state that the 2,800-episode evaluation was not executed and no results are available. The updated readiness report and artifact index agree that the latest read-only SSH attempts on 2026-10-12 timed out at TCP connect and started no remote command; the 2026-10-11 authentication failure is labeled historical. Target systemd/cgroup state remains unverified and `NOT_READY`. The development report correctly defines the scope as five conditions by 70 parents by eight policies (C0/C1 plus six fixed checkpoints), with the diagnostic episodes excluded.

Archive scans found no Python bytecode, `__pycache__`, `.git`, environment files, private-key extensions, or absolute/traversal paths. The index's stated exclusions are consistent with the assembled candidate. No secrets were found by the filename scan; this review did not inspect the semantic contents of every source file for undisclosed credentials.

At review time, the external candidate manifest still marked `independent_archive_review.status` as `pending`. Bind this report and its binding JSON in the companion manifest before publication. The candidate archive itself remains unchanged. Budget approval is absent and the package budget remains proposed; these facts keep execution unauthorized independently of the archive review.

## Scope Limits

This is a static archive and documentation review. No SSH, remote command, model loading, training, or evaluation was performed. Passing this review allows the exact archive to proceed to publication review; it does not authorize publication or target execution.
