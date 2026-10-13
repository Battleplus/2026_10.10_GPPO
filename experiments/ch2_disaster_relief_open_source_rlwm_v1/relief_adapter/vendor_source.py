"""Load the vendored or an explicitly supplied relief_env_v2 source tree."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


REQUIRED_SOURCE_FILES = (
    "__init__.py",
    "baselines.py",
    "chapter1_adapter.py",
    "relief_env.py",
    "scenario_schema.py",
    "stable_identity.py",
    "dataset_protocol.py",
    "graph_policy.py",
    "literal_graph_ops.py",
    "ppo_trainer.py",
    "independent_audit.py",
)


def resolve_source_root(source_root: str | Path | None = None) -> Path:
    if source_root is None:
        root = Path(__file__).resolve().parents[1] / "vendor" / "relief_env_v2"
    else:
        root = Path(source_root).expanduser().resolve()
        if (root / "relief_env_v2" / "__init__.py").is_file():
            root = root / "relief_env_v2"
    missing = [name for name in REQUIRED_SOURCE_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"relief_env_v2 source root {root} missing required files: {missing}"
        )
    return root


def source_file_hashes(source_root: str | Path | None = None) -> dict[str, str]:
    root = resolve_source_root(source_root)
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
            continue
        if "__pycache__" in path.parts:
            continue
        result[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result


def source_tree_sha256(source_root: str | Path | None = None) -> str:
    payload = json.dumps(
        source_file_hashes(source_root), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_source_module(
    module_name: str,
    source_root: str | Path | None = None,
) -> ModuleType:
    """Import a module with an isolated package name to avoid path collisions."""
    if module_name.startswith(".") or "." in module_name:
        raise ValueError("module_name must be a direct relief_env_v2 module name")
    root = resolve_source_root(source_root)
    package_digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    package_name = f"_relief_env_v2_{package_digest}"
    if package_name not in sys.modules:
        init_path = root / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            package_name,
            init_path,
            submodule_search_locations=[str(root)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load relief_env_v2 package from {root}")
        package = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = package
        spec.loader.exec_module(package)
    return importlib.import_module(f"{package_name}.{module_name}")
