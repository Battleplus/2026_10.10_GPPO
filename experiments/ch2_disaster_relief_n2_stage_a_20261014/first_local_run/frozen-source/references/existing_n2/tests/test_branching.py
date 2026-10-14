from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENGINEERING = ROOT / "references" / "existing_n2"
CIVIL = ROOT / "references" / "civil"
if str(ENGINEERING) not in sys.path:
    sys.path.insert(0, str(ENGINEERING))
if str(CIVIL) not in sys.path:
    sys.path.insert(0, str(CIVIL))

from branching import (
    ENGINEERING_WINDOW_STARTS,
    _step_c1,
    _digest,
    _task_outcome,
    capture_snapshot,
    public_record,
    restore_snapshot,
    run_synthetic_candidate_pair,
)
from relief_env import ReliefEnv


FIXTURE = CIVIL / "fixtures" / "control.json"


def env_at(scenario: dict, time: int) -> ReliefEnv:
    env = ReliefEnv(scenario)
    env.reset("C1")
    for _ in range(time):
        _, _, terminated, truncated, _ = _step_c1(env)
        if terminated or truncated:
            raise AssertionError("synthetic fixture ended before requested window")
    return env


def opportunity_scenario(scenario: dict) -> dict:
    scenario = copy.deepcopy(scenario)
    for task in scenario["tasks"]:
        if task["id"] == "latent-water":
            task["report_delay"] = 6
    hidden_inspection = copy.deepcopy(next(task for task in scenario["tasks"] if task["id"] == "inspect-east"))
    hidden_inspection.update({
        "id": "latent-inspection", "known_initial": False,
        "discovered_by": "inspect-east", "deadline": 45, "priority": 1, "report_delay": 6,
    })
    scenario["tasks"].append(hidden_inspection)
    return scenario


class BranchSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_json_snapshot_restores_pending_truth_catalog_and_isolates_siblings(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["disturbances"] = [{
            "id": "pending-failure", "time": 6, "kind": "failure", "platform_id": "uav-3", "report_delay": 12,
        }]
        env = env_at(scenario, 8)
        self.assertTrue(env._scheduled_reports)
        source_json = capture_snapshot(env)
        payload = json.loads(source_json)
        self.assertIsInstance(payload, dict)
        self.assertEqual(set(payload["implementation_sources"]), {
            "branching.py", "relief_env.py", "baselines.py", "scenario_schema.py",
        })
        self.assertNotIn("pickle", source_json.lower())
        restored = restore_snapshot(source_json)
        self.assertEqual(restored.__dict__, env.__dict__)
        self.assertEqual(restored._scheduled_reports, env._scheduled_reports)
        branch_a = restore_snapshot(source_json)
        branch_b = restore_snapshot(source_json)
        branch_a.step(["NOOP"])
        self.assertEqual(env.time, 8)
        self.assertEqual(branch_b.time, 8)
        self.assertEqual(branch_a.time, 9)

    def test_snapshot_requires_the_actual_c1_prefix(self):
        env = env_at(self.scenario, 8)
        env.transitions[0]["selected_actions"] = []
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_C1_PREFIX_MISMATCH"):
            capture_snapshot(env)

    def test_public_export_and_hidden_task_count_are_invariant(self):
        baseline = ReliefEnv(copy.deepcopy(self.scenario))
        baseline.reset("C1")
        extra_hidden = copy.deepcopy(self.scenario)
        hidden = copy.deepcopy(next(task for task in extra_hidden["tasks"] if not task["known_initial"]))
        hidden["id"] = "secret-added-order"
        extra_hidden["tasks"].append(hidden)
        changed = ReliefEnv(extra_hidden)
        changed.reset("C1")
        public_a, public_b = public_record(baseline), public_record(changed)
        self.assertEqual(_digest(public_a), _digest(public_b))
        serialized = json.dumps(public_a, sort_keys=True)
        self.assertNotIn("latent-medical", serialized)
        self.assertNotIn("secret-added-order", serialized)

    def test_candidate_id_is_validated_and_noop_branch_keeps_global_label(self):
        env = env_at(self.scenario, 8)
        snapshot = capture_snapshot(env)
        result = run_synthetic_candidate_pair(snapshot, "NOOP")
        self.assertIsNone(result["target_task"]["task_id"])
        self.assertFalse(result["target_task_head_valid"])
        self.assertTrue(result["global_return_valid"])
        self.assertEqual(result["candidate_id"], "NOOP")
        with self.assertRaisesRegex(ValueError, "CANDIDATE_ID_NOT_IN_SNAPSHOT"):
            run_synthetic_candidate_pair(snapshot, "unknown-candidate")

    def test_branch_targets_recompute_from_rewards_events_and_public_deadlines(self):
        env = env_at(opportunity_scenario(self.scenario), 8)
        snapshot = capture_snapshot(env)
        candidate_id = next(item["id"] for item in env.policy_input()["candidates"] if item["id"] != "NOOP")
        result = run_synthetic_candidate_pair(snapshot, candidate_id)
        targets = result["paired_targets"]
        self.assertEqual(targets["global_binary_names"], ["reward_improved", "energy_saved"])
        self.assertEqual(targets["global_continuous_names"], [
            "cumulative_reward_delta", "energy_use_delta",
            "other_task_on_time_count_delta", "inspection_report_count_delta",
        ])
        self.assertEqual(targets["task_binary_names"], [
            "service_completed_by_horizon", "service_on_time", "deadline_missed", "report_received_by_deadline",
        ])
        self.assertEqual(targets["task_continuous_names"], ["completion_elapsed_fraction", "report_delay_fraction"])
        self.assertEqual({task["id"] for task in result["source_public_tasks"]}, set(targets["public_task_ids"]))

        candidate_reward = sum(result["candidate_step_rewards"])
        reference_reward = sum(result["reference_step_rewards"])
        self.assertAlmostEqual(targets["global_continuous"][0], candidate_reward - reference_reward)
        energy = lambda events: sum(
            float(event.get("energy", 0.0))
            for event in events if event.get("type") in {"move", "service"}
        )
        self.assertAlmostEqual(
            targets["global_continuous"][1], energy(result["candidate_events"]) - energy(result["reference_events"])
        )
        self.assertEqual(targets["global_binary"], [
            float(candidate_reward > reference_reward),
            float(energy(result["candidate_events"]) < energy(result["reference_events"])),
        ])

        source_tasks = {task["id"]: task for task in result["source_public_tasks"]}
        deadlines = {task_id: int(task["deadline"]) for task_id, task in source_tasks.items()}
        for task_id in targets["public_task_ids"]:
            labels = targets["candidate_task_labels"][task_id]
            task_events = [event for event in result["candidate_events"] if event.get("task_id") == task_id]
            completion = next((event for event in task_events if event["type"] in {"inspection_completed", "delivery_confirmed"}), None)
            report = next((event for event in task_events if event["type"] == "report_received"), None)
            completion_time = completion["time"] if completion is not None else source_tasks[task_id].get("completed_at")
            expected_completed = completion_time is not None and completion_time <= result["end_time"]
            expected_ontime = expected_completed and completion_time <= deadlines[task_id]
            self.assertEqual(labels["binary"]["service_completed_by_horizon"], expected_completed)
            self.assertEqual(labels["binary"]["service_on_time"], bool(expected_ontime))
            report_time = report["time"] if report is not None else source_tasks[task_id].get("report_received_at")
            expected_report = (
                labels["kind"] == "inspection"
                and report_time is not None
                and report_time <= result["end_time"]
                and report_time <= deadlines[task_id]
            )
            self.assertEqual(labels["binary"]["report_received_by_deadline"], bool(expected_report))
            if labels["binary_valid"]["report_received_by_deadline"]:
                self.assertEqual(labels["binary"]["report_received_by_deadline"], bool(expected_report))

        audit = targets["externality_audit"]
        self.assertGreaterEqual(audit["task_count"], len(targets["public_task_ids"]))
        self.assertIn("latent-inspection", {event.get("task_id") for event in result["candidate_events"]})

        noop = run_synthetic_candidate_pair(snapshot, "NOOP")
        self.assertTrue(all(noop["paired_targets"]["global_binary_valid"]))
        self.assertEqual(len(noop["paired_targets"]["task_binary"]), len(targets["public_task_ids"]))

    def test_all_pre_action_windows_use_bounded_c1_continuation_and_terminal_vs_censor(self):
        self.assertEqual(ENGINEERING_WINDOW_STARTS, (8, 16, 24, 32))
        for start in ENGINEERING_WINDOW_STARTS:
            with self.subTest(start=start):
                snapshot = capture_snapshot(env_at(self.scenario, start))
                output = run_synthetic_candidate_pair(snapshot, "NOOP")
                if start == 32:
                    self.assertTrue(output["terminal"])
                    self.assertFalse(output["right_censored"])
                    self.assertEqual(output["end_time"], 60)
                else:
                    self.assertFalse(output["terminal"])
                    self.assertTrue(output["right_censored"])
                    self.assertEqual(output["horizon_minutes"], 30)
                self.assertEqual(output["continuation_rule_sha256"], json.loads(snapshot)["continuation_rule_sha256"])

    def test_true_terminal_before_limit_is_not_right_censored(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["horizon"] = 12
        for task in scenario["tasks"]:
            task["deadline"] = min(int(task["deadline"]), 12)
        snapshot = capture_snapshot(env_at(scenario, 8))
        output = run_synthetic_candidate_pair(snapshot, "NOOP")
        self.assertEqual(output["end_time"], 12)
        self.assertTrue(output["terminal"])
        self.assertFalse(output["right_censored"])
        self.assertEqual(output["terminal_reason"], "episode_terminal")

    def test_unfinished_task_is_unknown_until_deadline_or_true_terminal(self):
        scenario = copy.deepcopy(self.scenario)
        task = next(task for task in scenario["tasks"] if task["id"] == "known-water")
        task["deadline"] = 50
        env = ReliefEnv(scenario)
        env.reset("C1")
        before_deadline = _task_outcome(env, "known-water", 38, False)
        self.assertIsNone(before_deadline["on_time"])
        self.assertFalse(before_deadline["valid"])
        expired = _task_outcome(env, "known-water", 50, False)
        self.assertFalse(expired["on_time"])
        self.assertTrue(expired["valid"])
        terminal = _task_outcome(env, "known-water", 38, True)
        self.assertFalse(terminal["on_time"])
        self.assertTrue(terminal["valid"])

    def test_events_after_censor_horizon_do_not_change_targets(self):
        base_env = env_at(self.scenario, 8)
        event_scenario = copy.deepcopy(self.scenario)
        event_scenario["disturbances"] = [{
            "id": "post-window-failure", "time": 39, "kind": "failure",
            "platform_id": "uav-3", "report_delay": 1,
        }]
        event_env = env_at(event_scenario, 8)
        base = run_synthetic_candidate_pair(capture_snapshot(base_env), "NOOP")
        after = run_synthetic_candidate_pair(capture_snapshot(event_env), "NOOP")
        self.assertEqual(base["end_time"], 38)
        self.assertEqual(after["end_time"], 38)
        self.assertEqual(base["global_return_delta"], after["global_return_delta"])
        self.assertEqual(base["right_censored"], after["right_censored"])

    def test_snapshot_rejects_tampered_private_state(self):
        env = env_at(self.scenario, 8)
        payload = json.loads(capture_snapshot(env))
        payload["state"]["time"] = 9
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_STATE_DIGEST"):
            restore_snapshot(json.dumps(payload))

    def test_snapshot_rejects_changed_civilian_environment_identity(self):
        env = env_at(self.scenario, 8)
        payload = json.loads(capture_snapshot(env))
        payload["implementation_sources"]["relief_env.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_IMPLEMENTATION_IDENTITY"):
            restore_snapshot(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
