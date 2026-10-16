"""Atomic synthetic-run export and first-error receipts for engineering tests."""

from __future__ import annotations

import json
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_records_atomically(
    path: str | Path,
    records: Iterable[Any],
    *,
    run_identity: dict[str, Any],
    last_completed_update: int,
    checkpoint_path: str | Path | None,
    serializer: Callable[[Any], str] | None = None,
) -> dict[str, Any]:
    """Publish only a complete artifact and retain an explicit first-error receipt."""
    destination = Path(path)
    failure_path = destination.with_suffix(destination.suffix + ".failure.json")
    serialize = serializer or (lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".pending", dir=destination.parent)
    temporary = Path(temp_name)
    count = 0
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{\"status\":\"complete\",\"run_identity\":")
            handle.write(json.dumps(run_identity, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
            handle.write(",\"records\":[")
            for record in records:
                encoded = serialize(record)
                json.loads(encoded)
                if count:
                    handle.write(",")
                handle.write(encoded)
                count += 1
            handle.write("]}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        if failure_path.exists():
            failure_path.unlink()
        return {"status": "complete", "path": str(destination), "record_count": count}
    except BaseException as error:
        error_traceback = traceback.format_exc()
        cleanup_succeeded = True
        try:
            if temporary.exists():
                temporary.unlink()
        except BaseException as cleanup_error:
            cleanup_succeeded = False
            error.add_note(f"partial export cleanup failed: {cleanup_error!r}")
        pending_exists = temporary.exists()
        receipt = {
            "schema": "n2-engineering-failure-receipt/1",
            "status": "failed",
            "stage": "export",
            "run_identity": run_identity,
            "last_completed_update": int(last_completed_update),
            "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else None,
            "checkpoint_exists": bool(checkpoint_path is not None and Path(checkpoint_path).is_file()),
            "records_serialized_before_failure": count,
            "partial_artifact": "absent" if not destination.exists() else "preexisting-complete-artifact-preserved",
            "pending_cleanup": "succeeded" if cleanup_succeeded and not pending_exists else "failed",
            "pending_artifact": str(temporary) if pending_exists else None,
            "exception_type": type(error).__name__,
            "exception_message": str(error),
            "traceback": error_traceback,
        }
        try:
            _atomic_json(failure_path, receipt)
        except BaseException as receipt_error:
            error.add_note(f"failure receipt could not be written: {receipt_error!r}")
        raise


def write_training_failure_receipt(
    path: str | Path,
    *,
    run_identity: dict[str, Any],
    stage: str,
    last_completed_update: int,
    checkpoint_path: str | Path | None,
    error: BaseException,
) -> dict[str, Any]:
    receipt = {
        "schema": "n2-engineering-failure-receipt/1",
        "status": "failed",
        "stage": stage,
        "run_identity": run_identity,
        "last_completed_update": int(last_completed_update),
        "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else None,
        "checkpoint_exists": bool(checkpoint_path is not None and Path(checkpoint_path).is_file()),
        "exception_type": type(error).__name__,
        "exception_message": str(error),
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    }
    _atomic_json(Path(path), receipt)
    return receipt
