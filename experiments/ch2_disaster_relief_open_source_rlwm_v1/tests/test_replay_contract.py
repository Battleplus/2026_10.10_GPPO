import unittest

from relief_adapter.replay_contract import (
    ACTION_COUNT,
    COMMIT_ACTION_INDEX,
    DISPATCH_ACTION_COUNT,
    action_physical_time_delta,
    adapter_signature_sha256,
    contract_document,
    dispatch_action_index,
    dispatch_action_pair,
    stamp_observation,
)


class ReplayContractTests(unittest.TestCase):
    def test_dispatch_space_and_commit_index_are_fixed(self):
        self.assertEqual(DISPATCH_ACTION_COUNT, 64)
        self.assertEqual(COMMIT_ACTION_INDEX, 64)
        self.assertEqual(ACTION_COUNT, 65)
        for platform_slot in range(4):
            for task_slot in range(16):
                index = dispatch_action_index(platform_slot, task_slot)
                self.assertEqual(dispatch_action_pair(index), (platform_slot, task_slot))
                self.assertEqual(action_physical_time_delta(index), 0)
        self.assertEqual(action_physical_time_delta(COMMIT_ACTION_INDEX), 1)

    def test_only_commit_advances_physical_time(self):
        actions = contract_document()["actions"]
        self.assertEqual(actions["dispatch_physical_time_delta"], 0)
        self.assertEqual(actions["commit_physical_time_delta"], 1)
        self.assertTrue(actions["commit_is_only_physical_time_advancing_action"])
        self.assertTrue(actions["dispatch_never_auto_commits"])
        self.assertTrue(actions["full_platform_batch_allows_only_commit"])

    def test_observation_stamps_incoming_transition_metadata(self):
        observation = {"vector": (0.0, 1.0), "action_mask": [True] * ACTION_COUNT}
        reset = stamp_observation(observation, dt=0, is_first=True)
        self.assertTrue(reset["is_first"])
        self.assertFalse(reset["is_last"])
        self.assertFalse(reset["is_terminal"])
        dispatch_next = stamp_observation(observation, dt=0)
        commit_next = stamp_observation(observation, dt=1, is_last=True)
        self.assertEqual(dispatch_next["dt"], 0)
        self.assertEqual(commit_next["dt"], 1)
        self.assertTrue(commit_next["is_last"])
        self.assertEqual(len(adapter_signature_sha256()), 64)

    def test_rejects_inconsistent_or_malformed_metadata(self):
        observation = {"vector": (0.0,), "action_mask": [True] * ACTION_COUNT}
        with self.assertRaises(ValueError):
            stamp_observation(observation, dt=2)
        with self.assertRaises(ValueError):
            stamp_observation(observation, dt=1, is_terminal=True)
        with self.assertRaises(ValueError):
            stamp_observation({"vector": (0.0,), "action_mask": [True]}, dt=0)
        with self.assertRaises(ValueError):
            dispatch_action_index(4, 0)
        with self.assertRaises(ValueError):
            dispatch_action_pair(COMMIT_ACTION_INDEX)


if __name__ == "__main__":
    unittest.main()
