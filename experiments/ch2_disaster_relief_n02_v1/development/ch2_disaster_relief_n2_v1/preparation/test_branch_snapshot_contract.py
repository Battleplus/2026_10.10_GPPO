from __future__ import annotations

import copy
import hashlib
import json
import pickle
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CIVIL = ROOT / "development" / "ch2_disaster_relief_graph_v2"
if str(CIVIL) not in sys.path:
    sys.path.insert(0, str(CIVIL))

from baselines import choose_step_c1_actions
from graph_policy import encode_public_graph
from relief_env import ReliefEnv


FIXTURE = CIVIL / "fixtures" / "control.json"


def _encoded_graph_bytes(graph) -> bytes:
    fields = (
        "node_features", "node_types", "node_mask", "platform_mask", "task_mask",
        "edge_types", "edge_features",
    )
    payload = {
        name: getattr(graph, name).detach().cpu().contiguous().numpy().tobytes()
        for name in fields
    }
    payload["candidate_ids"] = graph.candidate_ids
    payload["candidate_pairs"] = graph.candidate_pairs
    payload["candidate_stock_requirements"] = graph.candidate_stock_requirements
    payload["stock_limits"] = graph.stock_limits
    return pickle.dumps(payload, protocol=5)


def _environment_bytes(env: ReliefEnv) -> bytes:
    return pickle.dumps(env, protocol=5)


def _public_binding(env: ReliefEnv) -> tuple[bytes, bytes]:
    policy_input = env.policy_input()
    public_bytes = json.dumps(
        policy_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return public_bytes, _encoded_graph_bytes(encode_public_graph(policy_input))


def _to_time_eight(env: ReliefEnv) -> None:
    observation = env.reset("C1")
    for _ in range(8):
        candidates = env.candidates()
        chosen = choose_step_c1_actions(observation, candidates)
        action_ids = [item["id"] for item in chosen]
        action_ids.append("NOOP")
        observation, _, terminated, truncated, _ = env.step(action_ids)
        if terminated or truncated:
            raise AssertionError("fixture ended before t=8")
    if env.time != 8:
        raise AssertionError(f"expected t=8, got {env.time}")


class BranchSnapshotContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_hidden_order_failure_and_stock_changes_do_not_change_public_actor_input(self):
        variants = []

        changed_order = copy.deepcopy(self.scenario)
        hidden = next(task for task in changed_order["tasks"] if not task["known_initial"])
        hidden["id"] = "hidden-medical-renamed"
        hidden["position"] = [1.5, 1.25]
        hidden["priority"] = 4.75
        hidden["deadline"] = 49
        variants.append(changed_order)

        changed_hidden_count = copy.deepcopy(self.scenario)
        hidden_extra = copy.deepcopy(next(
            task for task in changed_hidden_count["tasks"] if not task["known_initial"]
        ))
        hidden_extra["id"] = "hidden-extra-order"
        changed_hidden_count["tasks"].append(hidden_extra)
        variants.append(changed_hidden_count)

        changed_failure = copy.deepcopy(self.scenario)
        changed_failure["disturbances"] = [{
            "id": "unreported-failure",
            "time": 9,
            "kind": "failure",
            "platform_id": "uav-3",
            "report_delay": 20,
        }]
        variants.append(changed_failure)

        changed_stock = copy.deepcopy(self.scenario)
        changed_stock["disturbances"] = [{
            "id": "unreported-stock-loss",
            "time": 9,
            "kind": "stock_loss",
            "depot_id": "depot-1",
            "commodity": "medical",
            "quantity": 4,
            "report_delay": 20,
        }]
        variants.append(changed_stock)

        baseline = ReliefEnv(self.scenario)
        baseline.reset("C1")
        expected = _public_binding(baseline)
        expected_ids = [item["id"] for item in baseline.candidates()]
        self.assertEqual(expected_ids[-1], "NOOP")
        self.assertEqual(len(expected_ids), len(set(expected_ids)))

        for variant in variants:
            env = ReliefEnv(variant)
            env.reset("C1")
            self.assertEqual(_public_binding(env), expected)
            self.assertEqual([item["id"] for item in env.candidates()], expected_ids)
            public_json = expected[0].decode("ascii")
            self.assertNotIn("latent-medical", public_json)
            self.assertNotIn("latent-water", public_json)

    def test_t8_snapshot_restores_pending_truth_and_branches_are_isolated(self):
        scenario = copy.deepcopy(self.scenario)
        next(task for task in scenario["tasks"] if task["id"] == "inspect-west")["report_delay"] = 10
        scenario["disturbances"] = [{
            "id": "pending-failure",
            "time": 6,
            "kind": "failure",
            "platform_id": "uav-3",
            "report_delay": 12,
        }, {
            "id": "pending-stock-loss",
            "time": 7,
            "kind": "stock_loss",
            "depot_id": "depot-1",
            "commodity": "medical",
            "quantity": 4,
            "report_delay": 12,
        }]
        source = ReliefEnv(scenario)
        _to_time_eight(source)

        self.assertEqual(source.time, 8)
        self.assertTrue(source._scheduled_reports)
        source_bytes = _environment_bytes(source)
        source_sha = hashlib.sha256(source_bytes).hexdigest()
        public_bytes, _ = _public_binding(source)
        candidates = source.candidates()
        restored = pickle.loads(source_bytes)
        self.assertEqual(restored.__dict__, source.__dict__)
        self.assertEqual(restored.time, 8)
        self.assertEqual(restored._scheduled_reports, source._scheduled_reports)
        self.assertEqual(_public_binding(restored)[0], public_bytes)
        self.assertEqual(restored.candidates(), candidates)

        dispatch_ids = [item["id"] for item in candidates if item["type"] == "dispatch"]
        self.assertEqual(dispatch_ids, [])
        self.assertEqual([item["id"] for item in candidates], ["NOOP"])
        branch = pickle.loads(source_bytes)
        branch.step(["NOOP"])

        self.assertEqual(_environment_bytes(source), source_bytes)
        self.assertEqual(restored.__dict__, source.__dict__)
        self.assertEqual(branch.time, 9)
        self.assertEqual(source.time, 8)

    def test_engineering_opportunity_fixture_restores_dispatch_and_noop_branches(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["scenario_id"] = "n2-preparation-opportunity-noop-prefix"
        scenario["disturbances"] = [{
            "id": "pending-failure",
            "time": 6,
            "kind": "failure",
            "platform_id": "uav-3",
            "report_delay": 12,
        }]
        env = ReliefEnv(scenario)
        observation = env.reset("C1")
        for _ in range(8):
            observation, _, terminated, truncated, _ = env.step(["NOOP"])
            self.assertFalse(terminated)
            self.assertFalse(truncated)
        source_bytes = _environment_bytes(env)
        candidates = env.candidates()
        dispatch_ids = [item["id"] for item in candidates if item["type"] == "dispatch"]
        self.assertTrue(dispatch_ids)

        branches = []
        for action_id in (dispatch_ids[0], "NOOP"):
            branch = pickle.loads(source_bytes)
            branch.step([action_id])
            branches.append(branch)

        self.assertEqual(_environment_bytes(env), source_bytes)
        self.assertEqual(branches[0].time, 9)
        self.assertEqual(branches[1].time, 9)
        self.assertNotEqual(_environment_bytes(branches[0]), _environment_bytes(branches[1]))

    def test_candidate_catalog_is_dynamic_and_noop_is_always_explicit(self):
        env = ReliefEnv(self.scenario)
        observation = env.reset("C1")
        before = env.candidates()
        before_ids = [item["id"] for item in before]
        self.assertEqual(before_ids[-1], "NOOP")
        dispatch_id = next(item["id"] for item in before if item["type"] == "dispatch")
        observation, _, terminated, truncated, _ = env.step([dispatch_id, "NOOP"])
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        after = env.candidates()
        after_ids = [item["id"] for item in after]
        self.assertEqual(after_ids[-1], "NOOP")
        self.assertEqual(len(after_ids), len(set(after_ids)))
        self.assertNotEqual(before_ids, after_ids)
        self.assertEqual(observation, env.public_observation())


if __name__ == "__main__":
    unittest.main()
