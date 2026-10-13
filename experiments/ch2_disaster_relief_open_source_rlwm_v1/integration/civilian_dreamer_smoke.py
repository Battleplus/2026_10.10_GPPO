"""Bounded CPU smoke for the civilian adapter and pinned R2-Dreamer overlay.

This is an engineering integration check, not a training or evaluation run.
The checkpoint intentionally excludes simulator state and replay contents.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any


UPSTREAM_REVISION = "546e4fab8146ea4b14e1d7726bbc1a8a1d50322f"
SCENARIO_RELATIVE_PATH = Path(
    "relief_adapter/data/train/relief-n2-train-carrier_competition-00.json"
)


def _set_cpu_environment() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_equal(left: Any, right: Any, np, torch) -> bool:
    if torch.is_tensor(left) and torch.is_tensor(right):
        return torch.equal(left, right)
    if isinstance(left, np.ndarray) and isinstance(right, np.ndarray):
        return np.array_equal(left, right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _tree_equal(left[key], right[key], np, torch) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, type(left)):
        return len(left) == len(right) and all(
            _tree_equal(a, b, np, torch) for a, b in zip(left, right)
        )
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _rng_state(np, torch) -> dict[str, Any]:
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }


def _set_rng_state(state: dict[str, Any], np, torch) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"])


def _rng_probe(np, torch) -> tuple[float, float, Any]:
    return random.random(), float(np.random.random()), torch.rand(4)


def _counter_state(agent, completed_updates: int) -> dict[str, Any]:
    names = ("_slow_value_updates", "_ema_updates")
    return {
        "completed_engineering_updates": int(completed_updates),
        "agent_counters": {
            name: int(getattr(agent, name))
            for name in names
            if hasattr(agent, name)
        },
        "scheduler_last_epoch": int(agent._scheduler.last_epoch),
    }


def _obs_tensordict(observation: dict[str, Any], torch, TensorDict):
    vector = torch.as_tensor(observation["vector"], dtype=torch.float32).reshape(1, -1)
    mask = torch.as_tensor(observation["action_mask"], dtype=torch.bool).reshape(1, -1)
    return TensorDict(
        {
            "vector": vector,
            "action_mask": mask,
            "is_first": torch.tensor([[observation["is_first"]]], dtype=torch.bool),
            "is_last": torch.tensor([[observation["is_last"]]], dtype=torch.bool),
            "is_terminal": torch.tensor([[observation["is_terminal"]]], dtype=torch.bool),
            "reward": torch.tensor([[observation["reward"]]], dtype=torch.float32),
            "dt": torch.tensor([[observation["dt"]]], dtype=torch.float32),
        },
        batch_size=(1,),
    )


def _make_spaces(observation: dict[str, Any], gym, np):
    obs_space = gym.spaces.Dict(
        {
            "vector": gym.spaces.Box(
                -np.inf,
                np.inf,
                shape=(int(observation["vector_length"]),),
                dtype=np.float32,
            ),
            "action_mask": gym.spaces.Box(
                0, 1, shape=(int(observation["action_size"]),), dtype=np.bool_
            ),
            "is_first": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "is_last": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "is_terminal": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "reward": gym.spaces.Box(-np.inf, np.inf, shape=(1,), dtype=np.float32),
            "dt": gym.spaces.Box(0, 1, shape=(1,), dtype=np.float32),
        }
    )
    action_space = gym.spaces.Discrete(int(observation["action_size"]))
    action_space.n = int(action_space.n)
    return obs_space, action_space


def _scalar_metrics(metrics, torch) -> dict[str, float]:
    result = {}
    for key, value in metrics.items():
        if torch.is_tensor(value) and value.numel() == 1:
            scalar = float(value.detach().cpu().item())
            if not torch.isfinite(torch.tensor(scalar)):
                raise FloatingPointError(f"non-finite update metric {key}")
            result[str(key)] = scalar
    return result


def run(repo_root: Path, output_dir: Path, *, updates: int = 3, seed: int = 8201) -> dict[str, Any]:
    _set_cpu_environment()
    output_dir.mkdir(parents=True, exist_ok=True)
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    counters = {
        "adapter_step_calls": 0,
        "physical_minutes_advanced": 0,
        "dispatch_microsteps": 0,
        "commit_steps": 0,
        "replay_frames": 0,
        "completed_updates": 0,
        "illegal_action_count": 0,
    }
    receipt: dict[str, Any] = {
        "status": "technical_stop",
        "run_kind": "engineering_smoke_not_study",
        "first_error": None,
        "formal_training": False,
        "formal_evaluation": False,
        "formal_updates": 0,
        "policy_updates": 0,
        "evaluation_episodes": 0,
        "checkpoint_path": None,
    }
    adapter = None
    try:
        if updates != 3:
            raise ValueError("civilian Dreamer smoke is fixed to exactly three updates")
        if not repo_root.is_dir():
            raise FileNotFoundError(f"package root does not exist: {repo_root}")
        scenario_path = repo_root / SCENARIO_RELATIVE_PATH
        upstream_root = (
            repo_root
            / "upstream_r2"
            / f"r2dreamer-{UPSTREAM_REVISION}"
        )
        if not upstream_root.is_dir():
            raise FileNotFoundError(f"pinned upstream checkout is missing: {upstream_root}")
        sys.path.insert(0, str(repo_root))

        import gymnasium as gym
        import numpy as np
        import torch
        from tensordict import TensorDict

        from integration.dreamer_relief import (
            PINNED_UPSTREAM_REVISION as overlay_revision,
            ReliefDreamer,
            adapter_frame_tensors,
            ReliefReplayBuffer,
        )
        from relief_adapter.factory import make_relief_adapter
        from integration.cpu_precision import CPUFloat32ReliefDreamer as ReliefDreamer
        from relief_adapter.replay_contract import action_physical_time_delta
        from upstream_smoke.upstream_dreamer_smoke import (
            _compose_config,
            _hash_state,
            _jsonable,
            _rss_bytes,
            _tree_equal as optimizer_tree_equal,
        )

        if overlay_revision != UPSTREAM_REVISION:
            raise RuntimeError("Dreamer overlay revision does not match the pinned source")
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        if torch.cuda.is_initialized():
            raise RuntimeError("CUDA initialized in CPU-only smoke")

        scenario_bytes = scenario_path.read_bytes()
        scenario = json.loads(scenario_bytes.decode("utf-8"))
        adapter = make_relief_adapter(scenario)
        observation = adapter.reset()
        obs_space, act_space = _make_spaces(observation, gym, np)

        config = _compose_config(upstream_root)
        config.batch_size = 1
        config.batch_length = 4
        config.buffer.batch_size = 1
        config.buffer.batch_length = 4
        config.buffer.max_size = 512
        config.buffer.device = "cpu"
        config.buffer.storage_device = "cpu"
        config.model.device = "cpu"
        config.model.compile = False
        config.model.rep_loss = "dreamer"
        config.model.imag_horizon = 3
        model_config = copy.deepcopy(config.model)
        agent = ReliefDreamer(
            model_config,
            obs_space,
            act_space,
            commit_action_index=int(observation["commit_action_index"]),
        ).to("cpu")
        replay = ReliefReplayBuffer(config.buffer)
        initial_observation = copy.deepcopy(observation)
        initial_binding = None
        state = agent.get_initial_state(1)
        episode_id = 0
        frame_id = 0
        episode_frame_counts: dict[int, int] = {episode_id: 0}
        update_metrics: list[dict[str, float]] = []
        update_seconds: list[float] = []
        max_collection_steps = 128
        before_rss = _rss_bytes()

        while counters["adapter_step_calls"] < max_collection_steps:
            observation_td = _obs_tensordict(observation, torch, TensorDict)
            action, next_state = agent.act(observation_td, state, eval=False)
            action_index = int(action[0].argmax().item())
            mask = observation_td["action_mask"]
            if not bool(mask[0, action_index]):
                counters["illegal_action_count"] += 1
                raise RuntimeError("Dreamer selected an action masked by the public adapter")

            frame, binding = adapter_frame_tensors(
                observation,
                outgoing_action=action_index,
                episode_id=episode_id,
                device="cpu",
            )
            if initial_binding is None:
                initial_binding = binding
            elif any(binding[key] != initial_binding[key] for key in (
                "schema", "adapter_signature_sha256", "feature_layout_sha256",
                "action_size", "commit_action_index",
            )):
                raise RuntimeError("static adapter binding changed during the smoke episode")
            frame["frame_id"] = torch.tensor([frame_id], dtype=torch.int64)
            frame["stoch"] = next_state["stoch"]
            frame["deter"] = next_state["deter"]
            replay.add_transition(TensorDict(frame, batch_size=(1,)).detach())
            counters["replay_frames"] += 1
            episode_frame_counts[episode_id] = episode_frame_counts.get(episode_id, 0) + 1
            frame_id += 1
            state = next_state

            if bool(observation["is_last"]):
                episode_id += 1
                episode_frame_counts[episode_id] = 0
                observation = adapter.reset()
                state = agent.get_initial_state(1)
                continue

            next_observation, _, terminated, truncated, info = adapter.step(action_index)
            counters["adapter_step_calls"] += 1
            actual_dt = int(info["adapter"]["physical_time_delta"])
            expected_dt = action_physical_time_delta(action_index)
            if actual_dt != expected_dt or int(next_observation["dt"]) != actual_dt:
                raise RuntimeError("action, physical dt and replay dt are misaligned")
            counters["physical_minutes_advanced"] += actual_dt
            counters["commit_steps"] += int(actual_dt == 1)
            counters["dispatch_microsteps"] += int(actual_dt == 0)
            if bool(next_observation["is_last"]) != bool(terminated or truncated):
                raise RuntimeError("adapter termination flags do not match step result")
            observation = next_observation

        minimum_episode_frames = int(config.buffer.batch_length) + 1
        usable_episodes = {
            episode: count
            for episode, count in episode_frame_counts.items()
            if count >= minimum_episode_frames
        }
        if not usable_episodes:
            raise RuntimeError(
                "collection did not produce a replay episode long enough for strict sampling"
            )
        if replay.count() < minimum_episode_frames:
            raise RuntimeError("pinned R2 replay buffer did not retain enough frames")

        parameter_hash_before = _hash_state(agent.state_dict())
        for _ in range(3):
            update_start = time.perf_counter()
            metrics = agent.update(replay)
            update_seconds.append(time.perf_counter() - update_start)
            update_metrics.append(_scalar_metrics(metrics, torch))
            counters["completed_updates"] += 1
        parameter_hash_after = _hash_state(agent.state_dict())
        if parameter_hash_after == parameter_hash_before:
            raise RuntimeError("Dreamer updates completed without changing model parameters")

        checkpoint_path = output_dir / "civilian_dreamer_smoke.pt"
        metadata = agent.checkpoint_metadata(initial_observation)
        checkpoint = {
            "model": agent.state_dict(),
            "optimizer": agent._optimizer.state_dict(),
            "scheduler": agent._scheduler.state_dict(),
            "scaler": agent._scaler.state_dict(),
            "counters": _counter_state(agent, counters["completed_updates"]),
            "rng": _rng_state(np, torch),
            "metadata": metadata,
            "seed": int(seed),
            "upstream_revision": UPSTREAM_REVISION,
            "checkpoint_scope": {
                "includes": ["agent_model", "optimizer", "scheduler", "scaler", "counters", "rng", "adapter_metadata"],
                "excludes": ["replay_buffer", "simulator_state"],
            },
        }
        torch.save(checkpoint, checkpoint_path)
        saved = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        restored = ReliefDreamer(
            copy.deepcopy(config.model),
            obs_space,
            act_space,
            commit_action_index=int(initial_observation["commit_action_index"]),
        ).to("cpu")
        restored.load_state_dict(saved["model"], strict=True)
        restored._optimizer.load_state_dict(saved["optimizer"])
        restored._scheduler.load_state_dict(saved["scheduler"])
        restored._scaler.load_state_dict(saved["scaler"])
        for name, value in saved["counters"]["agent_counters"].items():
            setattr(restored, name, value)
        restored_model_hash = _hash_state(restored.state_dict())
        if restored_model_hash != parameter_hash_after:
            raise RuntimeError("strict model checkpoint restore changed the model state")
        if not optimizer_tree_equal(saved["optimizer"], restored._optimizer.state_dict()):
            raise RuntimeError("optimizer checkpoint state did not round-trip")
        if not optimizer_tree_equal(saved["scheduler"], restored._scheduler.state_dict()):
            raise RuntimeError("scheduler checkpoint state did not round-trip")
        if not optimizer_tree_equal(saved["scaler"], restored._scaler.state_dict()):
            raise RuntimeError("scaler checkpoint state did not round-trip")
        if saved["counters"] != _counter_state(restored, counters["completed_updates"]):
            raise RuntimeError("update counters did not round-trip")
        restored_metadata = restored.checkpoint_metadata(initial_observation)
        if restored_metadata != saved["metadata"]:
            raise RuntimeError("adapter-bound checkpoint metadata did not round-trip")

        expected_rng = saved["rng"]
        random.random()
        np.random.random()
        torch.rand(3)
        _set_rng_state(expected_rng, np, torch)
        restored_rng = _rng_state(np, torch)
        if not _tree_equal(expected_rng, restored_rng, np, torch):
            raise RuntimeError("Python, NumPy or Torch CPU RNG state did not round-trip")

        receipt.update(
            {
                "status": "pass",
                "cpu_precision": "float32_overlay",
                "exact_upstream_reproduction": False,
                "python": platform.python_version(),
                "torch": torch.__version__,
                "gymnasium": gym.__version__,
                "numpy": np.__version__,
                "device": "cpu",
                "cuda_initialized": torch.cuda.is_initialized(),
                "torch_threads": torch.get_num_threads(),
                "upstream_revision": UPSTREAM_REVISION,
                "scenario_id": scenario.get("scenario_id"),
                "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
                "adapter_signature_sha256": initial_observation["adapter_signature_sha256"],
                "feature_layout_sha256": initial_observation["feature_layout_sha256"],
                "action_size": int(initial_observation["action_size"]),
                "commit_action_index": int(initial_observation["commit_action_index"]),
                "batch_size": int(config.batch_size),
                "batch_length": int(config.batch_length),
                "minimum_replay_episode_frames": minimum_episode_frames,
                "usable_episode_frame_counts": usable_episodes,
                "update_metrics": update_metrics,
                "update_wall_seconds": update_seconds,
                "parameter_hash_before": parameter_hash_before,
                "parameter_hash_after": parameter_hash_after,
                "checkpoint_model_restore_hash": restored_model_hash,
                "replay_overlay": replay.overlay_name,
                "replay_alignment_trace": replay.alignment_trace,
                "checkpoint_optimizer_restored": True,
                "checkpoint_scheduler_restored": True,
                "checkpoint_scaler_restored": True,
                "checkpoint_counters_restored": True,
                "checkpoint_rng_restored": True,
                "checkpoint_metadata_restored": True,
                "checkpoint_scope": checkpoint["checkpoint_scope"],
                "checkpoint_path": str(checkpoint_path),
                "checkpoint_bytes": checkpoint_path.stat().st_size,
                "rss_before_bytes": before_rss,
                "formal_environment_steps": 0,
                "formal_world_model_updates": 0,
                "formal_policy_updates": 0,
                "formal_evaluation_episodes": 0,
            }
        )
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        receipt["first_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "sha256": hashlib.sha256(error_text.encode("utf-8")).hexdigest(),
            "traceback": traceback.format_exc(),
        }
    finally:
        if adapter is not None:
            close = getattr(getattr(adapter, "env", None), "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    if receipt.get("first_error") is None:
                        error_text = f"{type(exc).__name__}: {exc}"
                        receipt["status"] = "technical_stop"
                        receipt["first_error"] = {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "sha256": hashlib.sha256(error_text.encode("utf-8")).hexdigest(),
                            "traceback": traceback.format_exc(),
                        }
        receipt["resource"] = {
            **counters,
            "wall_seconds": time.perf_counter() - started_wall,
            "process_cpu_seconds": time.process_time() - started_cpu,
        }
        try:
            from upstream_smoke.upstream_dreamer_smoke import _rss_bytes

            receipt["resource"]["rss_after_bytes"] = _rss_bytes()
        except Exception:
            receipt["resource"]["rss_after_bytes"] = None
        receipt_path = output_dir / "civilian-dreamer-smoke-receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        receipt["receipt_path"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--updates", type=int, default=3)
    parser.add_argument("--seed", type=int, default=8201)
    args = parser.parse_args()
    result = run(args.repo_root.resolve(), args.output_dir.resolve(), updates=args.updates, seed=args.seed)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
