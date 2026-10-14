from __future__ import annotations

import argparse
import ctypes
import os
import signal
import sys
from pathlib import Path

from managed_runtime import run_worker_config


class ManagedWorkerStop(BaseException):
    pass


def _parent_death_guard(expected_parent: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_PDEATHSIG_FAILED")
    if os.getppid() != expected_parent:
        raise RuntimeError("SUPERVISOR_DIED_BEFORE_WORKER_GUARD")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervisor-pid", type=int, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    _parent_death_guard(args.supervisor_pid)

    def stop(signum, _frame):
        raise ManagedWorkerStop("SUPERVISOR_STOP_SIGNAL:" + str(signum))

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    return run_worker_config(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
