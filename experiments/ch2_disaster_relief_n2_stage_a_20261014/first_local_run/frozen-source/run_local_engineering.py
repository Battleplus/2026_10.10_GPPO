from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "LOCAL_ENGINEERING_BUDGET.json"
PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
ENGINEERING = ROOT / "references" / "existing_n2"
CIVIL = ROOT / "references" / "civil"
sys.path[:0] = [str(ROOT), str(ENGINEERING), str(CIVIL)]

from baselines import choose_step_c1_actions
from graph_policy import build_policy
from ppo_integration import CriticAugmentedPPOTrainer
from ppo_trainer import PPOTrainer, verify_next_update_equivalence
from relief_env import ReliefEnv
from references.existing_n2.tests.test_branching import opportunity_scenario
from branching import capture_snapshot, run_synthetic_candidate_pair
from world_model import (
    CriticAugmentedGraphPolicy,
    CriticOnlyGppoAdapter,
    DynamicConsequenceModel,
    EngineeringTrainer,
    public_branch_batch,
    _tensor_state_digest,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()


def build_ppo(
    run_dir: Path, scenarios: list[dict], wm_state: dict[str, torch.Tensor], model_hook=None,
) -> CriticAugmentedPPOTrainer:
    torch.manual_seed(901)
    base_policy = build_policy("L1", 8201)
    wm = DynamicConsequenceModel(5, 4, 5, hidden_dim=8)
    wm.load_state_dict(wm_state, strict=True)
    torch.manual_seed(271828)
    adapter = CriticOnlyGppoAdapter(hidden_dim=8)
    policy = CriticAugmentedGraphPolicy(base_policy, adapter, wm)
    data_hash = canonical_digest(scenarios)
    trainer = CriticAugmentedPPOTrainer(
        policy, variant="L1", seed=8201, scenarios=scenarios,
        data_hash=data_hash, package_root=CIVIL, run_dir=run_dir,
        allow_engineering_scenarios=True,
    )
    trainer.optimizer._n2_kind = "ppo"
    if model_hook is not None:
        model_hook(trainer.policy.world_model, "ppo_critic")
    return trainer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    output_writes = [0]
    output_root_text = str(output).casefold()
    if PROFILE.get("status") != "AUTHORIZED_LOCAL_ENGINEERING_ONLY":
        raise RuntimeError("LOCAL_PROFILE_STATUS_INVALID")
    profile_hash = sha256_file(PROFILE_PATH)
    source_files = [
        ROOT / "n2_contracts.py", ENGINEERING / "branching.py", ENGINEERING / "world_model.py",
        ENGINEERING / "ppo_integration.py", ROOT / "references" / "existing_n2" / "tests" / "test_branching.py",
        CIVIL / "fixtures" / "control.json", CIVIL / "relief_env.py", CIVIL / "baselines.py",
        CIVIL / "scenario_schema.py", CIVIL / "graph_policy.py", CIVIL / "ppo_trainer.py",
        Path(__file__).resolve(), ROOT / "run_local_engineering_watchdog.py",
    ]
    source_hashes_before = {str(path.relative_to(ROOT)): sha256_file(path) for path in source_files}
    counters = {
        "environment_steps": 0, "steps_by_phase": {}, "episode_constructions": 0,
        "ppo_episodes": 0, "wm_optimizer_steps": 0, "ppo_optimizer_steps": 0,
        "checkpoint_reads": 0, "checkpoint_writes": 0, "wm_forwards": 0, "wm_candidate_rows": 0,
    }
    phase = ["base_scan"]

    def audit_io(event, values):
        if event == "open" and values:
            path = str(values[0]).casefold()
            mode = values[1] if len(values) > 1 else None
            if path.startswith(output_root_text) and isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                output_writes[0] += 1
                if output_writes[0] > PROFILE["runtime"]["output_write_operations_max"]:
                    raise RuntimeError("LOCAL_OUTPUT_WRITE_CAP")
        elif event in {"os.rename", "os.remove"} and values:
            if any(str(value).casefold().startswith(output_root_text) for value in values[:2]):
                output_writes[0] += 1
                if output_writes[0] > PROFILE["runtime"]["output_write_operations_max"]:
                    raise RuntimeError("LOCAL_OUTPUT_WRITE_CAP")
        elif event in {"subprocess.Popen", "os.system", "os.spawn", "os.fork", "os.forkpty", "os.posix_spawn"}:
            raise RuntimeError("LOCAL_WORKER_PROCESS_SPAWN_FORBIDDEN")

    sys.addaudithook(audit_io)
    original_env_init = ReliefEnv.__init__
    original_env_reset = ReliefEnv.reset
    original_env_step = ReliefEnv.step

    def counted_init(self, *values, **kwargs):
        counters["episode_constructions"] += 1
        if counters["episode_constructions"] > PROFILE["work_caps"]["episode_constructions_max"]:
            raise RuntimeError("EPISODE_CONSTRUCTION_CAP")
        return original_env_init(self, *values, **kwargs)

    def counted_reset(self, *values, **kwargs):
        if phase[0] == "ppo_critic":
            counters["ppo_episodes"] += 1
            if counters["ppo_episodes"] > PROFILE["work_caps"]["ppo_rollout_episodes_max"]:
                raise RuntimeError("PPO_ROLLOUT_EPISODE_CAP")
        return original_env_reset(self, *values, **kwargs)

    def counted_step(self, *values, **kwargs):
        caps = PROFILE["work_caps"]
        phase_cap = {
            "base_scan": caps["base_rollout_steps_max"],
            "branches": caps["branch_steps_max"],
            "ppo_critic": caps["ppo_environment_steps_max"],
        }.get(phase[0])
        if counters["environment_steps"] >= caps["total_environment_steps_max"]:
            raise RuntimeError("TOTAL_ENVIRONMENT_STEP_CAP")
        if phase_cap is not None and counters["steps_by_phase"].get(phase[0], 0) >= phase_cap:
            raise RuntimeError(f"{phase[0].upper()}_ENVIRONMENT_STEP_CAP")
        counters["environment_steps"] += 1
        step_phase = phase[0]
        counters["steps_by_phase"][step_phase] = counters["steps_by_phase"].get(step_phase, 0) + 1
        return original_env_step(self, *values, **kwargs)

    original_policy_input = ReliefEnv.policy_input

    ReliefEnv.__init__, ReliefEnv.reset, ReliefEnv.step = counted_init, counted_reset, counted_step

    original_adam_step = torch.optim.Adam.step

    def counted_adam_step(self, *values, **kwargs):
        kind = getattr(self, "_n2_kind", None)
        if kind == "wm":
            cap = PROFILE["work_caps"]["wm_optimizer_steps_max"]
            key = "wm_optimizer_steps"
        elif kind == "ppo":
            cap = PROFILE["work_caps"]["ppo_optimizer_steps_max"]
            key = "ppo_optimizer_steps"
        else:
            return original_adam_step(self, *values, **kwargs)
        if counters[key] >= cap:
            raise RuntimeError(f"{key.upper()}_CAP")
        counters[key] += 1
        return original_adam_step(self, *values, **kwargs)

    torch.optim.Adam.step = counted_adam_step

    def checkpoint_count(kind):
        counters[f"checkpoint_{kind}"] += 1
        if counters["checkpoint_reads"] + counters["checkpoint_writes"] > PROFILE["runtime"]["checkpoint_reads_and_writes_max"]:
            raise RuntimeError("CHECKPOINT_OPERATION_CAP")

    def wrap_checkpoint(cls, name, kind):
        original = getattr(cls, name)

        def wrapped(self, *values, **kwargs):
            checkpoint_count(kind)
            return original(self, *values, **kwargs)

        setattr(cls, name, wrapped)

    wrap_checkpoint(EngineeringTrainer, "save_checkpoint", "writes")
    wrap_checkpoint(EngineeringTrainer, "restore_checkpoint", "reads")
    wrap_checkpoint(PPOTrainer, "save_checkpoint", "writes")
    wrap_checkpoint(PPOTrainer, "restore_checkpoint", "reads")
    torch.set_num_threads(1)
    wall_start, cpu_start = time.perf_counter(), time.process_time()

    fixture_path = CIVIL / "fixtures" / "control.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    scenario = opportunity_scenario(fixture)
    env = ReliefEnv(copy.deepcopy(scenario))
    env.reset("C1")
    snapshot_json = None
    max_catalog = 0
    base_steps = 0
    while not env._terminal:
        observation = env.public_observation()
        candidates = env.candidates()
        if len(candidates) > PROFILE["work_caps"]["candidate_catalog_cap_including_noop"]:
            raise RuntimeError("COMPLETE_CATALOG_EXCEEDS_FROZEN_CAP")
        max_catalog = max(max_catalog, len(candidates))
        if env.time == 8:
            snapshot_json = capture_snapshot(env, parent_id="n2-local-engineering", repeat=0, window_id="t8")
        actions = choose_step_c1_actions(observation, candidates)
        env.step([item["id"] for item in actions] + ["NOOP"] if actions else ["NOOP"])
        base_steps += 1
    if snapshot_json is None:
        raise RuntimeError("T8_SNAPSHOT_NOT_CAPTURED")

    phase[0] = "branches"
    source = ReliefEnv(copy.deepcopy(scenario))
    source.reset("C1")
    for _ in range(8):
        observation = source.public_observation()
        actions = choose_step_c1_actions(observation, source.candidates())
        source.step([item["id"] for item in actions] + ["NOOP"] if actions else ["NOOP"])
    catalog = source.candidates()
    candidate_ids = [item["id"] for item in catalog]
    if len(candidate_ids) != len(set(candidate_ids)) or candidate_ids.count("NOOP") != 1:
        raise RuntimeError("COMPLETE_CATALOG_IDENTITY_INVALID")
    if len(candidate_ids) > PROFILE["work_caps"]["candidate_catalog_cap_including_noop"]:
        raise RuntimeError("BRANCH_CATALOG_CAP")
    records = [run_synthetic_candidate_pair(snapshot_json, candidate_id) for candidate_id in candidate_ids]
    records_path = output / "branch_records.jsonl"
    with records_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    policy_input = source.policy_input()
    batch = public_branch_batch(
        policy_input, records, window_id=("n2-local-engineering", 0, "t8"),
    )

    torch.manual_seed(410)
    wm = DynamicConsequenceModel(5, 4, 5, hidden_dim=8)
    data_identity = canonical_digest({"fixture_sha256": sha256_file(fixture_path), "records": records})
    wm_trainer = EngineeringTrainer(wm, data_identity=data_identity)
    wm_trainer.optimizer._n2_kind = "wm"
    wm_trace = {"wm_train": 0, "resume_audit": 0, "inference": 0, "ppo_critic": 0}
    candidate_samples = {key: 0 for key in wm_trace}

    def count_forward(_module, inputs):
        rows = int(inputs[1].shape[0] * inputs[1].shape[1])
        if counters["wm_forwards"] >= PROFILE["work_caps"]["world_model_forwards_max"]:
            raise RuntimeError("WM_FORWARD_CAP")
        if counters["wm_candidate_rows"] + rows > PROFILE["work_caps"]["world_model_candidate_sample_evaluations_max"]:
            raise RuntimeError("WM_CANDIDATE_SAMPLE_CAP")
        wm_trace[phase[0]] += 1
        candidate_samples[phase[0]] += rows
        counters["wm_forwards"] += 1
        counters["wm_candidate_rows"] += rows

    def attach_model_hook(model, name):
        model.register_forward_pre_hook(count_forward)

    phase[0] = "wm_train"
    attach_model_hook(wm, "wm_train")
    wm_updates = [wm_trainer.update(batch) for _ in range(10)]
    wm_checkpoint = output / "wm-checkpoint.pt"
    wm_trainer.save_checkpoint(wm_checkpoint)
    restored_wm = DynamicConsequenceModel(5, 4, 5, hidden_dim=8)
    restored_wm_trainer = EngineeringTrainer(restored_wm, data_identity=data_identity)
    restored_wm_trainer.optimizer._n2_kind = "wm"
    attach_model_hook(restored_wm, "resume_audit")
    restored_wm_trainer.restore_checkpoint(wm_checkpoint)
    phase[0] = "resume_audit"
    wm_trainer.update(batch)
    restored_wm_trainer.update(batch)
    wm_equivalent = _tensor_state_digest(wm.state_dict()) == _tensor_state_digest(restored_wm.state_dict())
    if not wm_equivalent:
        raise RuntimeError("WM_NEXT_UPDATE_RESTORE_MISMATCH")
    phase[0] = "inference"
    with torch.no_grad():
        inputs = batch["inputs"]
        wm(inputs["context"], inputs["candidate_features"], inputs["task_features"],
           inputs["candidate_mask"], inputs["task_mask"], inputs["binding"])
    wm_frozen_checkpoint = output / "wm-frozen-checkpoint.pt"
    wm_trainer.save_checkpoint(wm_frozen_checkpoint)

    scenarios = []
    for index in range(4):
        item = copy.deepcopy(scenario)
        item["scenario_id"] = f"n2-local-ppo-{index}"
        scenarios.append(item)
    phase[0] = "ppo_critic"
    first = build_ppo(output / "ppo-original", scenarios, wm.state_dict(), attach_model_hook)
    first_result = first.train_round()
    checkpoint = Path(first_result["checkpoint"]["path"])
    equivalence = verify_next_update_equivalence(
        first, lambda: build_ppo(output / "ppo-restored", scenarios, wm.state_dict(), attach_model_hook), checkpoint,
    )
    if not equivalence.get("equivalent"):
        raise RuntimeError("PPO_NEXT_UPDATE_RESTORE_MISMATCH")

    wm_forward_total = counters["wm_forwards"]
    wm_row_total = counters["wm_candidate_rows"]
    combined_ppo_updates = 3 * first_result["optimizer_updates"]
    combined_ppo_steps = 3 * first_result["transition_count"]
    branch_steps = counters["steps_by_phase"].get("branches", 0)
    if wm_trainer.update_index != 11 or restored_wm_trainer.update_index != 11:
        raise RuntimeError("WM_UPDATE_COUNT_MISMATCH")
    if (not (PROFILE["work_caps"]["wm_optimizer_steps_min"] <= counters["wm_optimizer_steps"]
             <= PROFILE["work_caps"]["wm_optimizer_steps_max"])
            or combined_ppo_updates < PROFILE["work_caps"]["ppo_optimizer_steps_min"]
            or combined_ppo_updates > PROFILE["work_caps"]["ppo_optimizer_steps_max"]
            or combined_ppo_updates != counters["ppo_optimizer_steps"]):
        raise RuntimeError("OPTIMIZER_STEP_CAP")
    if (wm_forward_total > PROFILE["work_caps"]["world_model_forwards_max"]
            or wm_row_total > PROFILE["work_caps"]["world_model_candidate_sample_evaluations_max"]
            or counters["environment_steps"] > PROFILE["work_caps"]["total_environment_steps_max"]):
        raise RuntimeError("COMPUTE_OPERATION_CAP")
    if (len(records) > PROFILE["work_caps"]["branch_count_max"]
            or len(candidate_ids) > PROFILE["work_caps"]["candidate_catalog_cap_including_noop"]):
        raise RuntimeError("BRANCH_OR_CATALOG_CAP")
    if output_writes[0] > PROFILE["runtime"]["output_write_operations_max"]:
        raise RuntimeError("OUTPUT_WRITE_CAP")
    if (counters["ppo_optimizer_steps"] < PROFILE["work_caps"]["ppo_optimizer_steps_min"]
            or counters["ppo_optimizer_steps"] > PROFILE["work_caps"]["ppo_optimizer_steps_max"]):
        raise RuntimeError("PPO_OPTIMIZER_STEP_COUNT")

    source_hashes_after = {str(path.relative_to(ROOT)): sha256_file(path) for path in source_files}
    if source_hashes_after != source_hashes_before or sha256_file(PROFILE_PATH) != profile_hash:
        raise RuntimeError("LOCAL_SOURCE_OR_PROFILE_CHANGED_DURING_RUN")
    report = {
        "schema": "n2-local-engineering-run/1",
        "scope": "local synthetic engineering only; no study evidence or formal training",
        "runtime": {"python": platform.python_version(), "torch": torch.__version__, "device": "cpu", "windows_cgroup_metrics": "unavailable"},
        "budget": {"profile": str(PROFILE_PATH), "sha256": profile_hash},
        "input": {"fixture": str(fixture_path), "fixture_sha256": sha256_file(fixture_path), "base_episode_steps": base_steps, "base_full_catalog_max_including_noop": max_catalog},
        "branch": {"time": 8, "candidate_count_including_noop": len(candidate_ids), "candidate_ids": candidate_ids,
                   "branch_count": len(records), "reference": "same-window NOOP; both branches then frozen C1 continuation",
                   "continuation_steps_max": max(record["horizon_minutes"] for record in records),
                   "environment_steps": branch_steps},
        "world_model": {"optimizer_steps_across_both_paths": counters["wm_optimizer_steps"], "forward_counts_by_phase": wm_trace,
                        "candidate_rows_by_phase": candidate_samples,
                        "checkpoint_writes": counters["checkpoint_writes"], "checkpoint_reads": counters["checkpoint_reads"],
                        "next_update_equivalent": wm_equivalent, "checkpoint_sha256": sha256_file(wm_checkpoint),
                        "final_frozen_wm_sha256": _tensor_state_digest(wm.state_dict()),
                        "final_frozen_checkpoint_sha256": sha256_file(wm_frozen_checkpoint)},
        "ppo": {"variant": "civilian L1 actor with trained frozen WM critic adapter", "round1_transitions": first_result["transition_count"],
                "round1_optimizer_updates": first_result["optimizer_updates"], "restore_equivalence": equivalence,
                "combined_optimizer_updates_across_comparison_paths": counters["ppo_optimizer_steps"],
                "combined_environment_transitions_across_comparison_paths": counters["steps_by_phase"].get("ppo_critic", 0),
                "forward_counts_by_phase": {"ppo_critic": wm_trace["ppo_critic"]},
                "candidate_rows": candidate_samples["ppo_critic"]},
        "source_sha256": source_hashes_before,
        "measurement": {"wall_seconds_including_checkpoints": time.perf_counter() - wall_start,
                        "total_environment_steps": counters["environment_steps"],
                        "environment_steps_by_phase": counters["steps_by_phase"],
                        "episode_constructions": counters["episode_constructions"],
                        "ppo_episodes": counters["ppo_episodes"],
                        "process_cpu_seconds_including_checkpoints": time.process_time() - cpu_start,
                        "optimizer_steps_actual": {"wm": counters["wm_optimizer_steps"], "ppo": counters["ppo_optimizer_steps"]},
                        "checkpoint_operations_actual": {"reads": counters["checkpoint_reads"], "writes": counters["checkpoint_writes"]},
                        "audited_output_write_operations": output_writes[0],
                        "output_file_count": sum(1 for path in output.rglob("*") if path.is_file()),
                        "output_tree_bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file())},
        "limitations": ["Windows cgroup counters unavailable; this is not hosted-systemd settlement evidence.",
                        "Current target heads do not implement demand satisfaction, reassignment delta, or other-order newly-overdue outcomes.",
                        "Global reward labels use the copied civilian simulator reward semantics as an engineering proxy."],
    }
    report_path = output / "LOCAL_ENGINEERING_RECEIPT.json"
    report_path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(report_path), "wm_steps": report["world_model"]["optimizer_steps_across_both_paths"],
                      "ppo_updates": report["ppo"]["round1_optimizer_updates"],
                      "candidate_count": len(candidate_ids), "measurement": report["measurement"]}, sort_keys=True))


if __name__ == "__main__":
    main()
