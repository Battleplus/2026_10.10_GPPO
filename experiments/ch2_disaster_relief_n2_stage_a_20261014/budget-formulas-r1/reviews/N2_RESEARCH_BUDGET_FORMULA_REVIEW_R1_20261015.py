"""Bounded independent pure-formula probes; never imports Torch or training."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path('E:/10.14')
BUDGET = ROOT / 'n2-governance/research-budget-r1'
EXPECTED = {
    'operation_budget_r1.json': '946C7DA3BD8E5FDB3A4468C5A4FA0BFA848AC606FD9AC52FB00FCC7F0480B844',
    'calculate_operation_budget.py': '05927FDB851DAB8B120B53837926C69B10273C4B891B8024E020898F26F44533',
    'REPORT.md': '6D5E99815B15F5234700B1D25C8AD21B2DFE209E6D7B34A2EEFC91541457EA15',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    hashes = {name: sha(BUDGET / name) for name in EXPECTED}
    assert hashes == EXPECTED
    record = json.loads((BUDGET / 'operation_budget_r1.json').read_text(encoding='utf-8'))
    source_checks = {relative: sha(ROOT / relative) == expected for relative, expected in record['source_hashes'].items()}
    assert all(source_checks.values())
    spec = importlib.util.spec_from_file_location('pure_operation_budget', BUDGET / 'calculate_operation_budget.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calculate = module.calculate
    default = calculate()
    assert default['status'] == 'UNFROZEN' and default['authorization_created'] is False
    assert default['stage_b']['nominal_window_slots_by_split'] == {'train': 224, 'development': 56, 'confirmation': 96}
    assert default['stage_b']['context_scan_count_if_one_per_parent'] == 94
    assert default['world_model']['updates_all_three_seeds'] is None
    assert default['world_model']['candidate_sample_visits_all_three_seeds'] is None
    assert default['world_model']['formal_candidate_model_evaluations'] is None
    assert default['world_model']['formal_forward_call_count'] is None
    assert all(value is None for value in default['empirical_costs'].values())
    assert default['stage_b']['formal_horizon_minutes'] is None
    assert default['stage_b']['branch_count_by_split'] is None
    assert default['stage_b']['candidate_continuation_step_upper_bound_by_split'] is None
    assert default['stage_b']['complete_b_ledger_environment_steps'] is None
    assert default['stage_b']['noop_reference_and_restore_prefix_steps'] is None
    assert default['combination']['formal_smoke_environment_steps'] is None
    assert default['combination']['formal_total_environment_steps'] is None
    assert default['confirmation']['formal_minute_step_upper_bound'] is None
    c = default['combination']
    assert [c[key] for key in ['smoke_updates', 'total_updates_including_smoke', 'post_smoke_updates', 'smoke_episodes', 'total_episodes']] == [768, 3072, 2304, 192, 768]
    assert default['confirmation']['trajectories'] == 168
    assert default['confirmation']['logical_parent_draws'] == 240000
    assert default['confirmation']['trajectory_slots_across_resamples'] == 1680000
    probes = {}
    for windows in (0, 1, 8, 9, 224):
        actual = calculate(windows)['world_model']
        expected_per_seed = 40 * ((windows + 7) // 8)
        assert actual['updates_per_seed'] == expected_per_seed
        assert actual['updates_all_three_seeds'] == 3 * expected_per_seed
        probes[str(windows)] = {'updates_per_seed': actual['updates_per_seed'], 'updates_all_three_seeds': actual['updates_all_three_seeds']}
    counts = calculate(3, [1, 2, 7], [1, 3])
    assert counts['world_model']['candidate_sample_visits_all_three_seeds'] == 1200
    assert counts['world_model']['development_candidate_prediction_rows'] == 12
    assert counts['world_model']['formal_candidate_model_evaluations'] is None
    assert counts['world_model']['formal_forward_call_count'] is None
    rejected = {}
    for name, kwargs in {'zero_noop_catalog': {'usable_training_windows': 1, 'training_candidate_counts': [0]}, 'window_count_mismatch': {'usable_training_windows': 2, 'training_candidate_counts': [1]}, 'boolean_window_count': {'usable_training_windows': True}, 'zero_horizon': {'horizon_minutes': 0}}.items():
        try:
            calculate(**kwargs)
        except ValueError:
            rejected[name] = True
        else:
            raise AssertionError(name)
    branches = {'train': [{'minute': 8, 'candidate_count': 2}, {'minute': 32, 'candidate_count': 1}], 'development': [{'minute': 16, 'candidate_count': 1}], 'confirmation': [{'minute': 24, 'candidate_count': 3}]}
    branch_unknown_horizon = calculate(branch_windows_by_split=branches)
    assert branch_unknown_horizon['stage_b']['branch_count_by_split'] == {'train': 3, 'development': 1, 'confirmation': 3}
    assert branch_unknown_horizon['stage_b']['candidate_continuation_step_upper_bound_by_split'] is None
    explicit_horizon = calculate(branch_windows_by_split=branches, horizon_minutes=60)
    assert explicit_horizon['stage_b']['candidate_continuation_step_upper_bound_by_split'] == {'train': 88, 'development': 30, 'confirmation': 90}
    assert explicit_horizon['stage_b']['complete_b_ledger_environment_steps'] is None
    assert explicit_horizon['stage_b']['noop_reference_and_restore_prefix_steps'] is None
    assert explicit_horizon['combination']['formal_total_environment_steps'] == 46080
    assert explicit_horizon['confirmation']['formal_minute_step_upper_bound'] == 10080
    manifest = json.loads((ROOT / 'n2-development/hosted-engineering-package-r1-20261014/manifest.json').read_text(encoding='utf-8'))
    assert 'references/world_model/consequence_training.py' not in manifest['files']
    result = {
        'schema': 'n2-independent-research-budget-formula-review/1',
        'status': 'PASS_BOUNDED_FORMULA_REVIEW_NOT_RESOURCE_APPROVAL',
        'artifact_sha256': hashes,
        'source_hash_matches': source_checks,
        'protocol_parent_counts': {key: record['protocol']['parent_counts'][key] for key in ['train', 'development', 'confirmation']},
        'wm_window_count_probes': probes,
        'candidate_sample_visits_probe': 1200,
        'development_prediction_rows_probe': 12,
        'input_rejections': rejected,
        'default_counts_and_costs_unresolved': True,
        'explicit_horizon_probe_is_conditional_not_frozen': True,
        'formal_trainer_absent_from_hosted_manifest': True,
        'b_candidate_continuation_only_complete_ledger_unknown': True,
        'coordinator_mechanical_correction_disclosed': True,
        'no_torch_training_remote_or_authorization': True,
        'default_calculator_output': default,
    }
    path = Path(__file__).with_suffix('.json')
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'default_calculator_output'}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
