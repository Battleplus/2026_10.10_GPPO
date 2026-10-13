"""Write a scoped, read-only receipt for the existing old-data scanner."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCANNER_FUNCTION = "_read_old_ids_and_semantics"
DEFAULT_REGISTRY = Path(__file__).resolve().with_name("registry.json")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _sorted_set_hash(values: set[str]) -> str:
    canonical = json.dumps(
        sorted(values), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _normalise_values(values: Any) -> set[str]:
    return {str(value) for value in values if value is not None}


def _find_existing_scanner() -> tuple[Callable[..., tuple[set[str], set[str]]], Path]:
    module_dir = Path(__file__).resolve().parent
    matches: list[Path] = []
    for source_path in sorted(module_dir.glob("*.py")):
        if source_path.resolve() == Path(__file__).resolve():
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == SCANNER_FUNCTION
            for node in ast.walk(tree)
        ):
            matches.append(source_path)

    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one sibling definition of {SCANNER_FUNCTION}; "
            f"found {len(matches)}: {[path.name for path in matches]}"
        )

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    module_name = f"relief_adapter.data.{matches[0].stem}"
    module = importlib.import_module(module_name)
    scanner = getattr(module, SCANNER_FUNCTION, None)
    if not callable(scanner):
        raise RuntimeError(f"{module_name}.{SCANNER_FUNCTION} is not callable")
    return scanner, matches[0].resolve()


def _inventory_root(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    skipped_entries: list[dict[str, str]] = []
    parse_failures = 0
    parse_successes = 0

    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for directory in directories:
            child = current_path / directory
            if child.is_symlink():
                skipped_entries.append(
                    {
                        "path": child.relative_to(root).as_posix(),
                        "reason": "symlink_directory_not_followed",
                    }
                )
            else:
                kept_directories.append(directory)
        directories[:] = kept_directories

        for filename in filenames:
            path = current_path / filename
            suffix = path.suffix.lower()
            if suffix not in {".json", ".csv"}:
                continue
            relative_name = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                skipped_entries.append(
                    {"path": relative_name, "reason": "non_regular_file_not_read"}
                )
                continue

            record: dict[str, Any] = {
                "relative_path": relative_name,
                "format": suffix[1:],
                "sha256": None,
                "byte_count": None,
                "parse_status": "failed",
                "parse_error": None,
            }
            try:
                payload = path.read_bytes()
                record["sha256"] = _sha256_bytes(payload)
                record["byte_count"] = len(payload)
                decoded = payload.decode("utf-8-sig")
                if suffix == ".json":
                    json.loads(decoded)
                else:
                    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
                    for _ in reader:
                        pass
                record["parse_status"] = "ok"
                parse_successes += 1
            except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
                record["parse_error"] = f"{type(exc).__name__}: {exc}"
                parse_failures += 1
            files.append(record)

    files.sort(key=lambda item: item["relative_path"])
    skipped_entries.sort(key=lambda item: (item["path"], item["reason"]))
    return {
        "inventory_file_count": len(files),
        "json_file_count": sum(item["format"] == "json" for item in files),
        "csv_file_count": sum(item["format"] == "csv" for item in files),
        "parse_success_count": parse_successes,
        "parse_failure_count": parse_failures,
        "skipped_entry_count": len(skipped_entries),
        "skipped_entries": skipped_entries,
        "files": files,
    }


def _read_registry(path: Path) -> tuple[set[str], set[str], str]:
    payload = path.read_bytes()
    registry = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(registry, dict) or not isinstance(registry.get("scenarios"), list):
        raise ValueError("registry must be an object with a scenarios list")

    parent_ids: set[str] = set()
    semantic_hashes: set[str] = set()
    for row in registry["scenarios"]:
        if not isinstance(row, dict):
            raise ValueError("registry scenarios entries must be objects")
        parent_id = row.get("parent_id")
        semantic_hash = row.get("semantic_sha256")
        if parent_id is not None:
            parent_ids.add(str(parent_id))
        if semantic_hash is not None:
            semantic_hashes.add(str(semantic_hash))
    return parent_ids, semantic_hashes, _sha256_bytes(payload)


def _set_summary(values: set[str]) -> dict[str, Any]:
    return {"count": len(values), "sorted_set_sha256": _sorted_set_hash(values)}


def build_receipt(old_roots: list[Path], registry_path: Path) -> dict[str, Any]:
    roots: list[Path] = []
    for supplied_root in old_roots:
        root = supplied_root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)
        roots.append(root)

    registry = registry_path.expanduser().resolve(strict=True)
    if not registry.is_file():
        raise FileNotFoundError(registry)
    registry_parents, registry_semantics, registry_sha = _read_registry(registry)
    scanner, scanner_path = _find_existing_scanner()

    per_root: list[dict[str, Any]] = []
    union_ids: set[str] = set()
    union_semantics: set[str] = set()
    scanner_errors: list[dict[str, str]] = []

    for root in roots:
        inventory = _inventory_root(root)
        item: dict[str, Any] = {
            "root_path": os.path.normcase(str(root)),
            "inventory": inventory,
        }
        try:
            old_ids, old_semantics = scanner([root])
            ids = _normalise_values(old_ids)
            semantics = _normalise_values(old_semantics)
            union_ids.update(ids)
            union_semantics.update(semantics)
            item["extracted"] = {
                "old_ids": _set_summary(ids),
                "old_semantics": _set_summary(semantics),
            }
            item["registry_intersection"] = {
                "parent_ids": _set_summary(ids & registry_parents),
                "semantic_hashes": _set_summary(semantics & registry_semantics),
            }
        except Exception as exc:
            item["scan_error"] = f"{type(exc).__name__}: {exc}"
            scanner_errors.append(
                {"root_path": os.path.normcase(str(root)), "error": item["scan_error"]}
            )
        per_root.append(item)

    overall: dict[str, Any] = {}
    try:
        overall_ids_raw, overall_semantics_raw = scanner(roots)
        overall_ids = _normalise_values(overall_ids_raw)
        overall_semantics = _normalise_values(overall_semantics_raw)
        overall = {
            "old_ids": _set_summary(overall_ids),
            "old_semantics": _set_summary(overall_semantics),
            "registry_intersection": {
                "parent_ids": _set_summary(overall_ids & registry_parents),
                "semantic_hashes": _set_summary(
                    overall_semantics & registry_semantics
                ),
            },
            "matches_union_of_per_root_sets": (
                overall_ids == union_ids and overall_semantics == union_semantics
            ),
        }
    except Exception as exc:
        overall = {"scan_error": f"{type(exc).__name__}: {exc}"}
        scanner_errors.append({"scope": "all_roots", "error": overall["scan_error"]})

    receipt_path = Path(__file__).resolve()
    scanner_sha, _ = _sha256_file(scanner_path)
    receipt_script_sha, _ = _sha256_file(receipt_path)
    status = "complete" if not scanner_errors else "partial_with_scan_errors"
    return {
        "receipt_version": 1,
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_statement": "This receipt covers only the explicitly supplied old_roots. It does not claim that every historical data source was available or scanned.",
        "old_roots": per_root,
        "overall": overall,
        "overall_per_root_union": {
            "old_ids": _set_summary(union_ids),
            "old_semantics": _set_summary(union_semantics),
        },
        "registry": {
            "path": os.path.normcase(str(registry)),
            "sha256": registry_sha,
            "scenario_count": len(registry_parents),
            "distinct_semantic_hash_count": len(registry_semantics),
            "field_names": {
                "parent_id": "parent_id",
                "semantic_hash": "semantic_sha256",
            },
        },
        "source_identity": {
            "existing_scanner_function": SCANNER_FUNCTION,
            "existing_scanner_source_path": os.path.normcase(str(scanner_path)),
            "existing_scanner_source_sha256": scanner_sha,
            "receipt_generator_source_path": os.path.normcase(str(receipt_path)),
            "receipt_generator_source_sha256": receipt_script_sha,
        },
        "scanner_errors": scanner_errors,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--old-root",
        action="append",
        nargs="+",
        required=True,
        type=Path,
        help="Old-data roots to scan; pass several paths or repeat this option.",
    )
    parser.add_argument(
        "--registry", type=Path, default=DEFAULT_REGISTRY, help="Current registry JSON."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "reports" / "old-data-scan-receipt.json",
        help="Receipt output path.",
    )
    args = parser.parse_args()

    roots = [root for root_group in args.old_root for root in root_group]
    receipt = build_receipt(roots, args.registry)
    _atomic_write_json(args.output.expanduser().resolve(), receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "output": str(args.output.expanduser().resolve()),
                "roots": len(receipt["old_roots"]),
                "scanner_errors": len(receipt["scanner_errors"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if receipt["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
