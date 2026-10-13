from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[4]
ENGINEERING = ROOT / "development" / "ch2_disaster_relief_n2_v1" / "engineering"
CIVIL = ROOT / "development" / "ch2_disaster_relief_graph_v2"
for location in (ENGINEERING, CIVIL):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from failure_export import write_records_atomically
from graph_policy import build_policy
from ppo_integration import CriticAugmentedPPOTrainer
from ppo_trainer import verify_next_update_equivalence
from world_model import (
    CriticAugmentedGraphPolicy,
    CriticOnlyGppoAdapter,
    DynamicConsequenceModel,
)


FIXTURE = CIVIL / "fixtures" / "control.json"


def _trainer(run_dir: Path, seed: int, scenarios: list[dict]) -> CriticAugmentedPPOTrainer:
    torch.manual_seed(901)
    base = build_policy("L1", seed)
    torch.manual_seed(271828)
    world_model = DynamicConsequenceModel(5, 4, 5, hidden_dim=8)
    adapter = CriticOnlyGppoAdapter(hidden_dim=8)
    policy = CriticAugmentedGraphPolicy(base, adapter, world_model)
    data_identity = hashlib.sha256(
        json.dumps(scenarios, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CriticAugmentedPPOTrainer(
        policy, variant="L1", seed=seed, scenarios=scenarios,
        data_hash=data_identity, package_root=CIVIL, run_dir=run_dir,
        allow_engineering_scenarios=True,
    )


class CivilianPPOIntegrationTests(unittest.TestCase):
    def test_real_rollout_gae_update_checkpoint_restore_and_next_round_match(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenario = json.loads(FIXTURE.read_text(encoding="utf-8"))
            scenarios = [copy.deepcopy(scenario) for _ in range(4)]
            for index, item in enumerate(scenarios):
                item["scenario_id"] = f"n2-synthetic-{index}"
            trainer = _trainer(root / "original", 8201, scenarios)
            first = trainer.train_round()
            self.assertEqual(first["transition_count"], 240)
            self.assertEqual(first["optimizer_updates"], 16)
            self.assertLessEqual(first["max_initial_probability_ratio_error"], 2e-5)
            self.assertTrue(first["checkpoint"]["path"])

            rollout_records = [json.loads(line) for line in Path(first["rollout_path"]).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rollout_records), 240)
            self.assertTrue(all("advantage" in item and "return" in item and "next_value" in item for item in rollout_records))
            episode = [item for item in rollout_records if item["episode_index"] == 0]
            self.assertTrue(episode[-1]["terminated"])
            self.assertAlmostEqual(episode[0]["next_value"], episode[1]["old_value"], places=6)

            probe = copy.deepcopy(rollout_records[0])
            probe["terminated"] = False
            probe["truncated"] = False
            probe["rollout_cut"] = False
            expected_bootstrap = float(trainer.policy.value(probe["next_policy_input"]).detach())
            trainer._attach_gae([probe])
            self.assertTrue(probe["rollout_cut"])
            self.assertAlmostEqual(probe["next_value"], expected_bootstrap, places=6)

            def restore_factory():
                return _trainer(root / "resumed", 8201, scenarios)

            equivalence = verify_next_update_equivalence(trainer, restore_factory, first["checkpoint"]["path"])
            self.assertTrue(equivalence["equivalent"])
            self.assertEqual(equivalence["compared_round"], 2)
            self.assertEqual(trainer.round_number, 2)

            success = write_records_atomically(
                root / "normal.json", [first, equivalence],
                run_identity={"scope": "synthetic", "seed": 8201},
                last_completed_update=32,
                checkpoint_path=Path(first["checkpoint"]["path"]),
            )
            self.assertEqual(success["status"], "complete")
            exported = json.loads(Path(success["path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(exported["records"]), 2)


if __name__ == "__main__":
    unittest.main()
