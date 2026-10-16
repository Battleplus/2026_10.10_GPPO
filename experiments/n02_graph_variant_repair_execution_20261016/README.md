# L1 Execution Helpers

These helpers target the frozen CPU L1 release at `../n02_graph_variant_repair_release_20261016`. They keep local deployment and run evidence in this execution directory.

The release is `ch2_disaster_relief_n02_graph_variant_repair_l1_20261016`. Its manifest, bundle, request, and attempt payload identities are, respectively:

- Manifest: `3aaf0ddb966edbd64bf9da7cc6998774f30c0370fbf6ae8e1b5e4752eeed063f`
- Hash bundle: `f05eb10cb758d0da2052d3c4b92a581001db0134a634942f8656387f0121d06d`
- Candidate request: `76fa3f23191a46a19efa37f43dad657dfcbaa574822b790d06e92d322404146f`
- Candidate attempt: `21a213d2832cfd9fc77c482d4fd75455ee305354d77c16caede427886be9b90f`

Run `deploy_measured_final_once.py` first to publish the immutable package and perform the CPU-only target preflight under `n02-l1-graph-variant-repair-preflight-20261016-01`. The formal helper uses run ID `n02-l1-graph-variant-repair-run-20261016-01`; invoking it creates the package-external one-time authorization and submits the formal run. Invoke that second stage only after independent review passes and the run is explicitly authorized.

The formal budget remains 1,800 wall seconds, 900 CPU seconds, and 4 GiB RSS. The carried-forward measurement evidence covers only the earlier `input_admission` stage; it is not an L1 training-cost measurement.

The scripts were adapted from the prior release helpers `deploy_measured_final_once.py` (SHA-256 `ff10e93905caf0f98b39eca06ebcd8ea9f33d0bac33423484aaf7f58af5eef26`) and `formal_submit_measured_final_once.py` (SHA-256 `26fd08909ec4fd72f2cd93a2025d04814072dfaacec8692320acff456f813d73`).
