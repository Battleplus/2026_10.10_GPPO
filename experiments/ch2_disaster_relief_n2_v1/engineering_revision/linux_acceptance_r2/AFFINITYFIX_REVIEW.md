# N2 r2 Affinity Capture Revision: Independent Review

Review date: 2026-10-13

The reviewed candidate is r2_once_launcher_affinityfix.py with SHA-256 6905455158F576785875697C0A26C7717FA01DBF0414119D839763AF8CB6DE6E.

The diff from the prior reviewed launcher is limited to parsing the ordinary SSH shell affinity from the existing preflight output, recording it, and passing it to the frozen runner in that same transport. CPU ranges are expanded before passing the comma-separated list. Missing or malformed output stops before transfer and service submission. The parser does not require the ordinary SSH shell to have affinity {0}; CPU 0 is enforced later by the systemd unit and runner.

Static review confirmed one SSH connect call, one systemd-run submission site, unchanged package manifest pin, run identity and budget limits, and no retry or reconnect path. The exact candidate was subsequently used for the one authorized connection attempt, which stopped before upload because the server localized the taskset label and the parser did not recognize it. This review does not authorize a retry.
