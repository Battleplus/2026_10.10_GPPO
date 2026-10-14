import sys,json,subprocess,pathlib,site,datetime,hashlib,time,traceback
root=pathlib.Path('/home/user1/w1-pilot/rlwm-engineering-20261014')
specpath=root/'execution/environment-spec-r2.json'
spec=json.loads(specpath.read_text())
canonical=json.dumps(spec,sort_keys=True,separators=(',',':')).encode()
receipt={'schema':'rlwm-linux-environment-build/1','spec_sha256':hashlib.sha256(canonical).hexdigest(),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phases':[],'status':'running','old_runtime_modified':False}
rt=root/'runtime';rt.mkdir(exist_ok=True);out=root/'setup-r2';out.mkdir(exist_ok=True)
venv=rt/'venv-r2';python=venv/'bin/python';start=time.perf_counter()
def save():
 (out/'status.json').write_text(json.dumps(receipt,indent=2))
def call(argv,name,timeout=180):
 with (out/(name+'.log')).open('wb') as log:
  s=time.perf_counter();p=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
 receipt['phases'].append({'name':name,'exit_code':p.returncode,'wall_seconds':time.perf_counter()-s,'argv':argv});save()
 if p.returncode:raise RuntimeError(name+' failed; see preserved log')
try:
 assert not venv.exists(),'new environment path already exists'
 call([sys.executable,'-m','venv',str(venv)],'create-venv')
 sites=subprocess.check_output([str(python),'-c','import site,json; print(json.dumps(site.getsitepackages()))'],text=True)
 local=pathlib.Path(json.loads(sites)[0]);(local/'read_only_original_runtime.pth').write_text('/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/lib/python3.11/site-packages\n')
 for i,phase in enumerate(spec['pip_phases']):
  call([str(python),'-m','pip','install','--disable-pip-version-check',*phase['options'],*phase['packages']],f'install-phase-{i}')
 call([str(python),'-m','pip','check'],'pip-check',60)
 receipt['status']='installed_pending_witness_and_engineering';receipt['python']=str(python)
except Exception as exc:
 receipt['status']='technical_stop';receipt['first_error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
finally:
 receipt['wall_seconds']=time.perf_counter()-start;receipt['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
print(json.dumps(receipt));sys.exit(0 if receipt['status']=='installed_pending_witness_and_engineering' else 1)
