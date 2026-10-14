# N2 Linux Acceptance r2: Preflight Stop

Status: stopped before package transfer or acceptance submission.

The single authorized SSH connection authenticated to ru-server-MS-1 as user1. The remote identity, interpreter path, unique remote-root absence, and expected-unit absence checks passed. The preflight then ran taskset -pc $$ successfully, but the server returned its affinity label in Chinese. The launcher revision only recognized the English label and stopped with SSH_SHELL_AFFINITY_NOT_REPORTED.

No package files were uploaded, no remote run directory was created, no systemd-run command was submitted, and no invocation ID was created. The expected unit was absent during preflight. No engineering update, unit test, smoke, export, or model/research stage started. The runner therefore produced no resource receipt and the acceptance caps were not measured.

The attempt used one SSH connection, zero reconnects, and zero systemd submissions. The stop has consumed that one-shot authorization; this report does not authorize retry or resubmission. The raw transport transcript remains in this private local evidence directory and is excluded from the GitHub archive.
