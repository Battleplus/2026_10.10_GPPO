from __future__ import annotations

import datetime
import pathlib
from collections.abc import Mapping

import n2_controller
from n2_controller import ControllerConfig, canonical_sha256, controller_bundle_sha256, sha256


AUTHORIZATION_METADATA = {"authorization_id", "approved_at", "approved_by"}


def standalone_source_sha256() -> str:
    root = pathlib.Path(__file__).resolve().parent
    sources = {
        name: sha256(root / name)
        for name in ("standalone_controller.py", "exact_record_authorization.py")
    }
    return canonical_sha256(sources)


def expected_authorization(config: ControllerConfig) -> dict[str, object]:
    return {
        "approval_status": "APPROVED",
        "one_time_execution": True,
        "identity": config.expected_identity,
        "run_identity": config.run_identity,
        "target_host": config.target_host,
        "target_user": config.target_user,
        "connect_host": config.connect_host,
        "package_sha256": config.package_sha256.upper(),
        "systemd_unit": config.unit,
        "controller_sha256": sha256(pathlib.Path(n2_controller.__file__).resolve()),
        "controller_bundle_sha256": controller_bundle_sha256(),
        "standalone_source_sha256": standalone_source_sha256(),
        "budget_sha256": canonical_sha256(config.budget),
        "worker_entry": config.worker_entry,
        "worker_args": list(config.worker_args),
        "remote_root": config.remote_root,
        "consumption_root": str(config.consumption_root.resolve()),
    }


def validate_authorization(config: ControllerConfig, record: Mapping[str, object]) -> bool:
    if config.budget.get("status") != "APPROVED":
        raise ValueError("BUDGET_NOT_APPROVED")
    expected = expected_authorization(config)
    if set(record) != set(expected) | AUTHORIZATION_METADATA:
        raise ValueError("AUTHORIZATION_FIELDS_INVALID")
    for key, wanted in expected.items():
        observed = record.get(key)
        if type(observed) is not type(wanted) or observed != wanted:
            raise ValueError("AUTHORIZATION_MISMATCH:" + key)
    for key in AUTHORIZATION_METADATA:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("AUTHORIZATION_METADATA_INVALID:" + key)
    try:
        approved_at = datetime.datetime.fromisoformat(
            str(record["approved_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID") from exc
    if approved_at.tzinfo is None or approved_at.utcoffset() is None:
        raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID")
    return True
