# N1 development and engineering acceptance report

N1 package identity: `ch2-disaster-relief-n01-engineering-r2-20261011`. Runtime admission and the 100-sample engineering smoke completed on the target runtime. The 100-sample reviewer replay verified 100 trajectories, 100 audits, and 100 episode rows against the checkpoint barrier. The sample used fixed checkpoint `L1-8201` and is diagnostic evidence only; it does not cover the full matrix of five conditions and eight policies (C0/C1 plus three L0 and three L1 checkpoints).

The final 2,800 episodes were not executed. The scope is five conditions x 70 parents x eight policies (C0/C1 plus three L0 and three L1 checkpoints), with 100 diagnostic episodes excluded. External-commitment parents retain the additional commitment tasks: at 8x12 they have 14 tasks and at 12x18 they have 21; the other 60 parents have 12 and 18 tasks. No tasks were deleted or merged. N2 and N3 were not started.

Measured known resource use, including carry-forward, admission, smoke, and all failure probes, is 173.0790520354 wall seconds and 124.840999441 CPU seconds. The independent evaluation freeze scales the directly measured 100-sample cost conservatively by 28, yielding 1,511.543 wall and 1,373.107 CPU seconds before adding known costs. This exceeds both the engineering and whole-pilot caps, so the 2,800 run was stopped before launch.

Failure probes: disconnect v4 completed after SSH client termination and saved a checkpoint-bound artifact; RuntimeMaxSec produced a systemd timeout; guardian overrun killed the child and retained its failed receipt. Earlier disconnect attempts and the systemd authorization denial remain recorded as failed evidence and charged costs.

Known limitation: the guardian-overrun original receipt contains the text `engineering_smoke wall 107.745>108s`, which is numerically inconsistent. The original receipt is preserved unchanged; see `GUARDIAN_OVERRUN_CORRECTION_NOTE.md`. This report claims only that the guardian issued a wall-overrun kill, not a precise corrected threshold.

Editorial clarification for this GitHub supplement copy: the earlier draft described the scope as five methods and eight seeds. The bound evaluation plan instead specifies five conditions x 70 parents x eight policies (C0/C1 and six fixed checkpoints). The original workspace report remains preserved; this copy corrects that scope description without changing run status or evidence.
