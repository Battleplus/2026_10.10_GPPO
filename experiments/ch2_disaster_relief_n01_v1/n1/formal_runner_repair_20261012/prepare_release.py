from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "release"
OLD = "ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012"
NEW = "ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def canonical_sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def main() -> None:
    old_package = ROOT.parent / "prior_cost_repair_r2" / "package"
    if not (PKG / "n01_full_evaluator.py").is_file():
        raise SystemExit("release copy missing; copy the frozen package before preparing")

    evaluator = PKG / "n01_full_evaluator.py"
    src = evaluator.read_text(encoding="utf-8")
    if src.count(NEW) != 1:
        if src.count(OLD) != 1:
            raise SystemExit("expected exactly one old or repaired evaluator identity constant")
        evaluator.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\n")

    old_unit = "n01-full-evaluation-r2-prior-evidence-20261012"
    new_unit = "n01-full-evaluation-r2-formal-repair-v1-20261012"
    for name in ("n01_full_systemd_runner.sh", "n01_full_systemd_settle.py", "n01_full_evaluation.service", "n01_systemd_contract_probe.service"):
        path = PKG / name
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(OLD, NEW).replace(old_unit, new_unit), encoding="utf-8", newline="\n")

    identity_path = PKG / "N01_FULL_EVALUATION_IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["evaluation_identity"] = NEW
    identity["status"] = "proposed-new-repair-identity"
    identity["current_source_hashes"] = {name: digest(PKG / name) for name in identity["current_source_hashes"]}
    write_json(identity_path, identity)
    identity_sha = digest(identity_path)

    budget_path = PKG / "n01_full_evaluation_stage_budget.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    budget["evaluation_identity"] = NEW
    budget["approval_reference"] = None
    budget["approved_by"] = None
    budget["status"] = "proposed"
    write_json(budget_path, budget)
    budget_sha = digest(budget_path)

    identity["current_source_hashes"]["n01_full_evaluation_stage_budget.json"] = budget_sha
    identity["stage_budget_sha256"] = budget_sha
    write_json(identity_path, identity)
    identity_sha = digest(identity_path)

    plan_path = PKG / "static_plan_r2.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["evaluation_identity"] = NEW
    plan["identity_sha256"] = identity_sha
    plan["identity_manifest_sha256"] = identity_sha
    plan["stage_budget_sha256"] = budget_sha
    plan["current_source_hashes"] = identity["current_source_hashes"]
    plan.pop("plan_sha256", None)
    plan_sha = canonical_sha(plan)
    plan["plan_sha256"] = plan_sha
    write_json(plan_path, plan)
    reader_sha = digest(plan_path)

    # Verify every source entry now matches the copied release bytes.
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    actual = {name: digest(PKG / name) for name in identity["current_source_hashes"]}
    if actual != identity["current_source_hashes"]:
        raise SystemExit("release source hash inventory failed")
    request = {
        "schema": "n01-stage-budget-approval-request/1",
        "evaluation_identity": NEW,
        "stage_budget_sha256": budget_sha,
        "reader_sha256": reader_sha,
        "plan_sha256": plan_sha,
        "status": "NOT_APPROVED",
        "approval_reference": None,
        "approved_by": None,
        "formal_start_performed": False,
        "note": "Request only; the consumed prior identity and authorization are not reusable.",
    }
    write_json(ROOT / "N01_FULL_EVALUATION_BUDGET_APPROVAL_REQUEST.json", request)
    expected = {
        "evaluation_identity": NEW,
        "identity_sha256": identity_sha,
        "stage_budget_sha256": budget_sha,
        "reader_sha256": reader_sha,
        "plan_sha256": plan_sha,
        "package_source_count": len(actual),
        "package_source_hashes": actual,
        "scenario_manifest_sha256": digest(PKG / "n01_scenarios/scenario_manifest.json"),
        "checkpoint_manifest_sha256": digest(PKG / "n01_fixed_checkpoint_manifest.json"),
        "checkpoint_hashes": identity["checkpoint_sha256"],
        "unit_name": "n01-full-evaluation-r2-formal-repair-v1-20261012.service",
    }
    write_json(ROOT / "FROZEN_BINDINGS.json", expected)


if __name__ == "__main__":
    main()
