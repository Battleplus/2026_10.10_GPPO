"""Generate static N2 package identities without importing project code."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "package"
CANONICAL = PACKAGE / "civilian"
REGISTERED = CANONICAL / "registered_data"
FIXTURE_NAMES = {
    "combined.json",
    "control.json",
    "energy_change.json",
    "external_commitment.json",
    "failure.json",
    "report_delay.json",
    "stock_loss.json",
}
RELEASE_ID = "ch2_disaster_relief_n02_formal_auth_binding_v5"
PROTOCOL_ID = "n02-integration-smoke-v4-100x100"
STAGE_PROTOCOL = "n02-integration-smoke-v4-100x100/seven-stage"
MAP_CONTRACT = "relief-grid-100x100-v1"
SPLIT_SIZES = {"train": 2, "development": 1}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def validate_map_contract(scenario: dict[str, Any], identity: str) -> None:
    map_value = scenario.get("map")
    if not isinstance(map_value, dict) or (
        map_value.get("grid_contract") != MAP_CONTRACT
        or map_value.get("rows") != 100
        or map_value.get("cols") != 100
        or map_value.get("grid_cells") != 10000
        or map_value.get("cell_km") != 1.0
        or map_value.get("local_block") != [40, 40, 2, 2]
    ):
        raise ValueError(f"100x100 map contract mismatch: {identity}")
    for section in ("platforms", "depots", "tasks"):
        entities = scenario.get(section)
        if not isinstance(entities, list):
            raise ValueError(f"scenario entities are missing: {identity}:{section}")
        for entity in entities:
            position = entity.get("position") if isinstance(entity, dict) else None
            if (
                not isinstance(position, list)
                or len(position) != 2
                or any(type(value) not in (int, float) or not 0 <= value <= 99 for value in position)
            ):
                raise ValueError(f"scenario coordinate outside [0, 99]: {identity}:{section}")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def regular_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"required directory is missing or symlinked: {root}")
    files = []
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            if (current_path / name).is_symlink():
                raise ValueError(f"symlinked directory is not allowed: {current_path / name}")
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"non-regular package file: {path}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def static_validate() -> dict:
    package_files = regular_files(PACKAGE)
    if any("__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"} for path in package_files):
        raise ValueError("package contains __pycache__, .pyc, or .pyo files")
    python_files = [path for path in package_files if path.suffix == ".py"]
    json_files = [path for path in package_files if path.suffix == ".json"]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in json_files:
        json.loads(path.read_text(encoding="utf-8"))

    fixture_root = CANONICAL / "fixtures"
    fixture_files = regular_files(fixture_root)
    if {path.name for path in fixture_files} != FIXTURE_NAMES:
        raise ValueError("smoke fixture directory does not contain exactly the seven registered fixtures")
    fixture_hashes = {}
    for target in fixture_files:
        target_hash = sha256_file(target)
        fixture = json.loads(target.read_text(encoding="utf-8"))
        validate_map_contract(fixture, f"fixture:{target.name}")
        fixture_hashes[target.name] = target_hash

    registry_path = REGISTERED / "input_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if (
        registry.get("schema") != "n2-input-registry/2"
        or registry.get("status") != "prepared_static_not_preflighted"
        or registry.get("protocol_id") != PROTOCOL_ID
        or registry.get("map_contract") != MAP_CONTRACT
        or registry.get("scenario_count") != sum(SPLIT_SIZES.values())
        or registry.get("split_sizes") != SPLIT_SIZES
        or registry.get("synthetic_inputs") is not True
        or registry.get("validation_state", {}).get("target_runtime_preflight") != "pending"
        or registry.get("validation_state", {}).get("training_or_rollout") != "not_run"
        or registry.get("validation_state", {}).get("server_submission_or_authorization") != "not_performed"
    ):
        raise ValueError("input registry status or allocation does not match static-only contract")
    taskbook = ROOT / "TASKBOOK.md"
    if not taskbook.is_file() or sha256_file(taskbook) != registry.get("taskbook_sha256"):
        raise ValueError("registered taskbook digest does not match TASKBOOK.md")
    generator = CANONICAL / "scenario_matrix.py"
    if registry.get("generator") != {
        "path": "package/civilian/scenario_matrix.py",
        "sha256": sha256_file(generator),
        "function": "build_parent_matrix",
    }:
        raise ValueError("input registry is not bound to the packaged scenario generator")

    parents = registry.get("parents")
    if not isinstance(parents, list) or len(parents) != sum(SPLIT_SIZES.values()):
        raise ValueError("input registry does not contain the v4 parent allocation")
    expected_registered = {"input_registry.json"}
    split_counts = {split: 0 for split in SPLIT_SIZES}
    for entry in parents:
        rel = Path(entry.get("path", ""))
        if rel.is_absolute() or not rel.parts or any(part in {".", ".."} for part in rel.parts):
            raise ValueError("registered parent path is not normalized and relative")
        if entry.get("split") not in split_counts or entry.get("synthetic") is not True:
            raise ValueError("registered parent has an invalid split or is not synthetic")
        split_counts[entry["split"]] += 1
        target = REGISTERED / rel
        if target.is_symlink() or not target.is_file() or sha256_file(target) != entry.get("scenario_sha256"):
            raise ValueError(f"registered scenario digest mismatch: {entry.get('parent_id')}")
        scenario = json.loads(target.read_text(encoding="utf-8"))
        if scenario.get("scenario_id") != entry.get("parent_id") or scenario.get("synthetic") is not True:
            raise ValueError(f"registered scenario identity mismatch: {entry.get('parent_id')}")
        validate_map_contract(scenario, f"parent:{entry.get('parent_id')}")
        expected_registered.add(rel.as_posix())
    if split_counts != SPLIT_SIZES:
        raise ValueError(f"unexpected registered split sizes: {split_counts}")

    causal = registry.get("causal_case", {})
    causal_rel = Path(causal.get("path", ""))
    if causal_rel.as_posix() != "fixtures/causal_allocation_case.json":
        raise ValueError("causal fixture must use the registered-data-relative fixtures path")
    causal_path = REGISTERED / causal_rel
    causal_hash = sha256_file(causal_path)
    causal_value = json.loads(causal_path.read_text(encoding="utf-8"))
    if (
        causal_hash != causal.get("sha256")
        or causal.get("synthetic") is not True
        or causal_value.get("scenario_id") != causal.get("scenario_id")
        or causal_value.get("scenario", {}).get("synthetic") is not True
    ):
        raise ValueError("causal fixture identity or digest mismatch")
    validate_map_contract(causal_value.get("scenario", {}), "causal_fixture")
    expected_registered.add(causal_rel.as_posix())
    observed_registered = {
        path.relative_to(REGISTERED).as_posix()
        for path in regular_files(REGISTERED)
    }
    if observed_registered != expected_registered:
        raise ValueError("registered_data contains missing or unregistered files")

    layout_source = (CANONICAL / "package_layout.py").read_text(encoding="utf-8")
    if (
        f'PACKAGE_RELEASE_ID = "{RELEASE_ID}"' not in layout_source
        or "if not requested.is_absolute():" not in layout_source
        or "if root != CANONICAL_PACKAGE_ROOT:" not in layout_source
        or "SMOKE_FIXTURE_NAMES" not in layout_source
    ):
        raise ValueError("canonical package-root contract is incomplete")
    civilian_sources = [path for path in python_files if CANONICAL in path.parents]
    import_nodes = []
    for path in civilian_sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        import_nodes.extend(node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
    outer_n2_imports = []
    for node in import_nodes:
        modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
        outer_n2_imports.extend(name for name in modules if name == "n2" or name.startswith("n2."))
    if outer_n2_imports:
        raise ValueError(f"civilian source imports outer package/n2 modules: {outer_n2_imports}")

    runtime_spec = json.loads((CANONICAL / "runtime-spec.json").read_text(encoding="utf-8"))
    prior_cost = json.loads((CANONICAL / "PRIOR_RESOURCE_COST.json").read_text(encoding="utf-8"))
    if runtime_spec.get("measurement", {}).get("status") != "not_measured":
        raise ValueError("target runtime must remain explicitly unmeasured")
    gates = prior_cost.get("gates", {})
    if (
        prior_cost.get("measurement", {}).get("status") != "pending"
        or gates.get("target_runtime_preflight_allowed") is not True
        or gates.get("pipeline_execution_allowed") is not False
        or gates.get("request_freeze_allowed") is not False
    ):
        raise ValueError("resource-cost gate no longer represents preflight-only static readiness")

    civilian_python = set(civilian_sources)
    outer_n2_python = {path for path in python_files if PACKAGE / "n2" in path.parents}
    runtime_paths = set(civilian_python)
    runtime_paths.add(CANONICAL / "runtime-spec.json")
    runtime_paths.add(CANONICAL / "PRIOR_RESOURCE_COST.json")
    runtime_paths.update(REGISTERED.rglob("*.json"))
    runtime_paths.update(fixture_files)
    for name in ("protocol/preregistered_protocol.json", "REUSE_IMPLEMENTATION.json", "SOURCE_REUSE_TRAINING.json"):
        path = CANONICAL / name
        if path.is_file():
            runtime_paths.add(path)
    runtime_hashes = {
        path.relative_to(CANONICAL).as_posix(): sha256_file(path)
        for path in sorted(runtime_paths, key=lambda value: value.relative_to(CANONICAL).as_posix())
    }
    package_hashes = {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in package_files
    }
    return {
        "package_files": package_files,
        "python_count": len(python_files),
        "civilian_python_count": len(civilian_python),
        "outer_n2_python_count": len(outer_n2_python),
        "json_count": len(json_files),
        "fixture_hashes": fixture_hashes,
        "registry_sha256": sha256_file(registry_path),
        "causal_sha256": causal_hash,
        "split_counts": split_counts,
        "package_hashes": package_hashes,
        "runtime_hashes": runtime_hashes,
        "runtime_spec_sha256": sha256_file(CANONICAL / "runtime-spec.json"),
        "prior_resource_cost_sha256": sha256_file(CANONICAL / "PRIOR_RESOURCE_COST.json"),
        "taskbook_sha256": registry.get("taskbook_sha256"),
    }


def main() -> None:
    result = static_validate()
    manifest_body = {
        "schema": "n02-package-release-manifest/2",
        "package_release": RELEASE_ID,
        "protocol_id": PROTOCOL_ID,
        "stage_protocol": STAGE_PROTOCOL,
        "map_contract": MAP_CONTRACT,
        "taskbook_sha256": result["taskbook_sha256"],
        "input_registry_sha256": result["registry_sha256"],
        "scenario_count": sum(SPLIT_SIZES.values()),
        "allocation": result["split_counts"],
        "status": "static_candidate_not_frozen",
        "canonical_runtime_root": "package/civilian",
        "validation_state": {
            "static_source_and_json_checks": "passed",
            "synthetic_contract_tests": "passed_4",
            "synthetic_critic_interface_test": "passed_engineering_synthetic_only",
            "target_runtime_preflight": "not_run",
            "local_synthetic_critic_interface_validation": "passed_actual_module_forward_autograd",
            "target_runtime_critic_interface_validation": "not_run",
            "model_forward_training_checkpoint": "synthetic_forward_only_training_checkpoint_not_run",
            "authorization": "not_authorized",
            "request_freeze": "not_frozen",
            "independent_review": "pending",
        },
        "coverage": "Every regular file under package/, including shipped modules under package/n2/; symlinks and Python bytecode are rejected.",
        "files": [
            {"path": path, "size_bytes": (ROOT / path).stat().st_size, "sha256": digest}
            for path, digest in result["package_hashes"].items()
        ],
    }
    release_manifest_sha256 = sha256_bytes(canonical_bytes(manifest_body))
    manifest_path = ROOT / "V4_RELEASE_MANIFEST.json"
    checksums_path = ROOT / "V4_RELEASE_SHA256SUMS.txt"
    bundle_path = ROOT / "V4_HASH_BUNDLE.json"
    request_path = ROOT / "V4_STATIC_REQUEST_IDENTITY.json"
    attempt_path = ROOT / "V4_STATIC_ATTEMPT_IDENTITY.json"
    report_path = ROOT / "V4_STATIC_RELEASE_PREPARATION.md"
    write_json(manifest_path, {**manifest_body, "manifest_sha256": release_manifest_sha256})
    checksum_lines = "".join(
        f"{digest}  {path}\n" for path, digest in result["package_hashes"].items()
    )
    checksums_path.write_text(checksum_lines, encoding="utf-8")

    bundle_body = {
        "schema": "n02-static-hash-bundle/2",
        "package_release": RELEASE_ID,
        "protocol_id": PROTOCOL_ID,
        "map_contract": MAP_CONTRACT,
        "release_manifest_sha256": release_manifest_sha256,
        "input_registry_sha256": result["registry_sha256"],
        "complete_package_file_hashes": result["package_hashes"],
        "runtime_dependency_hashes": result["runtime_hashes"],
    }
    bundle_sha256 = sha256_bytes(canonical_bytes(bundle_body))
    write_json(bundle_path, {**bundle_body, "bundle_sha256": bundle_sha256})

    request_body = {
        "schema": "n02-static-request-identity/2",
        "package_release": RELEASE_ID,
        "protocol_id": PROTOCOL_ID,
        "stage_protocol": STAGE_PROTOCOL,
        "map_contract": MAP_CONTRACT,
        "release_manifest_sha256": release_manifest_sha256,
        "hash_bundle_sha256": bundle_sha256,
        "runtime_dependency_bundle_sha256": sha256_bytes(canonical_bytes(result["runtime_hashes"])),
        "input_registry_sha256": result["registry_sha256"],
        "runtime_spec_sha256": result["runtime_spec_sha256"],
        "prior_resource_cost_sha256": result["prior_resource_cost_sha256"],
        "scenario_count": sum(SPLIT_SIZES.values()),
        "allocation": result["split_counts"],
        "request_scope": "candidate_target_runtime_preflight_only",
        "identity_state": "static_candidate_not_authorized_not_frozen",
        "authorized": False,
        "request_frozen": False,
        "execution_started": False,
        "server_submission": "not_performed",
        "target_runtime_preflight": "not_run",
        "local_synthetic_critic_interface_validation": "passed_actual_module_forward_autograd",
        "target_runtime_critic_interface_validation": "not_run",
        "model_forward_training_checkpoint": "not_run",
        "independent_review": "pending",
    }
    request_identity = sha256_bytes(canonical_bytes(request_body))
    write_json(request_path, {**request_body, "candidate_request_identity_sha256": request_identity})

    attempt_body = {
        "schema": "n02-static-attempt-identity/2",
        "package_release": RELEASE_ID,
        "protocol_id": PROTOCOL_ID,
        "map_contract": MAP_CONTRACT,
        "candidate_request_identity_sha256": request_identity,
        "attempt_state": "candidate_identity_only_no_attempt_created",
        "attempt_started": False,
        "target_runtime_preflight": "not_run",
        "pipeline_execution": "not_run",
        "training_or_rollout": "not_run",
        "local_synthetic_critic_interface_validation": "passed_actual_module_forward_autograd",
        "target_runtime_critic_interface_validation": "not_run",
        "independent_review": "pending",
        "execution_receipt": None,
    }
    attempt_identity = sha256_bytes(canonical_bytes(attempt_body))
    write_json(attempt_path, {**attempt_body, "candidate_attempt_identity_sha256": attempt_identity})

    audit_tool_digest = sha256_file(Path(__file__))
    manifest_file_digest = sha256_file(manifest_path)
    checksum_file_digest = sha256_file(checksums_path)
    bundle_file_digest = sha256_file(bundle_path)
    report = f"""# Static Release Preparation

Status: v4 static candidate only. No target runtime was measured, no request was authorized or frozen, and no attempt, server submission, training, checkpoint operation, or rollout was started. One local synthetic tensor-only model forward and autograd probe exercised the actual G-WM critic modules; it is engineering evidence only, not research-data or runtime validation.

Release: `{RELEASE_ID}`  
Protocol: `{PROTOCOL_ID}`  
Map contract: `{MAP_CONTRACT}`  
Taskbook SHA-256: `{result['taskbook_sha256']}`  
Allocation: 2 train / 1 development; all registered data and seven smoke fixtures use the 100x100 map contract.

Static validation passed: Python AST parse for all package Python files; JSON parse for all package JSON files; exact 2 train / 1 development registered scenarios; 100x100 map, 10,000-cell, local-block, and coordinate checks for every registered parent, causal case, and smoke fixture; taskbook, registry, generator, and scenario digest checks; exact registered-data file set; and symlink/bytecode rejection. The registry remains `prepared_static_not_preflighted`; target runtime remains `not_measured`.

Previously recorded local synthetic contract tests: 4 passed. The focused local synthetic critic interface test also passed (1 test) on CPU PyTorch. It built a 100x100 public input and complete action proposals from the v4 synthetic scenario generator, then exercised the actual graph policy, world model, prediction cache, G-WM policy, and auxiliary critic. It checked paired actor initialization, candidate-key alignment, the WM-to-value path, and finite nonzero auxiliary value-loss gradients while actor action heads and the frozen WM received no gradients. Fixed adapter weights were set directly to expose the path; no optimizer step, research data, training episode, or checkpoint was used. Target-runtime critic interface validation remains `not_run`; this synthetic probe says nothing about learned adapter weights or deployed runtime behavior.  
Independent review: pending.

`V4_RELEASE_MANIFEST.json` payload identity SHA-256: `{release_manifest_sha256}`  
`V4_RELEASE_MANIFEST.json` file SHA-256: `{manifest_file_digest}`  
`V4_RELEASE_SHA256SUMS.txt` SHA-256: `{checksum_file_digest}`  
`V4_HASH_BUNDLE.json` payload identity SHA-256: `{bundle_sha256}`  
`V4_HASH_BUNDLE.json` file SHA-256: `{bundle_file_digest}`  
Runtime dependency bundle SHA-256: `{request_body['runtime_dependency_bundle_sha256']}`  
Candidate request identity SHA-256: `{request_identity}` (`authorized=false`, `request_frozen=false`)  
Candidate attempt identity SHA-256: `{attempt_identity}` (`attempt_started=false`)

Reproduce with `python -B "{Path(__file__).resolve()}"`. The command invokes this static checker only and does not import project modules. Checker SHA-256: `{audit_tool_digest}`.

Remaining gates: independent review of this v4 candidate, target-runtime inventory and bounded preflight measurement, real-data and deployed-runtime critic validation, measured resource-cost reconciliation, and a new separately authorized Request before any formal pipeline execution. No v3 review or identity is inherited by this release.
"""
    report_path.write_text(report, encoding="utf-8")
    print(json.dumps({
        "status": "static_candidate_only",
        "package_release": RELEASE_ID,
        "package_files": len(result["package_hashes"]),
        "python_files": result["python_count"],
        "civilian_python_files": result["civilian_python_count"],
        "outer_n2_python_files": result["outer_n2_python_count"],
        "json_files": result["json_count"],
        "registered_scenarios": result["split_counts"],
        "smoke_fixtures": len(result["fixture_hashes"]),
        "release_manifest_sha256": release_manifest_sha256,
        "release_manifest_file_sha256": manifest_file_digest,
        "hash_bundle_sha256": bundle_sha256,
        "hash_bundle_file_sha256": bundle_file_digest,
        "runtime_dependency_bundle_sha256": request_body["runtime_dependency_bundle_sha256"],
        "candidate_request_identity_sha256": request_identity,
        "candidate_attempt_identity_sha256": attempt_identity,
        "authorized": False,
        "request_frozen": False,
        "attempt_started": False,
        "target_runtime_preflight": "not_run",
        "local_synthetic_critic_interface_validation": "passed_actual_module_forward_autograd",
        "target_runtime_critic_interface_validation": "not_run",
        "independent_review": "pending",
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
