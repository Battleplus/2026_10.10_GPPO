from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator import checkpoint_barrier, run_evaluation
from graph_policy import build_policy
from ppo_trainer import (
    EXPECTED_VARIANTS,
    PPOConfig,
    SEEDS,
    _optimizer_state_digest,
    _state_digest,
    sha256_file,
    source_identity,
)


class CheckpointBarrierTests(unittest.TestCase):
    def _write_bundle(self, training_root: Path) -> tuple[dict, list[Path]]:
        training_root.mkdir(parents=True, exist_ok=True)
        package_root = ROOT
        registry_hash = sha256_file(package_root / "registered_data" / "input_registry.json")
        sources = source_identity(package_root)
        entries = []
        checkpoint_paths = []

        for seed in SEEDS:
            for variant in EXPECTED_VARIANTS:
                policy = build_policy(variant, seed)
                optimizer = torch.optim.Adam(policy.parameters(), lr=PPOConfig().learning_rate)
                model_state = policy.state_dict()
                optimizer_state = optimizer.state_dict()
                model_digest = _state_digest(model_state)
                optimizer_digest = _optimizer_state_digest(optimizer_state)
                run_id = f"{variant}-{seed}"
                relative_path = Path(run_id) / "final.pt"
                checkpoint_path = training_root / relative_path
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "schema": "relief-ppo-checkpoint/1",
                    "variant": variant,
                    "seed": seed,
                    "round_number": 8,
                    "training_complete": True,
                    "target_rounds": 8,
                    "config": asdict(PPOConfig()),
                    "data_hash": registry_hash,
                    "source_hashes": sources,
                    "architecture_evidence": policy.architecture_evidence,
                    "model_state": model_state,
                    "optimizer_state": optimizer_state,
                    "model_state_sha256": model_digest,
                    "optimizer_state_sha256": optimizer_digest,
                }
                torch.save(payload, checkpoint_path)
                checkpoint_paths.append(checkpoint_path)
                entries.append({
                    "run_id": run_id,
                    "variant": variant,
                    "seed": seed,
                    "rounds": 8,
                    "path": relative_path.as_posix(),
                    "sha256": sha256_file(checkpoint_path),
                    "model_state_sha256": model_digest,
                    "optimizer_state_sha256": optimizer_digest,
                    "architecture_evidence": policy.architecture_evidence,
                })

        (training_root / "budget_freeze.json").write_text(
            json.dumps({"eligible": True, "common_rounds": 8}), encoding="utf-8"
        )
        manifest = {
            "training_complete": True,
            "common_rounds": 8,
            "input_registry_sha256": registry_hash,
            "runs": entries,
        }
        (training_root / "final_checkpoints.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return manifest, checkpoint_paths

    def test_barrier_recomputes_checkpoint_optimizer_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            training_root = Path(temporary)
            manifest, checkpoint_paths = self._write_bundle(training_root)

            passed = checkpoint_barrier(ROOT, training_root)
            self.assertTrue(passed["passed"])
            self.assertTrue(passed["registry_validation"]["protocol_sha256"])
            self.assertEqual(passed["checkpoint_count"], 6)

    def test_barrier_rejects_strict_architecture_load_failure_before_heldout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            training_root = Path(temporary)
            manifest, checkpoint_paths = self._write_bundle(training_root)
            checkpoint_path = checkpoint_paths[0]
            payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            payload["model_state"]["unexpected.weight"] = torch.zeros(1)
            payload["model_state_sha256"] = _state_digest(payload["model_state"])
            torch.save(payload, checkpoint_path)
            manifest["runs"][0]["sha256"] = sha256_file(checkpoint_path)
            manifest["runs"][0]["model_state_sha256"] = payload["model_state_sha256"]
            (training_root / "final_checkpoints.json").write_text(json.dumps(manifest), encoding="utf-8")

            with patch("evaluator.load_registered_scenarios") as heldout_loader:
                with self.assertRaisesRegex(PermissionError, "strict model loading"):
                    run_evaluation(ROOT, training_root, Path(temporary) / "evaluation")
                heldout_loader.assert_not_called()

            checkpoint_path = checkpoint_paths[0]
            payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            payload["optimizer_state"]["param_groups"][0]["lr"] *= 2
            torch.save(payload, checkpoint_path)
            manifest["runs"][0]["sha256"] = sha256_file(checkpoint_path)
            (training_root / "final_checkpoints.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            with self.assertRaisesRegex(PermissionError, "optimizer state checksum"):
                checkpoint_barrier(ROOT, training_root)


if __name__ == "__main__":
    unittest.main()
