import copy, importlib.util, json, sys
from pathlib import Path
root = Path('E:/10.14/n2-development')
sys.path[:0] = [str(root), str(root/'references/civil'), str(root/'references/existing_n2')]
from relief_env import ReliefEnv
from baselines import choose_step_c1_actions
from n2_contracts import preaction_snapshot, verify_preaction, restore_preaction
scenario = json.loads((root/'references/civil/fixtures/control.json').read_text(encoding='utf-8'))
env = ReliefEnv(scenario); env.reset('C1')
snapshot = preaction_snapshot(env, 'audit-parent', 0, 't0')
for name, mutate in [
 ('duplicate_key', lambda x: x['candidate_keys'].append(copy.deepcopy(x['candidate_keys'][0]))),
 ('saved_catalog_tamper', lambda x: x['candidate_catalog'].clear()),
 ('context_time_tamper', lambda x: (x['context'].__setitem__('time', 999), [k.__setitem__('time',999) for k in x['candidate_keys']]))
]:
 changed = copy.deepcopy(snapshot); mutate(changed)
 try:
  verify_preaction(changed, env.public_observation(), env.candidates()); print(name+': ACCEPTED')
 except Exception as e: print(name+': REJECTED '+type(e).__name__+':'+str(e))
for _ in range(8):
 selected = choose_step_c1_actions(env.public_observation(), env.candidates())
 env.step([r['id'] for r in selected]+['NOOP'])
try:
 saved = preaction_snapshot(env,'audit-parent',0,'t8'); restored = restore_preaction(saved)
 print('t8_restore: PASS time='+str(restored.time)+' candidates='+str(len(restored.candidates())))
except Exception as e: print('t8_restore: FAIL '+type(e).__name__+':'+str(e))
import torch
from world_model import DynamicConsequenceModel, consequence_loss
spec=importlib.util.spec_from_file_location('audit_old_tests',root/'references/existing_n2/tests/test_world_model.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
batch=mod.synthetic_batch(); batch['valid']['continuous'][0,1,0]=False
batch['target']['continuous'][0,:,0] = torch.tensor([0.,0.,2.])
model=DynamicConsequenceModel(3,4,5,16)
def gradients(unknown):
 model.zero_grad(set_to_none=True)
 targets=copy.deepcopy(batch['target'])
 for key in targets: targets[key][~batch['valid'][key]]=unknown
 a=batch['inputs']; out=model(a['context'],a['candidate_features'],a['task_features'],a['candidate_mask'],a['task_mask'],a['binding'])
 loss,parts=consequence_loss(out,targets,batch['valid'],batch['window_ids']); loss.backward()
 return float(loss.detach()),[p.grad.clone() if p.grad is not None else None for p in model.parameters()]
a,ga=gradients(0.); b,gb=gradients(float('nan'))
print('unknown_nan_loss_equal: '+str(abs(a-b)<1e-8))
print('unknown_nan_gradient_equal: '+str(all((x is None and y is None) or (x is not None and y is not None and torch.isfinite(y).all() and torch.allclose(x,y,rtol=0,atol=0)) for x,y in zip(ga,gb))))
