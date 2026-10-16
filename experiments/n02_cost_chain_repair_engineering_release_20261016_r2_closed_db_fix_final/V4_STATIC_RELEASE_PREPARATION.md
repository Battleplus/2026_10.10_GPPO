# Measured Release Preparation

Status: measured engineering candidate only. The target runtime completed one bounded input_admission cost measurement and committed a single-stage measured receipt. No request was formally authorized or frozen, and no formal attempt, training, checkpoint operation, or rollout was started. The measurement is engineering evidence only and does not claim seven-stage runtime coverage.

Release: `ch2_disaster_relief_n02_formal_auth_binding_v5`  
Protocol: `n02-integration-smoke-v4-100x100`  
Map contract: `relief-grid-100x100-v1`  
Taskbook SHA-256: `4b544e39b5fffa89ef364095341412c807d4d609a11117191b6b981aa51bcf5c`  
Allocation: 2 train / 1 development; all registered data and seven smoke fixtures use the 100x100 map contract.

Static validation passed: Python AST parse for all package Python files; JSON parse for all package JSON files; exact 2 train / 1 development registered scenarios; 100x100 map, 10,000-cell, local-block, and coordinate checks for every registered parent, causal case, and smoke fixture; taskbook, registry, generator, and scenario digest checks; measured resource-cost receipt and evidence role/hash checks; exact registered-data file set; and symlink/bytecode rejection. Target runtime preflight and one bounded input_admission measurement passed; formal authorization remains external and not frozen.

Measured receipt: `bc60410eb314e7882b9cf85237d8d3243209f27edb11ce242dc94c6bfe485824`; stage coverage: `['input_admission']`; source identity: `d9b369faa831ce9d92c05c2b131e977ec70ee60a93c2114b8624ad0096226fec`. The measurement unit and evidence are copied into the package and hash-bound; no optimizer step, research-data training episode, formal attempt, or checkpoint was used.  
Independent review: pending.

`V4_RELEASE_MANIFEST.json` payload identity SHA-256: `27713671439cd34bc5100fb78025c0888ccaa5a678e90d44c1301476c64fce43`  
`V4_RELEASE_MANIFEST.json` file SHA-256: `5f4912417236e5819870c230451b634945a3a163132e10f716c20d97116fe0d4`  
`V4_RELEASE_SHA256SUMS.txt` SHA-256: `b680a7f4868579e5a2b1cd3904f6aff9214394b5c5b02f47568a151cfd574f84`  
`V4_HASH_BUNDLE.json` payload identity SHA-256: `74dacac7b13fda848630c4f4ec5045a27d16675d58a5570d95bc2933d519825d`  
`V4_HASH_BUNDLE.json` file SHA-256: `598a7035985d8f3b3f6f66f554ce5932d5f4824682866594fd4501fa0a045faa`  
Runtime dependency bundle SHA-256: `7039f1d71f0ba4f4b7a132c844795bb4d980ff76819cb7f80f5485ea22e74f7d`  
Candidate request identity SHA-256: `928428d9daab671fb1703c528370918387b1aaad9e16f67a2c9105074e8feb71` (`authorized=false`, `request_frozen=false`)  
Candidate attempt identity SHA-256: `070e24274b7204f41583596b511734a889240c945df049dd3e28186da7508b2d` (`attempt_started=false`)

Reproduce with `python -B "E:\Z博士\development\n02_cost_chain_repair_engineering_release_20261016_r2_closed_db_fix_final\prepare_measured_release.py"`. The command invokes this static checker only and does not import project modules. Checker SHA-256: `db42c95437c1345b7ac76984bd9156cc7e5e07dbcb5c985640f08e2abe5e593a`.

Remaining gates: independent review of this measured candidate, package-external formal authorization bound to these new identities, real-data and deployed-runtime critic validation, and the one formal pipeline execution. The static candidate sidecars remain unauthorized and unfrozen.
    