"""Run the bounded synthetic G/G-WM smoke through the civilian PPOTrainer."""

from __future__ import annotations

import copy
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2].parent
ENGINEERING = ROOT / "development" / "ch2_disaster_relief_n2_v1" / "engineering"
CIVIL = ROOT / "development" / "ch2_disaster_relief_graph_v2"
PREPARATION = ROOT / "development" / "ch2_disaster_relief_n2_v1" / "preparation"
for location in (ENGINEERING, CIVIL):
    sys.path.insert(0, str(location))

from failure_export import write_records_atomically
from graph_policy import build_policy
from ppo_integration import CriticAugmentedPPOTrainer
from ppo_trainer import verify_next_update_equivalence
from world_model import (
    CriticAugmentedGraphPolicy,
    CriticOnlyGppoAdapter,
    DynamicConsequenceModel,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build_trainer(run_dir: Path, scenarios: list[dict]) -> CriticAugmentedPPOTrainer:
    torch.manual_seed(901)
    base_policy = build_policy("L1", 8201)
    torch.manual_seed(271828)
    world_model = DynamicConsequenceModel(5, 4, 5, hidden_dim=8)
    adapter = CriticOnlyGppoAdapter(hidden_dim=8)
    policy = CriticAugmentedGraphPolicy(base_policy, adapter, world_model)
    data_identity = hashlib.sha256(
        json.dumps(scenarios, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()
    return CriticAugmentedPPOTrainer(
        policy, variant="L1", seed=8201, scenarios=scenarios,
        data_hash=data_identity, package_root=CIVIL, run_dir=run_dir,
        allow_engineering_scenarios=True,
    )


def main() -> None:
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=PREPARATION / "engineering_node",
        help="write rollout/checkpoint/export artifacts beneath this directory",
    )
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture = CIVIL / "fixtures" / "control.json"
    base_scenario = json.loads(fixture.read_text(encoding="utf-8"))
    scenarios = [copy.deepcopy(base_scenario) for _ in range(4)]
    for index, scenario in enumerate(scenarios):
        scenario["scenario_id"] = f"n2-synthetic-{index}"

    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    original = build_trainer(output / "ppo_original", scenarios)
    first = original.train_round()
    checkpoint_path = Path(first["checkpoint"]["path"])
    rollout_records = [
        json.loads(line)
        for line in Path(first["rollout_path"]).read_text(encoding="utf-8").splitlines()
    ]

    bootstrap_probe = copy.deepcopy(rollout_records[0])
    bootstrap_probe["terminated"] = False
    bootstrap_probe["truncated"] = False
    bootstrap_probe["rollout_cut"] = False
    expected_bootstrap = float(original.policy.value(bootstrap_probe["next_policy_input"]).detach())
    original._attach_gae([bootstrap_probe])
    if not bootstrap_probe["rollout_cut"] or abs(bootstrap_probe["next_value"] - expected_bootstrap) > 1e-6:
        raise AssertionError("critic adapter bootstrap probe mismatch")

    equivalence = verify_next_update_equivalence(
        original,
        lambda: build_trainer(output / "ppo_restored", scenarios),
        checkpoint_path,
    )
    final_checkpoint = output / "ppo_original" / "checkpoints" / "round_0002.pt"
    export_identity = {"scope": "local_synthetic_engineering", "seed": 8201, "fixture": fixture.name}
    success_path = output / "normal_export.json"
    success = write_records_atomically(
        success_path, [first, equivalence], run_identity=export_identity,
        last_completed_update=32, checkpoint_path=final_checkpoint,
    )

    failure_path = output / "failed_export.json"

    def fail_second_record(record: dict) -> str:
        if record.get("id") == "injected_failure":
            raise RuntimeError("synthetic N2 export failure injection")
        return json.dumps(record, sort_keys=True, separators=(",", ":"))

    try:
        write_records_atomically(
            failure_path,
            [{"id": "completed_prefix"}, {"id": "injected_failure"}],
            run_identity=export_identity, last_completed_update=32,
            checkpoint_path=final_checkpoint, serializer=fail_second_record,
        )
    except RuntimeError as error:
        if str(error) != "synthetic N2 export failure injection":
            raise
    else:
        raise AssertionError("failure export injection unexpectedly succeeded")

    source_files = {
        "ppo_integration.py": ENGINEERING / "ppo_integration.py",
        "world_model.py": ENGINEERING / "world_model.py",
        "branching.py": ENGINEERING / "branching.py",
        "failure_export.py": ENGINEERING / "failure_export.py",
        "ppo_trainer.py": CIVIL / "ppo_trainer.py",
        "graph_policy.py": CIVIL / "graph_policy.py",
        "relief_env.py": CIVIL / "relief_env.py",
        "baselines.py": CIVIL / "baselines.py",
        "scenario_schema.py": CIVIL / "scenario_schema.py",
    }
    report = {
        "schema": "n2-local-ppo-engineering-smoke/1",
        "scope": "local synthetic G/G-WM engineering smoke only; not research collection or policy efficacy",
        "runtime": {"python": platform.python_version(), "torch": torch.__version__, "device": "cpu"},
        "input": {"fixture": str(fixture), "fixture_sha256": sha256_file(fixture), "synthetic_scenarios": len(scenarios)},
        "source_sha256": {name: sha256_file(path) for name, path in source_files.items()},
        "ppo": {
            "variant": "L1 actor with critic-only frozen synthetic WM adapter",
            "seed": 8201,
            "first_round_transitions": first["transition_count"],
            "first_round_optimizer_updates": first["optimizer_updates"],
            "first_round_max_initial_probability_ratio_error": first["max_initial_probability_ratio_error"],
            "minibatch_value_path": "civilian PPOTrainer.evaluate_batch -> CriticAugmentedGraphPolicy.evaluate_batch -> adapted critic value",
            "bootstrap_adapter_probe": {
                "rollout_cut": bootstrap_probe["rollout_cut"],
                "observed_next_value": bootstrap_probe["next_value"],
                "direct_adapter_value": expected_bootstrap,
            },
            "next_round_strict_restore": equivalence,
            "total_optimizer_updates_per_continuous_or_resumed_path": 32,
            "total_environment_transitions_per_continuous_or_resumed_path": 480,
            "combined_optimizer_updates_across_comparison_paths": 48,
            "combined_environment_transitions_across_comparison_paths": 720,
            "checkpoint_round_1": str(checkpoint_path),
            "checkpoint_round_2": str(final_checkpoint),
            "rollout_round_1": first["rollout_path"],
            "rollout_round_1_sha256": first["rollout_sha256"],
        },
        "exports": {
            "normal": success,
            "failure_receipt": str(failure_path.with_suffix(failure_path.suffix + ".failure.json")),
        },
        "measurement": {
            "wall_seconds_including_checkpoints_and_exports": time.perf_counter() - wall_start,
            "process_cpu_seconds_including_checkpoints_and_exports": time.process_time() - cpu_start,
        },
        "limitations": [
            "Synthetic control fixture repeated as four engineering episodes; not a parent-split WM dataset.",
            "The smoke runs one civilian PPO rollout/update round and the strict next-round comparison; it does not run the 40-epoch research WM fit or development prediction gate.",
            "Target-Linux runtime/resource caps remain unmeasured; this CPU measurement is local Windows engineering evidence.",
        ],
    }
    report_path = output / "N2_ENGINEERING_NODE_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "measurement": report["measurement"], "strict_restore_equivalent": equivalence["equivalent"], "optimizer_updates_per_path": 32, "transitions_per_path": 480, "combined_optimizer_updates": 48, "combined_transitions": 720}, sort_keys=True))


if __name__ == "__main__":
    main()
