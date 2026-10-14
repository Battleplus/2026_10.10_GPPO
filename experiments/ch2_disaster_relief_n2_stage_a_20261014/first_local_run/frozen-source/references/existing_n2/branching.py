"""Synthetic-only, explicit state snapshots and bounded paired branch probes."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import defaultdict
from typing import Any

from baselines import choose_step_c1_actions
from relief_env import ReliefEnv
from n2_contracts import validate_public_view


SNAPSHOT_SCHEMA = "n2-engineering-relief-snapshot/1"
ENGINEERING_WINDOW_STARTS = (8, 16, 24, 32)
MAX_CONTINUATION_MINUTES = 30
CONTINUATION_RULE = "force-candidate-versus-same-window-NOOP-first-step; thereafter both branches choose_step_c1_actions(public_observation,candidates)+NOOP; stop after 30 elapsed minutes or true episode termination"
CONTINUATION_RULE_SHA256 = hashlib.sha256(CONTINUATION_RULE.encode("ascii")).hexdigest().upper()


def _implementation_identity() -> dict[str, str]:
    from pathlib import Path
    here = Path(__file__).resolve()
    civil_root = here.parents[1] / "civil"
    paths = {
        "branching.py": here,
        "relief_env.py": civil_root / "relief_env.py",
        "baselines.py": civil_root / "baselines.py",
        "scenario_schema.py": civil_root / "scenario_schema.py",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest().upper()
        for name, path in paths.items()
    }


def _implementation_sha256() -> str:
    encoded = json.dumps(_implementation_identity(), sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest().upper()


def _validate_c1_prefix(env: ReliefEnv) -> None:
    transitions = env.transitions
    if len(transitions) != int(env.time):
        raise ValueError("SNAPSHOT_PREFIX_LENGTH")
    replay = ReliefEnv(copy.deepcopy(env.scenario))
    replay.reset("C1")
    for expected_time, recorded in enumerate(transitions):
        observation = replay.public_observation()
        candidates = replay.candidates()
        selected = choose_step_c1_actions(observation, candidates)
        selected_ids = [item["id"] for item in selected]
        expected_ids = selected_ids + ["NOOP"] if selected_ids else ["NOOP"]
        recorded_ids = [item["id"] for item in recorded.get("selected_actions", [])] or ["NOOP"]
        if recorded.get("time") != expected_time or recorded_ids != (selected_ids or ["NOOP"]):
            raise ValueError("SNAPSHOT_C1_PREFIX_MISMATCH")
        _, _, terminated, truncated, _ = replay.step(expected_ids)
        if truncated or (terminated and expected_time + 1 < env.time):
            raise ValueError("SNAPSHOT_C1_PREFIX_TERMINATED_EARLY")
    if replay.__dict__ != env.__dict__:
        raise ValueError("SNAPSHOT_C1_PREFIX_STATE_MISMATCH")


def _encode(value: Any) -> Any:
    if isinstance(value, defaultdict):
        if value.default_factory not in (None, float):
            raise TypeError("SNAPSHOT_DEFAULT_FACTORY")
        return {"$n2_type": "defaultdict", "factory": "float" if value.default_factory is float else None,
                "items": [[_encode(key), _encode(item)] for key, item in value.items()]}
    if isinstance(value, dict):
        if all(isinstance(key, str) for key in value):
            return {key: _encode(item) for key, item in value.items()}
        items = [[_encode(key), _encode(item)] for key, item in value.items()]
        items.sort(key=lambda pair: json.dumps(pair[0], sort_keys=True, separators=(",", ":")))
        return {"$n2_type": "mapping", "items": items}
    if isinstance(value, tuple):
        return {"$n2_type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, set):
        items = [_encode(item) for item in value]
        items.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return {"$n2_type": "set", "items": items}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("SNAPSHOT_NONFINITE_NUMBER")
        return value
    raise TypeError(f"SNAPSHOT_UNSUPPORTED_TYPE:{type(value).__name__}")


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    marker = value.get("$n2_type")
    if marker == "tuple":
        return tuple(_decode(item) for item in value["items"])
    if marker == "set":
        return set(_decode(item) for item in value["items"])
    if marker == "mapping":
        return {_decode(key): _decode(item) for key, item in value["items"]}
    if marker == "defaultdict":
        factory = float if value["factory"] == "float" else None
        return defaultdict(factory, {_decode(key): _decode(item) for key, item in value["items"]})
    return {key: _decode(item) for key, item in value.items()}


def _canonical(value: Any) -> bytes:
    return json.dumps(_encode(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest().upper()


def capture_snapshot(
    env: ReliefEnv, *, parent_id: str = "engineering-parent", repeat: int = 0, window_id: str | None = None,
) -> str:
    """Return an integrity-bound JSON snapshot; never uses pickle or public fields as truth."""
    if not getattr(env, "_step_api_active", False):
        raise RuntimeError("SNAPSHOT_REQUIRES_ACTIVE_EPISODE")
    _validate_c1_prefix(env)
    state = copy.deepcopy(env.__dict__)
    observation = env.public_observation()
    candidates = env.candidates()
    public_binding = validate_public_view(observation, candidates)
    window_id = window_id or f"t{int(env.time)}"
    contract_context = {
        "parent_id": parent_id, "repeat": int(repeat), "window_id": window_id,
        "time": public_binding["time"], "public_prefix_sha256": public_binding["public_prefix_sha256"],
        "candidate_catalog_sha256": public_binding["candidate_catalog_sha256"],
    }
    candidate_ids = list(public_binding["candidate_ids"])
    scenario = copy.deepcopy(env.scenario)
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "implementation_sources": _implementation_identity(),
        "implementation_sha256": _implementation_sha256(),
        "continuation_rule": CONTINUATION_RULE,
        "continuation_rule_sha256": CONTINUATION_RULE_SHA256,
        "scenario_sha256": _digest(scenario),
        "event_tape_sha256": _digest(scenario.get("disturbances", [])),
        "time": int(env.time),
        "contract_context": contract_context,
        "public_observation_sha256": _digest(observation),
        "candidate_ids": candidate_ids,
        "state_sha256": _digest(state),
        "scenario": scenario,
        "state": _encode(state),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def restore_snapshot(snapshot_json: str) -> ReliefEnv:
    try:
        payload = json.loads(snapshot_json)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("SNAPSHOT_JSON_INVALID") from error
    if not isinstance(payload, dict) or payload.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("SNAPSHOT_SCHEMA")
    if (payload.get("implementation_sources") != _implementation_identity()
            or payload.get("implementation_sha256") != _implementation_sha256()):
        raise ValueError("SNAPSHOT_IMPLEMENTATION_IDENTITY")
    if (payload.get("continuation_rule") != CONTINUATION_RULE
            or payload.get("continuation_rule_sha256") != CONTINUATION_RULE_SHA256):
        raise ValueError("SNAPSHOT_CONTINUATION_IDENTITY")
    if _digest(payload.get("scenario")) != payload.get("scenario_sha256"):
        raise ValueError("SNAPSHOT_SCENARIO_DIGEST")
    if _digest(payload["scenario"].get("disturbances", [])) != payload.get("event_tape_sha256"):
        raise ValueError("SNAPSHOT_EVENT_TAPE_DIGEST")
    state = _decode(payload.get("state"))
    if not isinstance(state, dict) or _digest(state) != payload.get("state_sha256"):
        raise ValueError("SNAPSHOT_STATE_DIGEST")
    if int(state.get("time", -1)) != payload.get("time"):
        raise ValueError("SNAPSHOT_TIME_BINDING")
    env = ReliefEnv(payload["scenario"])
    env.__dict__.clear()
    env.__dict__.update(state)
    _validate_c1_prefix(env)
    observation = env.public_observation()
    candidates = env.candidates()
    contract_context = payload.get("contract_context")
    if not isinstance(contract_context, dict):
        raise ValueError("SNAPSHOT_CONTEXT_INVALID")
    public_binding = validate_public_view(observation, candidates, contract_context)
    if public_binding["public_prefix_sha256"] != contract_context.get("public_prefix_sha256"):
        raise ValueError("SNAPSHOT_PUBLIC_CONTRACT_MISMATCH")
    if public_binding["candidate_catalog_sha256"] != contract_context.get("candidate_catalog_sha256"):
        raise ValueError("SNAPSHOT_CATALOG_CONTRACT_MISMATCH")
    if _digest(observation) != payload.get("public_observation_sha256"):
        raise ValueError("SNAPSHOT_PUBLIC_DIGEST")
    if [candidate["id"] for candidate in env.candidates()] != payload.get("candidate_ids"):
        raise ValueError("SNAPSHOT_CANDIDATE_BINDING")
    return env


def public_record(env: ReliefEnv) -> dict[str, Any]:
    """Export public information only; private scenario/task IDs are not copied."""
    observation = env.public_observation()
    return {
        "schema": observation["schema"],
        "time": observation["time"],
        "public_observation": observation,
        "candidates": env.candidates(),
        "public_observation_sha256": _digest(observation),
    }


def _step_c1(env: ReliefEnv) -> tuple[dict, float, bool, bool, dict]:
    observation = env.public_observation()
    selected = choose_step_c1_actions(observation, env.candidates())
    action_ids = [item["id"] for item in selected] + ["NOOP"]
    return env.step(action_ids)


def _continue(env: ReliefEnv, stop_at: int) -> dict[str, Any]:
    rewards: list[float] = []
    terminated = bool(env._terminal)
    while not terminated and env.time < stop_at:
        _, reward, terminated, truncated, _ = _step_c1(env)
        if truncated:
            raise AssertionError("relief environment emitted unexpected truncation")
        rewards.append(float(reward))
    reached_limit = env.time >= stop_at and not terminated
    return {
        "end_time": int(env.time),
        "return": float(sum(rewards)),
        "step_rewards": rewards,
        "terminated": terminated,
        "right_censored": reached_limit,
        "terminal_reason": "episode_terminal" if terminated else ("30_minute_horizon" if reached_limit else None),
    }


def _task_outcome(env: ReliefEnv, task_id: str | None, end_time: int, terminated: bool) -> dict[str, Any]:
    if task_id is None or task_id not in env._public_tasks:
        return {"task_id": None, "on_time": None, "valid": False, "unknown_reason": "noop_or_not_public"}
    task = env._tasks[task_id]
    completed_at = task.get("completed_at")
    complete = bool(task.get("delivered")) if task["kind"] == "delivery" else task.get("report_received_at") is not None
    if complete and completed_at is not None and int(completed_at) <= end_time:
        on_time = bool(task.get("on_time"))
        return {"task_id": task_id, "on_time": on_time, "valid": True, "unknown_reason": None}
    deadline = int(task["deadline"])
    if terminated or deadline <= end_time:
        return {"task_id": task_id, "on_time": False, "valid": True, "unknown_reason": None}
    return {
        "task_id": task_id,
        "on_time": None,
        "valid": False,
        "unknown_reason": "deadline_after_observation_horizon",
    }


def _branch_task_labels(
    env: ReliefEnv,
    public_task_ids: tuple[str, ...],
    start_time: int,
    end_time: int,
    terminated: bool,
) -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    for task_id in public_task_ids:
        task = env._tasks[task_id]
        kind = task["kind"]
        completed_at = task.get("completed_at")
        report_at = task.get("report_received_at") if kind == "inspection" else None
        completed = completed_at is not None and int(completed_at) <= end_time
        reported = report_at is not None and int(report_at) <= end_time
        outcome_known = completed or terminated or int(task["deadline"]) <= end_time
        on_time = bool(completed and bool(task.get("on_time")))
        report_by_deadline = bool(
            reported and int(task["report_received_at"]) <= int(task["deadline"])
        )
        report_known = kind == "inspection" and (
            reported or terminated or int(task["deadline"]) <= end_time
        )
        service_unknown_reason = (
            "deadline_after_observation_horizon" if not outcome_known else None
        )
        report_unknown_reason = (
            "not_inspection" if kind != "inspection" else
            "deadline_after_observation_horizon" if not report_known else None
        )
        labels[task_id] = {
            "kind": kind,
            "binary": {
                "service_completed_by_horizon": bool(completed),
                "service_on_time": on_time,
                "deadline_missed": bool(outcome_known and not on_time),
                "report_received_by_deadline": report_by_deadline,
            },
            "binary_valid": {
                "service_completed_by_horizon": True,
                "service_on_time": bool(outcome_known),
                "deadline_missed": bool(outcome_known),
                "report_received_by_deadline": bool(report_known),
            },
            "continuous": {
                "completion_elapsed_fraction": (
                    (int(completed_at) - start_time) / MAX_CONTINUATION_MINUTES if completed else 0.0
                ),
                "report_delay_fraction": (
                    (int(report_at) - int(task["report_generated_at"])) / MAX_CONTINUATION_MINUTES
                    if reported and task.get("report_generated_at") is not None else 0.0
                ),
            },
            "continuous_valid": {
                "completion_elapsed_fraction": bool(completed),
                "report_delay_fraction": bool(reported and task.get("report_generated_at") is not None),
            },
            "right_censored": not bool(outcome_known),
            "censor_time": int(end_time) if not outcome_known else None,
            "censoring": {
                "service_outcome_reason": service_unknown_reason,
                "report_outcome_reason": report_unknown_reason,
                "completion_time_reason": None if completed else "not_completed_by_horizon",
                "report_delay_reason": None if reported and task.get("report_generated_at") is not None else report_unknown_reason,
            },
        }
    return labels


def _paired_target_labels(
    candidate_env: ReliefEnv,
    reference_env: ReliefEnv,
    public_task_ids: tuple[str, ...],
    target_task_id: str | None,
    start_time: int,
    end_time: int,
    terminated: bool,
    candidate_return: float,
    reference_return: float,
    candidate_events: list[dict[str, Any]],
    reference_events: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_tasks = _branch_task_labels(candidate_env, public_task_ids, start_time, end_time, terminated)
    reference_tasks = _branch_task_labels(reference_env, public_task_ids, start_time, end_time, terminated)
    return_delta = float(candidate_return - reference_return)
    def event_energy(events: list[dict[str, Any]]) -> float:
        return sum(
            float(event.get("energy", 0.0))
            for event in events
            if event.get("type") in {"move", "service"}
        )

    candidate_energy = event_energy(candidate_events)
    reference_energy = event_energy(reference_events)
    energy_delta = candidate_energy - reference_energy
    # This scalar audit label spans the scenario's complete task population,
    # including tasks revealed only after the snapshot. It never defines model axes.
    all_task_ids = tuple(sorted(candidate_env._tasks))
    candidate_all_tasks = _branch_task_labels(candidate_env, all_task_ids, start_time, end_time, terminated)
    reference_all_tasks = _branch_task_labels(reference_env, all_task_ids, start_time, end_time, terminated)
    external_ids = [task_id for task_id in all_task_ids if task_id != target_task_id]
    external_valid = all(
        candidate_all_tasks[task_id]["binary_valid"]["service_on_time"]
        and reference_all_tasks[task_id]["binary_valid"]["service_on_time"]
        for task_id in external_ids
    )
    external_delta = sum(
        int(candidate_all_tasks[task_id]["binary"]["service_on_time"])
        - int(reference_all_tasks[task_id]["binary"]["service_on_time"])
        for task_id in external_ids
    ) if external_valid else 0
    inspection_ids = [task_id for task_id in public_task_ids if candidate_tasks[task_id]["kind"] == "inspection"]
    report_valid = all(
        candidate_tasks[task_id]["binary_valid"]["report_received_by_deadline"]
        and reference_tasks[task_id]["binary_valid"]["report_received_by_deadline"]
        for task_id in inspection_ids
    )
    report_delta = sum(
        int(candidate_tasks[task_id]["binary"]["report_received_by_deadline"])
        - int(reference_tasks[task_id]["binary"]["report_received_by_deadline"])
        for task_id in inspection_ids
    ) if report_valid else 0
    binary_names = (
        "service_completed_by_horizon", "service_on_time", "deadline_missed", "report_received_by_deadline",
    )
    continuous_names = ("completion_elapsed_fraction", "report_delay_fraction")
    return {
        "global_binary_names": ["reward_improved", "energy_saved"],
        "global_binary": [float(return_delta > 0), float(energy_delta < 0)],
        "global_binary_valid": [True, True],
        "global_continuous_names": ["cumulative_reward_delta", "energy_use_delta", "other_task_on_time_count_delta", "inspection_report_count_delta"],
        "global_continuous": [return_delta, energy_delta, float(external_delta), float(report_delta)],
        "global_continuous_valid": [True, True, external_valid, report_valid],
        "public_task_ids": list(public_task_ids),
        "task_binary_names": list(binary_names),
        "task_binary": {task_id: [float(candidate_tasks[task_id]["binary"][name]) for name in binary_names]
                        for task_id in public_task_ids},
        "task_binary_valid": {task_id: [candidate_tasks[task_id]["binary_valid"][name] for name in binary_names]
                              for task_id in public_task_ids},
        "task_continuous_names": list(continuous_names),
        "task_continuous": {task_id: [candidate_tasks[task_id]["continuous"][name] for name in continuous_names]
                            for task_id in public_task_ids},
        "task_continuous_valid": {task_id: [candidate_tasks[task_id]["continuous_valid"][name] for name in continuous_names]
                                  for task_id in public_task_ids},
        "candidate_task_labels": candidate_tasks,
        "reference_task_labels": reference_tasks,
        "semantics": {
            "reward": "undiscounted civilian environment reward over the paired common horizon",
            "energy": "candidate minus reference sum of energy fields on raw move/service events",
            "other_tasks": "scenario-wide on-time outcomes excluding the candidate target task; scalar audit target only, with validity masked if any included task is unresolved in either branch",
            "inspection_report": "inspection reports received by their task deadline; unfinished reports are right-censored until deadline or episode terminal",
        },
        "externality_audit": {
            "task_count": len(all_task_ids),
            "excluded_target": target_task_id,
            "definition": "scenario-wide on-time service count delta excluding candidate target; invalid if any included task on-time outcome is right-censored in either branch",
            "valid": bool(external_valid),
            "censored_task_count": sum(
                not (candidate_all_tasks[task_id]["binary_valid"]["service_on_time"]
                     and reference_all_tasks[task_id]["binary_valid"]["service_on_time"])
                for task_id in external_ids
            ),
        },
    }


def run_synthetic_candidate_pair(snapshot_json: str, candidate_id: str, *, max_minutes: int = MAX_CONTINUATION_MINUTES) -> dict[str, Any]:
    """Run a local synthetic candidate/reference pair with a fixed public C1 continuation."""
    if max_minutes != MAX_CONTINUATION_MINUTES:
        raise ValueError("ENGINEERING_HORIZON_FIXED_AT_30_MINUTES")
    source = restore_snapshot(snapshot_json)
    if source.time not in ENGINEERING_WINDOW_STARTS:
        raise ValueError("ENGINEERING_WINDOW_START")
    catalog = source.candidates()
    candidate_by_id = {item["id"]: item for item in catalog}
    if candidate_id not in candidate_by_id:
        raise ValueError("CANDIDATE_ID_NOT_IN_SNAPSHOT")
    start = int(source.time)
    stop_at = start + MAX_CONTINUATION_MINUTES
    public_task_ids = tuple(task["id"] for task in source.public_observation().get("tasks", []))
    source_public_tasks = copy.deepcopy(source.public_observation().get("tasks", []))
    source_transition_count = len(source.transitions)
    source_event_count = len(source.events)
    target_task_id = candidate_by_id[candidate_id].get("task_id")

    candidate_env = restore_snapshot(snapshot_json)
    reference_env = restore_snapshot(snapshot_json)
    first_action = ["NOOP"] if candidate_id == "NOOP" else [candidate_id, "NOOP"]
    _, first_candidate_reward, cand_terminated, cand_truncated, _ = candidate_env.step(first_action)
    if cand_truncated:
        raise AssertionError("candidate branch unexpectedly truncated")
    _, first_reference_reward, ref_terminated, ref_truncated, _ = reference_env.step(["NOOP"])
    if ref_truncated:
        raise AssertionError("reference branch unexpectedly truncated")
    candidate_tail = _continue(candidate_env, stop_at) if not cand_terminated else {
        "end_time": int(candidate_env.time), "return": 0.0, "terminated": True,
        "right_censored": False, "terminal_reason": "episode_terminal",
    }
    reference_tail = _continue(reference_env, stop_at) if not ref_terminated else {
        "end_time": int(reference_env.time), "return": 0.0, "terminated": True,
        "right_censored": False, "terminal_reason": "episode_terminal",
    }
    if candidate_tail["end_time"] != reference_tail["end_time"]:
        raise AssertionError("paired branches diverged in observation horizon")
    end_time = int(candidate_tail["end_time"])
    terminal = bool(candidate_tail["terminated"])
    branch_return = float(first_candidate_reward) + float(candidate_tail["return"])
    reference_return = float(first_reference_reward) + float(reference_tail["return"])
    candidate_step_rewards = [float(first_candidate_reward), *candidate_tail.get("step_rewards", [])]
    reference_step_rewards = [float(first_reference_reward), *reference_tail.get("step_rewards", [])]
    candidate_events = copy.deepcopy(candidate_env.events[source_event_count:])
    reference_events = copy.deepcopy(reference_env.events[source_event_count:])
    target = _task_outcome(candidate_env, target_task_id, end_time, terminal)
    paired_targets = _paired_target_labels(
        candidate_env, reference_env, public_task_ids, target_task_id, start, end_time,
        terminal, branch_return, reference_return, candidate_events, reference_events,
    )
    return {
        "schema": "n2-synthetic-engineering-branch-label/2",
        "research_data": False,
        "source_state_sha256": json.loads(snapshot_json)["state_sha256"],
        "scenario_sha256": json.loads(snapshot_json)["scenario_sha256"],
        "implementation_sha256": _implementation_sha256(),
        "continuation_rule_sha256": CONTINUATION_RULE_SHA256,
        "source_prefix_sha256": _digest(source.transitions),
        "contract_context": copy.deepcopy(json.loads(snapshot_json)["contract_context"]),
        "window_start": start,
        "candidate_id": candidate_id,
        "reference_action_ids": ["NOOP"],
        "end_time": end_time,
        "horizon_minutes": end_time - start,
        "terminal": terminal,
        "right_censored": bool(candidate_tail["right_censored"]),
        "terminal_reason": candidate_tail["terminal_reason"],
        "target_task": target,
        "global_return_delta": branch_return - reference_return,
        "global_return_valid": True,
        "target_task_head_valid": target["valid"],
        "paired_targets": paired_targets,
        "source_public_tasks": source_public_tasks,
        "candidate_transitions": copy.deepcopy(candidate_env.transitions[source_transition_count:]),
        "reference_transitions": copy.deepcopy(reference_env.transitions[source_transition_count:]),
        "candidate_events": candidate_events,
        "reference_events": reference_events,
        "candidate_step_rewards": candidate_step_rewards,
        "reference_step_rewards": reference_step_rewards,
        "branch_evidence_scope": "raw synthetic replay evidence; event evidence is label-audit-only and never model input",
        "label_semantics": "synthetic simulator audit proxy; not a frozen research target",
    }
