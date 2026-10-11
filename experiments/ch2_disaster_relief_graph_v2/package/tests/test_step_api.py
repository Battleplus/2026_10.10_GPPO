from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph_policy import build_paired_policies
from baselines import choose_actions, choose_step_c0_actions, choose_step_c1_actions
from evaluator import _evaluate_baseline
from independent_audit import audit_run
from relief_env import ReliefEnv


class StepApiTests(unittest.TestCase):
    def test_learned_episode_steps_once_per_minute_and_exports_auditable_trace(self):
        scenario = json.loads((ROOT / "fixtures" / "control.json").read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        env.reset("L1")
        policy = build_paired_policies(8201)[1]
        rewards = []
        terminated = False
        while not terminated:
            sample = policy.sample_batch(env.policy_input(), deterministic=True)
            _, reward, terminated, truncated, info = env.step(sample["actions"])
            self.assertFalse(truncated)
            self.assertEqual(info["transition"]["time"], len(rewards))
            rewards.append(reward)
        result = env.export_trajectory()
        self.assertEqual(len(result["transitions"]), scenario["horizon"])
        self.assertEqual(result["transitions"][-1]["time"], scenario["horizon"] - 1)
        audit = audit_run(scenario, result, expected_policy="L1")
        self.assertEqual(audit["validation_level"], "full_artifact")
        self.assertEqual(env.episode_metrics, result["summary"])
        with self.assertRaisesRegex(RuntimeError, "terminated"):
            env.step([])

    def test_batch_rejects_duplicate_platform_or_task_and_unknown_ids(self):
        scenario = json.loads((ROOT / "fixtures" / "control.json").read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        env.reset("L1")
        catalog = [item for item in env.candidates() if item["id"] != "NOOP"]
        same_platform = next((a, b) for a in catalog for b in catalog if a["platform_id"] == b["platform_id"] and a["task_id"] != b["task_id"])
        with self.assertRaisesRegex(ValueError, "at most once"):
            env.step([same_platform[0]["id"], same_platform[1]["id"]])
        with self.assertRaisesRegex(ValueError, "unknown or non-dispatch"):
            env.step(["dispatch:not-present:not-present"])

    def test_step_rejects_same_batch_public_stock_overcommit_before_mutation(self):
        scenario = json.loads((ROOT / "fixtures" / "control.json").read_text(encoding="utf-8"))
        scenario["scenario_id"] = "same-batch-stock-reservation"
        scenario["depots"][0]["stock"]["water"] = 18
        food = next(task for task in scenario["tasks"] if task["id"] == "known-food")
        food.update({"commodity": "water", "quantity": 15})
        water_id = "dispatch:uav-1:known-water"
        food_id = "dispatch:heli-1:known-food"
        for policy in ("C0", "C1", "L0", "L1"):
            with self.subTest(policy=policy):
                env = ReliefEnv(scenario)
                env.reset(policy)
                event_count = len(env.events)
                self.assertIn(water_id, {item["id"] for item in env.candidates()})
                self.assertIn(food_id, {item["id"] for item in env.candidates()})

                with self.assertRaisesRegex(ValueError, "publicly available depot stock"):
                    env.step([water_id, food_id])

                self.assertEqual(env.time, 0)
                self.assertEqual(env.transitions, [])
                self.assertEqual(len(env.events), event_count)

    def test_empty_batch_is_a_valid_noop_minute(self):
        scenario = json.loads((ROOT / "fixtures" / "control.json").read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        observation = env.reset("L0")
        self.assertEqual(observation["time"], 0)
        next_observation, reward, terminated, truncated, info = env.step([])
        self.assertEqual(next_observation["time"], 1)
        self.assertEqual(info["transition"]["selected_actions"], [])
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertIsInstance(reward, float)

    def test_c1_filters_public_stock_overcommit_and_comparison_completes(self):
        scenario = json.loads((ROOT / "fixtures" / "control.json").read_text(encoding="utf-8"))
        scenario["scenario_id"] = "c1-residual-stock-filter"
        scenario["depots"][0]["stock"]["water"] = 18
        tasks = {task["id"]: task for task in scenario["tasks"]}
        tasks["known-water"].update({"quantity": 10})
        tasks["known-food"].update({"commodity": "water", "quantity": 9})
        scenario["chapter1_snapshot"]["queues"] = {
            "uav-1": ["known-water"],
            "uav-2": [],
            "uav-3": [],
            "heli-1": ["known-food"],
        }
        for platform in scenario["platforms"]:
            platform["capacity_kg"] = 12

        env = ReliefEnv(scenario)
        observation = env.reset("C1")
        candidates = env.candidates()
        legacy_chosen = choose_actions("C1", observation, candidates)
        chosen = choose_step_c1_actions(observation, candidates)
        legacy_deliveries = [
            item for item in legacy_chosen
            if tasks[item["task_id"]]["kind"] == "delivery"
        ]
        chosen_deliveries = [
            item for item in chosen
            if tasks[item["task_id"]]["kind"] == "delivery"
        ]
        self.assertEqual(len(legacy_deliveries), 2)
        self.assertEqual(len(chosen_deliveries), 1)
        self.assertEqual(chosen_deliveries[0]["task_id"], "known-water")
        self.assertLessEqual(
            sum(float(tasks[item["task_id"]]["quantity"]) for item in chosen_deliveries),
            18,
        )

        c0_env = ReliefEnv(scenario)
        c0_observation = c0_env.reset("C0")
        c0_candidates = c0_env.candidates()
        c0_chosen = choose_step_c0_actions(c0_observation, c0_candidates)
        c0_deliveries = [
            item for item in c0_chosen
            if tasks[item["task_id"]]["kind"] == "delivery"
        ]
        self.assertEqual(len(c0_deliveries), 1)
        self.assertEqual(c0_deliveries[0]["task_id"], "known-food")

        result, timings = _evaluate_baseline(scenario, "C1")
        self.assertEqual(len(result["transitions"]), scenario["horizon"])
        self.assertEqual(timings["decisions"], scenario["horizon"])
        self.assertFalse(any(event.get("reason") == "insufficient_stock" for event in result["events"]))


if __name__ == "__main__":
    unittest.main()
