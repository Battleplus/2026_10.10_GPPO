from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CIVILIAN_ROOT = PACKAGE_ROOT / "civilian"
sys.path.insert(0, str(CIVILIAN_ROOT))

from branching import (  # noqa: E402
    build_branch_record,
    capture_snapshot,
    paired_global_targets,
    paired_task_targets,
    reference_action_batch,
    restore_snapshot,
)
from dataset_protocol import validate_registry  # noqa: E402
from graph_policy import encode_public_graph  # noqa: E402
from relief_env import ReliefEnv  # noqa: E402
from scenario_matrix import make_parent  # noqa: E402
from scenario_schema import MAP_CONTRACT, validate_scenario  # noqa: E402
from stable_identity import key_digest  # noqa: E402
from world_model import DynamicConsequenceModel, public_policy_tensors  # noqa: E402


def _causal_choice_scenario() -> dict:
    scenario = make_parent("train", 0, "base")
    scenario["scenario_id"] = "n02-test-causal-choice-100x100"
    scenario["platforms"][1]["capabilities"] = ["inspect"]
    scenario["platforms"][2]["capabilities"] = ["inspect"]
    scenario["tasks"] = [
        {
            "id": "causal-inspection",
            "kind": "inspection",
            "position": [40.25, 40.25],
            "local": True,
            "known_initial": True,
            "deadline": 30,
            "priority": 3.0,
            "discovered_by": None,
            "report_delay": 6,
            "service_minutes": 2,
        },
        {
            "id": "causal-delivery-a",
            "kind": "delivery",
            "position": [41.0, 40.5],
            "local": True,
            "known_initial": False,
            "deadline": 14,
            "priority": 5.0,
            "discovered_by": "causal-inspection",
            "report_delay": 0,
            "commodity": "water",
            "quantity": 4.0,
            "depot_id": "n02-local-depot",
            "load_minutes": 1,
            "unload_minutes": 1,
        },
        {
            "id": "causal-delivery-b",
            "kind": "delivery",
            "position": [40.5, 41.0],
            "local": True,
            "known_initial": False,
            "deadline": 14,
            "priority": 5.0,
            "discovered_by": "causal-inspection",
            "report_delay": 0,
            "commodity": "water",
            "quantity": 4.0,
            "depot_id": "n02-local-depot",
            "load_minutes": 1,
            "unload_minutes": 1,
        },
    ]
    scenario["chapter1_snapshot"]["queues"] = {
        "n02-uav-1": ["causal-inspection"],
        "n02-uav-2": [],
        "n02-uav-3": [],
        "n02-heli-1": [],
    }
    validate_scenario(scenario)
    return scenario


def _run_choice(snapshot_json: str, action_batch: list[str]) -> tuple[ReliefEnv, float]:
    env = restore_snapshot(snapshot_json)
    total_reward = 0.0
    _, reward, terminated, _, _ = env.step(action_batch)
    total_reward += reward
    stop_at = int(env.time) + 29
    while not terminated and int(env.time) < stop_at:
        _, reward, terminated, _, _ = env.step(reference_action_batch(env))
        total_reward += reward
    return env, total_reward


def test_registered_inputs_and_fixtures_use_the_100x100_contract() -> None:
    report = validate_registry(CIVILIAN_ROOT / "registered_data")
    assert report["allocation"] == {"train": 2, "development": 1}
    assert report["scenarios_verified"] is True

    for path in sorted((CIVILIAN_ROOT / "fixtures").glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        validate_scenario(scenario)
        assert scenario["map"]["grid_contract"] == MAP_CONTRACT
        assert scenario["map"]["grid_cells"] == 10000


def test_schema_rejects_non_100x100_maps_and_out_of_range_coordinates() -> None:
    valid = make_parent("train", 0, "base")

    for rows, cols, cells in ((12, 12, 144), (100, 99, 9900), (101, 100, 10100)):
        scenario = copy.deepcopy(valid)
        scenario["map"].update({"rows": rows, "cols": cols, "grid_cells": cells})
        with pytest.raises(ValueError, match="100x100|10000"):
            validate_scenario(scenario)

    scenario = copy.deepcopy(valid)
    scenario["platforms"][0]["position"] = [100.0, 40.0]
    with pytest.raises(ValueError):
        validate_scenario(scenario)


def test_two_legal_global_choices_change_other_order_and_recompute_labels() -> None:
    scenario = _causal_choice_scenario()
    source = ReliefEnv(scenario)
    source.reset("C1")
    inspection_id = next(
        item["id"] for item in source.candidates()
        if item.get("type") == "dispatch" and item.get("task_id") == "causal-inspection"
        and item.get("platform_id") == "n02-uav-1"
    )
    source.step([inspection_id])
    while source.time < 8:
        source.step(["NOOP"])

    observation = source.public_observation()
    catalog = source.candidates()
    dispatches = {
        item["task_id"]: item["id"]
        for item in catalog
        if item.get("type") == "dispatch" and item.get("platform_id") == "n02-uav-1"
    }
    assert set(dispatches) == {"causal-delivery-a", "causal-delivery-b"}

    snapshot_json = capture_snapshot(
        source,
        parent_id=scenario["scenario_id"],
        repeat=0,
        window_id="causal-window-8",
        event_tape_id="causal-event-tape-8201",
    )
    payload = json.loads(snapshot_json)
    policy_input = {"observation": payload["public_prefix"], "candidates": payload["candidate_catalog"]}
    assert policy_input["observation"]["map"]["grid_cells"] == 10000

    graph = encode_public_graph(policy_input)
    platforms = sorted(observation["platforms"], key=lambda item: item["id"])
    platform_index = next(index for index, item in enumerate(platforms) if item["id"] == "n02-uav-1")
    platform = platforms[platform_index]
    assert graph.node_features[platform_index, 6].item() == pytest.approx(platform["position"][0] / 100.0)
    assert graph.node_features[platform_index, 7].item() == pytest.approx(platform["position"][1] / 100.0)

    wm_tensors, binding = public_policy_tensors(policy_input)
    assert wm_tensors["context"][0, 2:4].tolist() == [1.0, 1.0]
    assert binding.candidate_ids[0]
    model_layout = DynamicConsequenceModel().config
    assert (model_layout["map_contract"], model_layout["map_rows"], model_layout["map_cols"], model_layout["grid_cells"]) == (MAP_CONTRACT, 100, 100, 10000)

    action_a = [dispatches["causal-delivery-a"], "NOOP"]
    action_b = [dispatches["causal-delivery-b"], "NOOP"]
    candidate_env, candidate_return = _run_choice(snapshot_json, action_b)
    reference_env, reference_return = _run_choice(snapshot_json, action_a)
    tampered_payload = copy.deepcopy(payload)
    tampered_payload["candidate_catalog"] = [
        item for item in tampered_payload["candidate_catalog"] if item["id"] != action_b[0]
    ]
    tampered_payload["branch_envelope_sha256"] = hashlib.sha256(
        (json.dumps(
            {key: value for key, value in tampered_payload.items() if key != "branch_envelope_sha256"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )).encode("ascii")
    ).hexdigest().upper()
    tampered_snapshot = json.dumps(tampered_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with pytest.raises(ValueError):
        build_branch_record(
            tampered_snapshot,
            candidate_action_batch=action_b,
            reference_action_batch=action_a,
            parent_id=scenario["scenario_id"],
            repeat=0,
            window_id="causal-window-8",
            event_tape_id="causal-event-tape-8201",
            candidate_id=key_digest(action_b),
            candidate_return=candidate_return,
            reference_return=reference_return,
            candidate_env=candidate_env,
            reference_env=reference_env,
        )
    candidate_record = build_branch_record(
        snapshot_json,
        candidate_action_batch=action_b,
        reference_action_batch=action_a,
        parent_id=scenario["scenario_id"],
        repeat=0,
        window_id="causal-window-8",
        event_tape_id="causal-event-tape-8201",
        candidate_id=key_digest(action_b),
        candidate_return=candidate_return,
        reference_return=reference_return,
        candidate_env=candidate_env,
        reference_env=reference_env,
    )

    assert candidate_env._tasks["causal-delivery-b"]["on_time"] is True
    assert candidate_env._tasks["causal-delivery-a"]["on_time"] is False
    assert reference_env._tasks["causal-delivery-a"]["on_time"] is True
    assert reference_env._tasks["causal-delivery-b"]["on_time"] is False

    labels = candidate_record["paired_targets"]["task"]
    a_index = labels["task_ids"].index("causal-delivery-a")
    b_index = labels["task_ids"].index("causal-delivery-b")
    delivery_head = labels["names"].index("delivery_on_time")
    assert labels["valid"][a_index][delivery_head] is True
    assert labels["valid"][b_index][delivery_head] is True
    assert labels["values"][a_index][delivery_head] == -1.0
    assert labels["values"][b_index][delivery_head] == 1.0
    assert labels == paired_task_targets(candidate_env, reference_env, labels["task_ids"])

    recomputed_global = paired_global_targets(
        candidate_env,
        reference_env,
        candidate_return,
        reference_return,
        candidate_env.events,
        reference_env.events,
        window_start=8,
        exclude_task_ids={"causal-delivery-a", "causal-delivery-b"},
    )
    assert candidate_record["paired_targets"]["global"] == recomputed_global
    assert candidate_record["policy_input_sha256"] == key_digest({"observation": payload["public_prefix"], "candidates": payload["candidate_catalog"]})


def test_infeasible_stock_candidate_remains_excluded() -> None:
    scenario = make_parent("train", 0, "base")
    scenario["tasks"] = [copy.deepcopy(next(task for task in scenario["tasks"] if task["id"] == "n02-local-delivery-a"))]
    scenario["depots"][0]["stock"]["water"] = 0.0
    scenario["chapter1_snapshot"]["queues"] = {platform["id"]: [] for platform in scenario["platforms"]}
    env = ReliefEnv(scenario)
    env.reset("C1")
    catalog = env.candidates()
    assert [item["id"] for item in catalog] == ["NOOP"]
