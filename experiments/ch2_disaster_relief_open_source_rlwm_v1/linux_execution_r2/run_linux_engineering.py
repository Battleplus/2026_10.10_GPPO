"""Run a bounded Linux CPU compatibility sequence with durable receipts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import resource
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable


PINNED_UPSTREAM = "546e4fab8146ea4b14e1d7726bbc1a8a1d50322f"
EXPECTED_TESTS = 26
MAX_STAGE_SECONDS = 480
RUN_RECEIPT = "run-receipt.json"


class EngineeringStop(RuntimeError):
    pass


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(payload.encode("utf-8"))


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _safe_report_path(repo_root: Path, output_dir: Path) -> Path:
    report_root = (repo_root / "reports" / "linux-engineering-20261014").resolve()
    resolved = output_dir.resolve()
    if resolved != report_root and report_root not in resolved.parents:
        raise ValueError(f"output path must be under {report_root}")
    return resolved


def _source_manifest(repo_root: Path) -> dict[str, Any]:
    roots = [
        repo_root / "integration",
        repo_root / "relief_adapter",
        repo_root / "tests",
        repo_root / "upstream_smoke",
        repo_root / "vendor",
        repo_root / "upstream_r2" / f"r2dreamer-{PINNED_UPSTREAM}",
        repo_root / "linux_execution",
    ]
    suffixes = {".py", ".json", ".toml", ".yaml", ".yml", ".txt", ".sh"}
    excluded_dirs = {".git", "__pycache__", ".pytest_cache"}
    entries: list[dict[str, str]] = []
    for root in roots:
        if not root.exists():
            raise FileNotFoundError(f"required source directory is missing: {root}")
        for current, dirs, filenames in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in excluded_dirs)
            for filename in sorted(filenames):
                path = Path(current) / filename
                if path.suffix.lower() not in suffixes or path.is_symlink():
                    continue
                entries.append(
                    {
                        "path": path.relative_to(repo_root).as_posix(),
                        "sha256": _sha256_file(path),
                    }
                )
    entries.sort(key=lambda item: item["path"])
    return {
        "algorithm": "sha256",
        "files": entries,
        "file_count": len(entries),
        "manifest_sha256": _canonical_json_sha256(entries),
    }


def _artifact_rows(output_dir: Path) -> list[dict[str, Any]]:
    excluded = {"artifact-hashes.json", RUN_RECEIPT, RUN_RECEIPT + ".tmp"}
    rows = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name in excluded or path.name.endswith(".tmp"):
            continue
        rows.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return rows


def _write_artifacts(output_dir: Path, receipt: dict[str, Any]) -> None:
    rows = _artifact_rows(output_dir)
    receipt["artifact_hashes"] = rows
    receipt["artifact_index"] = "artifact-hashes.json"
    _write_json(output_dir / RUN_RECEIPT, receipt)
    index = {
        "algorithm": "sha256",
        "artifacts": rows,
        "run_receipt_sha256": _sha256_file(output_dir / RUN_RECEIPT),
    }
    _write_json(output_dir / "artifact-hashes.json", index)


def _versions() -> dict[str, str]:
    names = [
        "torch",
        "numpy",
        "gymnasium",
        "tensordict",
        "torchrl",
        "hydra-core",
        "omegaconf",
        "einops",
        "ruamel.yaml",
        "antlr4-python3-runtime",
        "cloudpickle",
        "packaging",
        "importlib-metadata",
        "zipp",
        "orjson",
        "pyvers",
        "psutil",
        "PyYAML",
        "setuptools",
        "wheel",
        "typing_extensions",
        "Farama-Notifications",
    ]
    values: dict[str, str] = {}
    for name in names:
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = "MISSING"
    return values


def _check_environment(repo_root: Path, venv_path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    expected_python = spec["base"]["python"]
    if platform.python_version() != expected_python:
        raise EngineeringStop(
            f"Python version mismatch: expected {expected_python}, found {platform.python_version()}"
        )
    if Path(sys.prefix).resolve() != venv_path.resolve():
        raise EngineeringStop(f"wrong Python environment: sys.prefix={sys.prefix}, expected={venv_path}")

    site_packages = Path(sysconfig_path()).resolve()
    pth_path = site_packages / "read_only_original_runtime.pth"
    if not pth_path.is_file():
        raise EngineeringStop(f"read-only base runtime path file is missing: {pth_path}")
    referenced_paths = [
        Path(line.strip()).resolve()
        for line in pth_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("import ")
    ]
    if len(referenced_paths) != 1 or not referenced_paths[0].is_dir():
        raise EngineeringStop("read_only_original_runtime.pth must contain one existing site-packages path")

    expected = {
        "torch": spec["base"]["torch"],
        "numpy": spec["base"]["numpy"],
        "setuptools": "77.0.3",
        "wheel": "0.45.1",
        "antlr4-python3-runtime": "4.9.3",
        "cloudpickle": "3.1.2",
        "Farama-Notifications": "0.0.4",
        "importlib-metadata": "8.6.1",
        "omegaconf": "2.3.0",
        "orjson": "3.10.18",
        "packaging": "25.0",
        "PyYAML": "6.0.2",
        "psutil": "6.1.1",
        "pyvers": "0.1.0",
        "typing_extensions": "4.15.0",
        "zipp": "3.21.0",
        "tensordict": "0.9.1",
        "torchrl": "0.9.2",
        "einops": "0.3.0",
        "gymnasium": "1.2.0",
        "hydra-core": "1.3.2",
        "ruamel.yaml": "0.17.4",
    }
    versions = _versions()
    for phase in spec["pip_phases"]:
        for package in phase["packages"]:
            name, version = package.split("==")
            expected[name] = version
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "MISSING"
    mismatches = {
        name: {"expected": version, "actual": versions.get(name, "MISSING")}
        for name, version in expected.items()
        if versions.get(name) != version
    }
    if mismatches:
        raise EngineeringStop(f"runtime package mismatch: {json.dumps(mismatches, sort_keys=True)}")

    if "2.8.0" == spec["base"]["torch"]:
        raise EngineeringStop("target runtime must not be represented as the upstream Torch 2.8 environment")

    return {
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "venv_prefix": str(Path(sys.prefix).resolve()),
        "read_only_runtime_site_packages": str(referenced_paths[0]),
        "torch_cuda_build": spec["base"]["torch"],
        "numpy": spec["base"]["numpy"],
        "versions": versions,
        "exact_upstream_torch_reproduction": False,
        "upstream_declared_torch": spec["base"]["upstream_declared_torch"],
        "cuda_disabled_by_environment": True,
    }


def sysconfig_path() -> str:
    import sysconfig

    return sysconfig.get_paths()["purelib"]


def _environment_from_spec(spec: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in spec["env"].items()})
    return env


def _usage_snapshot() -> resource.struct_rusage:
    return resource.getrusage(resource.RUSAGE_CHILDREN)


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _sample_process_tree_rss(process: subprocess.Popen[bytes]) -> int:
    try:
        import psutil

        parent = psutil.Process(process.pid)
        total = parent.memory_info().rss
        for child in parent.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                continue
        return int(total)
    except Exception:
        return 0


def _run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    output_dir: Path,
    receipt: dict[str, Any],
    timeout_seconds: int,
    validator: Callable[[Path], None] | None = None,
) -> None:
    log_path = output_dir / f"{len(receipt['stages']) + 1:02d}-{name}.log"
    stage: dict[str, Any] = {
        "name": name,
        "status": "running",
        "argv": argv,
        "started_at": _utc_now(),
        "log_path": log_path.name,
        "timeout_seconds": timeout_seconds,
    }
    receipt["stages"].append(stage)
    _write_json(output_dir / RUN_RECEIPT, receipt)
    before = _usage_snapshot()
    started = time.monotonic()
    peak_rss = 0
    process: subprocess.Popen[bytes] | None = None
    error: BaseException | None = None
    try:
        with log_path.open("xb") as log_stream:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = started + timeout_seconds
            while process.poll() is None:
                peak_rss = max(peak_rss, _sample_process_tree_rss(process))
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"stage exceeded {timeout_seconds} seconds")
                time.sleep(0.1)
            return_code = process.returncode
        stage["return_code"] = return_code
        stage["wall_seconds"] = time.monotonic() - started
        if return_code != 0:
            raise EngineeringStop(f"command exited with status {return_code}")
        if validator is not None:
            validator(log_path)
        stage["status"] = "pass"
    except BaseException as exc:
        error = exc
        if process is not None and process.poll() is None:
            _stop_process_group(process)
        stage["status"] = "technical_stop"
        stage["error_type"] = type(exc).__name__
        stage["error_message"] = str(exc)
    finally:
        after = _usage_snapshot()
        stage["finished_at"] = _utc_now()
        stage["wall_seconds"] = time.monotonic() - started
        stage["process_tree_peak_rss_bytes_sampled"] = peak_rss or None
        stage["child_user_cpu_seconds"] = max(0.0, after.ru_utime - before.ru_utime)
        stage["child_system_cpu_seconds"] = max(0.0, after.ru_stime - before.ru_stime)
        if log_path.exists():
            stage["log_bytes"] = log_path.stat().st_size
            stage["log_sha256"] = _sha256_file(log_path)
        if error is not None and receipt.get("first_error") is None:
            log_tail = ""
            if log_path.exists():
                log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
            receipt["first_error"] = {
                "stage": name,
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(error)),
                "log_tail": log_tail,
            }
        _write_json(output_dir / RUN_RECEIPT, receipt)
    if error is not None:
        raise EngineeringStop(f"stage {name} stopped: {error}") from error


def _log_text(log_path: Path) -> str:
    return log_path.read_text(encoding="utf-8", errors="replace")


def _validate_witness(log_path: Path) -> None:
    text = _log_text(log_path)
    expected = "WITNESS seed=8201 device=cpu shape=2x2 finite=true"
    if expected not in text:
        raise EngineeringStop("seeded CPU witness sentinel was missing")


def _validate_test_count(log_path: Path) -> None:
    text = _log_text(log_path)
    match = re.search(r"Ran\s+(\d+) tests?\s+in\s+[0-9.]+s", text)
    if match is None or int(match.group(1)) != EXPECTED_TESTS or not re.search(r"\nOK\s*$", text):
        raise EngineeringStop(f"expected {EXPECTED_TESTS} unittest passes; inspect {log_path.name}")


def _validate_upstream(output_dir: Path) -> None:
    receipt_path = output_dir / "upstream" / "smoke-receipt.json"
    artifact = output_dir / "upstream" / "dreamer_cartpole_smoke.pt"
    if not receipt_path.is_file() or not artifact.is_file():
        raise EngineeringStop("upstream smoke receipt or checkpoint is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks = {
        "status": receipt.get("status") == "pass",
        "run_kind": receipt.get("run_kind") == "engineering_smoke_not_study",
        "updates": receipt.get("updates") == 3,
        "formal_updates": receipt.get("formal_updates") == 0,
        "cuda_initialized": receipt.get("cuda_initialized") is False,
        "torch_threads": receipt.get("torch_threads") == 1,
        "checkpoint_restore": receipt.get("checkpoint_model_restore_hash") == receipt.get("parameter_hash_after"),
        "parameter_change": receipt.get("parameter_hash_before") != receipt.get("parameter_hash_after"),
        "upstream_pin": receipt.get("upstream_commit") == PINNED_UPSTREAM,
    }
    if not all(checks.values()):
        raise EngineeringStop(f"upstream receipt checks failed: {checks}")


def _validate_civilian(output_dir: Path) -> None:
    receipt_path = output_dir / "civilian" / "civilian-dreamer-smoke-receipt.json"
    artifact = output_dir / "civilian" / "civilian_dreamer_smoke.pt"
    if not receipt_path.is_file() or not artifact.is_file():
        raise EngineeringStop("civilian smoke receipt or checkpoint is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    resource_row = receipt.get("resource", {})
    checks = {
        "status": receipt.get("status") == "pass",
        "run_kind": receipt.get("run_kind") == "engineering_smoke_not_study",
        "completed_updates": resource_row.get("completed_updates") == 3,
        "adapter_steps": resource_row.get("adapter_step_calls") == 128,
        "physical_minutes": resource_row.get("physical_minutes_advanced") == 120,
        "illegal_actions": resource_row.get("illegal_action_count") == 0,
        "formal_updates": receipt.get("formal_world_model_updates") == 0,
        "formal_evaluation": receipt.get("formal_evaluation_episodes") == 0,
        "training_scenario": str(receipt.get("scenario_id", "")).startswith("relief-n2-train-"),
        "cuda_initialized": receipt.get("cuda_initialized") is False,
        "torch_threads": receipt.get("torch_threads") == 1,
        "checkpoint_restore": receipt.get("checkpoint_model_restore_hash") == receipt.get("parameter_hash_after"),
    }
    if not all(checks.values()):
        raise EngineeringStop(f"civilian receipt checks failed: {checks}")


def _validate_precision(output_dir: Path) -> None:
    path = output_dir / "precision-diagnostic.json"
    if not path.is_file():
        raise EngineeringStop("precision diagnostic report is missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = {row.get("mode"): row for row in report.get("results", [])}
    half = rows.get("cpu_float16_upstream")
    full = rows.get("cpu_float32_diagnostic")
    if half is None or full is None:
        raise EngineeringStop("precision diagnostic did not report both CPU precision paths")
    if full.get("status") != "pass_two_fixed_batch_updates" or full.get("optimizer_steps") != 2:
        raise EngineeringStop("FP32 diagnostic control did not complete two finite optimizer updates")
    if report.get("upstream_revision") != PINNED_UPSTREAM:
        raise EngineeringStop("precision diagnostic upstream pin mismatch")
    if report.get("formal_updates") != 0 or report.get("confirmation_evaluations") != 0:
        raise EngineeringStop("precision diagnostic crossed the engineering-only boundary")
    if half.get("status") not in {"technical_stop", "pass_two_fixed_batch_updates"}:
        raise EngineeringStop(f"unexpected FP16 diagnostic status: {half.get('status')}")


def run(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    venv_path = args.venv_path.resolve()
    output_dir = _safe_report_path(repo_root, args.output_dir)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", args.run_id):
        raise ValueError("run id must contain only letters, digits, dot, underscore or hyphen")
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "run-started.json").exists() or (output_dir / RUN_RECEIPT).exists():
        raise FileExistsError(f"run evidence already exists; refusing to rerun: {output_dir}")

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "run_id": args.run_id,
        "run_kind": "linux_engineering_compatibility_not_study",
        "status": "running",
        "first_error": None,
        "started_at": _utc_now(),
        "repo_root": str(repo_root),
        "source_identity_declared": args.source_identity,
        "runtime": {},
        "source_manifest_sha256": None,
        "stages": [],
        "formal_training": False,
        "heldout_confirmation": False,
        "six_path_study_training": False,
        "resource": {
            "scope": "runner plus child commands inside the systemd service; excludes SSH, deployment, and environment installation",
            "cpu_affinity_requested": [args.cpu],
            "gpu_enabled": False,
            "automatic_retries": 0,
        },
    }
    _write_json(output_dir / "run-started.json", {"run_id": args.run_id, "started_at": receipt["started_at"]})
    _write_json(output_dir / RUN_RECEIPT, receipt)
    started = time.monotonic()
    self_cpu_start = time.process_time()
    child_usage_start = _usage_snapshot()

    def stop_on_signal(signum: int, _frame: Any) -> None:
        raise EngineeringStop(f"received signal {signal.Signals(signum).name}")

    signal.signal(signal.SIGTERM, stop_on_signal)
    signal.signal(signal.SIGINT, stop_on_signal)
    try:
        spec_path = repo_root / "linux_execution" / "environment-spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec_hash = _canonical_json_sha256(spec)
        execution_plan = json.loads((repo_root / "linux_execution" / "execution-plan.json").read_text())
        if execution_plan["environment_spec_sha256"] != spec_hash:
            raise EngineeringStop("execution plan environment identity mismatch")
        receipt["execution_plan_sha256"] = _canonical_json_sha256(execution_plan)
        receipt["maximum_engineering_optimizer_steps"] = execution_plan["maximum_total_optimizer_steps"]
        receipt["environment_spec_path"] = str(spec_path)
        receipt["environment_spec_sha256"] = spec_hash
        env = _environment_from_spec(spec)
        allowed = set(os.sched_getaffinity(0))
        if args.cpu not in allowed:
            raise EngineeringStop(f"requested CPU {args.cpu} is outside current affinity {sorted(allowed)}")
        os.sched_setaffinity(0, {args.cpu})
        receipt["resource"]["cpu_affinity_effective"] = sorted(os.sched_getaffinity(0))
        receipt["runtime"] = _check_environment(repo_root, venv_path, spec)
        manifest = _source_manifest(repo_root)
        _write_json(output_dir / "source-hashes.json", manifest)
        receipt["source_manifest_sha256"] = manifest["manifest_sha256"]
        receipt["source_file_count"] = manifest["file_count"]
        _write_json(output_dir / RUN_RECEIPT, receipt)

        commands: list[tuple[str, list[str], Callable[[Path], None] | None]] = [
            (
                "seeded-cpu-witness",
                [sys.executable, "-m", "linux_execution.cpu_witness"],
                _validate_witness,
            ),
            (
                "unittest-26",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                _validate_test_count,
            ),
            (
                "upstream-cartpole-3-updates",
                [
                    sys.executable,
                    str(repo_root / "upstream_smoke" / "upstream_dreamer_smoke.py"),
                    "--repo-root",
                    str(repo_root / "upstream_r2" / f"r2dreamer-{PINNED_UPSTREAM}"),
                    "--output-dir",
                    str(output_dir / "upstream"),
                    "--updates",
                    "3",
                    "--length",
                    "8",
                    "--seed",
                    "8201",
                ],
                None,
            ),
            (
                "civilian-3-updates",
                [
                    sys.executable,
                    str(repo_root / "integration" / "civilian_dreamer_smoke.py"),
                    "--repo-root",
                    str(repo_root),
                    "--output-dir",
                    str(output_dir / "civilian"),
                    "--updates",
                    "3",
                    "--seed",
                    "8201",
                ],
                None,
            ),
            (
                "precision-diagnostic",
                [
                    sys.executable,
                    str(repo_root / "linux_execution" / "run_precision_diagnostic.py"),
                    "--repo-root",
                    str(repo_root),
                    "--output",
                    str(output_dir / "precision-diagnostic.json"),
                ],
                None,
            ),
        ]
        for name, argv, validator in commands:
            if name == "unittest-26":
                validator = _validate_test_count
            elif name == "upstream-cartpole-3-updates":
                validator = lambda _log: _validate_upstream(output_dir)
            elif name == "civilian-3-updates":
                validator = lambda _log: _validate_civilian(output_dir)
            elif name == "precision-diagnostic":
                validator = lambda _log: _validate_precision(output_dir)
            _run_command(
                name=name,
                argv=argv,
                cwd=repo_root,
                env=env,
                output_dir=output_dir,
                receipt=receipt,
                timeout_seconds=min(args.stage_timeout_seconds, MAX_STAGE_SECONDS),
                validator=validator,
            )
        precision_report = json.loads((output_dir / "precision-diagnostic.json").read_text())
        precision_rows = {r["mode"]: r for r in precision_report["results"]}
        completed_steps = {"upstream_cartpole": 3, "civilian_adapter": 3,
                           "precision_diagnostic_fp16_control": precision_rows["cpu_float16_upstream"]["optimizer_steps"],
                           "precision_diagnostic_fp32_control": precision_rows["cpu_float32_diagnostic"]["optimizer_steps"]}
        for stage_name, count in completed_steps.items():
            if not 0 <= count <= execution_plan["allowed_optimizer_steps"][stage_name]:
                raise EngineeringStop("optimizer step allowance exceeded: " + stage_name)
        receipt["completed_engineering_optimizer_steps"] = completed_steps
        receipt["completed_engineering_optimizer_steps_total"] = sum(completed_steps.values())
        receipt["status"] = "pass"
        receipt["completed_at"] = _utc_now()
    except BaseException as exc:
        receipt["status"] = "technical_stop"
        receipt["completed_at"] = _utc_now()
        if receipt.get("first_error") is None:
            receipt["first_error"] = {
                "stage": "preflight_or_runner",
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
    finally:
        child_usage_end = _usage_snapshot()
        receipt["resource"].update(
            {
                "wall_seconds": time.monotonic() - started,
                "runner_process_cpu_seconds": time.process_time() - self_cpu_start,
                "child_user_cpu_seconds": max(0.0, child_usage_end.ru_utime - child_usage_start.ru_utime),
                "child_system_cpu_seconds": max(0.0, child_usage_end.ru_stime - child_usage_start.ru_stime),
                "children_peak_rss_bytes": int(child_usage_end.ru_maxrss * 1024),
                "children_peak_rss_source": "Linux getrusage(RUSAGE_CHILDREN): maximum single-child RSS, not aggregate service memory; process-tree samples are separate",
            }
        )
        if not receipt.get("runtime"):
            receipt["runtime"]["python"] = platform.python_version()
            receipt["runtime"]["python_executable"] = str(Path(sys.executable).resolve())
        _write_artifacts(output_dir, receipt)

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--repo-root", type=Path, required=True)
    run_parser.add_argument("--venv-path", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path, required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--source-identity", required=True)
    run_parser.add_argument("--cpu", type=int, default=0)
    run_parser.add_argument("--stage-timeout-seconds", type=int, default=MAX_STAGE_SECONDS)
    run_parser.set_defaults(func=run)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
