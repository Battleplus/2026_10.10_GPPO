"""Small CPU smoke for the upstream Dreamer update path; not a study run."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import random
import copy
import sys
from pathlib import Path
import time
from pathlib import Path
from typing import Any


def _rss_bytes() -> int | None:
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        psapi = ctypes.WinDLL("Psapi.dll")
        kernel32 = ctypes.WinDLL("Kernel32.dll")
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if ok else None
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)
    except (ImportError, AttributeError):
        return None


def _hash_state(state: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(state.items()):
        digest.update(name.encode("utf-8"))
        if hasattr(value, "detach"):
            tensor = value.detach().cpu().contiguous()
            digest.update(str(tensor.dtype).encode("ascii"))
            digest.update(str(tuple(tensor.shape)).encode("ascii"))
            digest.update(tensor.numpy().tobytes())
        else:
            digest.update(repr(value).encode("utf-8"))
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
        return value.item() if value.numel() == 1 else value.tolist()
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _tree_equal(left: Any, right: Any) -> bool:
    import torch

    if torch.is_tensor(left) and torch.is_tensor(right):
        return torch.equal(left, right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _tree_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, type(left)):
        return len(left) == len(right) and all(
            _tree_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _compose_config(repo_root: Path):
    from hydra import compose, initialize_config_dir

    config_dir = repo_root / "configs"
    overrides = [
        "env=dmc_proprio",
        "model=size12M",
        "device=cpu",
        "batch_size=1",
        "batch_length=8",
        "buffer.max_size=256",
        "buffer.device=cpu",
        "buffer.storage_device=cpu",
        "model.rep_loss=dreamer",
        "model.compile=false",
        "model.horizon=8",
        "model.imag_horizon=3",
        "model.deter=64",
        "model.hidden=64",
        "model.discrete=8",
        "model.units=64",
        "model.rssm.stoch=8",
        "model.rssm.blocks=8",
        "model.encoder.mlp_keys='^vector$'",
        "model.encoder.cnn_keys='^$'",
        "model.decoder.mlp_keys='^vector$'",
        "model.decoder.cnn_keys='^$'",
    ]
    with initialize_config_dir(version_base=None, config_dir=str(config_dir)):
        cfg = compose(config_name="configs", overrides=overrides)
    return cfg


def _make_spaces(gym):
    import numpy as np

    obs_space = gym.spaces.Dict(
        {
            "vector": gym.spaces.Box(-np.inf, np.inf, shape=(4,), dtype=np.float32),
            "is_first": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "is_last": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "is_terminal": gym.spaces.Box(0, 1, shape=(1,), dtype=np.bool_),
            "reward": gym.spaces.Box(-np.inf, np.inf, shape=(1,), dtype=np.float32),
        }
    )
    action_space = gym.spaces.Discrete(2)
    action_space.n = int(action_space.n)
    action_space.discrete = True
    return obs_space, action_space


def _collect_cartpole(env, agent, replay, steps: int, seed: int, torch):
    import numpy as np
    from tensordict import TensorDict

    obs, _ = env.reset(seed=seed)
    state = agent.get_initial_state(1)
    episode = 0
    first = True
    last = False
    terminal = False
    reward = 0.0
    env_steps = 0
    for step in range(steps):
        trans = TensorDict(
            {
                "vector": torch.as_tensor(np.asarray(obs, dtype=np.float32))[None],
                "is_first": torch.tensor([[first]], dtype=torch.bool),
                "is_last": torch.tensor([[last]], dtype=torch.bool),
                "is_terminal": torch.tensor([[terminal]], dtype=torch.bool),
                "reward": torch.tensor([[reward]], dtype=torch.float32),
            },
            batch_size=[1],
        )
        action_out, state = agent.act(trans.clone(), state, eval=False)
        trans["action"] = action_out
        trans.update(state)
        trans["episode"] = torch.tensor([episode], dtype=torch.int64)
        replay.add_transition(trans.detach())

        action_index = int(action_out[0].argmax().item())
        if last:
            episode += 1
            obs, _ = env.reset(seed=seed + episode)
            first, last, terminal, reward = True, False, False, 0.0
            continue
        obs, reward, terminated, truncated, _ = env.step(action_index)
        env_steps += 1
        first = False
        last = bool(terminated or truncated)
        terminal = bool(terminated)
        reward = float(reward)
    return env_steps


def run(repo_root: Path, output_dir: Path, updates: int, length: int, seed: int):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    sys.path.insert(0, str(repo_root))
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    import gymnasium as gym
    import numpy as np
    import torch
    from buffer import Buffer
    from integration.dreamer_relief import ReliefReplayBuffer
    from integration.cpu_precision import CPUFloat32Dreamer as Dreamer

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

    config = _compose_config(repo_root)
    obs_space, act_space = _make_spaces(gym)
    env = gym.make("CartPole-v1", max_episode_steps=32)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    before_rss = _rss_bytes()
    agent = Dreamer(copy.deepcopy(config.model), obs_space, act_space).to("cpu")
    replay = ReliefReplayBuffer(config.buffer)
    env_steps = _collect_cartpole(env, agent, replay, steps=32, seed=seed, torch=torch)

    parameter_hash_before = _hash_state(agent.state_dict())
    update_results = []
    for _ in range(updates):
        update_results.append(_jsonable(agent.update(replay)))
    parameter_hash_after = _hash_state(agent.state_dict())
    if parameter_hash_before == parameter_hash_after:
        raise RuntimeError("Dreamer.update completed without changing model parameters")
    checkpoint_path = output_dir / "dreamer_cartpole_smoke.pt"
    checkpoint = {
        "model": agent.state_dict(),
        "optimizer": agent._optimizer.state_dict(),
        "scheduler": agent._scheduler.state_dict(),
        "scaler": agent._scaler.state_dict(),
        "seed": seed,
        "rep_loss": "dreamer",
    }
    torch.save(checkpoint, checkpoint_path)

    restored_config = copy.deepcopy(config.model)
    restored = Dreamer(restored_config, obs_space, act_space).to("cpu")
    saved = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    restored.load_state_dict(saved["model"], strict=True)
    restored._optimizer.load_state_dict(saved["optimizer"])
    restored._scheduler.load_state_dict(saved["scheduler"])
    restored._scaler.load_state_dict(saved["scaler"])
    restored_hash = _hash_state(restored.state_dict())
    if restored_hash != parameter_hash_after:
        raise RuntimeError("strict checkpoint restore produced different model parameters")
    optimizer_restore_equal = _tree_equal(
        saved["optimizer"], restored._optimizer.state_dict()
    )
    if not optimizer_restore_equal:
        raise RuntimeError("optimizer state differs after checkpoint restore")

    env.close()
    result = {
        "status": "pass",
        "run_kind": "engineering_smoke_not_study",
        "cpu_precision": "float32_overlay",
        "exact_upstream_reproduction": False,
        "replay_overlay": ReliefReplayBuffer.overlay_name,
        "checkpoint_scope": "model_optimizer_scheduler_scaler_only_not_exact_training_continuation",
        "upstream_commit": "546e4fab8146ea4b14e1d7726bbc1a8a1d50322f",
        "config": "DreamerV3 baseline, rep_loss=dreamer",
        "environment": "Gymnasium CartPole-v1",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "gymnasium": gym.__version__,
        "device": "cpu",
        "cuda_initialized": torch.cuda.is_initialized(),
        "torch_threads": torch.get_num_threads(),
        "environment_steps": env_steps,
        "updates": updates,
        "formal_updates": 0,
        "model_forward": "performed_by_upstream_Dreamer.update",
        "batch_size": 1,
        "batch_length": int(config.buffer.batch_length),
        "parameter_hash_before": parameter_hash_before,
        "parameter_hash_after": parameter_hash_after,
        "checkpoint_model_restore_hash": restored_hash,
        "checkpoint_optimizer_restored": optimizer_restore_equal,
        "update_metrics": update_results,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "wall_seconds": time.perf_counter() - start_wall,
        "process_cpu_seconds": time.process_time() - start_cpu,
        "rss_before_bytes": before_rss,
        "rss_after_bytes": _rss_bytes(),
    }
    result_path = output_dir / "smoke-receipt.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--updates", type=int, default=3)
    parser.add_argument("--length", type=int, default=8)
    parser.add_argument("--seed", type=int, default=8201)
    args = parser.parse_args()
    result = run(args.repo_root.resolve(), args.output_dir.resolve(), args.updates, args.length, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
