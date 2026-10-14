# Independent Engineering Review

**Status:** Complete for the bounded engineering run. This review does not assess algorithm superiority or establish a study result. It is a same-family review and is provisional with respect to model-family independence.

## Run 01

The locally saved `run-01` receipt and artifact index were read and checked. All nine artifact files match both the byte counts and SHA-256 values in `artifact-hashes.json`; the computed SHA-256 of `run-receipt.json` is `26346823777bb416f63f58e707bee65c5893f9850b3ac6cafa1b403b8c6e7d78`, matching the index.

The run stopped at `unittest-26`. The seeded CPU witness passed. The unittest log reports 14 discovered entries, 12 passing tests, and two import errors, so it does not meet the acceptance requirement of 26 tests passing. `test_decision_repeat_adapter` could not import `relief_env` because its legacy `SOURCE_ROOT` points outside the deployed source tree. `test_dreamer_time_mask` failed during import because `torch.utils.tensorboard` could not import the missing `tensorboard` package. These are environment and source-layout blockers; the stop does not establish an algorithm failure. The runner stopped before either smoke or the precision diagnostic, and the receipt records no formal training, heldout confirmation, or six-path study training. No optimizer updates are evidenced by run-01.

The saved systemd receipt confirms CPU 0 affinity, a one-core quota, a 4 GiB memory limit, a 10-minute runtime limit, and no automatic restart. It records 9.3031 seconds wall time and 7.489746 CPU seconds in the service cgroup. The 740,552,704-byte `RUSAGE_CHILDREN` figure is the maximum RSS of one child, not aggregate service memory; systemd cgroup peak memory was unavailable. Accounting excludes SSH, deployment, and environment installation.

The retained failed unit has `ExecMainPID=322261`, `ControlGroup=` empty, and `ActiveState=failed`. The old finalizer's `ExecMainPID == 0` test does not represent current liveness because systemd retains the historical PID. The failed service result itself is expected for this technical stop. The r2 finalizer switches the liveness check to `MainPID == 0` together with `SubState == exited`, while retaining `ExecMainPID` as raw evidence.

## R2 Review

The r2 test-path patch is suitable as a fixture-path portability repair, not a change to the evaluation target, subject to the recorded source-manifest identity check. I compared the original and r2 test copies: their only line difference is `SOURCE_ROOT`. The original test uses that root both in `sys.path` and to derive `FIXTURE_ROOT`, so pointing it at the colocated `vendor/relief_env_v2` fixes the imported package and fixture location. Test assertions and algorithm sources are unchanged, and the patch is present only in the separate r2 runtime copy; the original source test remains untouched.

The r2 environment specification pins TensorBoard and its import dependencies, and its CPU witness explicitly imports `torch.utils.tensorboard`. The r2 launcher and finalizer are copied into the isolated release. The saved deployment receipt and node report record 313 manifest-listed files plus the manifest itself, 314 deployment files total, with no mismatches; the run source check covers 224 files. The setup receipt records successful installation and `pip check` returning zero. I reviewed these saved records but did not open a separate server session.

I reviewed the exact argv in the r2 acceptance document. It targets the deployed `source-r2` launcher, `source-r2` repository and new `run-02` output directory, with the separate `runtime/venv-r2`, unit `rlwm-engineering-20261014-02`, run id `linux-eng-20261014-02`, and source identity `c8b705e+linux-engineering-r2`. My pre-run decision was GO for that single invocation. The saved agent-follows-doc result matches the reviewed argv; run-02 is reviewed below.

One nonblocking documentation defect remains in the r2 acceptance document: its relative environment-spec link resolves to the nonexistent `reports/linux_execution/environment-spec.json`. The r2 specification is `linux_execution_r2/environment-spec.json`; the link can be corrected without changing the invocation or installed environment.

## Run 02

Run-02 passed all documented engineering stages. All 26 tests passed. The upstream CartPole smoke completed three CPU updates, changed the model parameter hash, and restored the matching checkpoint hash. This remains a smoke, not an exact upstream reproduction: the runtime used Torch 2.7.0+cu128 while the declared upstream version is 2.8.0.

The civilian smoke completed three updates on the train-split scenario `relief-n2-train-carrier_competition-00`, with 128 adapter steps, 120 physical minutes, and zero illegal actions. It performed no formal policy updates or evaluations. In the last two of its three imagined updates, only COMMIT was legal and the actor/policy loss was zero. The short smoke therefore verifies that the training path executes, but does not show a usable learned policy; this mask behavior should be monitored in any separately authorized real pilot.

The CPU fixed-batch precision diagnostic passed two finite FP16 updates and two finite FP32 updates. The earlier Windows FP16 NaN is not reproduced by this Linux diagnostic. Neither result tests Torch 2.8, and neither is a formal update or confirmation evaluation.

All 17 indexed run-02 files, including both checkpoints, match their recorded byte counts and SHA-256 values. The run-receipt hash is `0449033931a122dbbf7f7cf2ea5298cd7cd326f6515bced9913a20d947cb66f7`. Before cleanup, the saved invocation receipt records the loaded unit at `MainPID=0`, `SubState=exited`, and `Result=success`; the historical `ExecMainPID=324825` remains nonzero. The service exit and explicit cleanup both returned zero. A later read-only status query reports `not-found/inactive/dead` after cleanup; that state confirms there is no active main process, but is not evidence of successful execution. Success is established by the retained pre-cleanup invocation receipt. Resource evidence is bounded to the service: 35.0467 seconds wall time, 30.636219 cgroup CPU seconds, and 829,440,000 bytes maximum single-child RSS. The 4 GiB memory limit and CPU 0/one-core quota were confirmed; cgroup peak memory was unavailable.

Run-02 records exactly ten engineering optimizer steps: three upstream smoke, three civilian smoke, two FP16 diagnostic, and two FP32 diagnostic. It records no formal training, heldout confirmation, or six-path study training. This is a Linux engineering compatibility pass under Torch 2.7, not evidence of policy quality or algorithm superiority.

## Evidence Boundary

I directly reviewed the local saved source, acceptance documents, run-01 and run-02 logs, receipts, artifact hashes, final service readback, and node report. The parent held the SSH connection and performed remote deployment and execution; I did not open a separate server session. The run-02 artifact byte/hash verification was performed locally against its saved index. The final readback occurred after explicit cleanup and is not used to establish service success.

## Bound Hashes

- Run-01 receipt: `26346823777bb416f63f58e707bee65c5893f9850b3ac6cafa1b403b8c6e7d78`
- Run-01 artifact index: `0f2a8b21ab341ae3c9eadd27ff3397016e00660fbce075afe5277a60e31ec664`
- Run-01 source hash index: `42856f33973b8700f9025eab77cd9faa10de07d24968add52c3261f7b91becfd`
- Run-01 agent-follows-doc result: `1002baed9fa77ce45af1e72a5f79f7ef3ef5a92629a7c5e03db34f9fc3261516`
- R2 acceptance document: `fa6b371a5bd0bc03a0b431ffa1a728092a982620157e30b43c84a83b0a20ecab`
- R2 test-path patch: `3c529cddb7d87ef19ca95bed2dc8e21c09f653c5e796a2710666f37d8d4aff55`
- R2 environment-spec file: `d177df84752887d4552272acd5bcfdf098b99e804f21f72a0de44c03ebb5a1c2`
- R2 CPU witness: `9316e1a87a09338566c2a38b8491c462345f8340229fc1306f0d42a832148ff4`
- R2 finalizer: `71e80b9feb5e9e99120e4d3e3afccdacf8da317c6d3a96b22d134a7198814c66`
- R2 launcher: `a088929e95748e2faea755cf4e3408fd249f033b6493fd9ccad6741fb7b234dc`
- R2 release-manifest file: `62553282bd69a851c83f3db3a3463c9f64e70323dfb93b6820a3c6ea8f644340`
- R2 test copy: `ff70464866c4b6a26226d0afd24eba3190f46dbb3e43282300e25df2a8db7734`
- Run-02 receipt: `0449033931a122dbbf7f7cf2ea5298cd7cd326f6515bced9913a20d947cb66f7`
- Run-02 artifact index: `4359f166af9024d9149a3f7bf1d9c2f75a9fc25d69d0aaeceb89ef0016322915`
- Run-02 source hash index: `ce63e52fcf7bd796f51dcf04c92af83eb36e386991e34e3a7e29679305cbd3ad`
- Run-02 agent-follows-doc result: `8457dc64b136a14639828169499bbe8e411eb8176312bd330e504d59d05c81cb`
- R2 setup status: `51faccd18ba5554c8f6098461f943fd7fa461ae305a522fdd22abf9e3a061e8f`
- R2 deployment receipt: `e649bfc801bd55fcbc863f0876fd318241aab9e056bb2102dc86fbf96779fdf8`
- Primary byte verification record: `39bb5fbb0e42c7a935127bfe75b4be8cb5064d77bfa4bd9d35a75dd8875a309a`
- Final service readback: `b38ef9b621f2315c445d96d413cd469d7297541d6703fd1c86bdca86bd283346`
- Linux node report: `24fd77a0c1e230b80da7d2ce5ad7d79f8fff41c4b64ccbb7c5e35a30e2cc09fd`

All nine run-01 artifacts and all 17 run-02 artifacts were recomputed locally; bytes and SHA-256 values matched their respective indexes. Exact records are in `review.json`.
