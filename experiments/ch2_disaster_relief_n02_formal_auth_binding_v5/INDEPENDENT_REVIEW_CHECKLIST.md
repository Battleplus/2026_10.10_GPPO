# v5 Independent Review Checklist

This is an executor-provided checklist for the separate review context. It is
not an independent approval.

## Identity and source

- Confirm the 46 package files match `V4_RELEASE_MANIFEST.json` and
  `V4_HASH_BUNDLE.json`.
- Confirm the four candidate digests in `FORMAL_AUTHORIZATION_CONTRACT.json`
  match the sidecars and `V5_RELEASE_INDEX.json`.
- Confirm no symlink, `__pycache__`, `.pyc`, or `.pyo` exists under `package/`.
- Confirm the v4 source tree and its evidence were not modified.

## Authorization repair

- Read `package/civilian/execution_gate.py` and verify that
  `load_release_binding()` accepts only the static candidate state.
- Verify that `validate_authorization_document()` requires the external
  `formal_upgrade` schema and exact candidate manifest, hash, Request, and
  Attempt digests.
- Verify formal scope and every budget field are compared in the upgrade,
  request, and top-level authorization.
- Verify the validator rejects changed hashes, scope, budget, or candidate
  flags before systemd submission.
- Re-run `package/tests/test_formal_auth_binding.py`; expected result is five
  passing tests.

## Boundary

- Treat the local tests as contract tests only; they do not establish target
  Linux runtime compatibility, server publication, preflight, or training.
- Do not create a formal authorization or token from this candidate.
- Any server action requires a separately approved deployment and preflight
  operation after this review.
