import copy
import unittest

from relief_adapter.data.build_registry import (
    CONDITIONS,
    SEED_NAMESPACE,
    _apply_condition,
    derive_seed,
    semantic_scenario_hash,
)


class ScenarioRegistryTests(unittest.TestCase):
    def test_seed_namespace_is_stable_and_split_condition_specific(self):
        seed = derive_seed("train", "carrier_competition", 0)
        self.assertEqual(seed, derive_seed("train", "carrier_competition", 0))
        self.assertNotEqual(seed, derive_seed("development", "carrier_competition", 0))
        self.assertNotEqual(seed, derive_seed("train", "stock_competition", 0))
        self.assertIn("n2-fresh", SEED_NAMESPACE)
        self.assertEqual(CONDITIONS, ("carrier_competition", "stock_competition"))

    def test_semantic_hash_ignores_only_scenario_id(self):
        scenario = {"scenario_id": "old", "tasks": [{"quantity": 2}]}
        renamed = copy.deepcopy(scenario)
        renamed["scenario_id"] = "new"
        self.assertEqual(semantic_scenario_hash(scenario), semantic_scenario_hash(renamed))
        changed = copy.deepcopy(scenario)
        changed["tasks"][0]["quantity"] = 3
        self.assertNotEqual(semantic_scenario_hash(scenario), semantic_scenario_hash(changed))

    def test_carrier_condition_creates_equal_known_and_hidden_food_loads(self):
        scenario = {
            "tasks": [
                {
                    "kind": "delivery",
                    "known_initial": True,
                    "commodity": "food",
                    "quantity": 4,
                },
                {
                    "kind": "delivery",
                    "known_initial": False,
                    "commodity": "water",
                    "quantity": 9,
                },
            ]
        }
        _apply_condition(scenario, "carrier_competition")
        self.assertEqual([task["quantity"] for task in scenario["tasks"]], [16, 16])

    def test_stock_condition_sets_each_depot_to_sixty_percent_demand(self):
        scenario = {
            "tasks": [
                {"kind": "delivery", "commodity": "water", "quantity": 10},
                {"kind": "delivery", "commodity": "food", "quantity": 7},
                {"kind": "delivery", "commodity": "water", "quantity": 5},
            ],
            "depots": [{"stock": {"water": 999}}, {"stock": {"water": 999}}],
        }
        _apply_condition(scenario, "stock_competition")
        self.assertEqual([depot["stock"]["water"] for depot in scenario["depots"]], [9.0, 9.0])


if __name__ == "__main__":
    unittest.main()
