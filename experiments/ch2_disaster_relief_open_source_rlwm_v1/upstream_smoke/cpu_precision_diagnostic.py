"""Fixed-batch CPU precision diagnosis; engineering only, never a study run."""
from __future__ import annotations

import copy
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
sys.path.insert(0, str(ROOT))
from integration.dreamer_relief import PINNED_UPSTREAM_REVISION, ReliefReplayBuffer
from upstream_smoke.upstream_dreamer_smoke import _compose_config, _make_spaces, _collect_cartpole, _hash_state
from dreamer import Dreamer
import torch
import numpy as np
import gymnasium as gym


def run():
    torch.set_num_threads(1)
    random.seed(8201)
    np.random.seed(8201)
    torch.manual_seed(8201)
    repo = ROOT / 'upstream_r2' / f'r2dreamer-{PINNED_UPSTREAM_REVISION}'
    cfg = _compose_config(repo)
    obs_space, act_space = _make_spaces(gym)
    base = Dreamer(copy.deepcopy(cfg.model), obs_space, act_space).to('cpu')
    replay = ReliefReplayBuffer(cfg.buffer)
    env = gym.make('CartPole-v1', max_episode_steps=32)
    steps = _collect_cartpole(env, base, replay, 32, 8201, torch)
    data, _, initial = replay.sample()
    frozen_data = base.preprocess(data).clone()
    frozen_initial = tuple(v.clone() for v in initial)
    frozen_model = copy.deepcopy(base.state_dict())
    rng = torch.get_rng_state().clone()
    results = []
    for name, enabled in [('cpu_float16_upstream', True), ('cpu_float32_diagnostic', False)]:
        agent = Dreamer(copy.deepcopy(cfg.model), obs_space, act_space).to('cpu')
        agent.load_state_dict(frozen_model, strict=True)
        torch.set_rng_state(rng.clone())
        row = {'mode': name, 'backward_attempts': 0, 'optimizer_steps': 0, 'status': 'pending', 'iterations': []}
        start = time.perf_counter()
        try:
            for i in range(2):
                agent._optimizer.zero_grad(set_to_none=True)
                agent._update_slow_target()
                row['backward_attempts'] += 1
                with torch.autograd.detect_anomaly(check_nan=True):
                    with torch.amp.autocast('cpu', dtype=torch.float16, enabled=enabled):
                        _, metrics = agent._cal_grad(frozen_data.clone(), tuple(v.clone() for v in frozen_initial))
                bad = [n for n, p in agent._named_params.items() if p.grad is not None and not torch.isfinite(p.grad).all()]
                if bad:
                    raise FloatingPointError('nonfinite gradients before AGC: ' + repr(bad[:8]))
                agent._agc(agent._named_params.values())
                bad = [n for n, p in agent._named_params.items() if p.grad is not None and not torch.isfinite(p.grad).all()]
                if bad:
                    raise FloatingPointError('nonfinite gradients after AGC: ' + repr(bad[:8]))
                agent._optimizer.step()
                row['optimizer_steps'] += 1
                bad = [n for n, p in agent._named_params.items() if not torch.isfinite(p).all()]
                if bad:
                    raise FloatingPointError('nonfinite parameters after optimizer: ' + repr(bad[:8]))
                row['iterations'].append({'iteration': i, 'loss': float(metrics['opt/loss'].detach()), 'parameters_finite': True, 'gradients_finite': True})
            row['status'] = 'pass_two_fixed_batch_updates'
        except Exception as exc:
            row['status'] = 'technical_stop'
            row['first_error'] = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
        row['wall_seconds'] = time.perf_counter() - start
        results.append(row)
    env.close()
    receipt = {'run_kind': 'engineering_fixed_batch_precision_diagnostic', 'python': sys.version, 'torch': torch.__version__, 'upstream_revision': PINNED_UPSTREAM_REVISION, 'environment_steps': steps, 'batch_hash': _hash_state(dict(frozen_data.items())), 'initial_model_hash': _hash_state(frozen_model), 'only_changed_factor': 'CPU autocast enabled float16 versus disabled float32', 'results': results, 'target_torch_2_8_tested': False, 'formal_updates': 0, 'confirmation_evaluations': 0}
    output = ROOT / 'reports' / 'cpu-precision-diagnostic-20261014.json'
    output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    run()
