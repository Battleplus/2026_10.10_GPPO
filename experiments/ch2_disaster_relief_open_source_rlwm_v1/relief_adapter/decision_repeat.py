"""Fixed-shape, public-only decision interface for ``ReliefEnv``.

The base simulator dispatches a joint batch and advances one physical minute.
This adapter exposes that batch as zero-time candidate-selection microsteps,
followed by one COMMIT action that performs the original simulator step.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
from numbers import Integral
from array import array
from collections import defaultdict
from pathlib import Path
from typing import Any


ADAPTER_SCHEMA = "relief-dreamer-adapter/1"
SIMULATOR_OBSERVATION_SCHEMA = "relief-public-observation/1"
DEFAULT_MAX_PLATFORM_SLOTS = 4
DEFAULT_MAX_TASK_SLOTS = 16
DEFAULT_MAX_DEPOT_SLOTS = 4
COMMODITY_SLOTS = ("food", "medical", "water")
COMMIT_KEY = "COMMIT"

_SOURCE_CONTRACT_FILES = (
    "relief_env.py",
    "scenario_schema.py",
    "chapter1_adapter.py",
    "baselines.py",
    "stable_identity.py",
)
_TASK_STATUSES = ("pending", "assigned", "active", "completed", "failed", "expired", "other")
_TASK_PHASES = (
    "pending",
    "released",
    "assigned",
    "to_inspection",
    "to_depot",
    "loading",
    "unloading",
    "observe",
    "to_delivery_site",
    "in_transit",
    "report_received",
    "inspection_completed",
    "delivery_confirmed",
    "failed",
    "other",
)
_CANDIDATE_FIELDS = (
    "available",
    "is_dispatch",
    "is_commit",
    "estimated_completion_fraction",
    "required_energy_fraction",
    "kind_inspection",
    "kind_delivery",
    "locked",
)


def _json_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unit(value: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(0.0, float(value) / float(denominator)))


def _signed_unit(value: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return min(1.0, max(-1.0, float(value) / float(denominator)))


class DecisionRepeatReliefAdapter:
    """Expose variable public candidates as fixed action and feature arrays.

    Actions ``0..(P*T-1)`` select one currently legal dispatch candidate.
    ``P*T`` is COMMIT/NOOP: it ends selection for this physical minute and
    calls the underlying simulator once with the accumulated dispatch batch.
    Selection calls have ``dt=0`` and zero reward; COMMIT has ``dt=1`` and
    carries the simulator reward.

    ``max_task_slots`` and the other slot capacities are configuration values.
    Task slots are allocated only after a task appears in a public observation;
    the adapter never reads the simulator's scenario or hidden task inventory.
    """

    def __init__(
        self,
        env: Any,
        *,
        max_platform_slots: int = DEFAULT_MAX_PLATFORM_SLOTS,
        max_task_slots: int = DEFAULT_MAX_TASK_SLOTS,
        max_depot_slots: int = DEFAULT_MAX_DEPOT_SLOTS,
    ):
        for name, value in (
            ("max_platform_slots", max_platform_slots),
            ("max_task_slots", max_task_slots),
            ("max_depot_slots", max_depot_slots),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("reset", "step", "public_observation", "candidates"):
            if not callable(getattr(env, name, None)):
                raise TypeError(f"simulator does not implement {name}()")

        self.env = env
        self.max_platform_slots = max_platform_slots
        self.max_task_slots = max_task_slots
        self.max_depot_slots = max_depot_slots
        self.dispatch_action_count = max_platform_slots * max_task_slots
        self.commit_action = self.dispatch_action_count
        self.action_size = self.dispatch_action_count + 1
        self._source_files = self._source_fingerprints(env)
        self._platform_ids: list[str] = []
        self._platform_slot: dict[str, int] = {}
        self._depot_ids: list[str] = []
        self._depot_slot: dict[str, int] = {}
        self._task_slot: dict[str, int] = {}
        self._slot_task: list[str | None] = [None] * max_task_slots
        self._pending_ids: list[str] = []
        self._pending_candidates: list[dict[str, Any]] = []
        self._used_platforms: set[str] = set()
        self._used_tasks: set[str] = set()
        self._reserved_stock: dict[tuple[str, str], float] = defaultdict(float)
        self._decision_log: list[dict[str, Any]] = []
        self._physical_step = 0
        self._last_observation: dict[str, Any] | None = None
        self._current_public: dict[str, Any] | None = None
        self._current_catalog: list[dict[str, Any]] = []
        self._started = False
        self._terminal = False
        self._feature_layout = self._build_feature_layout()
        self._feature_layout_sha256 = _json_digest(self._feature_layout)

    @staticmethod
    def _source_fingerprints(env: Any) -> dict[str, str]:
        source = inspect.getsourcefile(type(env))
        if source is None:
            raise ValueError("cannot fingerprint simulator source file")
        source_dir = Path(source).resolve().parent
        fingerprints: dict[str, str] = {}
        for filename in _SOURCE_CONTRACT_FILES:
            path = source_dir / filename
            if not path.is_file():
                raise ValueError(f"simulator source contract file is missing: {filename}")
            fingerprints[filename] = _sha256(path)
        return fingerprints

    def _build_feature_layout(self) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        offset = 0

        def add(name: str, names: list[str] | tuple[str, ...]) -> None:
            nonlocal offset
            fields.append({"name": name, "offset": offset, "length": len(names), "fields": list(names)})
            offset += len(names)

        add("global", ("time_fraction", "collection_open", "pending_dispatch_count_fraction"))
        platform_names = [
            "present", "type_uav", "type_helicopter", "local", "x_fraction", "y_fraction",
            "capacity_fraction", "speed_fraction", "energy_fraction", "energy_per_km_fraction",
            "service_energy_fraction", "failed", "busy",
        ] + [f"active_task_slot_{index:02d}" for index in range(self.max_task_slots)]
        for index in range(self.max_platform_slots):
            add(f"platform_slot_{index:02d}", platform_names)

        task_names = [
            "present", "kind_inspection", "kind_delivery", "local", "x_fraction", "y_fraction",
            "deadline_remaining_fraction", "priority_fraction", "quantity_fraction", "work_fraction",
            "deadline_missed",
        ]
        task_names += [f"status_{name}" for name in _TASK_STATUSES]
        task_names += [f"phase_{name}" for name in _TASK_PHASES]
        task_names += [f"assignee_platform_slot_{index:02d}" for index in range(self.max_platform_slots)]
        task_names += ["assignee_none"]
        task_names += [f"original_assignee_platform_slot_{index:02d}" for index in range(self.max_platform_slots)]
        task_names += ["original_assignee_none", "report_generated", "report_received"]
        for index in range(self.max_task_slots):
            add(f"task_slot_{index:02d}", task_names)

        depot_names = ["present", "x_fraction", "y_fraction"] + [
            f"stock_{commodity}_fraction" for commodity in COMMODITY_SLOTS
        ]
        for index in range(self.max_depot_slots):
            add(f"depot_slot_{index:02d}", depot_names)

        add("pending_platforms", [f"selected_platform_slot_{index:02d}" for index in range(self.max_platform_slots)])
        add("pending_tasks", [f"selected_task_slot_{index:02d}" for index in range(self.max_task_slots)])
        add(
            "pending_stock",
            [f"depot_slot_{depot:02d}_{commodity}_reserved_fraction" for depot in range(self.max_depot_slots) for commodity in COMMODITY_SLOTS],
        )
        for index in range(self.action_size):
            add(f"action_slot_{index:03d}", _CANDIDATE_FIELDS)
        return fields

    @property
    def feature_layout(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._feature_layout)

    @property
    def feature_size(self) -> int:
        return sum(item["length"] for item in self._feature_layout)

    @property
    def signature(self) -> dict[str, Any]:
        source_digest = _json_digest(self._source_files)
        return {
            "schema": ADAPTER_SCHEMA,
            "simulator_observation_schema": SIMULATOR_OBSERVATION_SCHEMA,
            "slot_config": {
                "max_platform_slots": self.max_platform_slots,
                "max_task_slots": self.max_task_slots,
                "max_depot_slots": self.max_depot_slots,
                "commodity_slots": list(COMMODITY_SLOTS),
            },
            "action": {
                "type": "discrete",
                "size": self.action_size,
                "dispatch_index": "platform_slot * max_task_slots + task_slot",
                "commit_index": self.commit_action,
                "semantics": "zero-time candidate selection; COMMIT advances one physical minute",
            },
            "feature_size": self.feature_size,
            "feature_layout_sha256": self._feature_layout_sha256,
            "simulator_source_sha256": source_digest,
            "simulator_source_files": copy.deepcopy(self._source_files),
        }

    @property
    def signature_sha256(self) -> str:
        return _json_digest(self.signature)

    def reset(self, policy: str = "LEARNED") -> dict[str, Any]:
        public = self.env.reset(policy)
        self._validate_public_observation(public)
        platforms = public["platforms"]
        depots = public["depots"]
        if len(platforms) > self.max_platform_slots:
            raise ValueError("public platform count exceeds configured slot capacity")
        if len(depots) > self.max_depot_slots:
            raise ValueError("public depot count exceeds configured slot capacity")

        self._platform_ids = sorted(item["id"] for item in platforms)
        self._platform_slot = {ident: index for index, ident in enumerate(self._platform_ids)}
        self._depot_ids = sorted(item["id"] for item in depots)
        self._depot_slot = {ident: index for index, ident in enumerate(self._depot_ids)}
        self._task_slot = {}
        self._slot_task = [None] * self.max_task_slots
        self._pending_ids = []
        self._pending_candidates = []
        self._used_platforms = set()
        self._used_tasks = set()
        self._reserved_stock = defaultdict(float)
        self._decision_log = []
        self._physical_step = 0
        self._started = True
        self._terminal = False
        self._refresh(public)
        return copy.deepcopy(self._last_observation)

    @staticmethod
    def _validate_public_observation(public: Any) -> None:
        if not isinstance(public, dict) or public.get("schema") != SIMULATOR_OBSERVATION_SCHEMA:
            raise ValueError("unsupported simulator public-observation schema")
        for field in ("time", "horizon", "map", "platforms", "depots", "tasks"):
            if field not in public:
                raise ValueError(f"public observation is missing {field!r}")
        if type(public["time"]) is not int or type(public["horizon"]) is not int or public["horizon"] <= 0:
            raise ValueError("public observation time or horizon is invalid")
        if type(public["platforms"]) is not list or type(public["depots"]) is not list or type(public["tasks"]) is not list:
            raise ValueError("public entity collections must be lists")

    def _register_public_tasks(self, public: dict[str, Any]) -> None:
        visible = public["tasks"]
        visible_ids = [item.get("id") for item in visible]
        if any(type(ident) is not str or not ident for ident in visible_ids):
            raise ValueError("public task IDs must be non-empty strings")
        if len(set(visible_ids)) != len(visible_ids):
            raise ValueError("duplicate task ID in public observation")
        for task_id in sorted(visible_ids):
            if task_id in self._task_slot:
                continue
            try:
                slot = self._slot_task.index(None)
            except ValueError as exc:
                raise ValueError("visible task count exceeds configured slot capacity") from exc
            self._task_slot[task_id] = slot
            self._slot_task[slot] = task_id

    def _refresh(self, public: dict[str, Any] | None = None) -> None:
        if public is None:
            public = self.env.public_observation()
        self._validate_public_observation(public)
        self._register_public_tasks(public)
        self._current_public = copy.deepcopy(public)
        self._current_catalog = copy.deepcopy(self.env.candidates())
        self._last_observation = self._encode_observation(public, self._current_catalog)

    def _candidate_index(self, candidate: dict[str, Any]) -> int:
        platform_id = candidate.get("platform_id")
        task_id = candidate.get("task_id")
        if platform_id not in self._platform_slot or task_id not in self._task_slot:
            raise ValueError("candidate refers to an entity outside the public slot maps")
        return self._platform_slot[platform_id] * self.max_task_slots + self._task_slot[task_id]

    @staticmethod
    def _public_stock_limits(public: dict[str, Any]) -> dict[tuple[str, str], float]:
        stock: dict[tuple[str, str], float] = {}
        for depot in public["depots"]:
            for commodity, quantity in depot.get("stock", {}).items():
                if commodity not in COMMODITY_SLOTS:
                    raise ValueError(f"unsupported public commodity {commodity!r}")
                stock[(depot["id"], commodity)] = float(quantity)
        commitments: dict[tuple[str, str], float] = defaultdict(float)
        for task in public["tasks"]:
            if (
                task.get("kind") == "delivery"
                and task.get("status") in {"active", "assigned"}
                and task.get("phase") in {"assigned", "to_depot", "loading"}
            ):
                key = (str(task["depot_id"]), str(task["commodity"]))
                commitments[key] += float(task["quantity"])
        return {key: max(0.0, value - commitments.get(key, 0.0)) for key, value in stock.items()}

    def _legal_action_state(
        self,
        public: dict[str, Any],
        catalog: list[dict[str, Any]],
    ) -> tuple[list[bool], list[dict[str, Any] | None], dict[int, dict[str, Any]]]:
        mask = [False] * self.action_size
        table: list[dict[str, Any] | None] = [None] * self.action_size
        by_index: dict[int, dict[str, Any]] = {}
        stock_limits = self._public_stock_limits(public)
        for candidate in catalog:
            if candidate.get("type") == "noop":
                continue
            if candidate.get("type") != "dispatch" or type(candidate.get("id")) is not str:
                raise ValueError("simulator returned an invalid candidate")
            index = self._candidate_index(candidate)
            if index in by_index:
                raise ValueError("candidate slot collision")
            platform_id = str(candidate["platform_id"])
            task_id = str(candidate["task_id"])
            legal = platform_id not in self._used_platforms and task_id not in self._used_tasks
            task_by_id = {item["id"]: item for item in public["tasks"]}
            task = task_by_id[task_id]
            if task.get("kind") == "delivery":
                key = (str(task["depot_id"]), str(task["commodity"]))
                legal = legal and (
                    self._reserved_stock.get(key, 0.0) + float(task["quantity"])
                    <= stock_limits.get(key, 0.0) + 1e-9
                )
            if legal:
                mask[index] = True
                table[index] = copy.deepcopy(candidate)
                by_index[index] = copy.deepcopy(candidate)
        mask[self.commit_action] = True
        table[self.commit_action] = {"id": COMMIT_KEY, "type": "commit"}
        return mask, table, by_index

    def _append_platform_features(self, output: list[float], platform: dict[str, Any] | None, public: dict[str, Any]) -> None:
        if platform is None:
            output.extend([0.0] * (13 + self.max_task_slots))
            return
        active_task = platform.get("active_task_id")
        values = [
            1.0,
            float(platform.get("type") == "uav"),
            float(platform.get("type") == "helicopter"),
            float(bool(platform.get("local"))),
            _unit(platform["position"][0], public["map"]["cols"] * public["map"]["cell_km"]),
            _unit(platform["position"][1], public["map"]["rows"] * public["map"]["cell_km"]),
            _unit(platform.get("capacity_kg", 0.0), 30.0),
            _unit(platform.get("speed_km_min", 0.0), 1.0),
            _unit(platform.get("energy", 0.0), 100.0),
            _unit(platform.get("energy_per_km", 0.0), 1.0),
            _unit(platform.get("service_energy_per_min", 0.0), 1.0),
            float(bool(platform.get("failed"))),
            float(bool(platform.get("busy"))),
        ]
        values.extend(float(active_task is not None and self._task_slot.get(active_task) == index) for index in range(self.max_task_slots))
        output.extend(values)

    def _append_task_features(self, output: list[float], task: dict[str, Any] | None, public: dict[str, Any]) -> None:
        if task is None:
            output.extend([0.0] * (11 + len(_TASK_STATUSES) + len(_TASK_PHASES) + 2 * (self.max_platform_slots + 1) + 2))
            return
        status = str(task.get("status", "other"))
        status = status if status in _TASK_STATUSES else "other"
        phase = str(task.get("phase", "other"))
        phase = phase if phase in _TASK_PHASES else "other"
        kind = str(task.get("kind"))
        service = float(task.get("service_minutes", 0.0)) if kind == "inspection" else float(task.get("load_minutes", 0.0)) + float(task.get("unload_minutes", 0.0))
        values = [
            1.0,
            float(kind == "inspection"),
            float(kind == "delivery"),
            float(bool(task.get("local"))),
            _unit(task["position"][0], public["map"]["cols"] * public["map"]["cell_km"]),
            _unit(task["position"][1], public["map"]["rows"] * public["map"]["cell_km"]),
            _signed_unit(float(task.get("deadline", 0)) - float(public["time"]), public["horizon"]),
            _unit(task.get("priority", 0.0), 5.0),
            _unit(task.get("quantity", 0.0), 30.0),
            _unit(service, public["horizon"]),
            float(bool(task.get("deadline_missed"))),
        ]
        values.extend(float(status == value) for value in _TASK_STATUSES)
        values.extend(float(phase == value) for value in _TASK_PHASES)
        for entity_id in self._platform_ids:
            values.append(float(task.get("assignee") == entity_id))
        values.append(float(task.get("assignee") is None))
        for entity_id in self._platform_ids:
            values.append(float(task.get("original_assignee") == entity_id))
        values.append(float(task.get("original_assignee") is None))
        values.append(float(task.get("report_generated_at") is not None))
        values.append(float(task.get("report_received_at") is not None))
        output.extend(values)

    def _encode_observation(
        self,
        public: dict[str, Any],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._validate_public_observation(public)
        platform_by_id = {item["id"]: item for item in public["platforms"]}
        task_by_id = {item["id"]: item for item in public["tasks"]}
        depot_by_id = {item["id"]: item for item in public["depots"]}
        if set(platform_by_id) != set(self._platform_ids) or set(depot_by_id) != set(self._depot_ids):
            raise ValueError("public platform or depot identity set changed during an episode")

        action_mask, action_table, candidate_by_index = self._legal_action_state(public, catalog)
        vector: list[float] = [
            _unit(public["time"], public["horizon"]),
            1.0,
            _unit(len(self._pending_ids), self.max_platform_slots),
        ]

        for entity_id in self._platform_ids:
            self._append_platform_features(vector, platform_by_id[entity_id], public)
        for task_id in self._slot_task:
            task = task_by_id.get(task_id) if task_id is not None else None
            self._append_task_features(vector, task, public)

        if len(depot_by_id) > self.max_depot_slots:
            raise ValueError("public depot count exceeds configured slot capacity")
        for slot in range(self.max_depot_slots):
            if slot >= len(self._depot_ids):
                vector.extend([0.0] * (3 + len(COMMODITY_SLOTS)))
                continue
            depot = depot_by_id[self._depot_ids[slot]]
            vector.extend([
                1.0,
                _unit(depot["position"][0], public["map"]["cols"] * public["map"]["cell_km"]),
                _unit(depot["position"][1], public["map"]["rows"] * public["map"]["cell_km"]),
            ])
            stocks = depot.get("stock", {})
            unknown = set(stocks) - set(COMMODITY_SLOTS)
            if unknown:
                raise ValueError(f"unsupported public commodities: {sorted(unknown)}")
            vector.extend(_unit(stocks.get(name, 0.0), 500.0) for name in COMMODITY_SLOTS)

        vector.extend(float(entity_id in self._used_platforms) for entity_id in self._platform_ids)
        vector.extend([0.0] * (self.max_platform_slots - len(self._platform_ids)))
        vector.extend(float(task_id in self._used_tasks) for task_id in self._slot_task)

        stock_reserved: dict[tuple[str, str], float] = defaultdict(float)
        for (depot_id, commodity), quantity in self._reserved_stock.items():
            stock_reserved[(depot_id, commodity)] += quantity
        for depot_id in self._depot_ids:
            for commodity in COMMODITY_SLOTS:
                vector.append(_unit(stock_reserved.get((depot_id, commodity), 0.0), 500.0))
        for _ in range(self.max_depot_slots - len(self._depot_ids)):
            vector.extend([0.0] * len(COMMODITY_SLOTS))

        for index in range(self.action_size):
            candidate = candidate_by_index.get(index)
            if index == self.commit_action:
                vector.extend([1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            elif candidate is None:
                vector.extend([0.0] * len(_CANDIDATE_FIELDS))
            else:
                task = task_by_id[candidate["task_id"]]
                vector.extend([
                    1.0,
                    1.0,
                    0.0,
                    _unit(candidate.get("estimated_completion", 0.0), public["horizon"]),
                    _unit(candidate.get("required_energy", 0.0), 100.0),
                    float(task.get("kind") == "inspection"),
                    float(task.get("kind") == "delivery"),
                    float(bool(candidate.get("locked"))),
                ])

        if len(vector) != self.feature_size:
            raise AssertionError(f"feature layout length mismatch: {len(vector)} != {self.feature_size}")
        if any(not math.isfinite(value) for value in vector):
            raise ValueError("encoded public observation contains a non-finite feature")
        float32_vector = array("f", vector)
        if float32_vector.itemsize != 4:
            raise RuntimeError("host does not provide 32-bit float array storage")

        action_keys: list[str | None] = [None] * self.action_size
        for index, candidate in enumerate(action_table):
            if candidate is not None:
                action_keys[index] = str(candidate["id"])
        task_ids_by_slot = tuple(self._slot_task)
        platform_ids_by_slot = tuple(self._platform_ids) + (None,) * (self.max_platform_slots - len(self._platform_ids))
        return {
            "schema": ADAPTER_SCHEMA,
            "vector": float32_vector,
            "vector_length": self.feature_size,
            "action_mask": tuple(action_mask),
            "action_size": self.action_size,
            "action_keys": tuple(action_keys),
            "task_ids_by_slot": task_ids_by_slot,
            "platform_ids_by_slot": platform_ids_by_slot,
            "time": public["time"],
            "phase": "collect",
            "adapter_signature_sha256": self.signature_sha256,
            "feature_layout_sha256": self._feature_layout_sha256,
            "public_observation": copy.deepcopy(public),
        }

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if not self._started:
            raise RuntimeError("call reset() before step()")
        if self._terminal:
            raise RuntimeError("episode is terminated")
        if isinstance(action, bool) or not isinstance(action, Integral):
            raise TypeError("action must be an integer discrete action index")
        action = int(action)
        if action < 0 or action >= self.action_size:
            raise ValueError("action index is outside the fixed action space")
        current = self._last_observation
        assert current is not None
        if not current["action_mask"][action]:
            raise ValueError("selected action is masked or unavailable")
        time = int(current["time"])

        if action != self.commit_action:
            candidate = next((item for item in self._current_catalog if item.get("id") == current["action_keys"][action]), None)
            if candidate is None:
                raise ValueError("selected candidate disappeared from the public catalog")
            self._pending_ids.append(str(candidate["id"]))
            self._pending_candidates.append(copy.deepcopy(candidate))
            self._used_platforms.add(str(candidate["platform_id"]))
            self._used_tasks.add(str(candidate["task_id"]))
            public = self._current_public
            assert public is not None
            task = next(item for item in public["tasks"] if item["id"] == candidate["task_id"])
            if task.get("kind") == "delivery":
                key = (str(task["depot_id"]), str(task["commodity"]))
                self._reserved_stock[key] += float(task["quantity"])
            record = {
                "physical_time": time,
                "physical_time_delta": 0,
                "discount_exponent": 0,
                "action_index": action,
                "action_key": candidate["id"],
                "action_type": "dispatch_selection",
            }
            self._decision_log.append(record)
            self._refresh(public)
            return copy.deepcopy(self._last_observation), 0.0, False, False, {"adapter": copy.deepcopy(record)}

        selected_ids = list(self._pending_ids)
        selected_candidates = copy.deepcopy(self._pending_candidates)
        # Discard simulator info payloads because reward_events may contain
        # disturbance truth before its public report is received.
        public, reward, terminated, truncated, simulator_info = self.env.step(selected_ids)
        self._validate_public_observation(public)
        safe_identity = None
        transition = simulator_info.get("transition") if isinstance(simulator_info, dict) else None
        if isinstance(transition, dict) and isinstance(transition.get("identity"), dict):
            safe_identity = copy.deepcopy(transition["identity"])
        record = {
            "physical_time": time,
            "physical_time_delta": 1,
            "discount_exponent": 1,
            "action_index": action,
            "action_key": COMMIT_KEY,
            "action_type": "commit",
            "selected_candidate_keys": [item["id"] for item in selected_candidates],
            "selected_action_ids": selected_ids,
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "public_decision_identity": safe_identity,
        }
        self._decision_log.append(record)
        self._pending_ids = []
        self._pending_candidates = []
        self._used_platforms = set()
        self._used_tasks = set()
        self._reserved_stock = defaultdict(float)
        self._physical_step += 1
        self._terminal = bool(terminated or truncated)
        self._refresh(public)
        return copy.deepcopy(self._last_observation), float(reward), bool(terminated), bool(truncated), {"adapter": copy.deepcopy(record)}

    @property
    def decision_log(self) -> list[dict[str, Any]]:
        """Return sanitized action timing records without simulator truth events."""
        return copy.deepcopy(self._decision_log)
