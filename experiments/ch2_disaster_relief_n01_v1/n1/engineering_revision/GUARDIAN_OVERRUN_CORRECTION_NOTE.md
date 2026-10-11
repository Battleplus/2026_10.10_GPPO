# Guardian overrun correction note

The original probe evidence is immutable and retained under `received/acceptance_probe/probe-work/guardians/05-engineering_smoke.json`.

Its `outer_guardian_kill_reason` is `engineering_smoke wall 107.745>108s`. The left-hand value is below the displayed threshold, so this text cannot be used as a precise numerical threshold claim. The same receipt records `status: failed`, a non-null outer guardian error, child termination, and a charged wall time of 3.2708789743 seconds. The delivery conclusion is therefore limited to: the guardian terminated the bounded child on its wall-overrun path and retained a failed receipt. The contradictory numeric string is flagged as unresolved; it is not rewritten or reinterpreted.
