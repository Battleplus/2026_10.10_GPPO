"""Copy only this project's public deliverables; preserve existing repo content."""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'github_archive' / 'experiments' / ROOT.name
INCLUDE = ['README.md', 'EXECUTION_STATUS.md', '.gitignore', '.gitattributes', '.aris', 'integration', 'relief_adapter', 'tests', 'vendor', 'upstream', 'upstream_r2', 'upstream_audit', 'upstream_smoke', 'reference', 'reports', 'protocols', 'linux_execution', 'linux_execution_r2']
OMIT_DIRS = {'.git', '__pycache__', '.pytest_cache'}
OMIT_FILES = {'graph_paper.txt'}
OMIT_SUFFIXES = {'.pyc', '.pyo', '.zip', '.pdf'}


def selected_files():
    files = []
    for name in INCLUDE:
        item = ROOT / name
        if not item.exists():
            continue
        for path in ([item] if item.is_file() else item.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in OMIT_DIRS for part in rel.parts) or path.name in OMIT_FILES or path.suffix.lower() in OMIT_SUFFIXES:
                continue
            if path.name == 'DELIVERY_HASHES.json':
                continue
            files.append(path)
    return sorted(files)


def main():
    files = selected_files()
    secret_pattern = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')
    matches = [p.relative_to(ROOT).as_posix() for p in files if p.suffix.lower() not in {'.pt', '.png', '.jpg', '.gif'} and secret_pattern.search(p.read_bytes())]
    if matches:
        raise RuntimeError('Potential credential-bearing files; archive aborted: ' + repr(matches))
    manifest = {'schema':'rlwm-delivery-hashes/1', 'scope':'engineering_artifacts_not_formal_results', 'files':{p.relative_to(ROOT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files}}
    manifest_path = ROOT / 'reports' / 'DELIVERY_HASHES.json'
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for source in files + [manifest_path]:
        target = DEST / source.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes() == source.read_bytes():
            continue
        shutil.copy2(source,target)
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            raise RuntimeError('Copy hash mismatch: ' + str(target))
    print(json.dumps({'copied_files':len(files)+1,'bytes':sum(p.stat().st_size for p in files)+manifest_path.stat().st_size,'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'destination':str(DEST)}))


if __name__ == '__main__':
    main()
