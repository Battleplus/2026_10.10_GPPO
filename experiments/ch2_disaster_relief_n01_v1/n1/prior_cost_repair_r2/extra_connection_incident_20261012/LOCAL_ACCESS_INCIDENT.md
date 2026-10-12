# Local Access Incident Record

Date: 2026-10-12 (client date; command timestamps not captured)

This record documents local actions after the one-time r2 deployment access was stopped. It is outside the frozen package and does not authorize or represent a deployment or evaluation run.

## Scope

- The parent task instructed that no further remote operation was allowed.
- No SCP, remote staging query, deployment, dry-run, systemd command, authorization, token, run creation, or evaluation was performed after that instruction.
- The remote target was not contacted by the commands recorded below.

## Local commands and observations

1. Local process and socket readback was run through WSL:

   `ps -p 718 -o pid=,ppid=,args=`

   Output identified PID 718 as the ControlMaster created by this task:

   `718 702 ssh -M -S /tmp/codex-n01-r2-control2 -fnNT -i /tmp/codex-n01-r2-key-20261012 -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 user1@172.17.27.173`

   `stat` identified `/tmp/codex-n01-r2-control2` as a local socket with mode 600. A local `ssh -S ... -O check` reported `Master running (pid=718)`. The command's exit-status capture was malformed by the WSL/PowerShell wrapper and is therefore recorded as unknown; the check text is the authoritative observation.

2. Local cleanup was run:

   `kill -TERM 718`

   The follow-up checked PID 718 and the socket. The first wrapper output did not preserve the shell variables correctly and reported `master_process_gone=no socket_gone=no`; this was not treated as proof of survival.

3. A second local readback ran:

   `ps -p 718 -o pid=,ppid=,stat=,args=`

   `stat -c ... /tmp/codex-n01-r2-control2`

   No process row was returned and `stat` reported `cannot statx '/tmp/codex-n01-r2-control2'`. This confirms the local process and socket were gone. No remote command was sent by these cleanup checks.

## Result

The task-created local ControlMaster was identified and terminated. No remote state is claimed. The r2 package remains unverified and undeployed from this task's evidence; no static dry-run or service readback is claimed.
