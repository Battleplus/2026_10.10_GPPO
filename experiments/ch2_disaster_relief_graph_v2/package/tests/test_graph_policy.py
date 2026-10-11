from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from graph_policy import STRUCTURAL_ZERO_NODE_COLUMNS, build_paired_policies, encode_public_graph
from relief_env import ReliefEnv


def _scenario(name: str = "control") -> dict:
    return json.loads((ROOT / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def _input(scenario: dict, policy: str = "L1") -> tuple[ReliefEnv, dict]:
    env = ReliefEnv(scenario)
    env.reset(policy)
    return env, env.policy_input()


class GraphPolicyTests(unittest.TestCase):
    def test_static_parameter_match_and_common_seed_initialization(self):
        l0, l1, evidence = build_paired_policies(8201)
        self.assertTrue(evidence["parameter_match_within_5_percent"])
        self.assertLessEqual(evidence["L0"]["relative_parameter_difference"], 0.05)
        self.assertEqual(l0.common_init_sha256, l1.common_init_sha256)
        self.assertEqual(evidence["common_init_sha256"], l0.common_init_sha256)
        self.assertEqual(l1.architecture_evidence["hidden_dim"], 64)
        self.assertEqual(l1.active_parameter_count(), l1.architecture_evidence["active_parameters"])
        self.assertLessEqual(
            abs(l0.active_parameter_count() - l1.active_parameter_count()) / l1.active_parameter_count(),
            0.05,
        )

    def test_structurally_unavailable_task_relations_are_frozen(self):
        _, policy_input = _input(_scenario())
        graph = encode_public_graph(policy_input)
        l0, l1, _ = build_paired_policies(8204)

        from literal_graph_ops import TASK_PREDECESSOR_EDGE, TASK_SUCCESSOR_EDGE

        self.assertFalse(bool((graph.edge_types == TASK_PREDECESSOR_EDGE).any()))
        self.assertFalse(bool((graph.edge_types == TASK_SUCCESSOR_EDGE).any()))
        predecessor_weight = l1.task_update.predecessor_mlp[0].weight
        successor_weight = l1.task_update.successor_mlp[0].weight
        self.assertFalse(predecessor_weight.requires_grad)
        self.assertFalse(successor_weight.requires_grad)
        self.assertTrue(bool((graph.node_features[:, list(STRUCTURAL_ZERO_NODE_COLUMNS)] == 0).all()))

        for policy in (l0, l1):
            sample = policy.sample_batch(policy_input, deterministic=True)
            loss = -(sample["log_prob"] + sample["value"])
            loss.backward()
            first_layer_gradient = policy.node_encoder[0].weight.grad
            self.assertEqual(
                float(first_layer_gradient[:, list(STRUCTURAL_ZERO_NODE_COLUMNS)].abs().sum()),
                0.0,
            )
        self.assertIsNone(predecessor_weight.grad)
        self.assertIsNone(successor_weight.grad)

    def test_candidate_ids_map_to_pairs_and_conditional_replay_matches(self):
        _, policy_input = _input(_scenario())
        graph = encode_public_graph(policy_input)
        self.assertEqual(graph.node_features.shape, (8, 60))
        self.assertEqual(graph.node_types.tolist().count(1), 4)
        self.assertEqual(graph.node_types.tolist().count(2), 4)
        self.assertEqual(graph.candidate_ids[-1], "NOOP")

        l0, l1, _ = build_paired_policies(8202)
        for policy in (l0, l1):
            sample = policy.sample_batch(policy_input, deterministic=False)
            replay = policy.evaluate_batch(policy_input, sample["actions"], sample["masks"])
            self.assertTrue(torch.allclose(sample["log_prob"], replay["log_prob"], atol=1e-7, rtol=0))
            self.assertTrue(torch.allclose(sample["value"], replay["value"], atol=1e-7, rtol=0))
            objective = -(replay["log_prob"] * 1.2) + 0.5 * replay["value"].square() - 0.01 * replay["entropy"]
            objective.backward()
            variant_parameters = policy.literal_attention.parameters() if policy.variant == "L1" else policy.entity_mlp.parameters()
            grad_sum = sum(float(parameter.grad.abs().sum()) for parameter in variant_parameters if parameter.grad is not None)
            self.assertGreater(grad_sum, 0.0)

    def test_public_permutation_padding_and_variable_entity_sizes(self):
        _, policy_input = _input(_scenario())
        policy = build_paired_policies(8203)[1]
        ids, logits, value = policy(policy_input)

        permuted = copy.deepcopy(policy_input)
        permuted["observation"]["platforms"].reverse()
        permuted["observation"]["tasks"].reverse()
        ids_permuted, logits_permuted, value_permuted = policy(permuted)
        self.assertEqual(ids, ids_permuted)
        self.assertTrue(torch.allclose(logits, logits_permuted, atol=1e-7, rtol=0))
        self.assertTrue(torch.allclose(value, value_permuted, atol=1e-7, rtol=0))

        encoded = encode_public_graph(policy_input, pad_to=(6, 8))
        padded_logits, padded_value = policy._graph_outputs(encoded)
        self.assertTrue(torch.allclose(logits, padded_logits, atol=1e-6, rtol=0))
        self.assertTrue(torch.allclose(value, padded_value, atol=1e-6, rtol=0))
        self.assertEqual(int(encoded.node_mask.sum()), 8)
        self.assertEqual(int(encoded.platform_mask.sum()), 4)
        self.assertEqual(int(encoded.task_mask.sum()), 4)

        smaller = copy.deepcopy(policy_input)
        smaller["observation"]["platforms"] = smaller["observation"]["platforms"][:1]
        smaller["observation"]["tasks"] = smaller["observation"]["tasks"][:1]
        smaller["candidates"] = [{"id": "NOOP", "type": "noop"}]
        smaller_graph = encode_public_graph(smaller)
        self.assertEqual(smaller_graph.node_features.shape, (2, 60))
        self.assertEqual(policy.sample_batch(smaller, deterministic=True)["actions"], [])

    def test_noop_only_and_empty_entity_graph_are_finite(self):
        _, base = _input(_scenario())
        empty = copy.deepcopy(base)
        empty["observation"]["platforms"] = []
        empty["observation"]["tasks"] = []
        empty["candidates"] = [{"id": "NOOP", "type": "noop"}]
        l0, l1, _ = build_paired_policies(8201)
        for policy in (l0, l1):
            sample = policy.sample_batch(empty, deterministic=True)
            replay = policy.evaluate_batch(empty, sample["actions"], sample["masks"])
            self.assertEqual(sample["actions"], [])
            self.assertEqual(sample["masks"][0]["selected_id"], "NOOP")
            self.assertTrue(torch.isfinite(sample["value"]))
            self.assertTrue(torch.isfinite(replay["log_prob"]))

    def test_hidden_task_and_unreported_disturbance_do_not_change_policy_input(self):
        base = _scenario()
        hidden = next(task for task in base["tasks"] if not task["known_initial"])
        changed = copy.deepcopy(base)
        changed_hidden = next(task for task in changed["tasks"] if task["id"] == hidden["id"])
        changed_hidden["id"] = "hidden-task-with-unseen-id"
        changed_hidden["position"] = [1.75, 1.5]
        changed_hidden["priority"] = 4.75
        changed_hidden["deadline"] = 59
        changed_hidden["report_delay"] = 11
        changed["disturbances"] = [{
            "id": "unreported-failure",
            "time": 3,
            "kind": "failure",
            "platform_id": "uav-2",
            "report_delay": 9,
        }]
        env_a, input_a = _input(base)
        env_b, input_b = _input(changed)
        self.assertEqual(input_a, input_b)
        self.assertEqual(env_a.candidates(), env_b.candidates())

        queued_hidden = copy.deepcopy(base)
        hidden_id = next(task["id"] for task in queued_hidden["tasks"] if not task["known_initial"])
        queued_hidden["chapter1_snapshot"]["queues"]["uav-3"].append(hidden_id)
        with self.assertRaisesRegex(ValueError, "hidden task .* cannot be in chapter1_snapshot"):
            ReliefEnv(queued_hidden)

    def test_rejects_forged_residual_mask(self):
        _, policy_input = _input(_scenario())
        policy = build_paired_policies(8201)[0]
        sample = policy.sample_batch(policy_input, deterministic=True)
        forged = copy.deepcopy(sample["masks"])
        forged[0]["valid_mask"][0] = not forged[0]["valid_mask"][0]
        with self.assertRaisesRegex(ValueError, "residual entity constraints"):
            policy.evaluate_batch(policy_input, sample["actions"], forged)

    def test_same_batch_mask_reserves_public_depot_stock_and_replays(self):
        scenario = _scenario()
        scenario["scenario_id"] = "same-batch-stock-reservation"
        scenario["depots"][0]["stock"]["water"] = 18
        food = next(task for task in scenario["tasks"] if task["id"] == "known-food")
        food.update({"commodity": "water", "quantity": 15})
        env, policy_input = _input(scenario)

        water_id = "dispatch:uav-1:known-water"
        food_id = "dispatch:heli-1:known-food"
        self.assertIn(water_id, {item["id"] for item in policy_input["candidates"]})
        self.assertIn(food_id, {item["id"] for item in policy_input["candidates"]})
        candidates_by_id = {item["id"]: item for item in policy_input["candidates"]}
        policy_input["candidates"] = [
            candidates_by_id[water_id],
            candidates_by_id[food_id],
            {"id": "NOOP", "type": "noop"},
        ]

        for policy in build_paired_policies(8201)[:2]:
            with torch.no_grad():
                for parameter in policy.parameters():
                    parameter.zero_()
            sample = policy.sample_batch(policy_input, deterministic=True)
            self.assertEqual(sample["actions"], [water_id])
            graph = encode_public_graph(policy_input)
            selected_index = graph.candidate_ids.index(water_id)
            selected_pair = graph.candidate_pairs[selected_index]
            requirement = graph.candidate_stock_requirements[selected_index]
            assert selected_pair is not None and requirement is not None
            stock_limits = {(depot_id, commodity): amount for depot_id, commodity, amount in graph.stock_limits}
            next_mask = policy._mask_at_step(
                graph.candidate_ids,
                graph.candidate_pairs,
                graph.candidate_stock_requirements,
                stock_limits,
                {selected_pair[0]},
                {selected_pair[1]},
                {(requirement[0], requirement[1]): requirement[2]},
            )
            self.assertEqual(next_mask, [False, False, True])
            replay = policy.evaluate_batch(policy_input, sample["actions"], sample["masks"])
            self.assertTrue(torch.allclose(sample["log_prob"], replay["log_prob"], atol=1e-7, rtol=0))

    def test_graph_stock_mask_subtracts_public_in_flight_commitments(self):
        scenario = _scenario()
        scenario["scenario_id"] = "graph-public-inflight-stock-reservation"
        scenario["depots"][0]["stock"]["water"] = 18
        tasks = {task["id"]: task for task in scenario["tasks"]}
        tasks["known-water"].update({"quantity": 10})
        tasks["known-food"].update({"commodity": "water", "quantity": 9})
        for platform in scenario["platforms"]:
            platform["capacity_kg"] = 12

        env, _ = _input(scenario)
        first = next(
            candidate for candidate in env.candidates()
            if candidate["id"] == "dispatch:uav-1:known-water"
        )
        env.step([first["id"]])
        policy_input = env.policy_input()
        graph = encode_public_graph(policy_input)
        self.assertEqual(
            {(depot_id, commodity): amount for depot_id, commodity, amount in graph.stock_limits}[("depot-1", "water")],
            8.0,
        )
        self.assertNotIn("dispatch:heli-1:known-food", {row["id"] for row in policy_input["candidates"]})


if __name__ == "__main__":
    unittest.main()
