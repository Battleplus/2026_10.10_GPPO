from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = next(parent for parent in HERE.parents if (parent / ".git").exists())
BASE = REPO / "experiments/ch2_disaster_relief_n01_v1/n1/prior_cost_repair_r2/package"
OVERRIDES = HERE / "release-overrides"
HASHES = HERE / "ARTIFACT_HASHES.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    local = json.loads(HASHES.read_text(encoding="utf-8"))
    entries = []
    for key, expected in sorted(local["files"].items()):
        if not key.startswith("release/"):
            continue
        relative = key.removeprefix("release/")
        base = BASE / relative
        override = OVERRIDES / relative
        if base.is_file() and sha(base) == expected:
            source = {"kind": "existing-tracked-file", "path": base.relative_to(REPO).as_posix()}
        elif override.is_file() and sha(override) == expected:
            source = {"kind": "new-overlay-file", "path": override.relative_to(HERE).as_posix()}
        else:
            raise SystemExit(f"cannot resolve verified release input: {relative}")
        entries.append({"release_path": relative, "sha256": expected, "source": source})
    payload = {
        "schema": "n01-r2-formal-repair-release-overlay/1",
        "evaluation_identity": json.loads((HERE / "release-overrides/N01_FULL_EVALUATION_IDENTITY.json").read_text(encoding="utf-8"))["evaluation_identity"],
        "entry_count": len(entries),
        "baseline_package": BASE.relative_to(REPO).as_posix(),
        "release_artifact_hashes": "ARTIFACT_HASHES.json",
        "entries": entries,
    }
    (HERE / "RELEASE_OVERLAY_INDEX.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
