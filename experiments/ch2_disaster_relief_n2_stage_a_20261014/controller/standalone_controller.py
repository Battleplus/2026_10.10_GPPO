from __future__ import annotations

import argparse
import json
import math
import pathlib
import posixpath
import shlex
import sys
import time
from collections.abc import Mapping

from exact_record_authorization import validate_authorization
from n2_controller import ControllerConfig, command, run_controller, validate_local


CONFIG_FIELDS = {
    "package_root", "manifest_rel", "package_sha256", "expected_identity",
    "run_identity", "unit", "target_host", "target_user", "connect_host",
    "remote_root", "python", "worker_entry", "worker_args", "ssh_key_file",
    "known_hosts", "evidence_root", "budget", "consumption_root",
}
FAILURE_ARTIFACTS = (
    "managed-first-error.json",
    "managed-worker-first-error.json",
    "managed-worker-receipt.json",
    "managed-supervisor-receipt.json",
    "managed-worker.log",
    "supervisor-phase-protocol.jsonl",
    "budget-ledger.sqlite3",
)


def _reject_constant(_value: str):
    raise ValueError("JSON_NONFINITE_NUMBER_INVALID")


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON_NONFINITE_NUMBER_INVALID")
    return parsed


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def load_json_object(path: pathlib.Path) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            object_pairs_hook=_object_pairs,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("JSON_INPUT_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON_ROOT_MUST_BE_OBJECT")
    return value


def build_config(raw: Mapping[str, object], authorization: Mapping[str, object]) -> ControllerConfig:
    if set(raw) != CONFIG_FIELDS:
        raise ValueError("CONTROLLER_CONFIG_FIELDS_INVALID")
    path_fields = (
        "package_root", "ssh_key_file", "known_hosts", "evidence_root", "consumption_root",
    )
    if any(not isinstance(raw.get(field), str) or not raw[field] for field in path_fields):
        raise ValueError("CONTROLLER_CONFIG_PATH_INVALID")
    string_fields = CONFIG_FIELDS - set(path_fields) - {"budget", "worker_args"}
    if any(not isinstance(raw.get(field), str) or not raw[field] for field in string_fields):
        raise ValueError("CONTROLLER_CONFIG_STRING_INVALID")
    if not isinstance(raw.get("budget"), dict):
        raise ValueError("CONTROLLER_BUDGET_INVALID")
    args = raw.get("worker_args")
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        raise ValueError("CONTROLLER_WORKER_ARGS_INVALID")
    if not isinstance(authorization, Mapping):
        raise ValueError("AUTHORIZATION_RECORD_INVALID")
    base = pathlib.Path(__file__).resolve().parent
    return ControllerConfig(
        package_root=pathlib.Path(raw["package_root"]),
        manifest_rel=raw["manifest_rel"],
        package_sha256=raw["package_sha256"],
        expected_identity=raw["expected_identity"],
        run_identity=raw["run_identity"],
        unit=raw["unit"],
        target_host=raw["target_host"],
        target_user=raw["target_user"],
        connect_host=raw["connect_host"],
        remote_root=raw["remote_root"],
        python=raw["python"],
        worker_entry=raw["worker_entry"],
        worker_args=tuple(args),
        ssh_key_file=pathlib.Path(raw["ssh_key_file"]),
        known_hosts=pathlib.Path(raw["known_hosts"]),
        evidence_root=pathlib.Path(raw["evidence_root"]),
        budget=raw["budget"],
        authorization=authorization,
        consumption_root=pathlib.Path(raw["consumption_root"]),
    )


def paramiko_connector(config: ControllerConfig):
    try:
        import paramiko
    except ImportError as exc:
        raise RuntimeError("PARAMIKO_RUNTIME_UNAVAILABLE") from exc
    client = paramiko.SSHClient()
    client.load_host_keys(str(config.known_hosts))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    def connect(**kwargs):
        try:
            client.connect(
                hostname=kwargs["hostname"],
                username=kwargs["username"],
                key_filename=kwargs["key_filename"],
                allow_agent=False,
                look_for_keys=False,
                timeout=kwargs["timeout"],
                banner_timeout=kwargs["banner_timeout"],
                auth_timeout=kwargs["auth_timeout"],
            )
        except BaseException:
            client.close()
            raise
        return client

    return connect


class _QuietEvidence:
    def write(self, _message: str) -> None:
        pass


def make_settle_failure(config: ControllerConfig):
    def settle_failure(client, unit: str, invocation: str | None,
                       first_error: BaseException, evidence_root: pathlib.Path,
                       deadline: float) -> str:
        del first_error
        if invocation is None:
            return "UNKNOWN_FAILURE_INVOCATION_NOT_STOPPED"
        try:
            _, output = command(
                client,
                _QuietEvidence(),
                label="verify_failed_invocation_before_collection",
                text=(
                    "set -eu\n"
                    f"test \"$(systemctl --user show {shlex.quote(unit)} -p InvocationID --value --no-pager)\" = {shlex.quote(invocation)}\n"
                ),
                timeout=max(1, deadline - time.monotonic()),
                deadline=deadline,
                now=time.monotonic,
            )
            del output
        except BaseException:
            return "UNKNOWN_FAILURE_INVOCATION_VERIFICATION"

        sftp = None
        collected = []
        incomplete = False
        work_path = posixpath.join(config.remote_root, "work")
        try:
            sftp = client.open_sftp()
            get_channel = getattr(sftp, "get_channel", None)
            if get_channel is None:
                return "UNKNOWN_FAILURE_SFTP_DEADLINE_UNAVAILABLE"
            channel = get_channel()
            local_root = evidence_root / "failure-artifacts"
            local_root.mkdir(exist_ok=True)
            for name in FAILURE_ARTIFACTS:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return "UNKNOWN_FAILURE_COLLECTION_DEADLINE"
                remote = posixpath.join(work_path, name)
                channel.settimeout(remaining)
                try:
                    sftp.stat(remote)
                except OSError as exc:
                    if getattr(exc, "errno", None) == 2:
                        continue
                    incomplete = True
                    continue
                try:
                    sftp.get(remote, str(local_root / name))
                except OSError:
                    incomplete = True
                    continue
                if time.monotonic() >= deadline:
                    return "UNKNOWN_FAILURE_COLLECTION_DEADLINE"
                collected.append(name)
        except BaseException:
            return "UNKNOWN_FAILURE_COLLECTION"
        finally:
            if sftp is not None:
                sftp.close()
        if incomplete:
            return "STOPPED_FAILURE_EVIDENCE_INCOMPLETE"
        if collected:
            return "STOPPED_FAILURE_EVIDENCE_COLLECTED"
        return "STOPPED_FAILURE_EVIDENCE_EMPTY"

    return settle_failure


def run_standalone(config_path: pathlib.Path, authorization_path: pathlib.Path,
                   *, connect_factory=None) -> str:
    config_raw = load_json_object(config_path)
    authorization = load_json_object(authorization_path)
    config = build_config(config_raw, authorization)
    validate_authorization(config, authorization)
    validate_local(config)
    connector = connect_factory or paramiko_connector(config)
    return run_controller(
        config,
        connect=connector,
        settle_failure=make_settle_failure(config),
        verify_authorization=lambda record: validate_authorization(config, record),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot N2 managed controller")
    parser.add_argument("--config", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    try:
        invocation = run_standalone(args.config, args.authorization)
    except Exception as exc:
        print("CONTROLLER_FAILED:" + type(exc).__name__, file=sys.stderr)
        return 2
    print("INVOCATION_ID=" + invocation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
