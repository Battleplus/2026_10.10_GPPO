from __future__ import annotations

import getpass
import pathlib
import sys

import paramiko


ROOT = pathlib.Path(__file__).resolve().parent
KEY = pathlib.Path(
    r"C:\Users\ASUS\AppData\Local\Temp\codex-n01-ssh-once-20261011\n01-deploy-once"
)
LOCK = ROOT / "measured-final-deployment-submission.lock"


def main() -> int:
    if LOCK.exists():
        raise FileExistsError("closed-db deployment wrapper already ran; do not resubmit")
    if not KEY.is_file():
        raise FileNotFoundError("validated SSH key path is unavailable")
    with LOCK.open("x", encoding="utf-8") as lock:
        lock.write("closed-db deployment submission reserved\n")

    getpass.getpass = lambda _prompt: ""
    original_connect = paramiko.SSHClient.connect

    def connect_with_key(self, *args, **kwargs):
        kwargs.update(
            password=None,
            key_filename=str(KEY),
            allow_agent=False,
            look_for_keys=False,
        )
        return original_connect(self, *args, **kwargs)

    paramiko.SSHClient.connect = connect_with_key
    sys.path.insert(0, str(ROOT))
    import deploy_measured_final_once

    return deploy_measured_final_once.main()


if __name__ == "__main__":
    raise SystemExit(main())
