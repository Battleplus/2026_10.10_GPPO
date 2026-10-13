# N2 Linux Acceptance r2 Independent Review

Review date: 2026-10-13

## Decision

The frozen staged package is ready to be considered for one bounded N2 engineering acceptance attempt, conditional on a separate explicit execution decision naming the target. This review does not authorize execution. Use only `E:\Z博士\build\n2-linux-acceptance-r2-os-user-verified` with manifest SHA-256 `C90FA16A70158E77FBF1EF56C35D9E511F4579F8CE926F35B9458963AAF5ACCA`.

Package identity: `n2-local-synthetic-engineering-linux-acceptance-r2`.

## Independent Checks

- The manifest digest matches in the candidate and staged copies.
- All 25 manifest-listed file hashes match in both copies. The staged package contains exactly 26 files: those 25 files and the manifest.
- The mutable candidate directory contains 39 files, including 13 unlisted files. It is not an acceptable staged package root; the runner is expected to reject such extras. The exact staged directory above is the reviewed target.
- The runtime probe obtains the OS account name with `pwd.getpwuid(os.geteuid()).pw_name`; it no longer uses `getpass.getuser()`. The contract test explicitly asserts this source and excludes the former lookup.
- The probe emits structured `name`, `actual`, `expected`, and `passed` checks for host, user, platform, interpreter and runtime versions, CUDA state, thread counts, and post-pin CPU affinity. The report parser verifies the schema, complete unique check names, consistent result values, and overall pass status.
- Ordinary SSH-shell affinity is recorded as caller-provided observation only. The runner records its own pre-pin affinity, verifies the selected CPU is available, applies `sched_setaffinity`, and checks exact affinity in the runtime probe. The focused contract suite passed: 3 tests.

The executor reports 32/32 local engineering tests and a local synthetic smoke with 720 transitions, 48 updates, strict restore equivalence, normal export completion, and an injected-failure receipt. It reports 55.8357 seconds wall time and 53.78125 seconds process CPU. These are executor-provided local results, not target Linux evidence; I did not rerun model work.

## Scope and Limitations

No SSH connection, package transfer, target command, dependency installation, research-data processing, 40-epoch world-model fit, prediction gate, policy comparison, or formal training was performed or authorized in this review. The specific failure from the earlier SSH preflight remains unknown and is not interpreted here.

Before any target attempt, the owner must separately decide and identify the target, use a fresh immutable package/work identity, pass the reviewed manifest digest out of band, and require runtime admission to match the reviewed host and OS-backed user. The manifest remains `prepared_not_authorized_for_execution`; all frozen resource caps and stop conditions remain in force. This acceptance covers engineering behavior only and does not complete N2 research gates or support formal data/training claims.
