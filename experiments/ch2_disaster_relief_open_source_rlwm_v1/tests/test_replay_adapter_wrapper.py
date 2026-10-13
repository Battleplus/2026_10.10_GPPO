import unittest

from relief_adapter.replay_adapter import (
    ReplayReliefAdapter,
)
from relief_adapter.replay_contract import (
    ACTION_COUNT,
    COMMIT_ACTION_INDEX,
)


class ReplayAdapterWrapperTests(unittest.TestCase):
    def _wrapper(self, used_platforms=()):
        adapter = object.__new__(ReplayReliefAdapter)
        adapter.commit_action = COMMIT_ACTION_INDEX
        adapter._used_platforms = set(used_platforms)
        return adapter

    def test_stamps_metadata_without_changing_encoder_vector(self):
        adapter = self._wrapper()
        vector = (0.25, 0.5)
        observation = {
            "vector": vector,
            "action_mask": tuple([False] * ACTION_COUNT),
            "adapter_signature_sha256": "a" * 64,
        }
        stamped = adapter._stamp(
            observation,
            dt=0,
            reward=0,
            is_first=True,
            is_last=False,
            is_terminal=False,
        )
        self.assertEqual(stamped["vector"], vector)
        self.assertTrue(stamped["is_first"])
        self.assertEqual(stamped["dt"], 0)
        self.assertTrue(stamped["action_mask"][COMMIT_ACTION_INDEX])
        self.assertEqual(len(stamped["action_mask"]), ACTION_COUNT)
        self.assertEqual(len(stamped["adapter_signature_sha256"]), 64)

    def test_full_platform_batch_leaves_only_commit_legal(self):
        adapter = self._wrapper({"p0", "p1", "p2", "p3"})
        observation = {
            "vector": (0.0,),
            "action_mask": tuple([True] * ACTION_COUNT),
            "adapter_signature_sha256": "b" * 64,
        }
        stamped = adapter._stamp(
            observation,
            dt=0,
            reward=0,
            is_first=False,
            is_last=False,
            is_terminal=False,
        )
        self.assertEqual(sum(stamped["action_mask"][:COMMIT_ACTION_INDEX]), 0)
        self.assertTrue(stamped["action_mask"][COMMIT_ACTION_INDEX])

    def test_rejects_time_or_terminal_contract_mismatch(self):
        adapter = self._wrapper()
        observation = {
            "vector": (0.0,),
            "action_mask": tuple([True] * ACTION_COUNT),
            "adapter_signature_sha256": "c" * 64,
        }
        with self.assertRaises(ValueError):
            adapter._stamp(
                observation,
                dt=2,
                reward=0,
                is_first=False,
                is_last=False,
                is_terminal=False,
            )
        with self.assertRaises(ValueError):
            adapter._stamp(
                observation,
                dt=0,
                reward=0,
                is_first=False,
                is_last=False,
                is_terminal=True,
            )


if __name__ == "__main__":
    unittest.main()
