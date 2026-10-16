# Static Release Preparation

Status: v4 static candidate only. No target runtime was measured, no request was authorized or frozen, and no attempt, server submission, training, checkpoint operation, or rollout was started. One local synthetic tensor-only model forward and autograd probe exercised the actual G-WM critic modules; it is engineering evidence only, not research-data or runtime validation.

Release: `ch2_disaster_relief_n02_formal_auth_binding_v5`  
Protocol: `n02-integration-smoke-v4-100x100`  
Map contract: `relief-grid-100x100-v1`  
Taskbook SHA-256: `4b544e39b5fffa89ef364095341412c807d4d609a11117191b6b981aa51bcf5c`  
Allocation: 2 train / 1 development; all registered data and seven smoke fixtures use the 100x100 map contract.

Static validation passed: Python AST parse for all package Python files; JSON parse for all package JSON files; exact 2 train / 1 development registered scenarios; 100x100 map, 10,000-cell, local-block, and coordinate checks for every registered parent, causal case, and smoke fixture; taskbook, registry, generator, and scenario digest checks; exact registered-data file set; and symlink/bytecode rejection. The registry remains `prepared_static_not_preflighted`; target runtime remains `not_measured`.

Previously recorded local synthetic contract tests: 4 passed. The focused local synthetic critic interface test also passed (1 test) on CPU PyTorch. It built a 100x100 public input and complete action proposals from the v4 synthetic scenario generator, then exercised the actual graph policy, world model, prediction cache, G-WM policy, and auxiliary critic. It checked paired actor initialization, candidate-key alignment, the WM-to-value path, and finite nonzero auxiliary value-loss gradients while actor action heads and the frozen WM received no gradients. Fixed adapter weights were set directly to expose the path; no optimizer step, research data, training episode, or checkpoint was used. Target-runtime critic interface validation remains `not_run`; this synthetic probe says nothing about learned adapter weights or deployed runtime behavior.  
Independent review: pending.

`V4_RELEASE_MANIFEST.json` payload identity SHA-256: `a2b71d1b08b0e55ec38bce595c5a1fb9068340f277d734ebaec0048341e3a46e`  
`V4_RELEASE_MANIFEST.json` file SHA-256: `d505881675d9146d2fc5b909fb55543ce4aca7e5cc6642d6a63fe1a575a23197`  
`V4_RELEASE_SHA256SUMS.txt` SHA-256: `d97bcca7c1a902fb1b68ab9417531c18330dfd7311ced0ad59a70fff1736b98b`  
`V4_HASH_BUNDLE.json` payload identity SHA-256: `394abb2255db7bc28fd98ef149e7131fe26173589affe37485ad61df5eec9ba9`  
`V4_HASH_BUNDLE.json` file SHA-256: `5cba6f801db89bc59cd933e11031f85cd1fdd55055a21660fe56a33f7d6c7bd5`  
Runtime dependency bundle SHA-256: `42ed1d0f066a8eceb32842d2299dfc755bc69143051b4bab134c983b39905b01`  
Candidate request identity SHA-256: `9722b65a413e2b8efda51c0f56e4df45c64750c1482a92dbe8ed5760feff6361` (`authorized=false`, `request_frozen=false`)  
Candidate attempt identity SHA-256: `63d15c195ba769c185cb7bedc98759b402c8c4f928907cbf646fe0b73d16a678` (`attempt_started=false`)

Reproduce with `python -B "E:\Z博士\development\n02_cost_chain_repair_engineering_release_20261016\prepare_static_release.py"`. The command invokes this static checker only and does not import project modules. Checker SHA-256: `0390749a6b2f00995f7ed0a41dd3a6d4e26b32d6e264e55368d4ff44f773ef10`.

Remaining gates: independent review of this v4 candidate, target-runtime inventory and bounded preflight measurement, real-data and deployed-runtime critic validation, measured resource-cost reconciliation, and a new separately authorized Request before any formal pipeline execution. No v3 review or identity is inherited by this release.
