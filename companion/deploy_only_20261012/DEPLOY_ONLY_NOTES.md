# Deploy-only preparation

Run `python prepare_deploy_only.py` from this directory to validate the frozen release, build the release archive, execute the generated remote Python entry against local systemctl/evaluator substitutes, and write `PREPARATION_REPORT.json`. This command does not connect to a server. Do not pass `--execute` during local preparation.

The optional SSH path builds an argv list for `subprocess.run` without `shell=True`. It sends `python3 -c ` followed by `shlex.quote(code)` as the SSH remote command, with the archive on stdin. The remote entry verifies all 560 release file hashes, runs prior-cost and static dry-runs, atomically publishes the package, installs and reads back the inactive user unit, and never starts the unit or invokes admission/formal evaluation.

The local substitute executes the same generated remote entry for both a successful static acceptance and a forced evaluator-child failure. The failure case checks that the original child return code, stdout, and stderr remain in diagnostics and that staging is retained.

`expanded_dry_run_plan.json` is the full 2800-key plan produced by the frozen evaluator's static dry-run. Its canonical plan SHA256 is `1c1563508730ed6b2cf63e9a4a3aec39e77401aecb17d920af883967d1e390e8`; this is distinct from the frozen reader JSON's own plan SHA256 `7e5334cd8c9691df59a63501e5ed8bbb8ad31e466ecffdb535ae45bed832fb45`. The static dry-run deserializes six checkpoint payloads with strict model loading disabled and performs no model forward. The local substitute also verifies a self-consistent plan is rejected when its expected expanded-plan SHA is changed.
