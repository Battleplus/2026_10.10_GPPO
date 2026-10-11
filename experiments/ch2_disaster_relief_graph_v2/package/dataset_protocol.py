"""Generate the frozen, parent-isolated disaster-relief scenario registry."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol" / "preregistered_protocol.json"
SPLIT_SIZES = {"train": 56, "development": 14, "heldout": 56}
STRATA = (
    "control",
    "failure",
    "energy_change",
    "stock_loss",
    "report_delay",
    "combined",
    "external_commitment",
)


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _seed(split: str, stratum: str, index: int) -> int:
    payload = f"relief-v1|{split}|{stratum}|{index}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _integer(seed: int, field: str, low: int, high: int) -> int:
    payload = f"{seed}\0{field}".encode("ascii")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return low + value % (high - low + 1)


def _coordinate(seed: int, field: str, *, outside: bool = False) -> float:
    if outside:
        # Integer quarter-cell offsets 8..36 produce coordinates 2..9 km.
        return _integer(seed, field, 8, 36) / 4.0
    return _integer(seed, field, 0, 7) / 4.0


def _position(seed: int, field: str, *, outside: bool = False) -> list[float]:
    return [
        _coordinate(seed, field + ".x", outside=outside),
        _coordinate(seed, field + ".y", outside=outside),
    ]


def _set_position(obj: dict, seed: int, field: str, *, outside: bool = False) -> None:
    obj["position"] = _position(seed, field, outside=outside)


def _apply_common_variation(scenario: dict, seed: int, *, outside_commitment: bool) -> None:
    for platform in scenario["platforms"]:
        if platform["type"] == "helicopter" and outside_commitment:
            platform["local"] = False
            _set_position(platform, seed, f"platform.{platform['id']}", outside=True)
        else:
            platform["local"] = True
            _set_position(platform, seed, f"platform.{platform['id']}")

    for depot in scenario["depots"]:
        _set_position(depot, seed, f"depot.{depot['id']}")

    for task in scenario["tasks"]:
        task_id = task["id"]
        task["priority"] = _integer(seed, f"task.{task_id}.priority", 1, 5)
        task["deadline"] = _integer(seed, f"task.{task_id}.deadline", 15, 60)
        is_outside = task_id == "committed-external"
        task["local"] = not is_outside
        _set_position(task, seed, f"task.{task_id}", outside=is_outside)
        if task["kind"] == "inspection":
            task["service_minutes"] = _integer(seed, f"task.{task_id}.service", 1, 4)
        else:
            task["quantity"] = _integer(seed, f"task.{task_id}.quantity", 1, 8)
            task["load_minutes"] = _integer(seed, f"task.{task_id}.load", 1, 3)
            task["unload_minutes"] = _integer(seed, f"task.{task_id}.unload", 1, 3)

    for platform in scenario["platforms"]:
        for task_id in scenario["chapter1_snapshot"]["queues"].get(platform["id"], []):
            task = next(item for item in scenario["tasks"] if item["id"] == task_id)
            task["local"] = bool(platform["local"])

    # Each commodity's initial stock is kept above total declared demand.
    commodity_demand: dict[tuple[str, str], float] = {}
    for task in scenario["tasks"]:
        if task["kind"] != "delivery":
            continue
        key = (task["depot_id"], task["commodity"])
        commodity_demand[key] = commodity_demand.get(key, 0.0) + float(task["quantity"])
    for (depot_id, commodity), demand in commodity_demand.items():
        depot = next(item for item in scenario["depots"] if item["id"] == depot_id)
        depot["stock"][commodity] = max(float(depot["stock"].get(commodity, 0)), demand)


def _delay_reports(scenario: dict, seed: int, *, disturbance_delay: bool = False) -> None:
    for task in scenario["tasks"]:
        task["report_delay"] = _integer(seed, f"task.{task['id']}.report_delay", 2, 12)
    if disturbance_delay:
        for disturbance in scenario["disturbances"]:
            disturbance["report_delay"] = _integer(seed, f"disturbance.{disturbance['id']}.report_delay", 2, 12)


def _disturbance_time(seed: int, label: str) -> int:
    return _integer(seed, f"disturbance.{label}.time", 2, 20)


def _add_stratum(scenario: dict, stratum: str, seed: int) -> None:
    horizon = int(scenario["horizon"])
    if stratum in {"failure", "combined"}:
        disturbance = {
            "id": f"{stratum}-failure",
            "time": min(_disturbance_time(seed, "failure"), horizon - 1),
            "kind": "failure",
            "platform_id": f"uav-{_integer(seed, 'failure.platform', 1, 3)}",
            "report_delay": 0,
        }
        scenario["disturbances"].append(disturbance)
    if stratum in {"energy_change", "combined"}:
        platform_id = f"uav-{_integer(seed, 'energy.platform', 1, 3)}"
        scenario["disturbances"].append({
            "id": f"{stratum}-energy",
            "time": min(_disturbance_time(seed, "energy"), horizon - 1),
            "kind": "energy_change",
            "platform_id": platform_id,
            "value": _integer(seed, "energy.new_value", 10, 28),
            "report_delay": 0,
        })
    if stratum in {"stock_loss", "combined"}:
        commodity = "water"
        scenario["disturbances"].append({
            "id": f"{stratum}-stock",
            "time": min(_disturbance_time(seed, "stock"), horizon - 1),
            "kind": "stock_loss",
            "depot_id": scenario["depots"][0]["id"],
            "commodity": commodity,
            "quantity": _integer(seed, "stock_loss.quantity", 1, 8),
            "report_delay": 0,
        })
    if stratum in {"report_delay", "combined"}:
        _delay_reports(scenario, seed, disturbance_delay=stratum == "combined")


def _load_base(stratum: str) -> dict:
    fixture_dir = HERE / "fixtures"
    fixture = "external_commitment.json" if stratum == "external_commitment" else "control.json"
    path = fixture_dir / fixture
    if not path.is_file():
        raise FileNotFoundError(f"required source fixture is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def generate_scenario(split: str, stratum: str, index: int) -> tuple[dict, int]:
    if split not in SPLIT_SIZES:
        raise ValueError(f"unknown split: {split}")
    if stratum not in STRATA:
        raise ValueError(f"unknown stratum: {stratum}")
    per_stratum = SPLIT_SIZES[split] // len(STRATA)
    if not 0 <= index < per_stratum:
        raise ValueError(f"index must be in [0, {per_stratum}) for {split}")
    seed = _seed(split, stratum, index)
    scenario = _load_base(stratum)
    scenario_id = f"graph-v1-{split}-{stratum}-{index:02d}"
    scenario["scenario_id"] = scenario_id
    outside_commitment = stratum == "external_commitment"
    _apply_common_variation(scenario, seed, outside_commitment=outside_commitment)
    _add_stratum(scenario, stratum, seed)
    # Keep the legacy control's original per-task report delays in the control,
    # failure, energy, and stock strata; only the preregistered report strata vary them.
    return scenario, seed


def build_registry(output_dir: str | Path, *, protocol_path: str | Path = PROTOCOL_PATH) -> dict:
    output = Path(output_dir)
    protocol_file = Path(protocol_path)
    protocol_bytes = protocol_file.read_bytes()
    protocol = json.loads(protocol_bytes.decode("utf-8"))
    entries: list[dict[str, Any]] = []
    for split, count in SPLIT_SIZES.items():
        per_stratum = count // len(STRATA)
        for stratum in STRATA:
            for index in range(per_stratum):
                scenario, seed = generate_scenario(split, stratum, index)
                relative = Path("data") / split / f"{scenario['scenario_id']}.json"
                encoded = _canonical_bytes(scenario)
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(encoded)
                entries.append({
                    "split": split,
                    "parent_id": scenario["scenario_id"],
                    "stratum": stratum,
                    "index": index,
                    "seed": seed,
                    "path": relative.as_posix(),
                    "scenario_sha256": _sha256_bytes(encoded),
                })
    if len({entry["parent_id"] for entry in entries}) != sum(SPLIT_SIZES.values()):
        raise AssertionError("parent identifiers are not unique")
    source_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    registry = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": _sha256_bytes(protocol_bytes),
        "generator_sha256": source_digest,
        "scenario_count": len(entries),
        "split_sizes": SPLIT_SIZES,
        "strata": list(STRATA),
        "parents": entries,
    }
    registry_path = output / "input_registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_bytes(_canonical_bytes(registry))
    return registry


def validate_registry(
    output_dir: str | Path,
    *,
    verify_scenarios: bool = True,
    verify_splits: set[str] | None = None,
) -> dict:
    root = Path(output_dir)
    registry = json.loads((root / "input_registry.json").read_text(encoding="utf-8"))
    protocol_bytes = PROTOCOL_PATH.read_bytes()
    protocol = json.loads(protocol_bytes.decode("utf-8"))
    protocol_digest = _sha256_bytes(protocol_bytes)
    generator_digest = _sha256_file(__file__)
    if registry.get("protocol_id") != protocol.get("protocol_id"):
        raise ValueError("registered protocol ID does not match the frozen protocol")
    if registry.get("protocol_sha256") != protocol_digest:
        raise ValueError("registered protocol digest does not match the frozen protocol")
    if registry.get("generator_sha256") != generator_digest:
        raise ValueError("registered generator digest does not match the current generator")
    if registry.get("split_sizes") != SPLIT_SIZES:
        raise ValueError("registered split sizes do not match the preregistered allocation")
    if registry.get("strata") != list(STRATA):
        raise ValueError("registered strata do not match the preregistered allocation")
    if registry.get("scenario_count") != sum(SPLIT_SIZES.values()):
        raise ValueError("registered scenario count mismatch")
    if verify_splits is not None and not verify_splits.issubset(SPLIT_SIZES):
        raise ValueError(f"unknown registered split(s): {sorted(verify_splits - set(SPLIT_SIZES))}")
    verified_splits = set(SPLIT_SIZES) if verify_scenarios and verify_splits is None else (verify_splits or set())
    expected_entries = []
    observed_counts = {split: {stratum: 0 for stratum in STRATA} for split in SPLIT_SIZES}
    for split, count in SPLIT_SIZES.items():
        per_stratum = count // len(STRATA)
        for stratum in STRATA:
            for index in range(per_stratum):
                scenario_id = f"graph-v1-{split}-{stratum}-{index:02d}"
                expected_entries.append({
                    "split": split,
                    "parent_id": scenario_id,
                    "stratum": stratum,
                    "index": index,
                    "seed": _seed(split, stratum, index),
                    "path": f"data/{split}/{scenario_id}.json",
                })
    entries = registry.get("parents")
    if not isinstance(entries, list) or len(entries) != len(expected_entries):
        raise ValueError("registered parent manifest count mismatch")
    seen: set[str] = set()
    for entry, expected in zip(entries, expected_entries):
        if not isinstance(entry, dict) or any(entry.get(key) != value for key, value in expected.items()):
            raise ValueError(f"registered parent manifest mismatch: {expected['parent_id']}")
        if set(entry) != {*expected, "scenario_sha256"}:
            raise ValueError(f"registered parent fields mismatch: {expected['parent_id']}")
        parent_id = expected["parent_id"]
        if parent_id in seen:
            raise ValueError(f"duplicate parent ID: {parent_id}")
        seen.add(parent_id)
        if not isinstance(entry["scenario_sha256"], str) or len(entry["scenario_sha256"]) != 64:
            raise ValueError(f"invalid registered scenario digest: {parent_id}")
        observed_counts[expected["split"]][expected["stratum"]] += 1
        if not verify_scenarios or expected["split"] not in verified_splits:
            continue
        path = root / expected["path"]
        data = path.read_bytes()
        if _sha256_bytes(data) != entry["scenario_sha256"]:
            raise ValueError(f"input hash mismatch: {parent_id}")
        scenario, seed = generate_scenario(expected["split"], expected["stratum"], expected["index"])
        if seed != expected["seed"] or data != _canonical_bytes(scenario):
            raise ValueError(f"registered scenario does not match the frozen generator: {parent_id}")
    return {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_digest,
        "generator_sha256": generator_digest,
        "scenario_count": len(seen),
        "allocation": observed_counts,
        "scenarios_verified": verify_scenarios and verified_splits == set(SPLIT_SIZES),
        "verified_splits": sorted(verified_splits) if verify_scenarios else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=HERE / "registered_data")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(validate_registry(args.output_dir), sort_keys=True))
    else:
        registry = build_registry(args.output_dir)
        print(json.dumps({"scenario_count": registry["scenario_count"], "registry": str(args.output_dir / "input_registry.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
