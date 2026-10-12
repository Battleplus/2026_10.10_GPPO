"""Independent event replay and accounting for the synthetic relief engine."""

from __future__ import annotations

import copy
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    from .stable_identity import bind_decision
    from .chapter1_adapter import normalize_initial_assignment
except ImportError:
    from stable_identity import bind_decision
    from chapter1_adapter import normalize_initial_assignment


_EPS = 1e-7
_TASK_REPORTS = {"inspection_result", "task_discovered", "task_failure"}
_RESOURCE_REPORTS = {"platform_failure", "energy_change", "stock_loss"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _num(value: Any, field: str) -> float:
    _require(type(value) in (int, float) and math.isfinite(float(value)), f"{field} must be finite numeric")
    return float(value)


def _close(left: Any, right: Any, *, tol: float = _EPS) -> bool:
    if left is None or right is None:
        return left is right
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(float(left), float(right), rel_tol=tol, abs_tol=tol)
    return left == right


def _distance(left: list[float], right: list[float]) -> float:
    return math.hypot(float(left[0]) - float(right[0]), float(left[1]) - float(right[1]))


def _position(value: Any, field: str) -> list[float]:
    _require(isinstance(value, list) and len(value) == 2, f"{field} must be a two-coordinate position")
    return [_num(value[0], field + "[0]"), _num(value[1], field + "[1]")]


def _event_task_id(event: dict, event_type: str) -> str | None:
    if event_type in {"report_generated", "report_received"}:
        if event.get("kind") not in _TASK_REPORTS:
            return None
        return event.get("task_id") or event.get("subject_id")
    if event_type in {
        "assignment", "move", "service", "arrival", "inspection_completed", "loaded",
        "delivery_confirmed", "cargo_lost", "task_failed", "task_expired", "dispatch_rejected",
    }:
        return event.get("task_id")
    return None


def _initial_owners(scenario: dict) -> tuple[dict[str, str], set[str]]:
    owners: dict[str, str] = {}
    task_ids = {task.get("id") for task in scenario.get("tasks", []) if isinstance(task, dict)}
    for platform_id, queue in scenario.get("chapter1_snapshot", {}).get("queues", {}).items():
        _require(isinstance(queue, list), f"snapshot queue {platform_id} must be a list")
        for task_id in queue:
            _require(task_id in task_ids, f"snapshot references unknown task {task_id}")
            _require(task_id not in owners, f"task {task_id} has multiple snapshot owners")
            owners[task_id] = platform_id
    return owners, set(owners)


def _validate_events(events: Any, horizon: int) -> list[dict]:
    _require(isinstance(events, list), "result events must be a list")
    previous_time = -1.0
    for index, event in enumerate(events):
        _require(isinstance(event, dict), f"events[{index}] must be an object")
        _require(event.get("seq") == index and type(event.get("seq")) is int, f"event seq must be contiguous at index {index}")
        time = _num(event.get("time"), f"events[{index}].time")
        _require(time.is_integer(), f"event time must be an integer at seq {index}")
        _require(previous_time <= time <= horizon, f"event time order/range invalid at seq {index}")
        previous_time = time
        _require(isinstance(event.get("type"), str) and event["type"], f"event {index} has no type")
    return events


def _task_rows(scenario: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    tasks = scenario.get("tasks")
    _require(isinstance(tasks, list), "scenario tasks must be a list")
    owners, _ = _initial_owners(scenario)
    rows: dict[str, dict] = {}
    specs: dict[str, dict] = {}
    for spec in tasks:
        _require(isinstance(spec, dict) and isinstance(spec.get("id"), str), "invalid scenario task")
        task_id = spec["id"]
        _require(task_id not in rows, f"duplicate scenario task {task_id}")
        kind = spec.get("kind")
        _require(kind in {"inspection", "delivery"}, f"unknown task kind for {task_id}")
        known = bool(spec.get("known_initial"))
        rows[task_id] = {
            "id": task_id,
            "kind": kind,
            "status": "pending" if known else "undiscovered",
            "phase": "pending" if known else "undiscovered",
            "assignee": owners.get(task_id),
            "original_assignee": owners.get(task_id),
            "known": known,
            "discovered": known,
            "discovery_time": 0 if known else None,
            "started_at": None,
            "completed_at": None,
            "deadline": spec["deadline"],
            "deadline_missed": False,
            "report_generated_at": None,
            "report_received_at": None,
            "failure_reason": None,
            "delivered": False,
            "on_time": None,
            "cargo_onboard": 0.0,
            "loaded": False,
            "delivered_at": None,
            "assignment_count": 0,
            "reassignment_count": 0,
            "new_assignment": False,
            "active_platform_id": None,
            "route": None,
            "arrived_at": None,
            "loading_service": 0.0,
            "unloading_service": 0.0,
            "inspection_service": 0.0,
        }
        specs[task_id] = spec
    return rows, specs


def _validate_transitions(scenario: dict, result: dict, rows: dict[str, dict], platforms: dict[str, dict], depots: dict[str, dict], stock: dict, horizon: int) -> None:
    transitions = result.get("transitions")
    if transitions is None:
        return
    _require(isinstance(transitions, list), "result transitions must be a list")
    _require(len(transitions) == horizon, f"transition count must equal horizon {horizon}")
    events = result["events"]
    event_index = 0
    public_energy = {item["id"]: float(item["energy_initial"]) for item in scenario.get("platforms", [])}
    public_failed = {platform_id: False for platform_id in public_energy}
    public_stock = {
        item["id"]: {commodity: float(quantity) for commodity, quantity in item.get("stock", {}).items()}
        for item in scenario.get("depots", [])
    }
    pending_energy_change = None
    scheduled_energy_changes: list[dict] = []
    known_tasks = {task_id for task_id, row in rows.items() if row["known"]}
    for time, transition in enumerate(transitions):
        _require(isinstance(transition, dict), f"transition {time} must be an object")
        _require(transition.get("time") == time, f"transition times must cover 0..H-1; expected {time}")
        observation = transition.get("public_observation")
        catalog = transition.get("candidates")
        _require(isinstance(observation, dict) and observation.get("time") == time, f"invalid public observation at {time}")
        _require(isinstance(catalog, list), f"candidate catalog missing at {time}")
        expected_identity = bind_decision(observation, catalog)
        identity = transition.get("identity")
        _require(identity == expected_identity, f"public identity mismatch at transition {time}")
        _require(transition.get("observation_sha256") == expected_identity["observation_sha256"], f"observation digest mismatch at {time}")
        _require(transition.get("candidate_catalog_sha256") == expected_identity["candidate_catalog_sha256"], f"candidate digest mismatch at {time}")

        while event_index < len(events) and events[event_index]["time"] <= time:
            event = events[event_index]
            event_index += 1
            event_type = event["type"]
            if event_type in {"move", "service"}:
                platform_id = event.get("platform_id")
                _require(platform_id in public_energy, f"resource event uses unknown platform {platform_id}")
                spent = _num(event.get("energy"), f"{event_type}.energy")
                public_energy[platform_id] = max(0.0, public_energy[platform_id] - spent)
            elif event_type == "energy_changed":
                platform_id = event.get("platform_id")
                _require(platform_id in public_energy, f"energy change uses unknown platform {platform_id}")
                pending_energy_change = {
                    "platform_id": platform_id,
                    "time": time,
                    "delta": _num(event.get("delta"), "energy_changed.delta"),
                    "old_energy": _num(event.get("old_energy"), "energy_changed.old_energy"),
                    "new_energy": _num(event.get("new_energy"), "energy_changed.new_energy"),
                }
            elif event_type == "report_generated" and event.get("kind") == "energy_change":
                _require(pending_energy_change is not None, f"energy report generated without external change at {time}")
                _require(pending_energy_change["platform_id"] == event.get("platform_id") and pending_energy_change["time"] == time, f"energy report does not match external change at {time}")
                scheduled_energy_changes.append({
                    **pending_energy_change,
                    "due": time + int(event.get("report_delay", 0)),
                    "received": False,
                })
                pending_energy_change = None
            elif event_type == "loaded":
                depot_id = event.get("depot_id")
                commodity = event.get("commodity")
                _require(depot_id in public_stock, f"load uses unknown depot {depot_id}")
                quantity = _num(event.get("quantity"), "loaded.quantity")
                public_stock[depot_id][commodity] = max(0.0, public_stock[depot_id].get(commodity, 0.0) - quantity)
            elif event_type == "report_received":
                kind = event.get("kind")
                if kind == "platform_failure":
                    platform_id = event.get("platform_id")
                    _require(platform_id in public_failed, f"failure report uses unknown platform {platform_id}")
                    public_failed[platform_id] = True
                elif kind == "energy_change":
                    platform_id = event.get("platform_id")
                    _require(platform_id in public_energy, f"energy report uses unknown platform {platform_id}")
                    report = next((item for item in scheduled_energy_changes if not item["received"] and item["due"] == time and item["platform_id"] == platform_id), None)
                    _require(report is not None, f"energy report received without matching external change at {time}")
                    report["received"] = True
                    public_energy[platform_id] += report["delta"]
                    reported_energy = event.get("new_energy")
                    if reported_energy is not None:
                        _require(_close(reported_energy, public_energy[platform_id]), f"energy report public value mismatch for {platform_id} at {time}")
                elif kind == "stock_loss":
                    depot_id = event.get("depot_id")
                    commodity = event.get("commodity")
                    _require(depot_id in public_stock, f"stock report uses unknown depot {depot_id}")
                    quantity = _num(event.get("quantity"), "stock report quantity")
                    public_stock[depot_id][commodity] = max(0.0, public_stock[depot_id].get(commodity, 0.0) - quantity)

        observation_platforms = observation.get("platforms")
        _require(isinstance(observation_platforms, list), f"observation platforms missing at {time}")
        platform_observation_by_id = {item.get("id"): item for item in observation_platforms if isinstance(item, dict)}
        _require(set(platform_observation_by_id) == set(public_energy), f"public platform set mismatch at transition {time}")
        for platform_id in public_energy:
            actual = platform_observation_by_id[platform_id]
            _require(_close(actual.get("energy"), public_energy[platform_id]), f"public energy mismatch for {platform_id} at transition {time}")
            _require(actual.get("failed") is public_failed[platform_id], f"public failure visibility mismatch for {platform_id} at transition {time}")

        observation_depots = observation.get("depots")
        _require(isinstance(observation_depots, list), f"observation depots missing at {time}")
        depot_observation_by_id = {item.get("id"): item for item in observation_depots if isinstance(item, dict)}
        _require(set(depot_observation_by_id) == set(public_stock), f"public depot set mismatch at transition {time}")
        for depot_id, expected_stock in public_stock.items():
            actual_stock = depot_observation_by_id[depot_id].get("stock")
            _require(isinstance(actual_stock, dict) and set(actual_stock) == set(expected_stock), f"public stock keys mismatch for {depot_id} at transition {time}")
            for commodity, quantity in expected_stock.items():
                _require(_close(actual_stock[commodity], quantity), f"public stock mismatch for {depot_id}/{commodity} at transition {time}")

        observation_tasks = observation.get("tasks")
        _require(isinstance(observation_tasks, list), f"observation tasks missing at {time}")
        visible_ids: set[str] = set()
        for task in observation_tasks:
            _require(isinstance(task, dict) and task.get("id") in rows, f"unknown public task at transition {time}")
            task_id = task["id"]
            row = rows[task_id]
            _require(task_id not in visible_ids, f"duplicate public task {task_id} at {time}")
            visible_ids.add(task_id)
            _require(task_id in known_tasks or (row["discovered"] and row["discovery_time"] <= time), f"hidden task leaked before report receipt: {task_id}")
            for private_field in ("known_initial", "discovered_by", "report_delay"):
                _require(private_field not in task, f"private task field {private_field} leaked at {time}")
        expected_visible = {
            task_id for task_id, row in rows.items()
            if row["known"] and (row["discovery_time"] is None or row["discovery_time"] <= time)
        }
        _require(visible_ids == expected_visible, f"public task set mismatch at transition {time}")
        _require("tasks" not in observation.get("map", {}), "invalid observation map")

        ids: set[str] = set()
        noops = 0
        for candidate in catalog:
            _require(isinstance(candidate, dict) and isinstance(candidate.get("id"), str), f"invalid candidate at {time}")
            _require(candidate["id"] not in ids, f"duplicate candidate id at {time}")
            ids.add(candidate["id"])
            if candidate.get("id") == "NOOP":
                noops += 1
                continue
            task_id = candidate.get("task_id")
            platform_id = candidate.get("platform_id")
            _require(task_id in visible_ids, f"candidate leaks hidden/unknown task {task_id} at {time}")
            _require(platform_id in platforms, f"candidate uses unknown platform {platform_id}")
            task = next(item for item in observation_tasks if item["id"] == task_id)
            platform = next(item for item in observation.get("platforms", []) if item.get("id") == platform_id)
            _require(not platform.get("busy") and not platform.get("failed"), f"candidate uses unavailable platform {platform_id}")
            _require(task.get("status") in {"pending", "assigned", "released"}, f"candidate uses non-actionable task {task_id}")
            needed = "inspect" if task.get("kind") == "inspection" else "deliver"
            _require(needed in platform.get("capabilities", []) and platform.get("local") == task.get("local"), f"candidate violates capability/locality for {task_id}")
            if task.get("kind") == "delivery":
                _require(float(task["quantity"]) <= float(platform["capacity_kg"]) + _EPS, f"candidate exceeds capacity for {task_id}")
                depot = next(item for item in observation.get("depots", []) if item.get("id") == task["depot_id"])
                _require(float(depot.get("stock", {}).get(task["commodity"], 0.0)) + _EPS >= float(task["quantity"]), f"candidate exceeds public stock for {task_id}")
        _require(noops == 1, f"candidate catalog must contain exactly one NOOP at {time}")
        selected = transition.get("selected_actions")
        _require(isinstance(selected, list), f"selected actions missing at {time}")
        selected_platforms: set[str] = set()
        selected_tasks: set[str] = set()
        for action in selected:
            _require(action in catalog and action.get("id") != "NOOP", f"selected action absent from candidates at {time}")
            _require(action["platform_id"] not in selected_platforms and action["task_id"] not in selected_tasks, f"duplicate selection at {time}")
            selected_platforms.add(action["platform_id"])
            selected_tasks.add(action["task_id"])


def _expected_external(scenario: dict) -> dict[str, dict]:
    disturbances = scenario.get("disturbances", [])
    _require(isinstance(disturbances, list), "disturbances must be a list")
    result = {}
    for disturbance in disturbances:
        _require(isinstance(disturbance, dict) and isinstance(disturbance.get("id"), str), "invalid disturbance")
        disturbance_id = disturbance["id"]
        _require(disturbance_id not in result, f"duplicate disturbance id {disturbance_id}")
        result[disturbance_id] = disturbance
    return result


def _check_final_state(final_state: Any, rows: dict[str, dict], energy: dict[str, float], energy_used_by_platform: dict[str, float], positions: dict[str, list[float]], failed_platforms: set[str], specs: dict[str, dict], depots: dict[str, dict], stock: dict[tuple[str, str], float], onboard: dict[tuple[str, str, str, str], float], horizon: int) -> None:
    if final_state is None:
        return
    _require(isinstance(final_state, dict), "final_state must be an object")
    _require(final_state.get("time") == horizon, "final_state time mismatch")
    final_tasks = final_state.get("tasks")
    _require(isinstance(final_tasks, list), "final_state.tasks missing")
    final_by_id = {item.get("id"): item for item in final_tasks if isinstance(item, dict)}
    _require(len(final_by_id) == len(final_tasks) and set(final_by_id) == set(rows), "final_state task set mismatch")
    for task_id, row in rows.items():
        actual = final_by_id[task_id]
        fields = ("kind", "status", "phase", "assignee", "original_assignee", "known", "discovered", "started_at", "completed_at", "deadline", "deadline_missed", "report_generated_at", "report_received_at", "failure_reason", "delivered", "on_time")
        _require((set(fields) | {"cargo_onboard"}) <= set(actual), f"final_state task fields missing for {task_id}")
        expected_values = dict(row, kind=row["kind"], known=row["known"], deadline=row["deadline"])
        for field in fields:
            _require(_close(actual[field], expected_values[field]), f"final_state mismatch for {task_id}.{field}: {actual[field]!r} != {expected_values[field]!r}")
        _require(_close(actual.get("cargo_onboard", 0.0), row["cargo_onboard"]), f"final cargo mismatch for {task_id}")

    final_platforms = final_state.get("platforms")
    _require(isinstance(final_platforms, list), "final_state.platforms missing")
    final_platform_by_id = {item.get("id"): item for item in final_platforms if isinstance(item, dict)}
    _require(len(final_platform_by_id) == len(final_platforms) and set(final_platform_by_id) == set(energy), "final_state platform set mismatch")
    active_by_platform = {row["active_platform_id"]: row["id"] for row in rows.values() if row["active_platform_id"] is not None}
    for platform_id, actual in final_platform_by_id.items():
        _require({"energy", "energy_used", "position", "failed", "active_task_id", "capacity_kg"} <= set(actual), f"final platform fields missing for {platform_id}")
        _require(_close(actual.get("energy"), energy[platform_id]), f"final energy mismatch for {platform_id}")
        _require(_close(actual.get("energy_used"), energy_used_by_platform[platform_id]), f"final energy_used mismatch for {platform_id}")
        _require(_position(actual.get("position"), f"final platform {platform_id}.position") == positions[platform_id], f"final position mismatch for {platform_id}")
        _require(actual.get("failed") is (platform_id in failed_platforms), f"final failure state mismatch for {platform_id}")
        _require(actual.get("active_task_id") == active_by_platform.get(platform_id), f"final active task mismatch for {platform_id}")
        _require(_close(actual.get("capacity_kg"), specs[platform_id]["capacity_kg"]), f"final capacity mismatch for {platform_id}")

    final_depots = final_state.get("depots")
    _require(isinstance(final_depots, list), "final_state.depots missing")
    final_depot_by_id = {item.get("id"): item for item in final_depots if isinstance(item, dict)}
    _require(len(final_depot_by_id) == len(final_depots) and set(final_depot_by_id) == set(depots), "final_state depot set mismatch")
    for depot_id, depot in final_depot_by_id.items():
        _require({"position", "stock"} <= set(depot), f"final depot fields missing for {depot_id}")
        _require(_position(depot.get("position"), f"final depot {depot_id}.position") == _position(depots[depot_id].get("position"), f"scenario depot {depot_id}.position"), f"final depot position mismatch for {depot_id}")
        _require(set(depot.get("stock", {})) == set(depots[depot_id].get("stock", {})) | {item for did, item in stock if did == depot_id}, f"final depot stock keys mismatch for {depot_id}")
        for commodity in set(depots[depot_id].get("stock", {})) | {item for did, item in stock if did == depot_id}:
            _require(_close(depot.get("stock", {}).get(commodity, 0.0), stock.get((depot_id, commodity), 0.0)), f"final stock mismatch for {depot_id}/{commodity}")
    final_onboard = final_state.get("onboard")
    _require(isinstance(final_onboard, list), "final_state.onboard missing")
    final_cargo = {}
    for item in final_onboard:
        key = (item.get("depot_id"), item.get("platform_id"), item.get("task_id"), item.get("commodity"))
        _require(key not in final_cargo, f"duplicate final onboard key {key}")
        final_cargo[key] = _num(item.get("quantity"), "final onboard quantity")
    replay_cargo = {key: quantity for key, quantity in onboard.items() if quantity > _EPS}
    _require(set(final_cargo) == set(replay_cargo), "final onboard cargo keys mismatch")
    for key, quantity in replay_cargo.items():
        _require(_close(final_cargo[key], quantity), f"final onboard quantity mismatch for {key}")


def audit_run(scenario: dict, result: dict, *, mode: str = "full", expected_policy: str | None = None) -> dict:
    """Rebuild task outcomes, energy, assignment, reports and inventory from events.

    Summary and final state are treated as evidence to compare against the
    independent replay; neither is used as an input to the calculated metrics.
    ``event_only`` is reserved for hand-authored event fixtures that do not
    include the engine's transition and final-state artifacts.
    """
    _require(isinstance(scenario, dict) and isinstance(result, dict), "scenario and result must be objects")
    _require(mode in {"full", "event_only"}, "audit mode must be 'full' or 'event_only'")
    _require(result.get("scenario_id") == scenario.get("scenario_id"), "scenario_id mismatch or missing")
    accepted_policies = {"C0", "C1", "L0", "L1", "LEARNED"}
    _require(result.get("policy") in accepted_policies, "invalid or missing result policy")
    if expected_policy is not None:
        _require(expected_policy in accepted_policies, "invalid expected_policy")
        _require(result["policy"] == expected_policy, "result policy does not match requested policy")
    _require(result.get("initial_handoff") == normalize_initial_assignment(scenario), "initial_handoff mismatch or missing")
    if mode == "full":
        _require("transitions" in result, "result transitions missing")
        _require("final_state" in result, "result final_state missing")
    horizon = int(_num(scenario.get("horizon"), "horizon"))
    events = _validate_events(result.get("events"), horizon)
    rows, task_specs = _task_rows(scenario)
    platforms = {platform["id"]: platform for platform in scenario.get("platforms", [])}
    _require(len(platforms) == len(scenario.get("platforms", [])), "duplicate/invalid platform ids")
    depots = {depot["id"]: depot for depot in scenario.get("depots", [])}
    owners, snapshot_tasks = _initial_owners(scenario)
    initial_assignment_seen: set[str] = set()

    energy = {platform_id: _num(spec.get("energy_initial"), "energy_initial") for platform_id, spec in platforms.items()}
    energy_used_by_platform = {platform_id: 0.0 for platform_id in platforms}
    positions = {platform_id: _position(spec.get("position"), f"platform {platform_id}.position") for platform_id, spec in platforms.items()}
    failed_platforms: set[str] = set()

    initial_stock: dict[tuple[str, str], float] = {}
    stock: dict[tuple[str, str], float] = {}
    for depot_id, spec in depots.items():
        for commodity, raw_amount in spec.get("stock", {}).items():
            amount = _num(raw_amount, "initial stock")
            _require(amount >= 0, "initial stock cannot be negative")
            initial_stock[(depot_id, commodity)] = amount
            stock[(depot_id, commodity)] = amount
    stock_loss: dict[tuple[str, str], float] = defaultdict(float)
    delivered: dict[tuple[str, str], float] = defaultdict(float)
    cargo_lost: dict[tuple[str, str], float] = defaultdict(float)
    onboard: dict[tuple[str, str, str, str], float] = defaultdict(float)

    assignment_owner = dict(owners)
    active_by_platform: dict[str, str] = {}
    generated_reports: list[dict] = []
    received_report_ids: set[int] = set()
    expected_external = _expected_external(scenario)
    external_seen: set[str] = set()
    external_reports_created: set[str] = set()
    external_report_index: dict[int, str] = {}
    external_energy_changes: dict[str, dict[str, float]] = {}
    external_stock_losses: dict[str, float] = {}
    expired_seen: set[str] = set()
    terminal_failed: set[str] = set()
    failure_attempts: dict[str, list[dict]] = defaultdict(list)
    confirmed: set[str] = set()
    energy_used = 0.0
    activity_tick: set[tuple[str, float]] = set()

    def ensure_task_known(task_id: str, event_type: str) -> dict:
        _require(task_id in rows, f"{event_type} references unknown task {task_id}")
        row = rows[task_id]
        _require(row["discovered"], f"hidden task {task_id} used before task_discovered report")
        return row

    def start_mission(task_id: str, platform_id: str, time: float) -> dict:
        row = ensure_task_known(task_id, "mission event")
        _require(platform_id in platforms, f"mission uses unknown platform {platform_id}")
        _require(platform_id not in failed_platforms, f"failed platform {platform_id} continues a mission")
        _require(row["status"] not in {"completed", "failed", "undiscovered"}, f"terminal task {task_id} continues")
        _require(assignment_owner.get(task_id) == platform_id, f"task {task_id} used by non-assignee {platform_id}")
        _require(row["active_platform_id"] in (None, platform_id), f"task {task_id} active on two platforms")
        other_task = active_by_platform.get(platform_id)
        _require(other_task in (None, task_id), f"platform {platform_id} handles concurrent tasks")
        if row["active_platform_id"] is None:
            row["active_platform_id"] = platform_id
            active_by_platform[platform_id] = task_id
            row["status"] = "active"
            if row["started_at"] is None:
                row["started_at"] = time
            if row["route"] is None:
                row["route"] = "inspection" if row["kind"] == "inspection" else "depot"
                row["phase"] = "to_inspection" if row["kind"] == "inspection" else "to_depot"
        return row

    def check_external(event: dict, kind: str) -> dict:
        disturbance_id = event.get("disturbance_id")
        _require(disturbance_id in expected_external, f"{kind} references unknown disturbance {disturbance_id}")
        _require(disturbance_id not in external_seen, f"duplicate disturbance event {disturbance_id}")
        disturbance = expected_external[disturbance_id]
        _require(disturbance.get("kind") == kind and disturbance.get("time") == event.get("time"), f"disturbance mismatch for {disturbance_id}")
        if kind in {"failure", "energy_change"}:
            _require(disturbance.get("platform_id") == event.get("platform_id"), f"disturbance platform mismatch for {disturbance_id}")
        else:
            _require(disturbance.get("depot_id") == event.get("depot_id") and disturbance.get("commodity") == event.get("commodity"), f"disturbance stock subject mismatch for {disturbance_id}")
            _require(_close(disturbance.get("quantity"), event.get("requested_quantity")), f"requested disturbance quantity mismatch for {disturbance_id}")
        if kind == "energy_change":
            _require(_close(disturbance.get("value"), event.get("new_energy")), f"energy disturbance value mismatch for {disturbance_id}")
        external_seen.add(disturbance_id)
        return disturbance

    for event in events:
        event_type = event["type"]
        time = _num(event["time"], "event time")
        task_id = _event_task_id(event, event_type)
        if task_id is not None:
            _require(task_id in rows, f"event {event_type} references unknown task {task_id}")

        if event_type == "assignment":
            _require(task_id is not None, "assignment requires task_id")
            row = rows[task_id]
            old, new = event.get("previous_assignee"), event.get("new_assignee")
            _require(new in platforms and (old is None or old in platforms), f"invalid assignment platform for {task_id}")
            if event.get("initial") is True:
                _require(time == 0 and task_id in snapshot_tasks and task_id not in initial_assignment_seen, f"invalid initial assignment marker for {task_id}")
                _require(old == owners[task_id] and new == owners[task_id], f"initial assignment mismatch for {task_id}")
                _require(event.get("reason") == "chapter1_snapshot", f"invalid initial assignment reason for {task_id}")
                initial_assignment_seen.add(task_id)
            else:
                _require(event.get("initial") is False, f"assignment initial flag missing for {task_id}")
                _require(row["discovered"], f"assignment before discovery for {task_id}")
                _require(row["status"] not in {"completed", "failed"}, f"terminal task reassigned: {task_id}")
                _require(assignment_owner.get(task_id) == old, f"assignment previous owner mismatch for {task_id}")
                _require(old != new, f"redundant non-initial assignment for {task_id}")
                _require(row["active_platform_id"] is None, f"active task reassigned without release: {task_id}")
                assignment_owner[task_id] = new
                row["assignee"] = new
                row["assignment_count"] += 1
                if row["original_assignee"] is None:
                    row["new_assignment"] = True
                elif new != row["original_assignee"]:
                    row["reassignment_count"] += 1
                row["phase"] = "assigned"
        elif event_type == "dispatch_rejected":
            _require(task_id is not None and event.get("platform_id") in platforms, "invalid dispatch_rejected event")
        elif event_type == "move":
            _require(task_id is not None, "move requires task_id")
            platform_id = event.get("platform_id")
            row = start_mission(task_id, platform_id, time)
            spec = task_specs[task_id]
            start = _position(event.get("from"), "move.from")
            end = _position(event.get("to"), "move.to")
            _require(all(_close(a, b) for a, b in zip(start, positions[platform_id])), f"move discontinuity for {platform_id}")
            distance = _distance(start, end)
            logged_distance = _num(event.get("distance"), "move.distance")
            duration = _num(event.get("duration"), "move.duration")
            spent = _num(event.get("energy"), "move.energy")
            rate = float(platforms[platform_id]["energy_per_km"])
            speed = float(platforms[platform_id]["speed_km_min"])
            _require(distance > _EPS and _close(distance, logged_distance), f"move geometry/distance mismatch for {platform_id}")
            _require(0 < duration <= 1 + _EPS and _close(distance, speed * duration), f"move speed/duration mismatch for {platform_id}")
            _require(_close(spent, distance * rate), f"move energy-rate mismatch for {platform_id}")
            tick = (platform_id, time)
            _require(tick not in activity_tick, f"platform {platform_id} has multiple service/move actions at {time}")
            activity_tick.add(tick)
            _require(energy[platform_id] + _EPS >= spent, f"negative energy after move on {platform_id}")
            energy[platform_id] -= spent
            energy_used_by_platform[platform_id] += spent
            energy_used += spent
            route_target = spec["position"] if row["kind"] == "inspection" or row["loaded"] else depots[spec["depot_id"]]["position"]
            remaining = _distance(start, route_target)
            _require(distance <= remaining + _EPS, f"move overshoots target for {task_id}")
            if distance + _EPS < remaining:
                expected = [start[i] + (route_target[i] - start[i]) * distance / remaining for i in range(2)]
                _require(all(_close(end[i], expected[i]) for i in range(2)), f"move path is not straight toward target for {task_id}")
            else:
                _require(all(_close(end[i], route_target[i]) for i in range(2)), f"move does not end at target for {task_id}")
            positions[platform_id] = end
        elif event_type == "arrival":
            _require(task_id is not None, "arrival requires task_id")
            platform_id = event.get("platform_id")
            row = start_mission(task_id, platform_id, time)
            spec = task_specs[task_id]
            stage = event.get("stage")
            position = _position(event.get("position"), "arrival.position")
            _require(all(_close(a, b) for a, b in zip(position, positions[platform_id])), f"arrival position discontinuity for {platform_id}")
            if row["kind"] == "inspection":
                _require(stage == "inspection_site" and row["route"] == "inspection", f"invalid inspection arrival stage for {task_id}")
                target = spec["position"]
                row["phase"] = "observe"
            elif stage == "depot":
                _require(not row["loaded"] and row["route"] == "depot", f"unexpected depot arrival for {task_id}")
                target = depots[spec["depot_id"]]["position"]
                row["phase"] = "loading"
            elif stage == "delivery_site":
                _require(row["loaded"] and row["route"] == "delivery_site", f"delivery arrival before load for {task_id}")
                target = spec["position"]
                row["phase"] = "unloading"
            else:
                raise ValueError(f"unknown arrival stage {stage!r}")
            _require(all(_close(a, b) for a, b in zip(position, target)), f"arrival away from stage target for {task_id}")
            _require(row["arrived_at"] is None or row["route"] == "delivery_site", f"duplicate arrival for {task_id}")
            row["arrived_at"] = time
            if row["route"] == "delivery_site":
                row["route"] = "unloading"
        elif event_type == "service":
            _require(task_id is not None, "service requires task_id")
            platform_id = event.get("platform_id")
            row = start_mission(task_id, platform_id, time)
            stage = event.get("stage")
            duration = _num(event.get("duration"), "service.duration")
            spent = _num(event.get("energy"), "service.energy")
            _require(_close(duration, 1.0), f"service duration must be one tick for {task_id}")
            _require((platform_id, time) not in activity_tick, f"platform {platform_id} has multiple service/move actions at {time}")
            activity_tick.add((platform_id, time))
            rate = float(platforms[platform_id]["service_energy_per_min"])
            _require(_close(spent, duration * rate), f"service energy-rate mismatch for {task_id}")
            _require(energy[platform_id] + _EPS >= spent, f"negative energy after service on {platform_id}")
            energy[platform_id] -= spent
            energy_used_by_platform[platform_id] += spent
            energy_used += spent
            spec = task_specs[task_id]
            if stage == "observe":
                _require(row["kind"] == "inspection" and row["phase"] == "observe", f"observation service before inspection arrival for {task_id}")
                row["inspection_service"] += duration
                _require(row["inspection_service"] <= float(spec["service_minutes"]) + _EPS, f"excess inspection service for {task_id}")
            elif stage == "loading":
                _require(row["kind"] == "delivery" and row["phase"] == "loading" and not row["loaded"], f"loading service out of order for {task_id}")
                row["loading_service"] += duration
                _require(row["loading_service"] <= float(spec["load_minutes"]) + _EPS, f"excess loading service for {task_id}")
            elif stage == "unloading":
                _require(row["kind"] == "delivery" and row["phase"] == "unloading" and row["loaded"], f"unloading service before delivery arrival for {task_id}")
                row["unloading_service"] += duration
                _require(row["unloading_service"] <= float(spec["unload_minutes"]) + _EPS, f"excess unloading service for {task_id}")
            else:
                raise ValueError(f"unknown service stage {stage!r}")
        elif event_type == "inspection_completed":
            _require(task_id is not None, "inspection_completed requires task_id")
            row = rows[task_id]
            spec = task_specs[task_id]
            _require(row["kind"] == "inspection" and row["phase"] == "observe", f"inspection completed before arrival for {task_id}")
            _require(row["inspection_service"] + _EPS >= float(spec["service_minutes"]), f"inspection completed before service duration for {task_id}")
            platform_id = event.get("platform_id")
            _require(row["active_platform_id"] == platform_id, f"inspection completion platform mismatch for {task_id}")
            row.update({"status": "completed", "phase": "inspection_completed", "completed_at": time, "on_time": time <= float(spec["deadline"]), "active_platform_id": None})
            active_by_platform.pop(platform_id, None)
        elif event_type == "loaded":
            _require(task_id is not None, "loaded requires task_id")
            row = rows[task_id]
            spec = task_specs[task_id]
            platform_id = event.get("platform_id")
            _require(row["kind"] == "delivery" and row["phase"] == "loading" and not row["loaded"], f"cargo loaded out of order for {task_id}")
            _require(row["active_platform_id"] == platform_id and row["loading_service"] + _EPS >= float(spec["load_minutes"]), f"insufficient loading service for {task_id}")
            quantity = _num(event.get("quantity"), "loaded.quantity")
            _require(event.get("commodity") == spec["commodity"] and event.get("depot_id") == spec["depot_id"], f"loaded commodity/depot mismatch for {task_id}")
            _require(_close(quantity, spec["quantity"]), f"partial or excess load for {task_id}")
            _require(quantity <= float(platforms[platform_id]["capacity_kg"]) + _EPS, f"load exceeds platform capacity for {task_id}")
            stock_key = (spec["depot_id"], spec["commodity"])
            _require(stock.get(stock_key, 0.0) + _EPS >= quantity, f"stock underflow loading {task_id}")
            stock[stock_key] -= quantity
            cargo_key = (spec["depot_id"], platform_id, task_id, spec["commodity"])
            _require(onboard[cargo_key] <= _EPS, f"duplicate cargo load for {task_id}")
            onboard[cargo_key] += quantity
            row["cargo_onboard"] = quantity
            row["loaded"] = True
            row["route"] = "delivery_site"
            row["phase"] = "to_delivery_site"
        elif event_type == "delivery_confirmed":
            _require(task_id is not None, "delivery_confirmed requires task_id")
            row = rows[task_id]
            spec = task_specs[task_id]
            platform_id = event.get("platform_id")
            _require(row["kind"] == "delivery" and task_id not in confirmed, f"duplicate or non-delivery confirmation for {task_id}")
            _require(row["phase"] == "unloading" and row["loaded"] and row["active_platform_id"] == platform_id, f"delivery confirmed before arrival/unload for {task_id}")
            _require(row["unloading_service"] + _EPS >= float(spec["unload_minutes"]), f"delivery confirmed before unload duration for {task_id}")
            quantity = _num(event.get("quantity"), "delivery_confirmed.quantity")
            _require(event.get("commodity") == spec["commodity"] and event.get("depot_id") == spec["depot_id"] and _close(quantity, spec["quantity"]), f"delivery details mismatch for {task_id}")
            cargo_key = (spec["depot_id"], platform_id, task_id, spec["commodity"])
            _require(_close(onboard.get(cargo_key, 0.0), quantity), f"delivery confirmation does not match onboard cargo for {task_id}")
            onboard[cargo_key] -= quantity
            delivered[(spec["depot_id"], spec["commodity"])] += quantity
            row.update({"cargo_onboard": 0.0, "status": "completed", "phase": "delivery_confirmed", "completed_at": time, "delivered_at": time, "delivered": True, "on_time": time <= float(spec["deadline"]), "active_platform_id": None})
            confirmed.add(task_id)
            active_by_platform.pop(platform_id, None)
        elif event_type == "cargo_lost":
            _require(task_id is not None, "cargo_lost requires task_id")
            row = rows[task_id]
            spec = task_specs[task_id]
            platform_id = event.get("platform_id")
            quantity = _num(event.get("quantity"), "cargo_lost.quantity")
            _require(row["loaded"] and event.get("depot_id") == spec.get("depot_id") and event.get("commodity") == spec.get("commodity"), f"cargo loss details mismatch for {task_id}")
            cargo_key = (spec["depot_id"], platform_id, task_id, spec["commodity"])
            _require(_close(onboard.get(cargo_key, 0.0), quantity) and quantity > 0, f"cargo loss does not match onboard cargo for {task_id}")
            onboard[cargo_key] -= quantity
            cargo_lost[(spec["depot_id"], spec["commodity"])] += quantity
            row["cargo_onboard"] = 0.0
        elif event_type == "task_failed":
            _require(task_id is not None, "task_failed requires task_id")
            row = rows[task_id]
            platform_id = event.get("platform_id")
            _require(platform_id in platforms and task_id not in terminal_failed and task_id not in confirmed, f"invalid/duplicate task failure for {task_id}")
            terminal = event.get("terminal")
            _require(type(terminal) is bool and event.get("released") is (not terminal), f"invalid failure disposition for {task_id}")
            _require(row["cargo_onboard"] <= _EPS, f"task failed while cargo remains onboard: {task_id}")
            _require(row["active_platform_id"] in (None, platform_id), f"failed task platform mismatch for {task_id}")
            attempt = len(failure_attempts[task_id]) + 1
            failure_attempts[task_id].append({"attempt": attempt, "time": time, "report_generated": False})
            row["failure_reason"] = event.get("reason")
            row["active_platform_id"] = None
            active_by_platform.pop(platform_id, None)
            if terminal:
                row["status"] = "failed"
                row["phase"] = "failed"
            else:
                _require(result.get("policy") in {"C1", "L0", "L1", "LEARNED"}, "only C1 and learned policies may release a failed task")
                row["status"] = "pending"
                row["phase"] = "released"
                row["assignee"] = None
                row["route"] = None
                row["arrived_at"] = None
                row["inspection_service"] = 0.0
                row["loading_service"] = 0.0
                row["unloading_service"] = 0.0
                assignment_owner[task_id] = None
            if terminal:
                terminal_failed.add(task_id)
        elif event_type == "task_expired":
            _require(task_id is not None, "task_expired requires task_id")
            row = rows[task_id]
            _require(task_id not in expired_seen and _close(event.get("deadline"), row["deadline"]), f"invalid/duplicate deadline event for {task_id}")
            _require(time == float(row["deadline"]), f"deadline event at wrong time for {task_id}")
            _require(row["status"] not in {"completed", "failed"}, f"terminal task emitted deadline event: {task_id}")
            expired_seen.add(task_id)
            row["deadline_missed"] = True
        elif event_type == "platform_failed":
            platform_id = event.get("platform_id")
            _require(platform_id in platforms and platform_id not in failed_platforms, "unknown or duplicate platform failure")
            disturbance = check_external(event, "failure")
            failed_platforms.add(platform_id)
            external_report_index[len(generated_reports)] = disturbance["id"]
        elif event_type == "energy_changed":
            platform_id = event.get("platform_id")
            _require(platform_id in platforms, f"energy change uses unknown platform {platform_id}")
            disturbance = check_external(event, "energy_change")
            old, new = _num(event.get("old_energy"), "old_energy"), _num(event.get("new_energy"), "new_energy")
            _require(_close(old, energy[platform_id]) and new >= 0 and _close(new - old, event.get("delta")), f"energy change ledger mismatch for {platform_id}")
            energy[platform_id] = new
            external_energy_changes[disturbance["id"]] = {"old_energy": old, "new_energy": new}
            external_report_index[len(generated_reports)] = disturbance["id"]
        elif event_type == "stock_lost":
            disturbance = check_external(event, "stock_loss")
            key = (event["depot_id"], event["commodity"])
            requested = _num(disturbance["quantity"], "requested stock loss")
            expected_actual = min(requested, stock.get(key, 0.0))
            quantity = _num(event.get("quantity"), "stock_loss.quantity")
            _require(_close(quantity, expected_actual), f"actual stock loss mismatch at {key}")
            if event.get("requested_quantity") is not None:
                _require(_close(event["requested_quantity"], requested), f"requested stock loss mismatch at {key}")
            stock[key] = max(0.0, stock.get(key, 0.0) - quantity)
            stock_loss[key] += quantity
            external_stock_losses[disturbance["id"]] = expected_actual
            external_report_index[len(generated_reports)] = disturbance["id"]
        elif event_type in {"report_generated", "report_received"}:
            kind = event.get("kind")
            _require(kind in _TASK_REPORTS | _RESOURCE_REPORTS, f"unknown report kind {kind!r}")
            if kind in _TASK_REPORTS:
                report_task_id = event.get("task_id") or event.get("subject_id")
                _require(report_task_id in rows and event.get("subject_id") == report_task_id and event.get("task_id") == report_task_id, f"invalid task report subject for {kind}")
                if kind == "inspection_result":
                    spec = task_specs[report_task_id]
                    _require(spec["kind"] == "inspection" and rows[report_task_id]["status"] == "completed", "inspection report before observation completion")
                    delay = int(spec.get("report_delay", 0))
                    if event_type == "report_generated":
                        _require(_close(time, rows[report_task_id]["completed_at"]), "inspection report generation time mismatch")
                        rows[report_task_id]["report_generated_at"] = time
                elif kind == "task_discovered":
                    spec = task_specs[report_task_id]
                    inspection_id = spec.get("discovered_by")
                    _require(spec["kind"] == "delivery" and inspection_id is not None and event.get("inspection_id") == inspection_id, f"invalid discovery source for {report_task_id}")
                    _require(rows[inspection_id]["completed_at"] is not None, f"discovery before inspection completion for {report_task_id}")
                    delay = int(spec.get("report_delay", 0))
                    if event_type == "report_generated":
                        _require(_close(time, rows[inspection_id]["completed_at"]), f"discovery report generation time mismatch for {report_task_id}")
                else:
                    if event_type == "report_generated":
                        failure_attempt = next((item for item in failure_attempts[report_task_id] if not item["report_generated"]), None)
                        _require(failure_attempt is not None and _close(failure_attempt["time"], time), f"failure report before task failure for {report_task_id}")
                    else:
                        failure_attempt = next((item for item in generated_reports if len(item["key"]) == 3 and item["key"][:2] == (kind, report_task_id) and not item["received"] and item["due"] == time), None)
                        _require(failure_attempt is not None, f"failure report received without matching failed attempt for {report_task_id}")
                    delay = 1
                if kind == "task_failure" and event_type == "report_generated":
                    report_key = (kind, report_task_id, failure_attempt["attempt"])
                elif kind == "task_failure":
                    report_key = failure_attempt["key"]
                else:
                    report_key = (kind, report_task_id)
                if event_type == "report_generated":
                    _require(not any(item["key"] == report_key for item in generated_reports), f"duplicate report generation {report_key}")
                    _require(event.get("report_delay") == delay, f"report delay mismatch for {report_key}")
                    generated_reports.append({"key": report_key, "time": time, "due": time + delay, "event": event, "received": False})
                    if kind == "task_failure":
                        failure_attempt["report_generated"] = True
                else:
                    match = next((item for item in generated_reports if item["key"][:2] == report_key[:2] and not item["received"]), None)
                    _require(match is not None, f"report received before generation for {report_key}")
                    _require(time == match["due"], f"report receipt delay mismatch for {report_key}")
                    match["received"] = True
                    received_report_ids.add(id(match))
                    row = rows[report_task_id]
                    row["report_received_at"] = time
                    if kind == "task_discovered":
                        _require(not row["discovered"], f"duplicate discovery report for {report_task_id}")
                        row["discovered"] = True
                        row["known"] = True
                        row["discovery_time"] = time
                        row["status"] = "pending"
                        row["phase"] = "report_received"
                    elif kind == "inspection_result":
                        row["phase"] = "report_received"
                    elif kind == "task_failure" and row["phase"] == "released":
                        row["phase"] = "released"
            else:
                _require(event.get("subject_id") is None and event.get("task_id") is None, f"resource report has task subject for {kind}")
                if kind == "platform_failure":
                    report_subject = (kind, event.get("platform_id"))
                    disturbance_kind = "failure"
                elif kind == "energy_change":
                    report_subject = (kind, event.get("platform_id"))
                    disturbance_kind = "energy_change"
                else:
                    report_subject = (kind, event.get("depot_id"), event.get("commodity"))
                    disturbance_kind = "stock_loss"
                resource_match = None
                if event_type == "report_generated":
                    expected_disturbances = [
                        item for item in expected_external.values()
                        if item.get("kind") == disturbance_kind and item.get("time") == time and item["id"] in external_seen
                        and ((disturbance_kind in {"failure", "energy_change"} and item.get("platform_id") == event.get("platform_id"))
                             or (disturbance_kind == "stock_loss" and item.get("depot_id") == event.get("depot_id") and item.get("commodity") == event.get("commodity")))
                    ]
                    candidate = next((item for item in expected_disturbances if item["id"] not in external_reports_created), None)
                else:
                    matching_reports = [
                        report for report in generated_reports
                        if report["key"][0] == "resource" and not report["received"] and report["due"] == time
                        and report["event"].get("kind") == kind
                        and report["event"].get("platform_id") == event.get("platform_id")
                        and report["event"].get("depot_id") == event.get("depot_id")
                        and report["event"].get("commodity") == event.get("commodity")
                    ]
                    resource_match = matching_reports[0] if matching_reports else None
                    candidate = expected_external.get(resource_match["key"][1]) if resource_match is not None else None
                _require(candidate is not None, f"resource report has no matching disturbance for {kind}")
                if event_type == "report_generated":
                    _require(event.get("report_delay") == int(candidate.get("report_delay", 0)), f"resource report delay mismatch for {candidate['id']}")
                if kind == "energy_change":
                    if event_type == "report_generated":
                        reported_value = event.get("new_energy", event.get("value"))
                        _require(_close(reported_value, candidate["value"]), "energy report value mismatch")
                        if event.get("value") is not None:
                            _require(_close(event["value"], candidate["value"]), "energy report value fields disagree")
                        change = external_energy_changes.get(candidate["id"])
                        _require(change is not None, f"energy report missing external-change ledger for {candidate['id']}")
                        if event.get("old_energy") is not None:
                            _require(_close(event["old_energy"], change["old_energy"]), "energy report old value mismatch")
                    else:
                        source = resource_match["event"]
                        _require(_close(event.get("value"), source.get("value", source.get("new_energy"))), "energy report target changed before receipt")
                        if source.get("old_energy") is not None:
                            _require(_close(event.get("old_energy"), source["old_energy"]), "energy report old value changed before receipt")
                        _require(event.get("new_energy") is not None, "energy report receipt missing public energy value")
                if kind == "stock_loss":
                    if event_type == "report_generated":
                        actual_quantity = external_stock_losses.get(candidate["id"])
                        _require(actual_quantity is not None and _close(event.get("quantity"), actual_quantity), "stock report actual quantity mismatch")
                        if event.get("requested_quantity") is not None:
                            _require(_close(event["requested_quantity"], candidate["quantity"]), "stock report requested quantity mismatch")
                    else:
                        source = resource_match["event"]
                        _require(_close(event.get("quantity"), source.get("quantity")), "stock report quantity changed before receipt")
                        if source.get("requested_quantity") is not None:
                            _require(_close(event.get("requested_quantity"), source["requested_quantity"]), "stock report requested quantity changed before receipt")
                if event_type == "report_generated":
                    key = ("resource", candidate["id"])
                    _require(not any(item["key"] == key for item in generated_reports), f"duplicate resource report generation {candidate['id']}")
                    external_reports_created.add(candidate["id"])
                    generated_reports.append({"key": key, "time": time, "due": time + int(candidate.get("report_delay", 0)), "event": event, "received": False})
                else:
                    key = ("resource", candidate["id"])
                    match = next((item for item in generated_reports if item["key"] == key and not item["received"]), None)
                    _require(match is not None, f"resource report received before generation for {candidate['id']}")
                    _require(time == match["due"], f"resource report receipt delay mismatch for {candidate['id']}")
                    match["received"] = True
        else:
            raise ValueError(f"unknown event type {event_type!r}")

    _require(initial_assignment_seen == snapshot_tasks, f"initial assignment events mismatch snapshot: missing {sorted(snapshot_tasks - initial_assignment_seen)}")
    _require(external_seen == set(expected_external), f"external disturbance events missing: {sorted(set(expected_external) - external_seen)}")
    _require(all(item["received"] or item["due"] > horizon for item in generated_reports), "a due report was not received by horizon")

    for task_id, row in rows.items():
        spec = task_specs[task_id]
        if row["kind"] == "delivery" and not row["discovered"]:
            row["status"] = "undiscovered"
        elif row["status"] not in {"completed", "failed"}:
            row["status"] = "expired"
        if row["kind"] == "inspection" and row["completed_at"] is not None:
            row["on_time"] = row["completed_at"] <= float(spec["deadline"])
        if row["kind"] == "delivery" and row["delivered_at"] is not None:
            row["on_time"] = row["delivered_at"] <= float(spec["deadline"])

    conservation = []
    ledger_keys = set(initial_stock) | set(stock) | set(stock_loss) | set(delivered) | set(cargo_lost)
    for depot_id, commodity in sorted(ledger_keys):
        remaining = stock.get((depot_id, commodity), 0.0)
        cargo = sum(quantity for (cargo_depot, _, _, item), quantity in onboard.items() if cargo_depot == depot_id and item == commodity)
        lost_amount = cargo_lost.get((depot_id, commodity), 0.0)
        initial = initial_stock.get((depot_id, commodity), 0.0)
        equation = remaining + cargo + delivered.get((depot_id, commodity), 0.0) + lost_amount + stock_loss.get((depot_id, commodity), 0.0)
        _require(math.isclose(initial, equation, rel_tol=1e-7, abs_tol=1e-7), f"inventory conservation failed for {depot_id}/{commodity}: {initial} != {equation}")
        conservation.append({
            "depot_id": depot_id, "commodity": commodity, "initial_stock": initial,
            "remaining_stock": remaining, "onboard": cargo,
            "delivered": delivered.get((depot_id, commodity), 0.0),
            "lost": lost_amount, "stock_loss": stock_loss.get((depot_id, commodity), 0.0), "conserved": True,
        })

    inspections = [row for row in rows.values() if row["kind"] == "inspection"]
    orders = [row for row in rows.values() if row["kind"] == "delivery"]
    total_weight = sum(float(task_specs[row["id"]]["priority"]) for row in orders)
    on_time_weight = sum(float(task_specs[row["id"]]["priority"]) for row in orders if row["delivered"] and row["on_time"])
    metrics = {
        "weighted_on_time_delivery_rate": None if not orders else on_time_weight / total_weight,
        "inspection_completion_rate": None if not inspections else sum(row["status"] == "completed" for row in inspections) / len(inspections),
        "inspection_on_time_rate": None if not inspections else sum(row["status"] == "completed" and row["on_time"] for row in inspections) / len(inspections),
        "delivered_orders": sum(bool(row["delivered"]) for row in orders),
        "late_orders": sum(bool(row["delivered"] and not row["on_time"]) for row in orders),
        "unmet_orders": sum(not row["delivered"] for row in orders),
        "undiscovered_orders": sum(not row["discovered"] for row in orders),
        "energy_used": energy_used,
        "reassignments": sum(row["reassignment_count"] > 0 for row in rows.values()),
        "new_assignments": sum(bool(row["new_assignment"]) for row in rows.values()),
    }

    _validate_transitions(scenario, result, rows, platforms, depots, stock, horizon)
    _check_final_state(result.get("final_state"), rows, energy, energy_used_by_platform, positions, failed_platforms, platforms, depots, stock, onboard, horizon)

    summary = result.get("summary")
    _require(isinstance(summary, dict), "result summary must be an object")
    for field, expected in metrics.items():
        _require(field in summary and _close(summary[field], expected), f"summary mismatch for {field}: expected {expected!r}, got {summary.get(field)!r}")

    task_rows = []
    for task_id in sorted(rows):
        exported = copy.deepcopy(rows[task_id])
        exported["assignment_count"] = int(exported["assignment_count"])
        exported["reassignment_count"] = int(exported["reassignment_count"])
        exported["reassigned"] = exported["reassignment_count"] > 0
        task_rows.append(exported)
    return {
        "validation_level": "full_artifact" if mode == "full" else "event_replay_only",
        "metrics": metrics,
        "task_rows": task_rows,
        "conservation": conservation,
    }


__all__ = ["audit_run"]
