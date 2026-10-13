"""Build fresh, split-isolated civilian scenario parents for the N2 WM pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from ..vendor_source import load_source_module, resolve_source_root


SPLIT_COUNTS = {"train": 56, "development": 14, "heldout": 56}
CONDITIONS = ("carrier_competition", "stock_competition")
SEED_NAMESPACE = "ch2-disaster-relief-open-source-rlwm-v1/n2-fresh-20261013"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def semantic_scenario_hash(scenario: dict[str, Any]) -> str:
    semantic = dict(scenario)
    semantic.pop("scenario_id", None)
    return sha256_bytes(canonical_json(semantic))


def derive_seed(split: str, condition: str, index: int) -> int:
    token = f"{SEED_NAMESPACE}|{split}|{condition}|{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big")


def _deep_scenario_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if all(key in value for key in ("tasks", "depots")):
            yield value
        for child in value.values():
            yield from _deep_scenario_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _deep_scenario_objects(child)


def _read_old_ids_and_semantics(old_roots: list[Path]) -> tuple[set[str], set[str]]:
    old_ids: set[str] = set()
    old_semantic_hashes: set[str] = set()
    id_keys = ("parent_id", "parent_scenario_id", "scenario_id")
    for root in old_roots:
        if not root.exists():
            raise FileNotFoundError(f"old-data root does not exist: {root}")
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            if path.suffix.lower() == ".json":
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                for record in _deep_records(value):
                    for key in id_keys:
                        item = record.get(key)
                        if isinstance(item, str):
                            old_ids.add(item)
                for scenario in _deep_scenario_objects(value):
                    scenario_id = scenario.get("scenario_id")
                    if isinstance(scenario_id, str):
                        old_ids.add(scenario_id)
                    old_semantic_hashes.add(semantic_scenario_hash(scenario))
            elif path.suffix.lower() == ".csv":
                try:
                    with path.open("r", encoding="utf-8-sig", newline="") as stream:
                        for row in csv.DictReader(stream):
                            for key in id_keys:
                                item = row.get(key)
                                if item:
                                    old_ids.add(item)
                except (OSError, UnicodeDecodeError, csv.Error):
                    continue
    return old_ids, old_semantic_hashes


def _deep_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _deep_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _deep_records(child)


def _apply_condition(scenario: dict[str, Any], condition: str) -> None:
    tasks = scenario["tasks"]
    delivery_tasks = [task for task in tasks if task.get("kind") == "delivery"]
    if condition == "carrier_competition":
        hidden = next(task for task in delivery_tasks if not task["known_initial"])
        known_food = next(
            task
            for task in delivery_tasks
            if task["known_initial"] and task["commodity"] == "food"
        )
        known_food["quantity"] = 16
        hidden["quantity"] = 16
    elif condition == "stock_competition":
        water_demand = sum(
            float(task["quantity"])
            for task in delivery_tasks
            if task["commodity"] == "water"
        )
        if water_demand <= 0:
            raise ValueError("stock-competition parent has no positive water demand")
        water_stock = 0.6 * water_demand
        for depot in scenario["depots"]:
            depot["stock"]["water"] = water_stock
    else:
        raise ValueError(f"unknown condition: {condition}")


def build_registry(
    output_root: Path,
    old_roots: list[Path],
    source_root: str | Path | None = None,
) -> dict[str, Any]:
    vendor_root = resolve_source_root(source_root)
    protocol = load_source_module("dataset_protocol", vendor_root)
    schema = load_source_module("scenario_schema", vendor_root)
    fixture_path = vendor_root / "fixtures" / "control.json"
    base = json.loads(fixture_path.read_text(encoding="utf-8"))
    old_ids, old_semantic_hashes = _read_old_ids_and_semantics(old_roots)

    pending: list[tuple[dict[str, Any], dict[str, Any], bytes]] = []
    seen_ids: set[str] = set()
    seen_semantics: set[str] = set()
    for split, total in SPLIT_COUNTS.items():
        per_condition = total // len(CONDITIONS)
        for condition in CONDITIONS:
            for index in range(per_condition):
                seed = derive_seed(split, condition, index)
                scenario = json.loads(json.dumps(base))
                varied = protocol._apply_common_variation(
                    scenario, seed, outside_commitment=False
                )
                if varied is not None:
                    scenario = varied
                _apply_condition(scenario, condition)

                parent_id = f"relief-n2-{split}-{condition}-{index:02d}"
                scenario["scenario_id"] = parent_id
                schema.validate_scenario(scenario)
                semantic_hash = semantic_scenario_hash(scenario)
                if parent_id in seen_ids or parent_id in old_ids:
                    raise ValueError(f"duplicate or reused parent id: {parent_id}")
                if semantic_hash in seen_semantics:
                    raise ValueError(f"duplicate scenario semantics: {parent_id}")
                if semantic_hash in old_semantic_hashes:
                    raise ValueError(
                        f"scenario semantics overlap prior data: {parent_id}"
                    )
                seen_ids.add(parent_id)
                seen_semantics.add(semantic_hash)

                scenario_bytes = (
                    json.dumps(
                        scenario,
                        sort_keys=True,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                ).encode("utf-8")
                relative_path = Path(split) / f"{parent_id}.json"
                row = {
                    "parent_id": parent_id,
                    "split": split,
                    "condition": condition,
                    "repeat": 0,
                    "seed": seed,
                    "semantic_sha256": semantic_hash,
                    "scenario_path": relative_path.as_posix(),
                    "content_sha256": sha256_bytes(scenario_bytes),
                }
                pending.append((row, scenario, scenario_bytes))

    expected_count = sum(SPLIT_COUNTS.values())
    if len(pending) != expected_count:
        raise AssertionError(f"built {len(pending)} scenarios, expected {expected_count}")

    for row, _scenario, scenario_bytes in pending:
        target = output_root / row["scenario_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(scenario_bytes)

    rows = [row for row, _scenario, _bytes in pending]
    vendor_files = {}
    for path in sorted(vendor_root.rglob("*")):
        if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
            continue
        if "__pycache__" in path.parts:
            continue
        vendor_files[path.relative_to(vendor_root).as_posix()] = sha256_bytes(
            path.read_bytes()
        )
    provenance_path = vendor_root / "SOURCE_PROVENANCE.json"
    source_provenance = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.is_file()
        else None
    )
    source_tree_digest = sha256_bytes(canonical_json(vendor_files))
    condition_counts = {
        split: dict(Counter(row["condition"] for row in rows if row["split"] == split))
        for split in SPLIT_COUNTS
    }
    manifest = {
        "registry_version": "relief-n2-scenario-registry/1",
        "seed_namespace": SEED_NAMESPACE,
        "split_counts": SPLIT_COUNTS,
        "condition_counts": condition_counts,
        "total_scenarios": len(rows),
        "old_parent_id_overlap_count": 0,
        "old_semantic_hash_overlap_count": 0,
        "within_registry_semantic_duplicates": 0,
        "policy_evaluation_performed": False,
        "source_protocol": "vendored relief_env_v2.dataset_protocol._apply_common_variation",
        "source_fixture": "vendor/relief_env_v2/fixtures/control.json",
        "source_provenance": source_provenance,
        "source_provenance_sha256": (
            sha256_bytes(provenance_path.read_bytes())
            if provenance_path.is_file()
            else None
        ),
        "vendor_source_tree_sha256": source_tree_digest,
        "vendor_file_sha256": vendor_files,
        "scenarios": rows,
    }
    (output_root / "registry.json").write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in manifest.items() if key != "scenarios"}
    summary["registry_sha256"] = sha256_bytes(canonical_json(manifest))
    summary["scenario_content_sha256"] = sha256_bytes(
        canonical_json([row["content_sha256"] for row in rows])
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--old-root",
        type=Path,
        action="append",
        required=True,
        help="N1 source/results roots scanned for parent IDs and semantic duplicates",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="optional relief_env_v2 source directory; defaults to the vendored copy",
    )
    args = parser.parse_args()
    summary = build_registry(args.output_root, args.old_root, args.source_root)
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
