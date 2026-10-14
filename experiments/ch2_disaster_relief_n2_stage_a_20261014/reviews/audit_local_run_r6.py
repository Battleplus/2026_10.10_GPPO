"""Read-only independent audit; no model, environment, optimizer or training execution."""
import hashlib, json, math
from pathlib import Path
import numpy as np
import torch

ROOT = Path('E:/10.14/n2-development')
RUN = ROOT/'runs/local-1791969402746190800'
ART = RUN/'artifacts'
OUT = Path('E:/10.14/n2-governance/reviews/audit_local_run_r6_output.json')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest().upper()
def rows(p): return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def equal(a,b):
    if isinstance(a,torch.Tensor): return isinstance(b,torch.Tensor) and torch.equal(a,b)
    if isinstance(a,np.ndarray): return np.array_equal(a,b)
    if isinstance(a,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)): return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b
def tensor_digest(s,wm=False):
    h=hashlib.sha256()
    for k,t in sorted(s.items()):
        t=t.detach().cpu().contiguous()
        for part in [k.encode(),str(t.dtype).encode(),(json.dumps(list(t.shape)) if wm else str(tuple(t.shape))).encode(),t.numpy().tobytes()]: h.update(part)
    return h.hexdigest().upper()
def load(p):
    with torch.serialization.safe_globals([np._core.multiarray._reconstruct,np.ndarray,np.dtype,np.dtypes.UInt32DType]):
        return torch.load(p,map_location='cpu',weights_only=True)
def steps(c): return sorted(set(int(v['step'].item()) for v in c['optimizer' if 'optimizer' in c else 'optimizer_state']['state'].values()))

w=json.loads((RUN/'WATCHDOG_RECEIPT.json').read_text()); r=json.loads((ART/'LOCAL_ENGINEERING_RECEIPT.json').read_text()); p=json.loads((ROOT/'LOCAL_ENGINEERING_BUDGET.json').read_text())
assert w['profile_sha256']==sha(ROOT/'LOCAL_ENGINEERING_BUDGET.json')==r['budget']['sha256']
for file,h in w['source_sha256'].items(): assert sha(ROOT/file)==h==r['source_sha256'][file]
b=rows(ART/'branch_records.jsonl'); assert len(b)==7
ids=[x['candidate_id'] for x in b]; assert len(set(ids))==7 and ids==r['branch']['candidate_ids']
refs=[x['reference_transitions'] for x in b]; assert all(x==refs[0] for x in refs)
noop=b[ids.index('NOOP')]; assert noop['candidate_transitions']==noop['reference_transitions'] and noop['candidate_events']==noop['reference_events']
assert noop['paired_targets']['global_continuous']==[0.,0.,0.,0.] and not noop['target_task_head_valid']
identity_fields=['source_state_sha256','scenario_sha256','source_prefix_sha256','implementation_sha256','continuation_rule_sha256','contract_context']
assert all(all(x[k]==b[0][k] for k in identity_fields) for x in b)
data_identity=digest({'fixture_sha256':sha(ROOT/'references/civil/fixtures/control.json'),'records':b})
label_summary=[]
for x in b:
    t=x['paired_targets']; assert x['window_start']==8 and x['end_time']==38 and x['horizon_minutes']==30 and not x['terminal'] and x['right_censored']
    assert t['global_binary']==[0.,0.] and t['global_continuous'][2:]==[0.,0.]
    assert len(x['candidate_transitions'])==len(x['reference_transitions'])==len(x['candidate_step_rewards'])==len(x['reference_step_rewards'])==30
    for side in ['candidate','reference']:
        for i,z in enumerate(x[side+'_transitions']):
            assert z['time']==8+i and z['public_observation']['time']==8+i
            assert digest(z['public_observation'])==z['observation_sha256'].upper()==z['identity']['observation_sha256'].upper()
            assert digest(z['candidates'])==z['candidate_catalog_sha256'].upper()==z['identity']['candidate_catalog_sha256'].upper()
            assert all(a['id'] in {a['id'] for a in z['candidates']} for a in z['selected_actions'])
        first=[a['id'] for a in x[side+'_transitions'][0]['selected_actions']]
        assert (first==[x['candidate_id']]) if side=='candidate' and x['candidate_id']!='NOOP' else first in [[],['NOOP']]
    reward=sum(x['candidate_step_rewards'])-sum(x['reference_step_rewards'])
    energy=sum(e.get('energy',0.) for e in x['candidate_events'])-sum(e.get('energy',0.) for e in x['reference_events'])
    assert math.isclose(reward,t['global_continuous'][0],abs_tol=1e-12) and math.isclose(energy,t['global_continuous'][1],abs_tol=1e-12)
    taskdiff=[k for k in t['public_task_ids'] if t['candidate_task_labels'][k]!=t['reference_task_labels'][k]]
    label_summary.append({'candidate_id':x['candidate_id'],'global_deltas':t['global_continuous'],'task_labels_changed':taskdiff})

curves=rows(ART/'ppo-original/learning_curve.jsonl')+rows(ART/'ppo-restored/learning_curve.jsonl')
assert len(curves)==3 and sum(x['optimizer_updates'] for x in curves)==48 and sum(len(x['episodes']) for x in curves)==12
rollout_counts=[]
for x in curves:
    f=Path(x['rollout_path']); a=rows(f); assert len(a)==x['transition_count']==240 and sha(f)==x['rollout_sha256'].upper()
    assert sha(Path(x['checkpoint']['path']))==x['checkpoint']['sha256'].upper()
    assert len({z['episode_index'] for z in a})==4 and all(sum(z['episode_index']==i for z in a)==60 for i in range(4))
    rollout_counts.append({'path':str(f),'rows':len(a),'terminated':sum(z['terminated'] for z in a),'truncated':sum(z['truncated'] for z in a),'rollout_cut':sum(z['rollout_cut'] for z in a)})
assert (ART/'ppo-original/rollouts/round_0002.jsonl').read_bytes()==(ART/'ppo-restored/rollouts/round_0002.jsonl').read_bytes()
wm10=load(ART/'wm-checkpoint.pt'); wm11=load(ART/'wm-frozen-checkpoint.pt')
assert wm10['identity']['data_identity']==wm11['identity']['data_identity']==data_identity
assert wm10['update_index']==10 and wm11['update_index']==11 and steps(wm10)==[10] and steps(wm11)==[11]
assert tensor_digest(wm10['model'],True)==wm10['model_sha256'] and tensor_digest(wm11['model'],True)==wm11['model_sha256']==r['world_model']['final_frozen_wm_sha256']
assert sha(ART/'wm-checkpoint.pt')==r['world_model']['checkpoint_sha256'] and sha(ART/'wm-frozen-checkpoint.pt')==r['world_model']['final_frozen_checkpoint_sha256']
wmchanged=[k for k in wm10['model'] if not torch.equal(wm10['model'][k],wm11['model'][k])]; assert wmchanged
c1=load(ART/'ppo-original/checkpoints/round_0001.pt'); c2=load(ART/'ppo-original/checkpoints/round_0002.pt'); cr=load(ART/'ppo-restored/checkpoints/round_0002.pt')
assert steps(c1)==[16] and steps(c2)==steps(cr)==[32]
for c in [c1,c2,cr]: assert tensor_digest(c['model_state'])==c['model_state_sha256'].upper() and c['architecture_evidence']['wm_source_identity']==wm11['model_sha256']
assert equal(c2['model_state'],cr['model_state']) and equal(c2['optimizer_state'],cr['optimizer_state'])
ppochanged=[k for k in c1['model_state'] if not torch.equal(c1['model_state'][k],c2['model_state'][k])]; assert ppochanged
wm_policy_keys=[k for k in c2['model_state'] if k.startswith('world_model.')]
frozen_matches={k: any(k.endswith(wk) and torch.equal(c2['model_state'][k],wv) for wk,wv in wm11['model'].items()) for k in wm_policy_keys}
assert wm_policy_keys and all(frozen_matches.values())
assert all(equal({k:c['model_state'][k] for k in wm_policy_keys},{k:c2['model_state'][k] for k in wm_policy_keys}) for c in [c1,cr])
files=[f for f in RUN.rglob('*') if f.is_file()]; actual_bytes=sum(f.stat().st_size for f in files)
assert actual_bytes<p['runtime']['output_tree_bytes_max'] and w['exit_code']==0 and w['violation'] is None and w['worker_cleanup_verified'] and not w['unexpected_descendants_seen']
assert w['wall_seconds']<1200 and w['final_process_tree_cpu_seconds']<900 and w['process_tree_rss_bytes_peak_sample']<4294967296
assert r['measurement']['total_environment_steps']==sum(r['measurement']['environment_steps_by_phase'].values())==1384
result={'status':'LOCAL_ENGINEERING_EVIDENCE_VERIFIED_WITH_LIMITS','hashes_current_match_frozen':True,'data_identity_sha256':data_identity,'branch_labels':label_summary,'raw_paired_steps':sum(len(x['candidate_transitions'])+len(x['reference_transitions']) for x in b),'rollout_counts':rollout_counts,'real_ppo_update_evidence':{'curve_sum':48,'checkpoint_adam_steps':[16,32,32],'changed_tensor_count':len(ppochanged),'changed_tensor_names':ppochanged,'restored_model_optimizer_exact_equal':True},'wm_update_evidence':{'receipt_total_including_restored_comparison':12,'checkpoint_indices':[10,11],'checkpoint_adam_steps':[steps(wm10),steps(wm11)],'changed_tensor_count_between_10_11':len(wmchanged),'policy_frozen_wm_tensor_count':len(wm_policy_keys),'policy_frozen_wm_exact_matches':all(frozen_matches.values())},'resources':{'wall_seconds':w['wall_seconds'],'cpu_seconds':w['final_process_tree_cpu_seconds'],'rss_peak_sample':w['process_tree_rss_bytes_peak_sample'],'actual_output_bytes_including_watchdog_receipt':actual_bytes,'actual_file_count':len(files),'watchdog_receipt_actual_bytes':(RUN/'WATCHDOG_RECEIPT.json').stat().st_size,'planned_total_discrepancy_bytes':actual_bytes-w['output_tree_bytes_planned_including_receipt']},'artifact_sha256':{str(f.relative_to(RUN)):sha(f) for f in files}}
OUT.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},sort_keys=True))
