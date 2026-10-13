from __future__ import annotations

import copy
import inspect
import json
import pathlib
import unittest
from types import SimpleNamespace

import torch
from tensordict import TensorDict
from torch import nn


DEV_ROOT = pathlib.Path(__file__).resolve().parents[1]

from integration.dreamer_relief import (
    PINNED_UPSTREAM_REVISION,
    adapter_frame_tensors,
    checkpoint_metadata,
    lambda_return_by_physical_time,
    masked_onehot_distribution,
    physical_time_reward_continuation,
    predicted_imagination_mask,
    time_discount_powers,
    validate_checkpoint_metadata,
)
from integration.dreamer_relief import ReliefReplayBuffer
from relief_adapter.factory import make_relief_adapter


FIXTURE_ROOT = DEV_ROOT / "relief_adapter" / "data" / "train"
COMMIT = 64
ACTION_SIZE = 65


class _TinyActor:
    def __init__(self):
        self.mlp = nn.Identity()
        self.last = nn.Linear(3, ACTION_SIZE, bias=False)
        with torch.no_grad():
            self.last.weight.copy_(torch.arange(ACTION_SIZE * 3, dtype=torch.float32).reshape(ACTION_SIZE, 3) / 100)


def _load_fixture(name="control.json"):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _first_legal_dispatch(observation):
    for index in range(COMMIT):
        if observation["action_mask"][index]:
            return index
    return COMMIT


class DreamerMaskTimeTests(unittest.TestCase):
    def test_upstream_is_pinned_and_dreamer_overlay_does_not_query_simulator(self):
        self.assertEqual(PINNED_UPSTREAM_REVISION, "546e4fab8146ea4b14e1d7726bbc1a8a1d50322f")
        source = inspect.getsource(__import__("integration.dreamer_relief", fromlist=["ReliefDreamer"]).ReliefDreamer._imagine)
        self.assertNotIn("env.", source)
        self.assertNotIn("candidates(", source)
        self.assertIn("_frozen_legal_mask_head(feat)", source)

    def test_real_actor_distribution_never_assigns_probability_to_masked_actions(self):
        actor = _TinyActor()
        features = torch.tensor([[1.0, 0.5, -0.25], [0.0, 0.25, 0.5]])
        mask = torch.zeros(2, ACTION_SIZE, dtype=torch.bool)
        mask[0, [2, 7, COMMIT]] = True
        mask[1, [13, COMMIT]] = True
        dist = masked_onehot_distribution(
            actor,
            features,
            mask,
            commit_action_index=COMMIT,
            unimix_ratio=0.01,
        )
        self.assertTrue(torch.equal(dist.probs[~mask], torch.zeros_like(dist.probs[~mask])))
        mode = dist.mode
        self.assertTrue(torch.equal(mode, dist.mode))
        self.assertTrue(bool(mask.gather(-1, mode.argmax(-1, keepdim=True)).all()))
        actions = torch.stack([dist.rsample() for _ in range(32)], dim=0)
        expanded_mask = mask.unsqueeze(0).expand_as(actions)
        self.assertTrue(bool(expanded_mask.gather(-1, actions.argmax(-1, keepdim=True)).all()))
        log_prob = dist.log_prob(mode)
        entropy = dist.entropy()
        self.assertTrue(torch.isfinite(log_prob).all())
        self.assertTrue(torch.isfinite(entropy).all())
        objective = (dist.rsample() * torch.arange(ACTION_SIZE, dtype=torch.float32)).sum()
        objective = objective + log_prob.sum() + entropy.sum()
        objective.backward()
        self.assertIsNotNone(actor.last.weight.grad)
        self.assertTrue(torch.isfinite(actor.last.weight.grad).all())
        self.assertGreater(float(actor.last.weight.grad.abs().sum()), 0.0)

    def test_imagination_mask_uses_only_prediction_and_forces_commit_fallback(self):
        predicted_logits = torch.full((2, ACTION_SIZE), -100.0)
        predicted_logits[1, 3] = 100.0
        mask, fallback = predicted_imagination_mask(
            predicted_logits,
            commit_action_index=COMMIT,
            threshold=0.5,
        )
        self.assertTrue(torch.equal(fallback, torch.tensor([True, False])))
        self.assertTrue(torch.equal(mask[0].nonzero().flatten(), torch.tensor([COMMIT])))
        self.assertTrue(bool(mask[1, 3]) and bool(mask[1, COMMIT]))

    def test_physical_discount_and_lambda_use_dt_zero_or_one(self):
        dt = torch.tensor([[[0.0], [1.0], [0.0], [1.0]]])
        gamma, trace = 0.99, 0.95
        discount, lambda_power = time_discount_powers(dt, gamma, trace)
        self.assertTrue(torch.allclose(discount.flatten(), torch.tensor([1.0, gamma, 1.0, gamma])))
        self.assertTrue(torch.allclose(lambda_power.flatten(), torch.tensor([1.0, trace, 1.0, trace])))

    def test_lambda_returns_distinguish_terminal_from_truncated_end(self):
        last = torch.tensor([[[False], [False], [False], [True]]])
        reward = torch.tensor([[[0.0], [0.0], [0.0], [2.0]]])
        value = torch.zeros_like(reward)
        bootstrap = torch.ones_like(reward)
        dt = torch.tensor([[[0.0], [1.0], [0.0], [1.0]]])
        truncated_terminal = torch.tensor([[[False], [False], [False], [False]]])
        terminated = torch.tensor([[[False], [False], [False], [True]]])
        gamma, trace = 0.9, 0.8

        truncated_return = lambda_return_by_physical_time(
            last, truncated_terminal, reward, value, bootstrap, dt, gamma, trace
        )
        terminated_return = lambda_return_by_physical_time(
            last, terminated, reward, value, bootstrap, dt, gamma, trace
        )
        self.assertAlmostEqual(float(truncated_return[0, -1, 0]), 2.9, places=5)
        self.assertAlmostEqual(float(terminated_return[0, -1, 0]), 2.0, places=5)
        self.assertTrue(torch.all(torch.isfinite(truncated_return)))

    def test_zero_time_microsteps_have_no_reward_or_weight_decay(self):
        predicted_reward = torch.tensor([[[4.0], [3.0], [2.0]]])
        predicted_continuation = torch.full_like(predicted_reward, 0.25)
        incoming_dt = torch.tensor([[[0.0], [0.0], [1.0]]])
        reward, continuation = physical_time_reward_continuation(
            predicted_reward, predicted_continuation, incoming_dt
        )
        self.assertTrue(torch.equal(reward[:, :2], torch.zeros_like(reward[:, :2])))
        self.assertTrue(torch.equal(continuation[:, :2], torch.ones_like(continuation[:, :2])))
        discount, _ = time_discount_powers(incoming_dt, gamma=0.9, trace_lambda=0.8)
        weights = torch.ones_like(continuation)
        weights[:, 1:] = torch.cumprod(
            continuation[:, 1:] * discount[:, 1:], dim=1
        )
        self.assertEqual(float(weights[0, 0, 0]), 1.0)
        self.assertEqual(float(weights[0, 1, 0]), 1.0)
        self.assertAlmostEqual(float(weights[0, 2, 0]), 0.25 * 0.9, places=6)

    def test_actual_adapter_frames_and_r2_buffer_keep_action_dt_and_mask_alignment(self):
        scenario_path = FIXTURE_ROOT / "relief-n2-train-carrier_competition-00.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        adapter = make_relief_adapter(scenario)
        observation = adapter.reset()
        first_action = _first_legal_dispatch(observation)
        frames = []

        frame, binding = adapter_frame_tensors(
            observation,
            is_first=True,
            outgoing_action=first_action,
            incoming_reward=0.0,
            incoming_dt=0,
            incoming_terminated=False,
            incoming_truncated=False,
            episode_id=0,
        )
        frame["frame_id"] = torch.tensor([0], dtype=torch.int64)
        frame["stoch"] = torch.zeros(1, 2, 3)
        frame["deter"] = torch.zeros(1, 4)
        frames.append(TensorDict(frame, batch_size=(1,)))

        action = first_action
        for index in range(4):
            observation, reward, terminated, truncated, info = adapter.step(action)
            incoming = info["adapter"]["physical_time_delta"]
            action = COMMIT
            frame, next_binding = adapter_frame_tensors(
                observation,
                is_first=False,
                outgoing_action=action,
                incoming_reward=reward,
                incoming_dt=incoming,
                incoming_terminated=terminated,
                incoming_truncated=truncated,
                episode_id=0,
            )
            frame_id = index + 1
            frame["frame_id"] = torch.tensor([frame_id], dtype=torch.int64)
            frame["stoch"] = torch.zeros(1, 2, 3)
            frame["deter"] = torch.zeros(1, 4)
            frames.append(TensorDict(frame, batch_size=(1,)))
            self.assertEqual(binding["adapter_signature_sha256"], next_binding["adapter_signature_sha256"])
            binding = next_binding

        config = SimpleNamespace(
            device="cpu",
            storage_device="cpu",
            batch_size=1,
            batch_length=4,
            max_size=16,
        )
        replay = ReliefReplayBuffer(config)
        for frame in frames:
            replay.add_transition(frame)
        data, _, _ = replay.sample()

        sampled_ids = data["frame_id"][0].tolist()
        self.assertEqual(len(sampled_ids), 4)
        self.assertEqual(data["action"].argmax(-1).tolist(), [[first_action, COMMIT, COMMIT, COMMIT]])
        for position, frame_id in enumerate(sampled_ids):
            source_frame = frames[int(frame_id)]
            previous_frame = frames[int(frame_id) - 1]
            self.assertTrue(torch.equal(data["action_mask"][0, position], source_frame["action_mask"][0]))
            self.assertTrue(torch.equal(data["dt"][0, position], source_frame["dt"][0]))
            self.assertTrue(torch.equal(data["action"][0, position], previous_frame["action"][0]))
        self.assertEqual(data["dt"].squeeze(-1).tolist(), [[0.0, 1.0, 1.0, 1.0]])
        self.assertNotIn("public_observation", data.keys())
        self.assertEqual(binding["action_size"], ACTION_SIZE)
        self.assertEqual(binding["commit_action_index"], COMMIT)

    def test_checkpoint_metadata_binds_model_to_adapter_layout_and_rejects_mismatch(self):
        metadata = checkpoint_metadata(
            adapter_signature_sha256="a" * 64,
            feature_layout_sha256="b" * 64,
            action_size=ACTION_SIZE,
            commit_action_index=COMMIT,
            gamma=0.99,
            trace_lambda=0.95,
        )
        validate_checkpoint_metadata(metadata, copy.deepcopy(metadata))
        wrong_layout = copy.deepcopy(metadata)
        wrong_layout["feature_layout_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "feature_layout_sha256"):
            validate_checkpoint_metadata(metadata, wrong_layout)


if __name__ == "__main__":
    unittest.main()
