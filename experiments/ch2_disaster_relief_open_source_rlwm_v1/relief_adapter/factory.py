"""Portable factory that binds the adapter to the vendored environment source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .replay_adapter import ReplayReliefAdapter
from .vendor_source import load_source_module, resolve_source_root, source_tree_sha256


def make_relief_adapter(
    scenario: dict[str, Any],
    source_root: str | Path | None = None,
) -> ReplayReliefAdapter:
    """Construct a relief environment from ``source_root`` and wrap it.

    ``source_root`` may name either the ``relief_env_v2`` package directory or
    its parent directory. When omitted, the frozen in-package vendor is used.
    """
    resolved_root = resolve_source_root(source_root)
    env_module = load_source_module("relief_env", resolved_root)
    env_class = getattr(env_module, "ReliefEnv", None)
    if env_class is None:
        raise ImportError(f"ReliefEnv class not found in {env_module.__file__}")
    adapter = ReplayReliefAdapter(env_class(scenario))
    adapter.source_root = str(resolved_root)
    adapter.source_tree_sha256 = source_tree_sha256(resolved_root)
    return adapter


__all__ = ["make_relief_adapter"]

