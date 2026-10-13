import json
import unittest
from pathlib import Path

from relief_adapter.factory import (
    make_relief_adapter,
)
from relief_adapter.replay_contract import (
    COMMIT_ACTION_INDEX,
    DISPATCH_ACTION_COUNT,
)


class FactoryReplaySmokeTests(unittest.TestCase):
    def test_default_vendor_factory_replay_metadata(self):
        package_root = Path(__file__).resolve().parents[1]
        fixture = (
            package_root
            / "vendor"
            / "relief_env_v2"
            / "fixtures"
            / "control.json"
        )
        scenario = json.loads(fixture.read_text(encoding="utf-8"))
        adapter = make_relief_adapter(scenario)
        self.assertEqual(Path(adapter.source_root).resolve(), fixture.parent.parent.resolve())
        self.assertEqual(len(adapter.source_tree_sha256), 64)
        observation = adapter.reset()

        self.assertTrue(observation["is_first"])
        self.assertEqual(observation["dt"], 0)
        self.assertEqual(observation["commit_action_index"], COMMIT_ACTION_INDEX)
        self.assertEqual(len(observation["action_mask"]), COMMIT_ACTION_INDEX + 1)
        self.assertTrue(observation["action_mask"][COMMIT_ACTION_INDEX])
        self.assertIsInstance(observation["vector"], __import__("array").array)
        self.assertEqual(observation["vector"].typecode, "f")

        dispatches = [
            index
            for index, legal in enumerate(observation["action_mask"][:DISPATCH_ACTION_COUNT])
            if legal
        ]
        if dispatches:
            next_observation, reward, terminated, truncated, info = adapter.step(dispatches[0])
            self.assertEqual(next_observation["dt"], 0)
            self.assertEqual(info["adapter"]["physical_time_delta"], 0)
            self.assertEqual(info["adapter"]["discount_exponent"], 0)
            self.assertEqual(next_observation["reward"], reward)
            observation = next_observation
            if terminated or truncated:
                return

        next_observation, reward, terminated, truncated, info = adapter.step(
            COMMIT_ACTION_INDEX
        )
        self.assertEqual(next_observation["dt"], 1)
        self.assertEqual(info["adapter"]["physical_time_delta"], 1)
        self.assertEqual(info["adapter"]["discount_exponent"], 1)
        self.assertEqual(next_observation["is_last"], bool(terminated or truncated))
        self.assertEqual(next_observation["is_terminal"], bool(terminated))
        self.assertEqual(next_observation["reward"], reward)


if __name__ == "__main__":
    unittest.main()
