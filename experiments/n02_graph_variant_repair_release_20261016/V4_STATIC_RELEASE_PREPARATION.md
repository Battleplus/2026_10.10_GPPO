# Measured Release Preparation

Status: NOT_APPROVED static L1 repair candidate. The copied prior receipt covers only input_admission for the earlier package; it does not measure L1 training costs or this repaired package. No new target-runtime preflight, authorization, formal attempt, training, checkpoint operation, or rollout was performed.

Release: `ch2_disaster_relief_n02_graph_variant_repair_l1_20261016`  
Candidate run ID: `n02-l1-graph-variant-repair-run-20261016-01`  
Protocol: `n02-integration-smoke-v4-100x100`  
Map contract: `relief-grid-100x100-v1`  
Taskbook SHA-256: `4b544e39b5fffa89ef364095341412c807d4d609a11117191b6b981aa51bcf5c`  
Allocation: 2 train / 1 development; all registered data and seven smoke fixtures use the 100x100 map contract.

Static validation passed: Python AST parse for all package Python files; JSON parse for all package JSON files; exact 2 train / 1 development registered scenarios; 100x100 map, 10,000-cell, local-block, and coordinate checks for every registered parent, causal case, and smoke fixture; taskbook, registry, generator, and scenario digest checks; prior measured receipt and evidence role/hash checks; exact registered-data file set; and symlink/bytecode rejection. The prior receipt's stage coverage is input_admission only; this L1 package has no target-runtime preflight or training-cost measurement.

Prior measured receipt: `bc60410eb314e7882b9cf85237d8d3243209f27edb11ce242dc94c6bfe485824`; stage coverage: `['input_admission']`; prior package source identity: `d9b369faa831ce9d92c05c2b131e977ec70ee60a93c2114b8624ad0096226fec`. The real prior evidence is copied and hash-bound without extending its scope.  
Independent review: pending.

`V4_RELEASE_MANIFEST.json` payload identity SHA-256: `3aaf0ddb966edbd64bf9da7cc6998774f30c0370fbf6ae8e1b5e4752eeed063f`  
`V4_RELEASE_MANIFEST.json` file SHA-256: `634631f55f1eebca18309dfbcf4915bb8c1bfab23a525384cecc514e9ff7fde2`  
`V4_RELEASE_SHA256SUMS.txt` SHA-256: `42a1b9b10b564e659fd4afedf255e264e2373b7453a9c54a66e329daa7e5b400`  
`V4_HASH_BUNDLE.json` payload identity SHA-256: `f05eb10cb758d0da2052d3c4b92a581001db0134a634942f8656387f0121d06d`  
`V4_HASH_BUNDLE.json` file SHA-256: `7fe4bbdf6e9390dbcbcaad236f79612108990715b966a27c0214322ea4783bc8`  
Runtime dependency bundle SHA-256: `58485fcd1c42a71daa3360d902b21fbb465dd8d3c6a152fbfdd6544e2b9e5274`  
Candidate request identity SHA-256: `76fa3f23191a46a19efa37f43dad657dfcbaa574822b790d06e92d322404146f` (`authorized=false`, `request_frozen=false`)  
Candidate attempt identity SHA-256: `21a213d2832cfd9fc77c482d4fd75455ee305354d77c16caede427886be9b90f` (`attempt_started=false`)

Reproduce with `python -B "E:\Z博士\development\n02_graph_variant_repair_release_20261016\prepare_measured_release.py"`. The command invokes this static checker only and does not import project modules. Checker SHA-256: `d48927db9e6e068b5a87082cb3cdf892025fbcde28bfd3906e93466b59e6fb5c`.

The static candidate remains NOT_APPROVED. Any future execution must use run ID `n02-l1-graph-variant-repair-run-20261016-01` after independent review and fresh package-external authorization bound to the new static identities. No execution launcher is included or authorized now.
    