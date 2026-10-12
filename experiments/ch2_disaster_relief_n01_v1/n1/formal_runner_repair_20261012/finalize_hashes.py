from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    overlay = json.loads((ROOT / "RELEASE_OVERLAY_INDEX.json").read_text(encoding="utf-8"))
    release_files = {
        "release/" + entry["release_path"]: entry["sha256"]
        for entry in overlay["entries"]
    }
    archive_files = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.name != "PUBLIC_ARCHIVE_HASH_INDEX.json":
            archive_files[rel] = sha(path)
    release_payload = {
        "schema": "n01-r2-formal-runner-repair-hashes/1",
        "hash_algorithm": "sha256",
        "self_hash_included": False,
        "file_count": len(release_files),
        "files": release_files,
    }
    archive_payload = {
        "schema": "n01-public-archive-hashes/1",
        "hash_algorithm": "sha256",
        "self_hash_included": False,
        "file_count": len(archive_files),
        "files": archive_files,
    }
    (ROOT / "ARTIFACT_HASHES.json").write_text(json.dumps(release_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (ROOT / "PUBLIC_ARCHIVE_HASH_INDEX.json").write_text(json.dumps(archive_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
