from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines import choose_actions
from independent_audit import audit_run
from relief_env import ReliefEnv
from scenario_schema import validate_scenario


def _fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


class ReliefEnvTests(unittest.TestCase):
    def test_all_fixtures_replay_for_both_policies(self):
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            for policy in ("C0", "C1"):
                with self.subTest(scenario=path.stem, policy=policy):
                    result = ReliefEnv(scenario).run(policy)
                    audit_run(scenario, result, expected_policy=policy)
                    second = ReliefEnv(scenario).run(policy)
                    self.assertEqual(result, second)

    def test_c0_waits_at_temporarily_infeasible_queue_head(self):
        observation = {
            "chapter1_snapshot": {"queues": {"p1": ["head", "tail"]}},
            "tasks": [
                {"id": "head", "status": "pending"},
                {"id": "tail", "status": "pending"},
            ],
        }
        candidates = [
            {"id": "dispatch:p1:tail", "platform_id": "p1", "task_id": "tail"},
            {"id": "NOOP", "type": "noop"},
        ]
        self.assertEqual(choose_actions("C0", observation, candidates), [])
        observation["tasks"][0]["status"] = "failed"
        self.assertEqual(choose_actions("C0", observation, candidates), [candidates[0]])

    def test_c1_estimate_rounds_each_leg_to_a_tick(self):
        scenario = _fixture("control")
        scenario["platforms"] = [scenario["platforms"][0]]
        scenario["platforms"][0].update({"position": [0, 0], "speed_km_min": 1})
        scenario["depots"][0].update({"position": [0.2, 0], "stock": {"water": 10}})
        scenario["tasks"] = [copy.deepcopy(scenario["tasks"][2])]
        scenario["tasks"][0].update({"position": [0.4, 0], "quantity": 1, "deadline": 20})
        scenario["chapter1_snapshot"]["queues"] = {"uav-1": [scenario["tasks"][0]["id"]]}
        scenario["horizon"] = 20
        env = ReliefEnv(scenario)
        platform = env._platforms["uav-1"]
        completion, _ = env._estimated_mission(platform, scenario["tasks"][0], 0)
        self.assertEqual(completion, 6)

    def test_delayed_failure_does_not_change_public_mirror_early(self):
        control = _fixture("control")
        failure = copy.deepcopy(control)
        failure["scenario_id"] = "delayed-failure-mirror"
        failure["disturbances"] = [{
            "id": "failure-uav-2", "time": 1, "kind": "failure",
            "platform_id": "uav-2", "report_delay": 5,
        }]
        baseline_result = ReliefEnv(control).run("C1")
        failure_result = ReliefEnv(failure).run("C1")
        self.assertEqual(
            failure_result["transitions"][1]["public_observation"],
            baseline_result["transitions"][1]["public_observation"],
        )
        observation_at_two = failure_result["transitions"][2]["public_observation"]
        failed_platform = next(item for item in observation_at_two["platforms"] if item["id"] == "uav-2")
        self.assertTrue(failed_platform["busy"])
        self.assertFalse(failed_platform["failed"])
        observation_at_six = failure_result["transitions"][6]["public_observation"]
        failed_platform = next(item for item in observation_at_six["platforms"] if item["id"] == "uav-2")
        self.assertFalse(failed_platform["busy"])
        self.assertTrue(failed_platform["failed"])
        audit_run(failure, failure_result, expected_policy="C1")

    def test_energy_report_applies_delta_after_known_consumption(self):
        scenario = _fixture("control")
        scenario["scenario_id"] = "delayed-energy-mirror"
        scenario["disturbances"] = [{
            "id": "energy-uav-3", "time": 1, "kind": "energy_change",
            "platform_id": "uav-3", "value": 20, "report_delay": 5,
        }]
        result = ReliefEnv(scenario).run("C1")
        baseline = ReliefEnv(_fixture("control")).run("C1")
        generated = next(event for event in result["events"] if event["type"] == "report_generated" and event.get("kind") == "energy_change")
        received = next(event for event in result["events"] if event["type"] == "report_received" and event.get("kind") == "energy_change")
        self.assertEqual(generated["report_delay"], 5)
        self.assertEqual(generated["new_energy"], 20)
        self.assertNotEqual(generated["old_energy"], generated["new_energy"])
        self.assertEqual(received["report_delay"], 5)
        public_platform = next(item for item in result["transitions"][6]["public_observation"]["platforms"] if item["id"] == "uav-3")
        baseline_platform = next(item for item in baseline["transitions"][6]["public_observation"]["platforms"] if item["id"] == "uav-3")
        self.assertAlmostEqual(
            public_platform["energy"],
            baseline_platform["energy"] + generated["new_energy"] - generated["old_energy"],
        )
        self.assertAlmostEqual(received["new_energy"], public_platform["energy"])
        audit_run(scenario, result, expected_policy="C1")

    def test_stock_loss_is_capped_by_remaining_stock(self):
        scenario = _fixture("control")
        scenario["scenario_id"] = "capped-stock-loss"
        scenario["disturbances"] = [{
            "id": "water-stock-loss", "time": 20, "kind": "stock_loss",
            "depot_id": "depot-1", "commodity": "water", "quantity": 18,
        }]
        result = ReliefEnv(scenario).run("C1")
        loss = next(event for event in result["events"] if event["type"] == "stock_lost")
        self.assertEqual(loss["requested_quantity"], 18)
        self.assertEqual(loss["quantity"], 9)
        water = next(item["stock"]["water"] for item in result["final_state"]["depots"] if item["id"] == "depot-1")
        self.assertEqual(water, 0)
        audit_run(scenario, result, expected_policy="C1")

    def test_external_commitment_reports_insufficient_stock(self):
        scenario = _fixture("external_commitment")
        scenario["depots"][0]["stock"]["food"] = 12
        for policy in ("C0", "C1"):
            with self.subTest(policy=policy):
                result = ReliefEnv(scenario).run(policy)
                shortage = next(
                    event for event in result["events"]
                    if event["type"] == "task_failed"
                    and event.get("task_id") == "committed-external"
                )
                self.assertEqual(shortage["reason"], "insufficient_stock")
                audit_run(scenario, result, expected_policy=policy)

    def test_failure_retry_repeats_partial_inspection_service(self):
        scenario = _fixture("control")
        scenario["scenario_id"] = "retry-service-progress"
        scenario["disturbances"] = [{
            "id": "retry-failure", "time": 1, "kind": "failure",
            "platform_id": "uav-2", "report_delay": 0,
        }]
        result = ReliefEnv(scenario).run("C1")
        service_events = [
            event for event in result["events"]
            if event["type"] == "service" and event.get("task_id") == "inspect-west"
        ]
        self.assertEqual(len(service_events), 3)
        audit_run(scenario, result, expected_policy="C1")

    def test_schema_rejects_fractional_deadlines_local_mismatch_and_unknown_public_fields(self):
        scenario = _fixture("control")
        fractional = copy.deepcopy(scenario)
        fractional["tasks"][0]["deadline"] = 1.5
        with self.assertRaisesRegex(ValueError, "deadline must be an integer"):
            validate_scenario(fractional)

        locality = copy.deepcopy(scenario)
        locality["platforms"][0]["local"] = False
        with self.assertRaisesRegex(ValueError, "incompatible locality"):
            validate_scenario(locality)

        metadata = copy.deepcopy(scenario)
        metadata["map"]["future_event_tape"] = ["hidden"]
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            validate_scenario(metadata)

    def test_task_local_uses_half_open_local_block_boundaries(self):
        scenario = _fixture("control")
        scenario["tasks"][0]["position"] = [0, 0]
        validate_scenario(scenario)

        outside = copy.deepcopy(scenario)
        outside["tasks"][0]["position"] = [2, 1]
        with self.assertRaisesRegex(ValueError, "map.local_block"):
            validate_scenario(outside)

        outside["tasks"][0]["local"] = False
        for platform_id, queue in outside["chapter1_snapshot"]["queues"].items():
            outside["chapter1_snapshot"]["queues"][platform_id] = [task_id for task_id in queue if task_id != outside["tasks"][0]["id"]]
        validate_scenario(outside)


if __name__ == "__main__":
    unittest.main()
