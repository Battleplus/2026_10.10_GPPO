"""Stage the frozen N2 Linux acceptance package and print its manifest digest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SOURCE_MANIFEST = Path("development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/package-manifest.json")
STAGED_MANIFEST = Path("preparation/linux_acceptance/package-manifest.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve(strict=True)
    output = args.output_root.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise SystemExit("PACKAGE_SOURCE_AND_OUTPUT_MUST_BE_DISJOINT")
    if output.exists() and any(output.iterdir()):
        raise SystemExit("PACKAGE_OUTPUT_MUST_BE_EMPTY")

    source_manifest = source / SOURCE_MANIFEST
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if manifest.get("builder") != {
        "name": "package_n2_linux_acceptance.py",
        "version": "1.0.0",
    }:
        raise SystemExit("PACKAGE_BUILDER_IDENTITY_MISMATCH")
    files = manifest.get("files", [])
    expected_hashes = manifest.get("hashing", {}).get("file_sha256", {})
    if set(expected_hashes) != set(files):
        raise SystemExit("PACKAGE_MANIFEST_HASH_TABLE_INCOMPLETE")

    output.mkdir(parents=True, exist_ok=True)
    for relative in files:
        unresolved = source / relative
        if unresolved.is_symlink():
            raise SystemExit(f"PACKAGE_SOURCE_SYMLINK_FORBIDDEN:{relative}")
        src = unresolved.resolve(strict=True)
        if source not in src.parents or not src.is_file():
            raise SystemExit(f"PACKAGE_SOURCE_INVALID:{relative}")
        if sha256(src) != expected_hashes[relative]:
            raise SystemExit(f"PACKAGE_SOURCE_HASH_MISMATCH:{relative}")
        dst = output / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    staged_manifest = output / STAGED_MANIFEST
    staged_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_manifest, staged_manifest)

    for relative in files:
        if sha256(output / relative) != expected_hashes[relative]:
            raise SystemExit(f"PACKAGE_STAGED_HASH_MISMATCH:{relative}")
    print(json.dumps({
        "package_root": str(output),
        "manifest_path": str(staged_manifest),
        "manifest_sha256": sha256(staged_manifest),
        "file_count": len(files),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
