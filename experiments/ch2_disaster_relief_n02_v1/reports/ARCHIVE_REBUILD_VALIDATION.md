# Archive Rebuild Validation

Date: 2026-10-13

The public `development/` tree was copied into an isolated workspace with the documented repository layout. The N2 engineering suite completed 29 tests successfully in 67.728 seconds using Python 3.14.4, PyTorch 2.13.0+cpu, and NumPy 2.5.0. The workspace included `development/ch2_disaster_relief_graph_v2/PRIOR_RESOURCE_COST.json` (SHA-256 `B577B88138699DCEFC8286314B64D0C41D7278F36ED3DB38ECCDAE962A5ED263`), a source-identity runtime input not listed in the Linux package manifest.

The package builder staged 23 manifest-listed files and reproduced the revised archive manifest digest `4BBA81400B575F6D6C928DE2D6FB4CC7AFB5136DB993BD29A24A1793B9285051`. Running the same 29-test suite inside that exact package completed 28 tests and errored in `test_real_rollout_gae_update_checkpoint_restore_and_next_round_match`: `ppo_trainer.source_identity()` requires the absent `PRIOR_RESOURCE_COST.json`. The frozen Linux candidate is therefore not test-complete. The public archive records this gap; the original staged package and its historical digest evidence were not changed.

The synthetic PPO smoke was rerun from the reconstructed workspace into an isolated temporary output directory. It reported 720 combined transitions, 48 combined optimizer updates, 480 transitions and 32 updates per path, and strict restore equivalence. Measured time was 57.328843 seconds wall and 54.5625 seconds process CPU. The sanitized public receipt SHA-256 is `6F9A04CEB1B20ECCCAD520B62FCC9D8A3795DFED4E60EFA1C02877382FC94E4D`. Generated checkpoints, rollouts, exports, and the raw receipt with local paths are excluded.

No code in the original workspace, frozen staged package, private SSH evidence, or remote target was changed during this archive validation. No SSH retry, package upload, systemd submission, research collection, formal model training, or prediction gate was performed.
