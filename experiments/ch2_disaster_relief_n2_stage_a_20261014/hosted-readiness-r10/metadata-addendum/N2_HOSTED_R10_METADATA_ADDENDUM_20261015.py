"""Verify the snapshot metadata-only delta; no controller execution."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path('E:/10.14')
OLD = '5215D07FA2A7AFF21AEDCDA088E014C0A4269EDFAB185FE344B332E5339DA07B'
NEW = 'B6D0AFEF6672868079B4008A43FF769FDDD0E610E797077760FCCB7BEF077C6C'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest().upper()


def main():
    snapshot_path = ROOT / 'n2-development/controller-password-r10-SNAPSHOT_SHA256.json'
    snapshot = json.loads(snapshot_path.read_text())
    assert sha(snapshot_path) == NEW
    before = copy.deepcopy(snapshot)
    added = before.pop('read_only_r10_preflight')
    reconstructed = (json.dumps(before, indent=2) + '\n').encode('utf-8')
    assert hashlib.sha256(reconstructed).hexdigest().upper() == OLD
    original_result_path = ROOT / 'n2-governance/reviews/N2_HOSTED_FINAL_INDEPENDENT_REVIEW_R10_20261015.json'
    original_result = json.loads(original_result_path.read_text())
    assert original_result['snapshot_record_sha256'] == OLD
    source_root = ROOT / 'n2-development/controller-password-r10'
    actual = {p.relative_to(source_root).as_posix(): sha(p) for p in source_root.rglob('*') if p.is_file()}
    assert actual == snapshot['file_sha256'] == original_result['source_sha256']
    assert len(actual) == 17
    assert canonical(actual) == snapshot['canonical_sha256_excluding_this_file'] == original_result['controller_snapshot_sha256']
    for key in ('controller_sha256', 'controller_bundle_sha256', 'standalone_source_sha256'):
        assert snapshot[key] == original_result[key]
    config = Path(snapshot['proposed_config']['path'])
    assert sha(config) == snapshot['proposed_config']['sha256'] == original_result['config_sha256']
    raw = json.loads(config.read_text())
    assert raw['budget']['status'] == 'NOT_APPROVED'
    assert sha(Path(snapshot['verification']['log_path'])) == snapshot['verification']['log_sha256']
    receipt_path = Path(added['path'])
    receipt = json.loads(receipt_path.read_text())
    assert sha(receipt_path) == added['sha256'] == original_result['exact_preflight_receipt_sha256']
    assert added['status'] == receipt['status'] == 'READ_ONLY_PREFLIGHT_MATCH'
    assert all(added[key] is False and receipt[key] is False for key in ('remote_upload', 'remote_training', 'authorization_consumed', 'credential_persisted'))
    assert receipt['parsed_cpu_admission']['sched_affinity'] == receipt['parsed_cpu_admission']['allowed_cpus'] == list(range(32))
    assert '/sys/fs/cgroup/user.slice' in receipt['commands'][0]['stdout']
    request_path = ROOT / 'n2-governance/ENGINEERING_AUTHORIZATION_REQUEST_R10_20261015.json'
    request = json.loads(request_path.read_text())
    assert request['source_snapshot_sha256'] == NEW
    assert request['proposed_config']['sha256'] == sha(config)
    assert request['readonly_preflight']['sha256'] == sha(receipt_path)
    assert request['budget'] == raw['budget']
    assert request['execution_authorized'] is False and request['requested_attempt_count'] == 1
    for key in ('run_identity', 'target_host', 'target_user', 'connect_host', 'remote_root', 'ssh_auth_mode', 'ssh_key_file'):
        assert request[key] == raw[key]
    package = Path(raw['package_root'])
    manifest = json.loads((package / 'manifest.json').read_text())
    package_hashes = {relative: sha(package / relative) for relative in manifest['files']}
    assert package_hashes == manifest['file_sha256']
    assert {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()} == set(manifest['files']) | {'manifest.json'}
    assert sha(package / 'manifest.json') == raw['package_sha256'] == request['package_manifest_sha256']
    archives = {}
    for name in ('n2-hosted-readiness-r10-20261015.zip', 'n2-hosted-readiness-r10-public-source-20261015.zip'):
        path = ROOT / 'archives' / name
        with zipfile.ZipFile(path) as stream:
            members = [member for member in stream.namelist() if member.endswith('controller-password-r10-SNAPSHOT_SHA256.json')]
            assert len(members) == 1
            archived_snapshot_hash = hashlib.sha256(stream.read(members[0])).hexdigest().upper()
            assert archived_snapshot_hash == NEW
            archive_original_result = [member for member in stream.namelist() if member.endswith('N2_HOSTED_FINAL_INDEPENDENT_REVIEW_R10_20261015.json')]
            assert len(archive_original_result) == 1
            assert hashlib.sha256(stream.read(archive_original_result[0])).hexdigest().upper() == sha(original_result_path)
        archives[name] = {'sha256': sha(path), 'snapshot_metadata_sha256': archived_snapshot_hash, 'original_review_result_preserved': True}
    result = {
        'schema': 'n2-independent-r10-metadata-addendum/1',
        'status': 'PASS_METADATA_ONLY_NO_APPROVAL_SCOPE_CHANGE',
        'previous_snapshot_metadata_sha256': OLD,
        'current_snapshot_metadata_sha256': NEW,
        'removing_exact_added_block_reproduces_previous_bytes_sha256': True,
        'only_metadata_delta': {'added_top_level_key': 'read_only_r10_preflight', 'value': added},
        'all_17_controller_file_hashes_unchanged': actual,
        'all_54_worker_package_file_hashes_match': package_hashes,
        'controller_canonical_source_sha256': canonical(actual),
        'proposed_config_sha256': sha(config),
        'actual_preflight_receipt_sha256': sha(receipt_path),
        'test_log_sha256': sha(Path(snapshot['verification']['log_path'])),
        'current_request_sha256': sha(request_path),
        'request_and_archives_bind_current_metadata': True,
        'archives': archives,
        'original_review_report_sha256': sha(original_result_path.with_suffix('.md')),
        'original_review_result_sha256': sha(original_result_path),
        'observed_file_mtime_utc': {'snapshot_unix_seconds': snapshot_path.stat().st_mtime, 'original_output_unix_seconds': original_result_path.stat().st_mtime},
        'approval_scope_changed': False,
        'execution_authorized': False,
        'reviewer_ssh_training_experiment_or_authorization_creation': False,
    }
    Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('all_17_controller_file_hashes_unchanged', 'all_54_worker_package_file_hashes_match')}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
