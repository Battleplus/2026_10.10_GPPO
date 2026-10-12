from __future__ import annotations

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


source = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
package = root / "package"
actual = {path.relative_to(package).as_posix(): path for path in package.rglob("*") if path.is_file()}
if set(actual) != set(source["files"]):
    raise SystemExit("package file inventory differs from source-manifest.json")
for relative, record in source["files"].items():
    if sha(actual[relative]) != record["sha256"] or actual[relative].stat().st_size != record["bytes"]:
        raise SystemExit(f"package hash or size mismatch: {relative}")

tar = root / "n01-prior-cost-repair-r2-20261012.tar.gz"
tar_manifest = json.loads((root / "tar-sha256-manifest.json").read_text(encoding="utf-8"))
if sha(tar) != tar_manifest["sha256"]:
    raise SystemExit("authoritative package tar SHA-256 mismatch")

fixed_r1 = {
    "systemd-settlement.json": "95c5b18b454c04e3db51d5831f0c3b2e0f535e499ee19451628f7f68e27c0c42",
    "journal.txt": "7a6678807de343ec25598fc0c807758441f0130cc2251633964dbb51f0ff5b00",
    "N1_TECHNICAL_STOP_REPORT_CN.md": "e524ba49926c827b4b0cae4a7ee4b677c48df2a734ed9d632486fe11c688ebb4",
}
for name, digest in fixed_r1.items():
    if sha(root / "r1_stop_evidence" / name) != digest:
        raise SystemExit(f"r1 evidence does not match independent hash: {name}")

files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "release-file-manifest.json")
manifest = {
    "schema": "n01-github-release-draft-manifest/1",
    "status": "draft-not-published",
    "package_budget_status": "proposed",
    "external_budget_request_status": "NOT_APPROVED",
    "package_file_count": len(actual),
    "r1_stop_evidence_file_count": sum(1 for path in (root / "r1_stop_evidence").rglob("*") if path.is_file()),
    "files": {
        path.relative_to(root).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
        for path in files
    },
}
manifest["file_count_excluding_manifest"] = len(files)
(root / "release-file-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"package_files": len(actual), "release_files_excluding_manifest": len(files), "r1_hashes_match": len(fixed_r1), "tar_sha256": sha(tar), "status": "verified"}, indent=2))
