from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    final_manifest_path = ROOT / "final_checkpoints.json"
    index_path = ROOT / "checkpoint_index.csv"
    final_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        index = {row["run_id"]: row for row in csv.DictReader(handle)}
    if final_manifest.get("common_rounds") != 32 or final_manifest.get("run_count") != 6:
        raise ValueError("source final-checkpoint manifest does not bind six round-32 checkpoints")
    checkpoints = []
    provenance = None
    for entry in final_manifest["runs"]:
        run_id = entry["run_id"]
        source_row = index.get(run_id)
        if source_row is None:
            raise ValueError(f"checkpoint index is missing {run_id}")
        filename = f"{run_id}.pt"
        checkpoint_path = ROOT / "fixed_checkpoints" / filename
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if sha256(checkpoint_path) != entry["sha256"] or entry["sha256"] != source_row["sha256"]:
            raise ValueError(f"checkpoint artifact hash mismatch: {run_id}")
        if payload.get("variant") != entry["variant"] or int(payload.get("seed", -1)) != int(entry["seed"]):
            raise ValueError(f"checkpoint metadata mismatch: {run_id}")
        if provenance is None:
            provenance = payload["source_hashes"]
        elif payload["source_hashes"] != provenance:
            raise ValueError("source checkpoint artifacts disagree on historical code provenance")
        checkpoints.append({
            "run_id": run_id,
            "file": filename,
            "sha256": entry["sha256"],
            "model_state_sha256": entry["model_state_sha256"],
            "optimizer_state_sha256": entry["optimizer_state_sha256"],
            "architecture_evidence": entry["architecture_evidence"],
            "source_index_sha256": source_row["sha256"],
        })
    receipt = {
        "schema": "n01-frozen-checkpoints/1",
        "source_release": "research-executions/ch2-disaster-relief-graph-v2-20261011",
        "source_final_checkpoints_sha256": sha256(final_manifest_path),
        "source_checkpoint_index_sha256": sha256(index_path),
        "source_evidence_archive_sha256": "9259d39d8c8ec1950b2f6b27376c30068594f8e39ac6e0e4b055a065d296e3c3",
        "input_registry_sha256": final_manifest["input_registry_sha256"],
        "common_rounds": 32,
        "historical_source_hashes": provenance,
        "checkpoints": checkpoints,
    }
    (ROOT / "n01_fixed_checkpoint_manifest.json").write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
