from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[4]
ENGINEERING = ROOT / "development" / "ch2_disaster_relief_n2_v1" / "engineering"
CIVIL = ROOT / "development" / "ch2_disaster_relief_graph_v2"
if str(ENGINEERING) not in sys.path:
    sys.path.insert(0, str(ENGINEERING))
if str(CIVIL) not in sys.path:
    sys.path.insert(0, str(CIVIL))

from graph_policy import build_policy
from relief_env import ReliefEnv
from world_model import (
    CriticOnlyGppoAdapter,
    DynamicConsequenceModel,
    EngineeringTrainer,
    GppoEngineeringTrainer,
    InputBinding,
    public_branch_batch,
    _tensor_state_digest,
    gppo_critic_forward,
    pair_weighted_ranking_loss,
    branch_records_to_targets,
    consequence_loss,
)


FIXTURE = CIVIL / "fixtures" / "control.json"


def assert_optimizer_states_equal(test: unittest.TestCase, left: dict, right: dict) -> None:
    test.assertEqual(left["param_groups"], right["param_groups"])
    test.assertEqual(left["state"].keys(), right["state"].keys())
    for parameter_id in left["state"]:
        test.assertEqual(left["state"][parameter_id].keys(), right["state"][parameter_id].keys())
        for name, value in left["state"][parameter_id].items():
            other = right["state"][parameter_id][name]
            if isinstance(value, torch.Tensor):
                torch.testing.assert_close(value, other, rtol=0.0, atol=0.0)
            else:
                test.assertEqual(value, other)


def synthetic_batch(candidate_ids: tuple[str, ...] = ("c0", "c1", "NOOP"), task_ids: tuple[str, ...] = ("t0", "t1")) -> dict:
    generator = torch.Generator().manual_seed(90210)
    context = torch.randn((1, 3), generator=generator)
    candidate_features = torch.randn((1, len(candidate_ids), 4), generator=generator)
    task_features = torch.randn((1, len(task_ids), 5), generator=generator)
    candidate_mask = torch.ones((1, len(candidate_ids)), dtype=torch.bool)
    task_mask = torch.ones((1, len(task_ids)), dtype=torch.bool)
    binding = InputBinding((candidate_ids,), (task_ids,))
    target = {
        "binary": torch.tensor([[[1.0, 0.0]] * len(candidate_ids)]),
        "continuous": torch.tensor([[[0.1, 0.2, 0.0, -0.1]] * len(candidate_ids)]),
        "per_task": torch.zeros((1, len(candidate_ids), len(task_ids), 4)),
        "per_task_continuous": torch.zeros((1, len(candidate_ids), len(task_ids), 2)),
    }
    valid = {
        "binary": candidate_mask.unsqueeze(-1).expand_as(target["binary"]).clone(),
        "continuous": candidate_mask.unsqueeze(-1).expand_as(target["continuous"]).clone(),
        "per_task": (candidate_mask[:, :, None] & task_mask[:, None, :]).unsqueeze(-1).expand_as(target["per_task"]).clone(),
        "per_task_continuous": (candidate_mask[:, :, None] & task_mask[:, None, :]).unsqueeze(-1).expand_as(target["per_task_continuous"]).clone(),
    }
    noop_index = candidate_ids.index("NOOP")
    valid["per_task"][:, noop_index] = False
    valid["per_task_continuous"][:, noop_index] = False
    return {
        "inputs": {"context": context, "candidate_features": candidate_features,
                   "task_features": task_features, "candidate_mask": candidate_mask,
                   "task_mask": task_mask, "binding": binding},
        "target": target,
        "valid": valid,
        "window_ids": (("synthetic-parent", 0, "t8"),),
    }


class DynamicWorldModelTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(11)
        self.model = DynamicConsequenceModel(3, 4, 5, hidden_dim=16)

    def test_dynamic_public_task_axes_and_candidate_id_join(self):
        batch = synthetic_batch()
        args = batch["inputs"]
        output = self.model(args["context"], args["candidate_features"], args["task_features"],
                            args["candidate_mask"], args["task_mask"], args["binding"])
        self.assertEqual(output["per_task"].shape, (1, 3, 2, 4))
        self.assertEqual(output["per_task_continuous"].shape, (1, 3, 2, 2))
        self.assertEqual(output["candidate_ids"], args["binding"].candidate_ids)
        self.assertEqual(output["task_ids"], args["binding"].task_ids)

        permutation = torch.tensor([2, 0, 1])
        permuted_ids = tuple(args["binding"].candidate_ids[0][i] for i in permutation.tolist())
        permuted_binding = InputBinding((permuted_ids,), args["binding"].task_ids)
        permuted = self.model(args["context"], args["candidate_features"][:, permutation], args["task_features"],
                              args["candidate_mask"][:, permutation], args["task_mask"], permuted_binding)
        for index, candidate_id in enumerate(args["binding"].candidate_ids[0]):
            other_index = permuted_ids.index(candidate_id)
            torch.testing.assert_close(output["continuous"][0, index], permuted["continuous"][0, other_index])
            torch.testing.assert_close(output["per_task"][0, index], permuted["per_task"][0, other_index])
            torch.testing.assert_close(output["per_task_continuous"][0, index], permuted["per_task_continuous"][0, other_index])

        larger = synthetic_batch(task_ids=("t0", "t1", "t2", "t3"))
        large_out = self.model(
            larger["inputs"]["context"], larger["inputs"]["candidate_features"], larger["inputs"]["task_features"],
            larger["inputs"]["candidate_mask"], larger["inputs"]["task_mask"], larger["inputs"]["binding"])
        self.assertEqual(large_out["per_task"].shape, (1, 3, 4, 4))
        self.assertEqual(large_out["per_task_continuous"].shape, (1, 3, 4, 2))

    def test_binding_rejects_duplicate_or_missing_noop_ids(self):
        batch = synthetic_batch(candidate_ids=("c0", "c1", "c1", "NOOP"))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDIDATE_ID"):
            args = batch["inputs"]
            self.model(args["context"], args["candidate_features"], args["task_features"],
                        args["candidate_mask"], args["task_mask"], args["binding"])

    def test_noop_has_global_supervision_but_no_task_supervision(self):
        batch = synthetic_batch()
        noop = batch["inputs"]["binding"].candidate_ids[0].index("NOOP")
        self.assertTrue(bool(batch["valid"]["continuous"][0, noop].all()))
        self.assertFalse(bool(batch["valid"]["per_task"][0, noop].any()))
        self.assertFalse(bool(batch["valid"]["per_task_continuous"][0, noop].any()))

    def test_real_branch_targets_join_dynamic_axes_and_train(self):
        import json
        from branching import _step_c1, capture_snapshot, run_synthetic_candidate_pair

        scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for task in scenario["tasks"]:
            if task["id"] == "latent-water":
                task["report_delay"] = 6
        hidden_inspection = copy.deepcopy(next(task for task in scenario["tasks"] if task["id"] == "inspect-east"))
        hidden_inspection.update({
            "id": "latent-inspection", "known_initial": False,
            "discovered_by": "inspect-east", "deadline": 45, "priority": 1, "report_delay": 6,
        })
        scenario["tasks"].append(hidden_inspection)
        env = ReliefEnv(scenario)
        env.reset("C1")
        for _ in range(8):
            _, _, terminated, truncated, _ = _step_c1(env)
            self.assertFalse(terminated or truncated)
        snapshot = capture_snapshot(env)
        catalog = env.policy_input()["candidates"]
        candidate_ids = tuple(item["id"] for item in catalog)
        records = [run_synthetic_candidate_pair(snapshot, candidate_id) for candidate_id in reversed(candidate_ids)]
        batch = public_branch_batch(
            env.policy_input(), records, window_id=("control-parent", 8, "t8"),
        )
        target, valid, window_ids = batch["target"], batch["valid"], batch["window_ids"]
        task_ids = batch["inputs"]["binding"].task_ids[0]
        self.assertEqual(tuple(window_ids), (("control-parent", 8, "t8"),))
        self.assertEqual(target["per_task"].shape, (1, len(candidate_ids), len(task_ids), 4))
        self.assertEqual(target["per_task_continuous"].shape, (1, len(candidate_ids), len(task_ids), 2))
        noop = candidate_ids.index("NOOP")
        self.assertFalse(bool(valid["per_task"][0, noop].any()))
        self.assertFalse(bool(valid["per_task_continuous"][0, noop].any()))
        self.assertTrue(bool(valid["binary"][0, noop].all()))
        self.assertTrue(bool(valid["continuous"][0, noop].all()))

        model = DynamicConsequenceModel(5, 4, 5, hidden_dim=16)
        args = batch["inputs"]
        prediction = model(
            args["context"], args["candidate_features"], args["task_features"],
            args["candidate_mask"], args["task_mask"], args["binding"],
        )
        loss, parts = consequence_loss(prediction, target, valid, window_ids)
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(set(parts), {
            "binary", "continuous", "per_task_binary", "per_task_continuous",
            "ranking", "ranking_reduction", "valid_pair_count",
        })
        trainer = EngineeringTrainer(model, data_identity="real-branch-target-fixture-v1")
        report = trainer.update(batch)
        self.assertTrue(torch.isfinite(torch.tensor(report["loss"])))

    def test_pair_weighted_ranking_uses_pair_denominator_and_skips_empty(self):
        predicted = torch.tensor([0.0, 0.3, 0.0, 0.3, 0.6])
        target = torch.tensor([0.0, 1.0, 0.0, 1.0, 2.0])
        valid = torch.ones(5, dtype=torch.bool)
        windows = (("p", 0, "A"), ("p", 0, "A"), ("p", 0, "B"), ("p", 0, "B"), ("p", 0, "B"))
        loss, stats = pair_weighted_ranking_loss(predicted, target, valid, windows)
        expected_pairs = []
        for i, j in ((0, 1), (2, 3), (2, 4), (3, 4)):
            expected_pairs.append(torch.nn.functional.softplus(-torch.sign(target[i] - target[j]) * (predicted[i] - predicted[j])))
        torch.testing.assert_close(loss, torch.stack(expected_pairs).mean())
        self.assertEqual(stats["valid_pair_count"], 4)
        empty, empty_stats = pair_weighted_ranking_loss(predicted, target, torch.zeros(5, dtype=torch.bool), windows)
        self.assertTrue(torch.isfinite(empty))
        self.assertEqual(float(empty), 0.0)
        self.assertEqual(empty_stats["valid_pair_count"], 0)

    def test_checkpoint_next_update_matches_continuous_update_and_rejects_bad_identity(self):
        batch = synthetic_batch()
        torch.manual_seed(71)
        continuous = EngineeringTrainer(DynamicConsequenceModel(3, 4, 5, 16), data_identity="synthetic-engineering-v1")
        resumed = EngineeringTrainer(DynamicConsequenceModel(3, 4, 5, 16), data_identity="synthetic-engineering-v1")
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "next-update.pt"
            continuous.save_checkpoint(checkpoint)
            resumed.restore_checkpoint(checkpoint)
            loss_a = continuous.update(batch)
            loss_b = resumed.update(batch)
            self.assertEqual(loss_a["update_index"], loss_b["update_index"])
            self.assertAlmostEqual(loss_a["loss"], loss_b["loss"], places=8)
            self.assertEqual(_tensor_state_digest(continuous.model.state_dict()), _tensor_state_digest(resumed.model.state_dict()))
            assert_optimizer_states_equal(self, continuous.optimizer.state_dict(), resumed.optimizer.state_dict())

            wrong = EngineeringTrainer(DynamicConsequenceModel(3, 4, 5, 16), data_identity="other-data")
            before = _tensor_state_digest(wrong.model.state_dict())
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_IDENTITY_MISMATCH"):
                wrong.restore_checkpoint(checkpoint)
            self.assertEqual(before, _tensor_state_digest(wrong.model.state_dict()))

    def test_injected_post_step_failure_rolls_back_model_optimizer_and_counter(self):
        batch = synthetic_batch()
        torch.manual_seed(84)
        trainer = EngineeringTrainer(DynamicConsequenceModel(3, 4, 5, 16), data_identity="synthetic-engineering-v1")
        model_before = _tensor_state_digest(trainer.model.state_dict())
        optimizer_before = copy.deepcopy(trainer.optimizer.state_dict())
        with self.assertRaisesRegex(RuntimeError, "INJECTED_AFTER_OPTIMIZER_STEP"):
            trainer.update(batch, failpoint="after_optimizer_step")
        self.assertEqual(0, trainer.update_index)
        self.assertEqual(model_before, _tensor_state_digest(trainer.model.state_dict()))
        assert_optimizer_states_equal(self, optimizer_before, trainer.optimizer.state_dict())

    def test_actual_graph_policy_critic_adapter_is_actor_independent_and_equal_capacity(self):
        scenario = __import__("json").loads(FIXTURE.read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        env.reset("C1")
        public_input = env.policy_input()

        torch.manual_seed(123)
        policy_g = build_policy("L0", seed=37)
        policy_wm = build_policy("L0", seed=37)
        torch.manual_seed(555)
        adapter_g = CriticOnlyGppoAdapter()
        torch.manual_seed(555)
        adapter_wm = CriticOnlyGppoAdapter()
        self.assertEqual(sum(p.numel() for p in adapter_g.parameters()), sum(p.numel() for p in adapter_wm.parameters()))
        for left, right in zip(adapter_g.parameters(), adapter_wm.parameters()):
            torch.testing.assert_close(left, right)

        ids, logits_g, value_g = gppo_critic_forward(policy_g, public_input, adapter_g, wm_enabled=False)
        wm_values = torch.linspace(-100.0, 100.0, len(ids)).unsqueeze(0).requires_grad_()
        ids_wm, logits_wm, value_wm = gppo_critic_forward(
            policy_wm, public_input, adapter_wm, wm_candidate_value=wm_values,
            wm_candidate_ids=ids,
            wm_enabled=True, wm_source_identity="synthetic-world-model-sha256:fixture-v1",
        )
        self.assertEqual(ids, ids_wm)
        torch.testing.assert_close(logits_g, logits_wm)
        self.assertNotEqual(float(value_g.detach()), float(value_wm.detach()))
        self.assertEqual(adapter_wm.provenance()["wm_source_identity"], "synthetic-world-model-sha256:fixture-v1")

        critic_loss = (value_wm - torch.tensor(1.25)).square()
        critic_loss.backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in adapter_wm.parameters()))
        self.assertIsNone(wm_values.grad)
        self.assertTrue(all(parameter.grad is None for parameter in policy_wm.pair_actor.parameters()))

    def test_actual_gppo_update_consumes_trained_wm_and_resumes_adapter(self):
        import json
        from graph_policy import encode_public_graph

        scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        env.reset("C1")
        public_input = env.policy_input()
        graph = encode_public_graph(public_input)
        task_ids = tuple(task["id"] for task in public_input["observation"]["tasks"])
        batch = synthetic_batch(candidate_ids=graph.candidate_ids, task_ids=task_ids)
        torch.manual_seed(902)
        wm = DynamicConsequenceModel(3, 4, 5, 16)
        wm_trainer = EngineeringTrainer(wm, data_identity="synthetic-engineering-fixture-v1")
        wm_trainer.update(batch)
        wm.eval()
        with torch.no_grad():
            inputs = batch["inputs"]
            prediction = wm(inputs["context"], inputs["candidate_features"], inputs["task_features"],
                            inputs["candidate_mask"], inputs["task_mask"], inputs["binding"])
            candidate_values = prediction["continuous"][:, :, 0].detach()
        wm_candidate_ids = inputs["binding"].candidate_ids[0]
        wm_source = _tensor_state_digest(wm.state_dict())

        selected_id = graph.candidate_ids[0]
        policy0 = build_policy("L0", seed=147)
        base_logits, _ = policy0._graph_outputs(graph)
        selected_index = graph.candidate_ids.index(selected_id)
        old_log_probability = torch.distributions.Categorical(logits=base_logits).log_prob(torch.tensor(selected_index)).detach()

        def make_trainer(seed: int) -> GppoEngineeringTrainer:
            policy = build_policy("L0", seed=147)
            torch.manual_seed(seed)
            adapter = CriticOnlyGppoAdapter()
            return GppoEngineeringTrainer(
                policy, adapter, data_identity="synthetic-gppo-fixture-v1", wm_enabled=True,
                wm_source_identity=wm_source,
            )

        continuous = make_trainer(322)
        resumed = make_trainer(322)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "gppo-before-next-update.pt"
            metadata = continuous.save_checkpoint(checkpoint)
            self.assertEqual(metadata["next_batch_index"], 0)
            resumed.restore_checkpoint(checkpoint)
            arguments = {
                "policy_input": public_input,
                "selected_candidate_id": selected_id,
                "legal_candidate_ids": graph.candidate_ids,
                "old_log_probability": old_log_probability,
                "advantage": torch.tensor(0.2),
                "return_target": torch.tensor(0.7),
                "wm_candidate_value": candidate_values,
                "wm_candidate_ids": wm_candidate_ids,
                "batch_index": 0,
            }
            report_a = continuous.update(**arguments)
            report_b = resumed.update(**arguments)
            self.assertAlmostEqual(report_a["total_loss"], report_b["total_loss"], places=7)
            self.assertEqual(_tensor_state_digest(continuous.policy.state_dict()), _tensor_state_digest(resumed.policy.state_dict()))
            self.assertEqual(_tensor_state_digest(continuous.adapter.state_dict()), _tensor_state_digest(resumed.adapter.state_dict()))
            self.assertEqual(report_a["metadata"]["wm_source_identity"], wm_source)
            self.assertEqual([group["name"] for group in continuous.optimizer.param_groups], ["gppo_policy", "critic_adapter"])
            assert_optimizer_states_equal(self, continuous.optimizer.state_dict(), resumed.optimizer.state_dict())

            before_policy = _tensor_state_digest(continuous.policy.state_dict())
            before_adapter = _tensor_state_digest(continuous.adapter.state_dict())
            with self.assertRaisesRegex(RuntimeError, "GPPO_INJECTED_AFTER_OPTIMIZER_STEP"):
                continuous.update(**{**arguments, "batch_index": 1, "failpoint": "after_optimizer_step"})
            self.assertEqual(before_policy, _tensor_state_digest(continuous.policy.state_dict()))
            self.assertEqual(before_adapter, _tensor_state_digest(continuous.adapter.state_dict()))
            self.assertEqual(continuous.update_index, 1)
            self.assertEqual(continuous.next_batch_index, 1)

    def test_wm_scores_join_by_candidate_id_and_mask_invalid_candidates(self):
        scenario = __import__("json").loads(FIXTURE.read_text(encoding="utf-8"))
        env = ReliefEnv(scenario)
        env.reset("C1")
        policy_input = env.policy_input()
        policy = build_policy("L0", seed=40)
        torch.manual_seed(91)
        adapter = CriticOnlyGppoAdapter()
        ids = tuple(item["id"] for item in policy_input["candidates"])
        legal_ids = ids[:-1]
        values = torch.arange(len(legal_ids), dtype=torch.float32).unsqueeze(0)
        ordered = gppo_critic_forward(policy, policy_input, adapter, legal_candidate_ids=legal_ids,
                                      wm_candidate_value=values, wm_candidate_ids=legal_ids,
                                      wm_enabled=True, wm_source_identity="synthetic-wm-v1")
        perm = tuple(reversed(legal_ids))
        perm_values = values[:, torch.tensor(list(reversed(range(len(legal_ids))))) ]
        permuted = gppo_critic_forward(policy, policy_input, adapter, legal_candidate_ids=legal_ids,
                                       wm_candidate_value=perm_values, wm_candidate_ids=perm,
                                       wm_enabled=True, wm_source_identity="synthetic-wm-v1")
        torch.testing.assert_close(ordered[2], permuted[2])
        torch.testing.assert_close(ordered[1], permuted[1])
        with self.assertRaisesRegex(ValueError, "GPPO_ADAPTER_MISSING_WM_CANDIDATE"):
            gppo_critic_forward(policy, policy_input, adapter, legal_candidate_ids=ids,
                                wm_candidate_value=values, wm_candidate_ids=legal_ids,
                                wm_enabled=True, wm_source_identity="synthetic-wm-v1")


if __name__ == "__main__":
    unittest.main()
