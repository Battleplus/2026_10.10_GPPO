"""Bind the exact package source map and deployment payload archive."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


def source_identity_sha256(package_root: Path) -> str:
    package_root = package_root.resolve(strict=True)
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from ppo_trainer import source_identity

    identity = source_identity(package_root)
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_deployment_archive(
    release_root: Path,
    files: Iterable[Path],
    archive_path: Path,
) -> str:
    release_root = release_root.resolve(strict=True)
    archive_path = archive_path.resolve(strict=False)
    if archive_path.exists():
        raise FileExistsError(f"deployment archive already exists: {archive_path}")

    entries: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for path in files:
        candidate = Path(path)
        if candidate.is_symlink():
            raise ValueError(f"deployment file is symlinked: {candidate}")
        path = candidate.resolve(strict=True)
        if not path.is_file() or release_root not in path.parents:
            raise ValueError(f"deployment file is invalid or outside release root: {path}")
        relative = path.relative_to(release_root).as_posix()
        if relative in seen:
            raise ValueError(f"duplicate deployment archive member: {relative}")
        seen.add(relative)
        entries.append((relative, path))
    if not entries:
        raise ValueError("deployment archive cannot be empty")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=archive_path.name + ".",
        suffix=".tmp",
        dir=archive_path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, path in sorted(entries):
                archive.write(path, arcname=relative)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(archive_path)
        return digest
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
