from __future__ import annotations

import copy
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from independent_audit import audit_run
from chapter1_adapter import normalize_initial_assignment
from stable_identity import bind_decision


def _scenario() -> dict:
    return {
        "schema_version": "relief-engineering/1",
        "scenario_id": "audit-hand",
        "synthetic": True,
        "units": {"distance": "km", "time": "min", "quantity": "kg", "energy": "synthetic_unit"},
        "map": {"rows": 4, "cols": 4, "cell_km": 1.0, "local_block": [0, 0, 2, 2]},
        "horizon": 15,
        "dt": 1,
        "platforms": [
            {
                "id": "p1",
                "type": "uav",
                "position": [0, 0],
                "local": True,
                "capabilities": ["inspect", "deliver"],
                "capacity_kg": 8,
                "speed_km_min": 1,
                "energy_initial": 20,
                "energy_per_km": 1,
                "service_energy_per_min": 0.1,
            }
        ],
        "depots": [{"id": "d1", "position": [0, 0], "stock": {"water": 10}}],
        "tasks": [
            {
                "id": "inspect-1",
                "kind": "inspection",
                "position": [1, 0],
                "local": True,
                "known_initial": True,
                "deadline": 10,
                "priority": 1,
                "discovered_by": None,
                "report_delay": 0,
                "service_minutes": 1,
            },
            {
                "id": "order-1",
                "kind": "delivery",
                "position": [1, 1],
                "local": True,
                "known_initial": True,
                "deadline": 12,
                "priority": 2,
                "discovered_by": None,
                "report_delay": 0,
                "commodity": "water",
                "quantity": 3,
                "depot_id": "d1",
                "load_minutes": 1,
                "unload_minutes": 1,
            },
            {
                "id": "order-hidden",
                "kind": "delivery",
                "position": [1, 1],
                "local": True,
                "known_initial": False,
                "deadline": 15,
                "priority": 1,
                "discovered_by": None,
                "report_delay": 0,
                "commodity": "water",
                "quantity": 2,
                "depot_id": "d1",
                "load_minutes": 1,
                "unload_minutes": 1,
            },
        ],
        "chapter1_snapshot": {"source": "synthetic_initial_assignment", "time": 0, "queues": {"p1": ["inspect-1", "order-1"]}},
        "disturbances": [],
    }


def _result() -> dict:
    events = [
        {"seq": 0, "time": 0, "type": "assignment", "task_id": "inspect-1", "previous_assignee": "p1", "new_assignee": "p1", "initial": True, "reason": "chapter1_snapshot"},
        {"seq": 1, "time": 0, "type": "assignment", "task_id": "order-1", "previous_assignee": "p1", "new_assignee": "p1", "initial": True, "reason": "chapter1_snapshot"},
        {"seq": 2, "time": 1, "type": "move", "platform_id": "p1", "task_id": "inspect-1", "from": [0, 0], "to": [1, 0], "distance": 1, "duration": 1, "energy": 1},
        {"seq": 3, "time": 1, "type": "arrival", "platform_id": "p1", "task_id": "inspect-1", "stage": "inspection_site", "position": [1, 0]},
        {"seq": 4, "time": 2, "type": "service", "task_id": "inspect-1", "platform_id": "p1", "stage": "observe", "duration": 1, "energy": 0.1},
        {"seq": 5, "time": 2, "type": "inspection_completed", "task_id": "inspect-1", "platform_id": "p1"},
        {"seq": 6, "time": 2, "type": "report_generated", "kind": "inspection_result", "subject_id": "inspect-1", "task_id": "inspect-1", "report_delay": 0},
        {"seq": 7, "time": 2, "type": "report_received", "kind": "inspection_result", "subject_id": "inspect-1", "task_id": "inspect-1"},
        {"seq": 8, "time": 3, "type": "move", "platform_id": "p1", "task_id": "order-1", "from": [1, 0], "to": [0, 0], "distance": 1, "duration": 1, "energy": 1},
        {"seq": 9, "time": 3, "type": "arrival", "platform_id": "p1", "task_id": "order-1", "stage": "depot", "position": [0, 0]},
        {"seq": 10, "time": 4, "type": "service", "task_id": "order-1", "platform_id": "p1", "stage": "loading", "duration": 1, "energy": 0.1},
        {"seq": 11, "time": 4, "type": "loaded", "task_id": "order-1", "platform_id": "p1", "depot_id": "d1", "commodity": "water", "quantity": 3},
        {"seq": 12, "time": 5, "type": "move", "platform_id": "p1", "task_id": "order-1", "from": [0, 0], "to": [0.7071067811865475, 0.7071067811865475], "distance": 1, "duration": 1, "energy": 1},
        {"seq": 13, "time": 6, "type": "move", "platform_id": "p1", "task_id": "order-1", "from": [0.7071067811865475, 0.7071067811865475], "to": [1, 1], "distance": 0.4142135623730951, "duration": 0.4142135623730951, "energy": 0.4142135623730951},
        {"seq": 14, "time": 6, "type": "arrival", "platform_id": "p1", "task_id": "order-1", "stage": "delivery_site", "position": [1, 1]},
        {"seq": 15, "time": 7, "type": "service", "task_id": "order-1", "platform_id": "p1", "stage": "unloading", "duration": 1, "energy": 0.1},
        {"seq": 16, "time": 7, "type": "delivery_confirmed", "task_id": "order-1", "platform_id": "p1", "depot_id": "d1", "commodity": "water", "quantity": 3},
    ]
    return {
        "scenario_id": "audit-hand",
        "policy": "C1",
        "events": events,
        "summary": {
            "weighted_on_time_delivery_rate": 2 / 3,
            "inspection_completion_rate": 1.0,
            "inspection_on_time_rate": 1.0,
            "delivered_orders": 1,
            "late_orders": 0,
            "unmet_orders": 1,
            "undiscovered_orders": 1,
            "energy_used": 3.714213562373095,
            "reassignments": 0,
            "new_assignments": 0,
        },
    }


class IndependentAuditTests(unittest.TestCase):
    def test_replay_metrics_and_conservation(self):
        audited = self._audit_event_only(_scenario(), _result())
        self.assertEqual(audited["metrics"]["delivered_orders"], 1)
        self.assertEqual(audited["metrics"]["undiscovered_orders"], 1)
        self.assertAlmostEqual(audited["metrics"]["weighted_on_time_delivery_rate"], 2 / 3)
        self.assertEqual(audited["validation_level"], "event_replay_only")
        water = next(item for item in audited["conservation"] if item["commodity"] == "water")
        self.assertTrue(water["conserved"])
        self.assertEqual(water["initial_stock"], 10)
        self.assertEqual(water["remaining_stock"], 7)
        self.assertEqual(water["delivered"], 3)

    def test_tampered_summary_is_rejected(self):
        result = _result()
        result["summary"]["energy_used"] += 1
        with self.assertRaises(ValueError):
            self._audit_event_only(_scenario(), result)

    def test_duplicate_delivery_confirmation_is_rejected(self):
        scenario = _scenario()
        result = _result()
        duplicate = copy.deepcopy(result["events"][-1])
        duplicate["seq"] = 13
        duplicate["time"] = 10
        result["events"].append(duplicate)
        with self.assertRaises(ValueError):
            self._audit_event_only(scenario, result)

    def test_geometry_energy_and_stage_preconditions_are_enforced(self):
        scenario = _scenario()
        result = _result()
        result["events"][2]["distance"] = 2
        with self.assertRaisesRegex(ValueError, "geometry/distance"):
            self._audit_event_only(scenario, result)

        result = _result()
        result["events"] = [event for event in result["events"] if not (event["type"] == "service" and event.get("stage") == "loading")]
        for seq, event in enumerate(result["events"]):
            event["seq"] = seq
        with self.assertRaisesRegex(ValueError, "loading service"):
            self._audit_event_only(scenario, result)

    def test_resource_report_null_subject_is_not_a_task(self):
        scenario = _scenario()
        scenario["disturbances"] = [{"id": "e1", "time": 0, "kind": "energy_change", "platform_id": "p1", "value": 18}]
        result = _result()
        result["events"][2:2] = [
            {"seq": 1, "time": 0, "type": "energy_changed", "platform_id": "p1", "old_energy": 20, "new_energy": 18, "delta": -2, "disturbance_id": "e1"},
            {"seq": 2, "time": 0, "type": "report_generated", "kind": "energy_change", "subject_id": None, "task_id": None, "platform_id": "p1", "new_energy": 18, "value": 18, "report_delay": 0},
            {"seq": 3, "time": 0, "type": "report_received", "kind": "energy_change", "subject_id": None, "task_id": None, "platform_id": "p1", "new_energy": 18, "value": 18},
        ]
        for seq, event in enumerate(result["events"]):
            event["seq"] = seq
        audited = self._audit_event_only(scenario, result)
        self.assertAlmostEqual(audited["metrics"]["energy_used"], 3.714213562373095)

    def test_same_commodity_cargo_is_accounted_per_depot(self):
        scenario = _scenario()
        scenario["depots"].append({"id": "d2", "position": [0, 0], "stock": {"water": 10}})
        scenario["tasks"][2]["discovered_by"] = None
        result = _result()
        result["events"] = result["events"][:12]
        for seq, event in enumerate(result["events"]):
            event["seq"] = seq
        result["summary"] = {
            "weighted_on_time_delivery_rate": 0.0,
            "inspection_completion_rate": 1.0,
            "inspection_on_time_rate": 1.0,
            "delivered_orders": 0,
            "late_orders": 0,
            "unmet_orders": 2,
            "undiscovered_orders": 1,
            "energy_used": 2.2,
            "reassignments": 0,
            "new_assignments": 0,
        }
        audited = self._audit_event_only(scenario, result)
        d1 = next(item for item in audited["conservation"] if item["depot_id"] == "d1")
        d2 = next(item for item in audited["conservation"] if item["depot_id"] == "d2")
        self.assertEqual(d1["onboard"], 3)
        self.assertEqual(d2["onboard"], 0)

    def test_full_audit_rejects_missing_transition_or_final_state_artifacts(self):
        result = _result()
        result["initial_handoff"] = normalize_initial_assignment(_scenario())
        with self.assertRaisesRegex(ValueError, "transitions missing"):
            audit_run(_scenario(), result)

        result["transitions"] = []
        with self.assertRaisesRegex(ValueError, "final_state missing"):
            audit_run(_scenario(), result)

    def test_requested_policy_and_initial_handoff_identity_are_checked(self):
        scenario = _scenario()
        result = _result()
        with self.assertRaisesRegex(ValueError, "requested policy"):
            self._audit_event_only(scenario, result, expected_policy="C0")

        result = _result()
        result["initial_handoff"] = {"schema": "relief-chapter-handoff/1"}
        with self.assertRaisesRegex(ValueError, "initial_handoff mismatch"):
            audit_run(scenario, result, mode="event_only", expected_policy="C1")

    def test_resigned_early_resource_information_is_rejected(self):
        from relief_env import ReliefEnv

        cases = [
            (
                {"id": "late-energy", "time": 1, "kind": "energy_change", "platform_id": "p1", "value": 5, "report_delay": 2},
                "public energy mismatch",
            ),
            (
                {"id": "late-failure", "time": 1, "kind": "failure", "platform_id": "p1", "report_delay": 2},
                "public failure visibility mismatch",
            ),
            (
                {"id": "late-stock", "time": 1, "kind": "stock_loss", "depot_id": "d1", "commodity": "water", "quantity": 4, "report_delay": 2},
                "public stock mismatch",
            ),
        ]
        for disturbance, message in cases:
            with self.subTest(kind=disturbance["kind"]):
                scenario = _scenario()
                scenario["tasks"] = []
                scenario["chapter1_snapshot"]["queues"] = {"p1": []}
                scenario["disturbances"] = [disturbance]
                result = ReliefEnv(scenario).run("C0")
                self.assertEqual(audit_run(scenario, result, expected_policy="C0")["validation_level"], "full_artifact")

                transition = result["transitions"][1]
                observation = transition["public_observation"]
                if disturbance["kind"] == "energy_change":
                    observation["platforms"][0]["energy"] = 5
                elif disturbance["kind"] == "failure":
                    observation["platforms"][0]["failed"] = True
                else:
                    observation["depots"][0]["stock"]["water"] = 6
                identity = bind_decision(observation, transition["candidates"])
                transition["identity"] = identity
                transition["observation_sha256"] = identity["observation_sha256"]
                transition["candidate_catalog_sha256"] = identity["candidate_catalog_sha256"]
                with self.assertRaisesRegex(ValueError, message):
                    audit_run(scenario, result, expected_policy="C0")

    def test_stock_loss_is_capped_at_inventory_available_when_disturbance_occurs(self):
        from relief_env import ReliefEnv

        scenario = _scenario()
        order = next(task for task in scenario["tasks"] if task["id"] == "order-1")
        scenario["tasks"] = [order]
        scenario["depots"][0]["stock"]["water"] = order["quantity"]
        scenario["chapter1_snapshot"]["queues"] = {"p1": [order["id"]]}
        scenario["disturbances"] = [
            {"id": "loss-after-load", "time": 2, "kind": "stock_loss", "depot_id": "d1", "commodity": "water", "quantity": 2, "report_delay": 1}
        ]
        result = ReliefEnv(scenario).run("C1")
        stock_event = next(event for event in result["events"] if event["type"] == "stock_lost")
        self.assertEqual(stock_event["requested_quantity"], 2)
        self.assertEqual(stock_event["quantity"], 0)
        audited = audit_run(scenario, result, expected_policy="C1")
        water = next(item for item in audited["conservation"] if item["depot_id"] == "d1" and item["commodity"] == "water")
        self.assertEqual(water["delivered"], order["quantity"])
        self.assertEqual(water["stock_loss"], 0)

    @staticmethod
    def _audit_event_only(scenario: dict, result: dict, expected_policy: str = "C1") -> dict:
        result["initial_handoff"] = normalize_initial_assignment(scenario)
        return audit_run(scenario, result, mode="event_only", expected_policy=expected_policy)


if __name__ == "__main__":
    unittest.main()
