"""Bind the critic-only adapter to the existing civilian PPO rollout/update path."""

from __future__ import annotations

from pathlib import Path

import torch

try:
    from ..ch2_disaster_relief_graph_v2.ppo_trainer import PPOTrainer
except ImportError:
    from ppo_trainer import PPOTrainer


class CriticAugmentedPPOTrainer(PPOTrainer):
    """Use civilian collection, bootstrap, GAE, replay and PPO; validate N2 code on restore."""

    def restore_checkpoint(self, path: str | Path) -> dict:
        payload = torch.load(Path(path), map_location="cpu", weights_only=False)
        expected_architecture = getattr(self.policy, "architecture_evidence", None)
        if payload.get("architecture_evidence") != expected_architecture:
            raise ValueError("checkpoint identity mismatch in N2 architecture evidence")
        return super().restore_checkpoint(path)
