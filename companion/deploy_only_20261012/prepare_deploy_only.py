from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


PREP = pathlib.Path(__file__).resolve().parent
FROZEN = PREP.parent
RELEASE = FROZEN / "release"
IDENTITY = "ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012"
UNIT = "n01-full-evaluation-r2-formal-repair-v1-20261012.service"
BASE = "/home/user1/w1-pilot"
RUNTIME = "/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha(payload.encode("ascii"))


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_local_release() -> tuple[dict, dict[str, str]]:
    bindings = read_json(FROZEN / "FROZEN_BINDINGS.json")
    artifacts = read_json(FROZEN / "ARTIFACT_HASHES.json")
    id_path = RELEASE / "N01_FULL_EVALUATION_IDENTITY.json"
    budget_path = RELEASE / "n01_full_evaluation_stage_budget.json"
    reader_path = RELEASE / "static_plan_r2.json"
    identity = read_json(id_path)
    budget = read_json(budget_path)
    reader = read_json(reader_path)
    if bindings["evaluation_identity"] != IDENTITY or identity["evaluation_identity"] != IDENTITY:
        raise ValueError("frozen evaluation identity mismatch")
    checks = {
        "identity_sha256": sha(id_path.read_bytes()),
        "stage_budget_sha256": sha(budget_path.read_bytes()),
        "reader_sha256": sha(reader_path.read_bytes()),
        "plan_sha256": reader["plan_sha256"],
    }
    for key, value in checks.items():
        if bindings[key] != value:
            raise ValueError(f"frozen binding mismatch: {key}")
    if budget["evaluation_identity"] != IDENTITY or budget["status"] != "proposed":
        raise ValueError("frozen stage budget is not proposed for the new identity")
    if budget.get("approval_reference") is not None or budget.get("approved_by") is not None:
        raise ValueError("frozen budget unexpectedly contains approval fields")
    if reader.get("evaluation_identity") != IDENTITY or reader.get("identity_sha256") != bindings["identity_sha256"]:
        raise ValueError("frozen reader does not bind the identity manifest")

    files = {key[len("release/"):]: value for key, value in artifacts["files"].items() if key.startswith("release/")}
    if len(files) != 560 or len(files) != len(set(files)):
        raise ValueError(f"expected 560 frozen release files, got {len(files)}")
    for rel, expected in files.items():
        path = (RELEASE / pathlib.PurePosixPath(rel)).resolve(strict=True)
        if RELEASE.resolve() not in path.parents:
            raise ValueError(f"release file escapes package: {rel}")
        if sha(path.read_bytes()) != expected:
            raise ValueError(f"release file hash mismatch: {rel}")
    sources = {name: sha((RELEASE / name).read_bytes()) for name in identity["current_source_hashes"]}
    if sources != identity["current_source_hashes"] or sources != bindings["package_source_hashes"]:
        raise ValueError("identity-bound package source hashes mismatch")
    if len(identity["checkpoint_sha256"]) != 6 or identity["scope"]["scenario_count"] != 350 or identity["scope"]["episode_count"] != 2800:
        raise ValueError("frozen evaluation scope mismatch")
    if bindings["unit_name"] != UNIT or bindings["package_source_count"] != 28:
        raise ValueError("frozen unit or source count mismatch")
    request = read_json(FROZEN / "N01_FULL_EVALUATION_BUDGET_APPROVAL_REQUEST.json")
    if request["evaluation_identity"] != IDENTITY or request["status"] != "NOT_APPROVED":
        raise ValueError("frozen request must remain NOT_APPROVED")
    return bindings, files


def make_archive(files: dict[str, str]) -> tuple[bytes, str]:
    output = io.BytesIO()
    manifest = json.dumps({"schema": "n01-deploy-release-manifest/1", "files": files}, sort_keys=True, separators=(",", ":")).encode("ascii")
    with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=6, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            meta = tarfile.TarInfo("META/deploy-manifest.json")
            meta.size = len(manifest)
            meta.mode = 0o644
            meta.mtime = 0
            archive.addfile(meta, io.BytesIO(manifest))
            for rel in sorted(files):
                raw = (RELEASE / pathlib.PurePosixPath(rel)).read_bytes()
                info = tarfile.TarInfo(f"package/{rel}")
                info.size = len(raw)
                info.mode = 0o755 if rel.endswith(".sh") else 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
    return output.getvalue(), sha(manifest)


REMOTE_BODY = r'''import hashlib, io, json, os, pathlib, shutil, subprocess, sys, tarfile
CFG=json.loads(CONFIG_JSON)
BASE=pathlib.Path(CFG["base"]); PACKAGES=BASE/"packages"
PKG=PACKAGES/CFG["package_name"]; STAGE=PACKAGES/CFG["stage_name"]
DIAG=BASE/"diagnostics"/CFG["diagnostics_name"]; RUN=BASE/"runs"/CFG["run_name"]
UNIT=CFG["unit"]; UNIT_FILE=pathlib.Path(CFG["unit_file"])
SYSTEMCTL=CFG["systemctl"]; RUNTIME=CFG["runtime"]
COMMAND_INDEX=0
def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def run(argv,check=True,env=None):
    global COMMAND_INDEX
    p=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if DIAG.is_dir():
        COMMAND_INDEX+=1; stem=DIAG/("child-%03d"%COMMAND_INDEX)
        stem.with_suffix(".stdout.txt").write_text(p.stdout,encoding="utf-8")
        stem.with_suffix(".stderr.txt").write_text(p.stderr,encoding="utf-8")
        stem.with_suffix(".json").write_text(json.dumps({"argv":argv,"returncode":p.returncode},sort_keys=True,indent=2)+"\n",encoding="utf-8")
    if check and p.returncode: raise RuntimeError("child rc=%s argv=%r stdout=%s stderr=%s"%(p.returncode,argv,p.stdout[-3000:],p.stderr[-3000:]))
    return p
if any(os.path.lexists(p) for p in (PKG,STAGE,DIAG,RUN,UNIT_FILE)):
    raise SystemExit("new package/stage/diagnostics/run/unit path already exists; refusing overwrite")
if not PACKAGES.is_dir() or not DIAG.parent.is_dir(): raise SystemExit("base package/diagnostics directories must exist")
old=run(SYSTEMCTL+["--user","show",UNIT,"--no-pager","-p","LoadState"],check=False)
if old.returncode!=0 or old.stdout.splitlines()!=["LoadState=not-found"]: raise SystemExit("new unit already exists or unit readback is ambiguous: rc=%s stdout=%r stderr=%r"%(old.returncode,old.stdout,old.stderr))
archive_bytes=sys.stdin.buffer.read()
if not archive_bytes: raise SystemExit("empty package archive")
STAGE.mkdir(mode=0o700); DIAG.mkdir(mode=0o700)
(STAGE/"release.tar.gz").write_bytes(archive_bytes)
candidate=STAGE/"candidate"; candidate.mkdir(mode=0o700)
seen=set()
with tarfile.open(fileobj=io.BytesIO(archive_bytes),mode="r:gz") as tar:
    members=tar.getmembers()
    if len(members)!=561: raise SystemExit("archive must contain 560 release files plus one hash manifest")
    metadata=tar.extractfile("META/deploy-manifest.json")
    if metadata is None: raise SystemExit("release hash manifest missing")
    manifest_bytes=metadata.read()
    if hashlib.sha256(manifest_bytes).hexdigest()!=CFG["archive_manifest_sha256"]: raise SystemExit("release hash manifest digest mismatch")
    manifest=json.loads(manifest_bytes)
    if manifest.get("schema")!="n01-deploy-release-manifest/1": raise SystemExit("release hash manifest schema mismatch")
    EXPECTED=manifest.get("files",{})
    if len(EXPECTED)!=560: raise SystemExit("hash manifest does not bind 560 files")
    for member in members:
        if member.name=="META/deploy-manifest.json": continue
        parts=pathlib.PurePosixPath(member.name).parts
        if not member.isfile() or len(parts)<2 or parts[0]!="package" or any(x in ("",".","..") for x in parts):
            raise SystemExit("unsafe archive member: "+repr(member.name))
        rel=pathlib.PurePosixPath(*parts[1:]).as_posix()
        if rel in seen or rel not in EXPECTED: raise SystemExit("duplicate/unexpected archive member: "+rel)
        seen.add(rel); target=candidate.joinpath(*pathlib.PurePosixPath(rel).parts); target.parent.mkdir(parents=True,exist_ok=True)
        source=tar.extractfile(member)
        if source is None: raise SystemExit("unreadable archive member: "+rel)
        with source,target.open("wb") as out: shutil.copyfileobj(source,out)
        if digest(target)!=EXPECTED[rel]: raise SystemExit("release SHA mismatch: "+rel)
if seen!=set(EXPECTED): raise SystemExit("archive file set incomplete")
id_path=candidate/"N01_FULL_EVALUATION_IDENTITY.json"; budget_path=candidate/"n01_full_evaluation_stage_budget.json"; reader_path=candidate/"static_plan_r2.json"
identity=json.loads(id_path.read_text(encoding="utf-8")); budget=json.loads(budget_path.read_text(encoding="utf-8")); reader=json.loads(reader_path.read_text(encoding="utf-8"))
if identity.get("evaluation_identity")!=CFG["identity"] or digest(id_path)!=CFG["identity_sha256"]: raise SystemExit("identity manifest/hash mismatch")
if budget.get("evaluation_identity")!=CFG["identity"] or budget.get("status")!="proposed" or digest(budget_path)!=CFG["budget_sha256"]: raise SystemExit("budget/hash mismatch")
if budget.get("approval_reference") is not None or budget.get("approved_by") is not None: raise SystemExit("approval fields must remain empty")
if reader.get("evaluation_identity")!=CFG["identity"] or digest(reader_path)!=CFG["reader_sha256"] or reader.get("plan_sha256")!=CFG["plan_sha256"]: raise SystemExit("reader/plan hash mismatch")
if identity.get("current_source_hashes")!=CFG["package_source_hashes"]: raise SystemExit("identity source map mismatch")
for rel,expected in identity["current_source_hashes"].items():
    path=(candidate/rel).resolve(strict=True)
    if candidate.resolve() not in path.parents or digest(path)!=expected: raise SystemExit("source hash mismatch: "+rel)
if len(identity.get("checkpoint_sha256",{}))!=6 or identity.get("scope",{}).get("scenario_count")!=350 or identity.get("scope",{}).get("episode_count")!=2800: raise SystemExit("identity scope/checkpoint binding mismatch")
if pathlib.Path(RUNTIME[0]).is_file() is False: raise SystemExit("frozen Python runtime not found")
env=os.environ.copy(); env.update({"CUDA_VISIBLE_DEVICES":"","OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1","PYTHONDONTWRITEBYTECODE":"1"})
def evaluator(mode,*extra):
    argv=RUNTIME+["-B",str(candidate/"n01_full_evaluator.py"),"--package-root",str(candidate),"--mode",mode]+list(extra)
    result=run(argv,env=env); (DIAG/(mode+".output.txt")).write_text(result.stdout,encoding="utf-8"); return result.stdout
prior=json.loads(evaluator("prior-cost-dry-run"))
if prior.get("evaluation_identity")!=CFG["identity"] or prior.get("budget_status")!="proposed" or prior.get("model_loaded") is not False: raise SystemExit("prior-cost dry-run state mismatch")
plan_path=DIAG/"canonical-plan.json"; evaluator("dry-run","--plan-output",str(plan_path)); plan=json.loads(plan_path.read_text(encoding="utf-8")); keys=plan.get("run_keys",[])
key_ids=[(x.get("condition"),x.get("parent_id"),x.get("split"),x.get("method"),x.get("seed")) for x in keys]
if plan.get("evaluation_identity")!=CFG["identity"] or plan.get("scenario_count")!=350 or plan.get("episode_count")!=2800 or len(keys)!=2800 or len(set(key_ids))!=2800 or plan.get("static_only") is not True: raise SystemExit("dry-run scope/key validation failed")
barrier=plan.get("checkpoint_barrier",{})
if barrier.get("passed") is not True or len(barrier.get("checkpoints",[]))!=6: raise SystemExit("six-checkpoint dry-run barrier failed")
claimed=plan.pop("plan_sha256",None); canonical=json.dumps(plan,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
if claimed!=hashlib.sha256(canonical).hexdigest(): raise SystemExit("canonical dry-run plan hash mismatch")
if claimed!=CFG["expected_expanded_dry_run_plan_sha256"]: raise SystemExit("expanded dry-run plan SHA mismatch")
plan["plan_sha256"]=claimed
if os.path.lexists(PKG): raise SystemExit("package destination appeared before atomic publish")
os.rename(candidate,PKG)
deploy_checks_passed=False
try:
    tmp_unit=UNIT_FILE.with_name(UNIT_FILE.name+".prepare")
    if os.path.lexists(tmp_unit): raise SystemExit("unit temp path exists")
    UNIT_FILE.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(PKG/"n01_full_evaluation.service",tmp_unit); os.chmod(tmp_unit,0o644); os.replace(tmp_unit,UNIT_FILE)
    run(SYSTEMCTL+["--user","daemon-reload"])
    props=["Type","ExecStart","ExecStopPost","CPUAffinity","MemoryMax","Restart","KillMode","RuntimeMaxUSec","TimeoutStopUSec","DropInPaths","LoadState","ActiveState","SubState","InvocationID"]
    show=run(SYSTEMCTL+["--user","show",UNIT,"--no-pager"]+sum((["-p",p] for p in props),[])); cat=run(SYSTEMCTL+["--user","cat",UNIT,"--no-pager"])
    (DIAG/"systemd-show.txt").write_text(show.stdout,encoding="utf-8"); (DIAG/"systemd-cat.txt").write_text(cat.stdout,encoding="utf-8")
    fields=dict(x.split("=",1) for x in show.stdout.splitlines() if "=" in x)
    required={"Type":"exec","CPUAffinity":"0","MemoryMax":"4294967296","Restart":"no","KillMode":"control-group","LoadState":"loaded","ActiveState":"inactive","SubState":"dead","InvocationID":""}
    if any(fields.get(k)!=v for k,v in required.items()) or fields.get("DropInPaths",""): raise SystemExit("installed unit readback mismatch")
    if CFG["identity"] not in cat.stdout or "/packages/"+CFG["identity"] not in cat.stdout: raise SystemExit("installed unit does not bind new package")
    if os.path.lexists(RUN): raise SystemExit("deploy-only run path unexpectedly exists")
    deploy_checks_passed=True
finally:
    if deploy_checks_passed: shutil.rmtree(STAGE,ignore_errors=True)
report={"status":"DEPLOY_ONLY_STATIC_ACCEPTANCE","evaluation_identity":CFG["identity"],"release_file_count":len(EXPECTED),"scenario_count":350,"checkpoint_count":6,"run_key_count":2800,"budget_status":"proposed","package_published":True,"unit_installed":True,"unit_started":False,"admission_called":False,"approval_or_token_created":False,"run_created":False}
(DIAG/"deployment_result.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":report["status"],"identity":CFG["identity"],"package":str(PKG),"unit":UNIT,"start_called":False,"admission_called":False,"run_created":False},sort_keys=True))
'''


def remote_config(bindings: dict, files: dict[str, str], manifest_sha256: str, expanded_plan_sha256: str, *, base: str = BASE,
                  runtime: list[str] | None = None, systemctl: list[str] | None = None,
                  unit_file: str | None = None) -> dict:
    return {
        "base": base,
        "package_name": IDENTITY,
        "stage_name": "." + IDENTITY + ".deploy-only.stage",
        "diagnostics_name": IDENTITY + "-deploy-only-20261012",
        "run_name": IDENTITY + "-once",
        "unit": UNIT,
        "unit_file": unit_file or "/home/user1/.config/systemd/user/" + UNIT,
        "identity": IDENTITY,
        "identity_sha256": bindings["identity_sha256"],
        "budget_sha256": bindings["stage_budget_sha256"],
        "reader_sha256": bindings["reader_sha256"],
        "plan_sha256": bindings["plan_sha256"],
        "expected_expanded_dry_run_plan_sha256": expanded_plan_sha256,
        "package_source_hashes": bindings["package_source_hashes"],
        "archive_manifest_sha256": manifest_sha256,
        "runtime": runtime or [RUNTIME],
        "systemctl": systemctl or ["/usr/bin/systemctl"],
    }


def render_remote(config: dict) -> str:
    encoded = json.dumps(config, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "CONFIG_JSON=" + repr(encoded) + "\n" + REMOTE_BODY


def local_substitute_check(archive_bytes: bytes, manifest_sha256: str, expanded_plan_sha256: str, expanded_plan_path: pathlib.Path, bindings: dict, files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="n01-deploy-only-") as tmp:
        root = pathlib.Path(tmp)
        base = root / "pilot"
        for name in ("packages", "diagnostics", "runs"):
            (base / name).mkdir(parents=True)
        unit_file = root / ".config/systemd/user" / UNIT
        unit_file.parent.mkdir(parents=True)
        systemctl_log = root / "systemctl.jsonl"
        evaluator_log = root / "evaluator.jsonl"
        fake_evaluator = f'''import hashlib,json,pathlib,sys,os
args=sys.argv[1:]; mode=args[args.index("--mode")+1]
if mode=="dry-run" and os.environ.get("N01_FAKE_FAIL_DRY_RUN"): print("dry-run failure stdout"); print("dry-run failure stderr",file=sys.stderr); raise SystemExit(7)
if not os.environ.get("N01_FAKE_NO_LOGS"):
 with open({str(evaluator_log)!r},"a",encoding="utf-8") as f: f.write(json.dumps({{"mode":mode,"args":args}})+"\\n")
if mode=="prior-cost-dry-run": print(json.dumps({{"evaluation_identity":{IDENTITY!r},"budget_status":"proposed","model_loaded":False}})); raise SystemExit(0)
if mode!="dry-run": raise SystemExit(91)
out=pathlib.Path(args[args.index("--plan-output")+1]); out.write_bytes(pathlib.Path(os.environ["N01_PLAN_FIXTURE"]).read_bytes())
'''
        fake_systemctl = f'''import json,pathlib,sys
a=sys.argv[1:]
if not __import__("os").environ.get("N01_FAKE_NO_LOGS"):
 with open({str(systemctl_log)!r},"a",encoding="utf-8") as f: f.write(json.dumps(a)+"\\n")
unit=pathlib.Path({str(unit_file)!r})
if a[:2]==["--user","show"]:
 if not unit.exists(): print("LoadState=not-found"); raise SystemExit(0)
 print("Type=exec\\nCPUAffinity=0\\nMemoryMax=4294967296\\nRestart=no\\nKillMode=control-group\\nRuntimeMaxUSec=1h 38min 20s\\nTimeoutStopUSec=40s\\nDropInPaths=\\nLoadState=loaded\\nActiveState=inactive\\nSubState=dead\\nInvocationID="); raise SystemExit(0)
if a[:2]==["--user","daemon-reload"]: raise SystemExit(0)
if a[:2]==["--user","cat"]: print(unit.read_text()); raise SystemExit(0)
raise SystemExit(92)
'''
        cfg = remote_config(bindings, files, manifest_sha256, expanded_plan_sha256, base=str(base), runtime=[sys.executable, "-c", fake_evaluator], systemctl=[sys.executable, "-c", fake_systemctl], unit_file=str(unit_file))
        code = render_remote(cfg)
        if "--user start" in code or "_guardian-token" in code or '"admit"' in code:
            raise AssertionError("deploy-only source contains a forbidden start/admit path")
        env = os.environ.copy(); env["N01_PLAN_FIXTURE"] = str(expanded_plan_path)
        result = subprocess.run([sys.executable, "-c", code], input=archive_bytes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, check=False)
        output = result.stdout.decode("utf-8", errors="replace")
        if result.returncode:
            raise RuntimeError(f"local remote-code substitute failed ({result.returncode}): {output[-3000:]}")
        calls = [json.loads(line) for line in systemctl_log.read_text(encoding="utf-8").splitlines()]
        eval_calls = [json.loads(line) for line in evaluator_log.read_text(encoding="utf-8").splitlines()]
        if any(len(call) > 1 and call[1] == "start" for call in calls) or [c["mode"] for c in eval_calls] != ["prior-cost-dry-run", "dry-run"]:
            raise AssertionError("substitute run invoked a forbidden systemd/evaluator mode")
        report_path = base / "diagnostics" / (IDENTITY + "-deploy-only-20261012") / "deployment_result.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["unit_started"] or report["admission_called"] or report["approval_or_token_created"] or report["run_created"]:
            raise AssertionError("deploy-only result contains forbidden actions")
        if not (base / "packages" / IDENTITY / "n01_full_evaluation.service").is_file() or (base / "runs" / (IDENTITY + "-once")).exists():
            raise AssertionError("publish/no-run substitute assertion failed")
        success_result = {"remote_substitute_exit": result.returncode, "systemctl_call_count": len(calls), "evaluator_modes": [c["mode"] for c in eval_calls], "package_published": True, "unit_started": False, "run_created": False}

    # A self-consistent but modified plan must fail the frozen expanded-plan pin.
    with tempfile.TemporaryDirectory(prefix="n01-deploy-only-mismatch-") as tmp:
        root = pathlib.Path(tmp)
        base = root / "pilot"
        for name in ("packages", "diagnostics", "runs"):
            (base / name).mkdir(parents=True)
        unit_file = root / ".config/systemd/user" / UNIT
        unit_file.parent.mkdir(parents=True)
        cfg = remote_config(bindings, files, manifest_sha256, expanded_plan_sha256, base=str(base), runtime=[sys.executable, "-c", fake_evaluator], systemctl=[sys.executable, "-c", fake_systemctl], unit_file=str(unit_file))
        cfg["expected_expanded_dry_run_plan_sha256"] = "0" * 64
        env = os.environ.copy(); env["N01_PLAN_FIXTURE"] = str(expanded_plan_path); env["N01_FAKE_NO_LOGS"] = "1"
        result = subprocess.run([sys.executable, "-c", render_remote(cfg)], input=archive_bytes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, check=False)
        diag = base / "diagnostics" / (IDENTITY + "-deploy-only-20261012")
        output = result.stdout.decode("utf-8", errors="replace")
        if result.returncode == 0 or "expanded dry-run plan SHA mismatch" not in output:
            raise AssertionError(f"self-consistent expanded-plan mismatch was not rejected (rc={result.returncode}): {output[-2500:]}")
        if not (base / "packages" / ("." + IDENTITY + ".deploy-only.stage")).is_dir() or not diag.is_dir() or (base / "packages" / IDENTITY).exists():
            raise AssertionError("expanded-plan mismatch did not retain stage/diagnostics before publish")
        mismatch_result = {"expanded_plan_mismatch_rejected": True, "mismatch_stage_retained": True, "mismatch_diagnostics_retained": True}

    # Run the same generated remote entry against fresh paths and force its actual
    # evaluator child to fail, so diagnostics are checked at the process boundary.
    with tempfile.TemporaryDirectory(prefix="n01-deploy-only-failure-") as tmp:
        root = pathlib.Path(tmp)
        base = root / "pilot"
        for name in ("packages", "diagnostics", "runs"):
            (base / name).mkdir(parents=True)
        unit_file = root / ".config/systemd/user" / UNIT
        unit_file.parent.mkdir(parents=True)
        failure_evaluator_log = root / "evaluator.jsonl"
        failure_systemctl_log = root / "systemctl.jsonl"
        failure_evaluator = fake_evaluator
        failure_systemctl = fake_systemctl
        cfg = remote_config(bindings, files, manifest_sha256, expanded_plan_sha256, base=str(base), runtime=[sys.executable, "-c", failure_evaluator], systemctl=[sys.executable, "-c", failure_systemctl], unit_file=str(unit_file))
        code = render_remote(cfg)
        env = os.environ.copy()
        env["N01_FAKE_FAIL_DRY_RUN"] = "1"
        env["N01_FAKE_NO_LOGS"] = "1"
        result = subprocess.run([sys.executable, "-c", code], input=archive_bytes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, check=False)
        diag = base / "diagnostics" / (IDENTITY + "-deploy-only-20261012")
        if not (diag / "child-002.json").is_file():
            output = result.stdout.decode("utf-8", errors="replace")
            raise RuntimeError(f"failure substitute did not reach child 2 (outer rc={result.returncode}): {output[-3000:]}; diagnostics={list(diag.glob('*')) if diag.exists() else 'missing'}")
        child_meta = json.loads((diag / "child-002.json").read_text(encoding="utf-8"))
        child_stdout = (diag / "child-002.stdout.txt").read_text(encoding="utf-8")
        child_stderr = (diag / "child-002.stderr.txt").read_text(encoding="utf-8")
        stage = base / "packages" / ("." + IDENTITY + ".deploy-only.stage")
        if result.returncode == 0 or child_meta["returncode"] != 7 or "dry-run failure stdout" not in child_stdout or "dry-run failure stderr" not in child_stderr:
            raise AssertionError("failure substitute did not preserve original evaluator rc/stdout/stderr")
        if not stage.is_dir() or not diag.is_dir() or (base / "packages" / IDENTITY).exists():
            raise AssertionError("failure substitute did not retain stage/diagnostics before publish")
        if (base / "runs" / (IDENTITY + "-once")).exists():
            raise AssertionError("failure substitute created a run")
        failure_result = {"remote_substitute_failure_exit": result.returncode, "failed_child_returncode": child_meta["returncode"], "failed_child_stdout_retained": True, "failed_child_stderr_retained": True, "stage_retained": True, "diagnostics_retained": True}
    return {**success_result, **mismatch_result, **failure_result}


def execute_once(args: argparse.Namespace, archive_bytes: bytes, bindings: dict, manifest_sha256: str, expanded_plan_sha256: str, files: dict[str, str]) -> int:
    if not (args.host and args.user and args.key):
        raise ValueError("--execute requires --host, --user, and --key")
    key = pathlib.Path(args.key).expanduser().resolve(strict=True)
    code = render_remote(remote_config(bindings, files, manifest_sha256, expanded_plan_sha256))
    command = [
        "ssh", "-i", str(key), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no", "-o", "ControlMaster=no",
        "-o", "ControlPath=none", "-o", "ProxyJump=none", "-o", "ProxyCommand=none",
        "-o", "ConnectionAttempts=1", f"{args.user}@{args.host}",
        "python3 -c " + shlex.quote(code),
    ]
    proc = subprocess.run(command, input=archive_bytes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    sys.stdout.buffer.write(proc.stdout)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Local preparation for the N01 deploy-only static acceptance session.")
    parser.add_argument("--execute", action="store_true", help="run one SSH session for deploy+static acceptance only")
    parser.add_argument("--host")
    parser.add_argument("--user")
    parser.add_argument("--key")
    args = parser.parse_args()
    bindings, files = validate_local_release()
    expanded_plan_path = PREP / "expanded_dry_run_plan.json"
    with tempfile.TemporaryDirectory(prefix="n01-expanded-plan-") as tmp:
        generated = pathlib.Path(tmp) / "canonical-plan.json"
        env = os.environ.copy()
        env.update({"CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        command = [sys.executable, "-B", str(RELEASE / "n01_full_evaluator.py"), "--package-root", str(RELEASE), "--mode", "dry-run", "--plan-output", str(generated)]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
        if result.returncode:
            raise RuntimeError(f"local frozen evaluator static dry-run failed (rc={result.returncode}): stdout={result.stdout[-2000:]} stderr={result.stderr[-2000:]}")
        expanded_plan_path.write_bytes(generated.read_bytes())
    expanded_plan = read_json(expanded_plan_path)
    expanded_claimed = expanded_plan.get("plan_sha256")
    expanded_payload = dict(expanded_plan); expanded_payload.pop("plan_sha256", None)
    if expanded_claimed != canonical_sha(expanded_payload):
        raise ValueError("local expanded dry-run plan canonical hash mismatch")
    if expanded_plan.get("evaluation_identity") != IDENTITY or expanded_plan.get("scenario_count") != 350 or expanded_plan.get("episode_count") != 2800 or len(expanded_plan.get("run_keys", [])) != 2800 or len(expanded_plan.get("checkpoint_barrier", {}).get("checkpoints", [])) != 6:
        raise ValueError("local expanded dry-run plan scope mismatch")
    archive_bytes, manifest_sha256 = make_archive(files)
    substitute = local_substitute_check(archive_bytes, manifest_sha256, expanded_claimed, expanded_plan_path, bindings, files)
    report = {
        "schema": "n01-deploy-only-preparation/1",
        "evaluation_identity": IDENTITY,
        "status": "LOCAL_PREPARATION_PASS",
        "frozen_identity_sha256": bindings["identity_sha256"],
        "frozen_budget_sha256": bindings["stage_budget_sha256"],
        "frozen_reader_sha256": bindings["reader_sha256"],
        "frozen_plan_sha256": bindings["plan_sha256"],
        "expanded_dry_run_plan_sha256": expanded_claimed,
        "expanded_dry_run_plan_file": expanded_plan_path.name,
        "expanded_dry_run_plan_bytes": expanded_plan_path.stat().st_size,
        "static_checkpoint_payloads_deserialized": 6,
        "release_file_count": len(files),
        "release_archive_sha256": sha(archive_bytes),
        "release_manifest_sha256": manifest_sha256,
        "release_archive_bytes": len(archive_bytes),
        "archive_member_count": len(files) + 1,
        "scope": {"scenarios": 350, "checkpoints": 6, "run_keys": 2800},
        "static_checkpoint_deserializations_expected": 6,
        "model_forward": False,
        "training": False,
        "admission": False,
        "formal_evaluation": False,
        "approval_or_token_creation": False,
        "systemctl_start": False,
        "ssh_performed": False,
        "substitute_run": substitute,
    }
    report_path = PREP / "PREPARATION_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if args.execute:
        return execute_once(args, archive_bytes, bindings, manifest_sha256, expanded_claimed, files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
