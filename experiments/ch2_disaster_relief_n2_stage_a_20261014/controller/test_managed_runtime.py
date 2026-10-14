from __future__ import annotations

import hashlib
import pathlib
import tempfile
import unittest

from managed_runtime import ManagedRuntime, ManagedRuntimeError
from managed_stage_supervisor import resource_request_from_engineering_profile
from vendor.stage_contract import STAGE_ORDER


class FakeLedger:
    stage = "settlement_and_verified_export"

    def call(self, _name, _amounts, function):
        return function()


class ManagedRuntimeContractTests(unittest.TestCase):
    def test_profile_request_uses_w7_order_and_stage_caps_fit_global_totals(self):
        profile = {
            "runtime": {
                "checkpoint_reads_and_writes_max": 32,
                "output_write_operations_max": 1000,
                "exports_max": 1,
            },
            "work_caps": {
                "base_rollout_episodes_max": 4,
                "episode_constructions_max": 1024,
                "branch_count_max": 128,
                "ppo_rollout_episodes_max": 12,
                "total_environment_steps_max": 8000,
                "wm_optimizer_steps_max": 20,
                "ppo_optimizer_steps_max": 64,
                "world_model_forwards_max": 10000,
                "world_model_candidate_sample_evaluations_max": 1280000,
                "candidate_catalog_cap_including_noop": 128,
                "candidate_truncation_allowed": False,
            },
        }
        request = resource_request_from_engineering_profile(profile)
        self.assertEqual(request["stage_order"], list(STAGE_ORDER))
        for resource, total in request["totals"].items():
            self.assertLessEqual(sum(stage.get(resource, 0)
                                     for stage in request["stages"].values()), total)
        self.assertEqual(request["stages"]["offline_prediction"]["world_model_candidate_sample_evaluations"], 128)
        self.assertEqual(request["stages"]["paired_collection"]["output_write_operations"], 1)
        self.assertEqual(
            sum(stage.get("episode_constructions", 0) for stage in request["stages"].values()),
            request["totals"]["episode_constructions"],
        )

    def test_catalog_guard_requires_full_untruncated_catalog(self):
        runtime = ManagedRuntime(
            work_root=pathlib.Path("."),
            request={"stage_order": ["input_admission"], "admission_guards": {
                "candidate_catalog_size_including_noop_max": 4,
                "candidate_truncation_allowed": False,
            }},
            ledger=FakeLedger(),
            export_root=pathlib.Path("."),
        )
        runtime.check_catalog_size(4)
        with self.assertRaisesRegex(ManagedRuntimeError, "CANDIDATE_CATALOG_CAP"):
            runtime.check_catalog_size(5)

    def test_export_hash_mismatch_never_creates_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / "checkpoint.bin"
            source.write_bytes(b"checkpoint-content")
            export_root = root / "export"
            export_root.mkdir()
            runtime = ManagedRuntime(
                work_root=root,
                request={"stage_order": ["settlement_and_verified_export"]},
                ledger=FakeLedger(),
                export_root=export_root,
            )
            actual = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            wrong = ("0" if actual[0] != "0" else "1") + actual[1:]
            with self.assertRaisesRegex(ManagedRuntimeError, "EXPORT_SHA256_MISMATCH"):
                runtime.export_verified(
                    source=source,
                    relative_path="checkpoint.bin",
                    expected_sha256=wrong,
                    amounts={"verified_exports": 1},
                )
            self.assertFalse((export_root / "checkpoint.bin").exists())
            self.assertEqual(list(export_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
