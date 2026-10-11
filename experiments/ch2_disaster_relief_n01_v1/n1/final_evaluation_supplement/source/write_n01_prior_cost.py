from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "prior_n01_r1"
EVIDENCE = [
    "resource-ledger.jsonl",
    "runtime_admission.json",
    "budget_freeze.json",
    "guardians/01-admission.json",
    "guardians/02-engineering_smoke.json",
    "receipts/01-admission.json",
    "receipts/02-engineering_smoke.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    ledger_path = HISTORY / "resource-ledger.jsonl"
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    stage_costs: dict[str, dict[str, float]] = {}
    for row in rows:
        stage = row["stage"]
        cost = stage_costs.setdefault(stage, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
        cost["wall_seconds"] += float(row["wall_seconds"])
        cost["cpu_seconds"] += float(row["cpu_seconds"])
    evidence = []
    for relative in EVIDENCE:
        path = HISTORY / relative
        evidence.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
        })
    receipt = {
        "schema": "n01-prior-resource-cost/1",
        "status": "frozen",
        "prior_identity": "ch2-disaster-relief-n01-v1-20261011",
        "description": "Measured admission and engineering-smoke resources from the previous N01 target run. The old six-run training budget freeze is retained as history only and is not applicable to the revised identity.",
        "ledger_path": (HISTORY / "resource-ledger.jsonl").relative_to(ROOT).as_posix(),
        "stage_costs": stage_costs,
        "total_wall_seconds": sum(item["wall_seconds"] for item in stage_costs.values()),
        "total_cpu_seconds": sum(item["cpu_seconds"] for item in stage_costs.values()),
        "evidence_files": evidence,
    }
    (ROOT / "PRIOR_RESOURCE_COST.json").write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
