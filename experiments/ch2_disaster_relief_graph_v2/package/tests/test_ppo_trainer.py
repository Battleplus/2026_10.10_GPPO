import unittest
import tempfile
from pathlib import Path

import numpy as np
import torch

from ppo_trainer import _optimizer_state_digest, compute_gae, source_identity


class GeneralizedAdvantageEstimationTests(unittest.TestCase):
    def test_optimizer_digest_binds_ordered_parameter_mapping_and_tensor_metadata(self):
        parameters = [torch.nn.Parameter(torch.tensor([1.0, 2.0])), torch.nn.Parameter(torch.tensor([3.0]))]
        optimizer = torch.optim.Adam(parameters, lr=3e-4)
        sum(parameter.square().sum() for parameter in parameters).backward()
        optimizer.step()
        state = optimizer.state_dict()
        original = _optimizer_state_digest(state)

        reordered = {
            "param_groups": [dict(state["param_groups"][0], params=list(reversed(state["param_groups"][0]["params"])))],
            "state": state["state"],
        }
        self.assertNotEqual(original, _optimizer_state_digest(reordered))

        metadata_changed = {
            "param_groups": state["param_groups"],
            "state": {
                key: {
                    **values,
                    "exp_avg": values["exp_avg"].to(dtype=torch.float64),
                }
                for key, values in state["state"].items()
            },
        }
        self.assertNotEqual(original, _optimizer_state_digest(metadata_changed))

    def test_terminal_truncation_and_rollout_cut_masks(self):
        advantages, returns = compute_gae(
            rewards=[1.0, 2.0, 3.0, 4.0],
            values=[0.5, 0.25, 1.0, 1.5],
            next_values=[0.25, 99.0, 2.0, 6.0],
            terminated=[False, True, False, False],
            truncated=[False, False, True, False],
            rollout_cut=[False, False, False, True],
            gamma=0.9,
            gae_lambda=0.8,
        )

        np.testing.assert_allclose(advantages, [1.985, 1.75, 3.8, 7.9], rtol=0, atol=1e-6)
        np.testing.assert_allclose(returns, [2.485, 2.0, 4.8, 9.4], rtol=0, atol=1e-6)

    def test_rejects_misaligned_transition_fields(self):
        with self.assertRaisesRegex(ValueError, "lengths must match"):
            compute_gae(
                rewards=[1.0],
                values=[],
                next_values=[0.0],
                terminated=[True],
                truncated=[False],
                rollout_cut=[False],
            )

    def test_checkpoint_identity_covers_runtime_and_evaluation_dependencies(self):
        package_root = Path(__file__).resolve().parents[1]
        identity = source_identity(package_root)

        self.assertTrue({
            "driver.py",
            "ppo_trainer.py",
            "evaluator.py",
            "resource_supervisor.py",
            "graph_policy.py",
            "literal_graph_ops.py",
            "relief_env.py",
            "dataset_protocol.py",
            "protocol/preregistered_protocol.json",
            "PRIOR_RESOURCE_COST.json",
            "fixtures/control.json",
            "fixtures/external_commitment.json",
        }.issubset(identity))

    def test_source_identity_requires_prior_cost_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "PRIOR_RESOURCE_COST.json"):
                source_identity(Path(temporary))


if __name__ == "__main__":
    unittest.main()
