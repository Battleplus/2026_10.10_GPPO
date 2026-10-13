from __future__ import annotations

import copy
import json
import math
import pathlib
import sys
import unittest
from array import array


DEV_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_ROOT = DEV_ROOT.parents[1] / "research-executions" / "ch2-disaster-relief-graph-v2-20261011" / "source" / "package"
if str(DEV_ROOT) not in sys.path:
    sys.path.insert(0, str(DEV_ROOT))
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from relief_adapter import DecisionRepeatReliefAdapter
from relief_env import ReliefEnv


FIXTURE_ROOT = SOURCE_ROOT / "fixtures"


def load_fixture(name: str = "control.json") -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def dispatch_indices(observation: dict) -> list[int]:
    return [
        index
        for index, (valid, key) in enumerate(zip(observation["action_mask"], observation["action_keys"]))
        if index < observation["action_size"] - 1 and valid and key is not None
    ]


class DecisionRepeatAdapterTests(unittest.TestCase):
    def test_fixed_float32_layout_and_hidden_task_padding(self):
        scenario = load_fixture()
        env = ReliefEnv(scenario)
        adapter = DecisionRepeatReliefAdapter(env)
        observation = adapter.reset()

        self.assertEqual(observation["schema"], "relief-dreamer-adapter/1")
        self.assertEqual(observation["action_size"], 65)
        self.assertEqual(len(observation["action_mask"]), 65)
        self.assertEqual(len(observation["vector"]), adapter.feature_size)
        self.assertIsInstance(observation["vector"], array)
        self.assertEqual(observation["vector"].typecode, "f")
        self.assertEqual(observation["vector"].itemsize, 4)
        self.assertTrue(all(math.isfinite(value) for value in observation["vector"]))

        visible_ids = {task["id"] for task in observation["public_observation"]["tasks"]}
        hidden_ids = {task["id"] for task in scenario["tasks"] if not task["known_initial"]}
        self.assertTrue(hidden_ids.isdisjoint(visible_ids))
        self.assertTrue(hidden_ids.isdisjoint({item for item in observation["task_ids_by_slot"] if item is not None}))
        self.assertEqual(set(item for item in observation["task_ids_by_slot"] if item is not None), visible_ids)
        self.assertEqual(sum(item is None for item in observation["task_ids_by_slot"]), 16 - len(visible_ids))
        self.assertNotIn("all_task_count", observation)
        self.assertEqual(adapter.signature["slot_config"]["max_task_slots"], 16)

    def test_selection_microsteps_then_commit_match_original_joint_batch(self):
        scenario = load_fixture()
        adapter_env = ReliefEnv(copy.deepcopy(scenario))
        direct_env = ReliefEnv(copy.deepcopy(scenario))
        adapter = DecisionRepeatReliefAdapter(adapter_env)
        observation = adapter.reset("LEARNED")
        direct_env.reset("LEARNED")

        original_time = adapter_env.public_observation()["time"]
        first = dispatch_indices(observation)[0]
        first_key = observation["action_keys"][first]
        observation, reward, terminated, truncated, info = adapter.step(first)
        self.assertEqual((reward, terminated, truncated), (0.0, False, False))
        self.assertEqual(info["adapter"]["physical_time_delta"], 0)
        self.assertEqual(info["adapter"]["discount_exponent"], 0)
        self.assertEqual(adapter_env.public_observation()["time"], original_time)
        self.assertFalse(observation["action_mask"][first])

        second = next(
            (
                index
                for index in dispatch_indices(observation)
                if observation["action_keys"][index] != first_key
                and observation["action_keys"][index].split(":")[1] != first_key.split(":")[1]
                and observation["action_keys"][index].split(":")[2] != first_key.split(":")[2]
            ),
            None,
        )
        selected = [first_key]
        if second is not None:
            second_key = observation["action_keys"][second]
            observation, reward, terminated, truncated, _ = adapter.step(second)
            self.assertEqual((reward, terminated, truncated), (0.0, False, False))
            self.assertEqual(adapter_env.public_observation()["time"], original_time)
            selected.append(second_key)

        with self.assertRaisesRegex(ValueError, "masked or unavailable"):
            adapter.step(first)
        observation, reward, terminated, truncated, info = adapter.step(adapter.commit_action)
        direct_observation, direct_reward, direct_terminated, direct_truncated, direct_info = direct_env.step(selected)

        self.assertEqual(observation["public_observation"], direct_observation)
        self.assertEqual(reward, direct_reward)
        self.assertEqual(terminated, direct_terminated)
        self.assertEqual(truncated, direct_truncated)
        self.assertEqual(adapter_env.public_observation()["time"], original_time + 1)
        self.assertEqual(info["adapter"]["physical_time_delta"], 1)
        self.assertEqual(info["adapter"]["discount_exponent"], 1)
        self.assertEqual(info["adapter"]["selected_action_ids"], selected)
        self.assertNotIn("reward_events", info)
        self.assertIn("identity", direct_info["transition"])

    def test_candidate_order_permutation_does_not_change_action_identity_or_encoding(self):
        scenario = load_fixture()
        env_a = ReliefEnv(copy.deepcopy(scenario))
        env_b = ReliefEnv(copy.deepcopy(scenario))
        original_candidates = env_b.candidates
        env_b.candidates = lambda: list(reversed(original_candidates()))

        adapter_a = DecisionRepeatReliefAdapter(env_a)
        adapter_b = DecisionRepeatReliefAdapter(env_b)
        observation_a = adapter_a.reset()
        observation_b = adapter_b.reset()

        self.assertEqual(observation_a["vector"], observation_b["vector"])
        self.assertEqual(observation_a["action_mask"], observation_b["action_mask"])
        self.assertEqual(observation_a["action_keys"], observation_b["action_keys"])

    def test_hidden_future_task_and_event_perturbations_do_not_change_reset_input(self):
        baseline = load_fixture("failure.json")
        perturbed = copy.deepcopy(baseline)
        hidden = next(task for task in perturbed["tasks"] if not task["known_initial"])
        hidden["id"] = "unpublished-future-order"
        hidden["quantity"] = min(30, hidden["quantity"] + 7)
        hidden["deadline"] = min(perturbed["horizon"], hidden["deadline"] + 3)
        disturbance = perturbed["disturbances"][0]
        disturbance["time"] = min(perturbed["horizon"] - 1, disturbance["time"] + 1)
        disturbance["platform_id"] = next(
            platform["id"] for platform in perturbed["platforms"]
            if platform["id"] != disturbance["platform_id"]
        )

        adapter_a = DecisionRepeatReliefAdapter(ReliefEnv(baseline))
        adapter_b = DecisionRepeatReliefAdapter(ReliefEnv(perturbed))
        observation_a = adapter_a.reset()
        observation_b = adapter_b.reset()

        self.assertEqual(observation_a["vector"], observation_b["vector"])
        self.assertEqual(observation_a["action_mask"], observation_b["action_mask"])
        self.assertEqual(observation_a["public_observation"], observation_b["public_observation"])
        self.assertNotIn("unpublished-future-order", repr(observation_b))

    def test_task_slot_is_allocated_only_after_new_task_becomes_public(self):
        scenario = load_fixture()
        env = ReliefEnv(scenario)
        adapter = DecisionRepeatReliefAdapter(env)
        observation = adapter.reset()
        initial_slots = tuple(observation["task_ids_by_slot"])
        hidden_id = next(task["id"] for task in scenario["tasks"] if not task["known_initial"])
        self.assertNotIn(hidden_id, initial_slots)

        inspection_index = next(
            index for index in dispatch_indices(observation)
            if observation["action_keys"][index].endswith(":inspect-west")
        )
        observation, _, _, _, _ = adapter.step(inspection_index)
        observation, _, _, _, _ = adapter.step(adapter.commit_action)
        for _ in range(scenario["horizon"]):
            visible_ids = {task["id"] for task in observation["public_observation"]["tasks"]}
            if hidden_id in visible_ids:
                break
            observation, _, terminated, _, _ = adapter.step(adapter.commit_action)
            if terminated:
                break

        visible_ids = {task["id"] for task in observation["public_observation"]["tasks"]}
        self.assertIn(hidden_id, visible_ids)
        self.assertIn(hidden_id, observation["task_ids_by_slot"])
        for task_id in initial_slots:
            if task_id is not None:
                self.assertEqual(observation["task_ids_by_slot"].index(task_id), initial_slots.index(task_id))

    def test_capacity_is_fixed_configuration_not_hidden_task_total(self):
        scenario = load_fixture("external_commitment.json")
        self.assertGreater(len(scenario["tasks"]), 5)
        adapter = DecisionRepeatReliefAdapter(ReliefEnv(scenario), max_task_slots=5)
        observation = adapter.reset()
        self.assertEqual(sum(item is not None for item in observation["task_ids_by_slot"]), 5)
        self.assertEqual(adapter.action_size, 4 * 5 + 1)


if __name__ == "__main__":
    unittest.main()
