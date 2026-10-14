from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping


class ManagedRuntimeError(RuntimeError):
    pass


def _atomic_json(path: pathlib.Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_worker(config: Mapping[str, object]):
    worker_path = pathlib.Path(str(config["worker_path"])).resolve(strict=True)
    expected = str(config["worker_sha256"]).upper()
    actual = _sha256(worker_path)
    if actual != expected:
        raise ManagedRuntimeError("WORKER_SOURCE_SHA256_MISMATCH")
    module_name = "n2_managed_worker_" + expected[:16].lower()
    spec = importlib.util.spec_from_file_location(module_name, worker_path)
    if spec is None or spec.loader is None:
        raise ManagedRuntimeError("WORKER_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = getattr(module, str(config.get("worker_callable", "managed_worker")), None)
    if not callable(entry):
        raise ManagedRuntimeError("WORKER_MANAGED_ENTRY_REQUIRED")
    return entry


class ManagedRuntime:
    """Main-worker adapter over the W7 BudgetLedger contract."""

    def __init__(self, *, work_root: pathlib.Path, request: Mapping[str, object],
                 ledger, export_root: pathlib.Path):
        self.work_root = work_root
        self.request = request
        self.ledger = ledger
        self.export_root = export_root
        self.exports: list[dict[str, object]] = []
        self.operation_results: list[dict[str, object]] = []
        self.stage_order = tuple(request["stage_order"])
        self._next_stage_index = 0

    @property
    def current_stage(self) -> str:
        return self.ledger.stage

    def select_stage(self, stage: str) -> None:
        if self._next_stage_index >= len(self.stage_order):
            raise ManagedRuntimeError("STAGE_ORDER_EXHAUSTED")
        expected = self.stage_order[self._next_stage_index]
        if stage != expected:
            raise ManagedRuntimeError(f"STAGE_ORDER_MISMATCH:{expected}:{stage}")
        self.ledger.select(stage)
        self._next_stage_index += 1

    def check_catalog_size(self, observed_including_noop: int) -> None:
        guards = self.request.get("admission_guards", {})
        maximum = guards.get("candidate_catalog_size_including_noop_max")
        if (type(observed_including_noop) is not int or observed_including_noop < 1
                or type(maximum) is not int or observed_including_noop > maximum):
            raise ManagedRuntimeError("CANDIDATE_CATALOG_CAP_EXCEEDED_OR_UNCONFIGURED")
        if guards.get("candidate_truncation_allowed") is not False:
            raise ManagedRuntimeError("CANDIDATE_TRUNCATION_MUST_BE_FORBIDDEN")

    def operation(self, *, stage: str, name: str, amounts: Mapping[str, int],
                  function: Callable, args: tuple = (), kwargs: Mapping[str, object] | None = None):
        if self.current_stage != stage:
            raise ManagedRuntimeError("OPERATION_STAGE_NOT_SELECTED:" + stage)
        before = time.monotonic()
        result = self.ledger.call(name, dict(amounts), function, *args, **dict(kwargs or {}))
        self.operation_results.append({
            "name": name,
            "stage": stage,
            "reserved_actual_units": dict(amounts),
            "controller_elapsed_wall_seconds": time.monotonic() - before,
            "status": "complete",
        })
        return result

    def export_verified(self, *, source: pathlib.Path, relative_path: str,
                        expected_sha256: str, amounts: Mapping[str, int]) -> dict[str, object]:
        if source.is_symlink():
            raise ManagedRuntimeError("EXPORT_SOURCE_NOT_REGULAR_FILE")
        source = source.resolve(strict=True)
        if not source.is_file():
            raise ManagedRuntimeError("EXPORT_SOURCE_NOT_REGULAR_FILE")
        relative = pathlib.PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ManagedRuntimeError("EXPORT_PATH_INVALID")
        destination = self.export_root.joinpath(*relative.parts)
        if destination.exists() or destination.is_symlink():
            raise ManagedRuntimeError("EXPORT_DESTINATION_ALREADY_EXISTS")
        if len(expected_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha256):
            raise ManagedRuntimeError("EXPORT_EXPECTED_SHA256_INVALID")

        def perform() -> dict[str, object]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix="." + destination.name + ".", dir=destination.parent)
            try:
                with os.fdopen(fd, "wb") as output, source.open("rb") as input_stream:
                    shutil.copyfileobj(input_stream, output)
                    output.flush()
                    os.fsync(output.fileno())
                copied_hash = _sha256(pathlib.Path(temporary))
                if copied_hash != expected_sha256.upper():
                    raise ManagedRuntimeError("EXPORT_SHA256_MISMATCH")
                os.link(temporary, destination)
                os.unlink(temporary)
                dir_fd = os.open(destination.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except BaseException:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
            return {"path": destination.relative_to(self.export_root).as_posix(),
                    "bytes": destination.stat().st_size, "sha256": copied_hash}

        record = self.ledger.call("verified_export", dict(amounts), perform)
        self.exports.append(record)
        return record

    def complete(self, worker_result: Mapping[str, object]) -> dict[str, object]:
        if self._next_stage_index != len(self.stage_order):
            raise ManagedRuntimeError("WORKER_DID_NOT_VISIT_ALL_STAGES")
        if self.current_stage != self.stage_order[-1]:
            raise ManagedRuntimeError("WORKER_NOT_IN_FINAL_SETTLEMENT_STAGE")
        ledger = self.ledger.assert_settled()
        if ledger.get("failed_calls", 0) != 0:
            raise ManagedRuntimeError("WORKER_HAS_FAILED_BUDGETED_OPERATIONS")
        return {
            "schema": "n2-managed-worker-receipt/1",
            "status": "complete",
            "worker_result": dict(worker_result),
            "ledger": ledger,
            "operation_results": self.operation_results,
            "exports": self.exports,
            "export_status": "complete" if self.exports else "not_requested",
            "stage_server_socket_present": bool(os.environ.get("W1_PHASE_ACCOUNTING_SOCKET")),
            "settlement": "complete",
        }


def run_worker_config(config_path: pathlib.Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    infrastructure = pathlib.Path(config["w7_infrastructure"]).resolve(strict=True)
    os.sys.path.insert(0, str(infrastructure))
    from budget_ledger import BudgetLedger

    request_path = pathlib.Path(config["resource_request_path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    work_root = pathlib.Path(config["work_root"])
    export_root = pathlib.Path(config["export_root"])
    ledger = BudgetLedger(work_root / "budget-ledger.sqlite3", request)
    runtime = ManagedRuntime(work_root=work_root, request=request, ledger=ledger, export_root=export_root)
    first_error: dict[str, object] | None = None
    try:
        if not os.environ.get("W1_PHASE_ACCOUNTING_SOCKET"):
            raise ManagedRuntimeError("W7_STAGE_SERVER_SOCKET_MISSING")
        worker = load_worker(config)
        result = worker(runtime)
        if not isinstance(result, Mapping):
            raise ManagedRuntimeError("WORKER_RESULT_MUST_BE_OBJECT")
        receipt = runtime.complete(result)
        ledger.close(snapshot=True)
        _atomic_json(work_root / "managed-worker-receipt.json", receipt)
        return 0
    except BaseException as exc:
        first_error = {"type": type(exc).__name__, "message": str(exc), "recorded_monotonic": time.monotonic()}
        try:
            with (work_root / "managed-worker-first-error.json").open("x", encoding="utf-8") as stream:
                json.dump(first_error, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        except BaseException:
            pass
        settlement: dict[str, object] = {"status": "failed", "first_error": first_error}
        try:
            settlement["ledger"] = ledger.snapshot()
            settlement["ledger_assert_settled"] = ledger.assert_settled()
            settlement["settlement_status"] = "complete"
        except BaseException as settlement_error:
            settlement["settlement_status"] = "incomplete"
            settlement["settlement_error"] = type(settlement_error).__name__ + ": " + str(settlement_error)
        try:
            ledger.close(snapshot=True)
        except BaseException as close_error:
            settlement["ledger_close_error"] = type(close_error).__name__ + ": " + str(close_error)
        try:
            _atomic_json(work_root / "managed-worker-receipt.json", settlement)
        except BaseException:
            pass
        return 1
