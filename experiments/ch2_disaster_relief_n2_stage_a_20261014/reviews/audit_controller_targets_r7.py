"""Bounded local accounting/receipt probes; no SSH, systemd, worker launch or optimizer."""
import hashlib, json, math, sys, tempfile, time
from pathlib import Path
ROOT=Path('E:/10.14/n2-development/controller')
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from managed_stage_supervisor import GuardLimits,resource_request_from_engineering_profile
from budget_ledger import BudgetLedger
from n2_controller import collect_managed_receipts,controller_bundle_sha256

out={'scope':'local finite admission probes only','source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in ROOT.glob('*.py')},'bundle_sha256':controller_bundle_sha256()}
base={'wall_seconds_total_including_settlement':1200,'settlement_reserve_seconds':45,'complete_process_cpu_seconds_total_including_descendants_and_settlement':900,'settlement_cpu_reserve_seconds':30,'cgroup_memory_max_bytes':4294967296,'memory_settlement_reserve_bytes':1,'combined_working_plus_export_peak_bytes_max':536870912}
bad=[('cpu_nan','complete_process_cpu_seconds_total_including_descendants_and_settlement',float('nan')),('cpu_inf','complete_process_cpu_seconds_total_including_descendants_and_settlement',float('inf')),('memory_float','cgroup_memory_max_bytes',1.5),('interval_nan','sample_interval_seconds',float('nan'))]
out['guard_rejections']=[]
for name,key,value in bad:
    try:GuardLimits.from_mapping({**base,key:value})
    except Exception as e:out['guard_rejections'].append({'name':name,'error':str(e)})
    else:raise AssertionError(name+' admitted')
profile=json.loads((ROOT.parent/'LOCAL_ENGINEERING_BUDGET.json').read_text())
req=resource_request_from_engineering_profile(profile)
out['stage_allocations']={'paired_constructions':req['stages']['paired_collection']['episode_constructions'],'total_constructions':req['totals']['episode_constructions']}
out['normal_stage_operations']=[]
for stage,amounts in [('offline_prediction',{'world_model_forwards':1,'world_model_candidate_sample_evaluations':7}),('paired_collection',{'output_write_operations':1})]:
    with tempfile.TemporaryDirectory() as t:
        ledger=BudgetLedger(Path(t)/'ledger.sqlite',req);ledger.stage=stage;effect=[]
        ledger.call('independent_admission_probe',amounts,lambda:effect.append(1))
        assert effect==[1]
        ledger.connection.close()
        out['normal_stage_operations'].append({'stage':stage,'effect':effect,'amounts':amounts})

raw=b'one-checkpoint'; h=hashlib.sha256(raw).hexdigest(); inv='a'*32; bundle='B'*64
worker={'schema':'n2-managed-worker-receipt/1','status':'complete','settlement':'complete','stage_server_socket_present':True,'ledger':{'pending_calls':0,'failed_calls':0},'export_status':'complete','exports':[{'path':'checkpoint.pt','sha256':h,'bytes':len(raw)}]}
sup={'schema':'n2-managed-stage-supervisor/1','status':'complete','systemd_invocation_id':inv,'controller_bundle_sha256':bundle,'stage_server_final_stage':'settlement_and_verified_export','supervisor_pid':123,'cgroup_configuration':{'path':'/sys/fs/cgroup/user.slice/test.service','cpuset_effective':[4],'sched_affinity':[4],'cpu_quota_percent':100,'memory_max_bytes':1000},'cgroup_final':{'pids':[123],'memory_peak_bytes':100},'cgroup_cpu_seconds_total':1.0}
class Channel:
    def settimeout(self,t):assert math.isfinite(t) and t>0
class Sftp:
    def __init__(self,supervisor):self.supervisor=supervisor
    def get_channel(self):return Channel()
    def get(self,remote,local):
        if remote.endswith('managed-worker-receipt.json'):Path(local).write_text(json.dumps(worker))
        elif remote.endswith('managed-supervisor-receipt.json'):Path(local).write_text(json.dumps(self.supervisor))
        else:Path(local).write_bytes(raw)
    def close(self):pass
class Client:
    def __init__(self,supervisor):self.supervisor=supervisor
    def open_sftp(self):return Sftp(self.supervisor)
out['collector_cases']=[]
for mode in ['valid','quota_nan','cpu_nan']:
    s=json.loads(json.dumps(sup))
    if mode=='quota_nan':s['cgroup_configuration']['cpu_quota_percent']=float('nan')
    if mode=='cpu_nan':s['cgroup_cpu_seconds_total']=float('nan')
    with tempfile.TemporaryDirectory() as t:
        try:
            value=collect_managed_receipts(Client(s),'/work',Path(t)/'collected',invocation=inv,control_group='/user.slice/test.service',bundle_sha256=bundle,guard_limits={'cpu_quota_percent':100,'cgroup_memory_max_bytes':1000,'complete_process_cpu_seconds_total_including_descendants_and_settlement':900},final_stage='settlement_and_verified_export',deadline=time.monotonic()+10)
        except Exception as e:
            assert mode!='valid'
            out['collector_cases'].append({'mode':mode,'status':'rejected','error':str(e)})
        else:
            assert mode=='valid' and value['status']=='complete'
            out['collector_cases'].append({'mode':mode,'status':'complete'})
out['status']='TARGETED_LOCAL_PROBES_PASS'
destination=Path('E:/10.14/n2-governance/reviews/audit_controller_targets_r7_output.json')
destination.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
print(json.dumps(out,sort_keys=True))
