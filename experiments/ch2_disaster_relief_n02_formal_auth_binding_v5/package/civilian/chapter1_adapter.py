"""An explicit synthetic, public-only chapter handoff (initial state only).

In-progress cargo/mission snapshots require a future schema version; this module
does not pretend to accept arbitrary Chapter 1 execution states.
"""
from copy import deepcopy

try:
    from .scenario_schema import validate_scenario
    from .stable_identity import key_digest
except ImportError:
    from scenario_schema import validate_scenario
    from stable_identity import key_digest


def normalize_initial_assignment(scenario):
    validate_scenario(scenario)
    handoff = {
        'schema': 'relief-chapter-handoff/1',
        'source': scenario['chapter1_snapshot']['source'],
        'synthetic': True,
        'time': scenario['chapter1_snapshot']['time'],
        'units': deepcopy(scenario['units']),
        'map': deepcopy(scenario['map']),
        'platforms': deepcopy(scenario['platforms']),
        'depots': deepcopy(scenario['depots']),
        'known_tasks': [deepcopy(task) for task in scenario['tasks'] if task['known_initial']],
        'queues': deepcopy(scenario['chapter1_snapshot']['queues']),
    }
    # Do not bind the internal scenario ID, hidden task count, future event tape,
    # or hidden truth hash into the policy-facing handoff identity.
    handoff['public_sha256'] = key_digest(handoff)
    return handoff
