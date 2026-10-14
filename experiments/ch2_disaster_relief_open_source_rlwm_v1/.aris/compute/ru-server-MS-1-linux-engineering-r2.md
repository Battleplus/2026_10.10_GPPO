# Provider ledger: ru-server-MS-1, Linux engineering r2

Recorded after the 2026-10-14 bounded run, without changing the executed environment specification or old ledger.

- Provider: direct SSH / systemd user service, CPU0, one thread, CUDA hidden.
- Source: `/home/user1/w1-pilot/rlwm-engineering-20261014/source-r2`.
- Dedicated venv: `/home/user1/w1-pilot/rlwm-engineering-20261014/runtime/venv-r2`.
- Python 3.11.16, read-only shared Torch 2.7.0+cu128 and NumPy 1.26.0; all new pinned dependencies are local to this venv.
- Canonical spec SHA-256: `e3a397648bcecf7f8fa556cf6d20df21b54c82fe6b3c5b7f5fa1076026f60230`.
- Installation phases and pip check: exit 0; build wall 21.7755 seconds.
- Seeded CPU kernel/import witness: pass. Agent-follows-doc argv checked by a fresh Luna reviewer and transported through the parent's authenticated connection.
- Engineering invocation `linux-eng-20261014-02`: pass; 26 tests, 10 engineering optimizer steps, zero formal-study updates or heldout confirmation episodes.
- Final receipt SHA-256: `0449033931a122dbbf7f7cf2ea5298cd7cd326f6515bced9913a20d947cb66f7`.
- Readiness is limited to the documented small engineering configuration. The full study budget is not frozen and no heldout learner evaluation has occurred.

Warm reuse requires an unchanged spec hash and rechecking the relevant runtime identity. A changed spec requires a new environment build and witness. Never treat import success alone as readiness. The upstream declares Torch 2.8.0; this environment is a compatibility runtime, not exact upstream reproduction.

Evidence: `reports/linux-engineering-20261014/`. Run-01 and its first errors remain preserved. Do not resubmit either old run identity. A new pilot must have its own fixed counts, source identity, resource limits, and documented invocation.
