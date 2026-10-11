from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dataset_protocol import STRATA, build_registry, generate_scenario, validate_registry
from scenario_schema import validate_scenario


class DatasetProtocolTests(unittest.TestCase):
    def test_generation_is_deterministic_and_valid(self) -> None:
        for split, stratum, index in (
            ("train", "control", 0),
            ("development", "combined", 1),
            ("heldout", "external_commitment", 7),
        ):
            first, first_seed = generate_scenario(split, stratum, index)
            second, second_seed = generate_scenario(split, stratum, index)
            self.assertEqual(first_seed, second_seed)
            self.assertEqual(first, second)
            validate_scenario(first)

    def test_registry_has_disjoint_parent_ids_exact_counts_and_valid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = build_registry(root)
            summary = validate_registry(root)
            self.assertEqual(registry["scenario_count"], 126)
            self.assertEqual(summary["scenario_count"], 126)
            self.assertEqual(len({row["parent_id"] for row in registry["parents"]}), 126)
            self.assertEqual(
                {split: sum(row["split"] == split for row in registry["parents"]) for split in ("train", "development", "heldout")},
                {"train": 56, "development": 14, "heldout": 56},
            )
            for split, per_stratum in (("train", 8), ("development", 2), ("heldout", 8)):
                self.assertEqual(set(summary["allocation"][split]), set(STRATA))
                self.assertEqual(set(summary["allocation"][split].values()), {per_stratum})
            for row in registry["parents"]:
                scenario = json.loads((root / row["path"]).read_text(encoding="utf-8"))
                validate_scenario(scenario)
                self.assertEqual(scenario["scenario_id"], row["parent_id"])

    def test_heldout_generation_has_no_training_seed_or_outcome_dependency(self) -> None:
        scenario, seed = generate_scenario("heldout", "stock_loss", 0)
        self.assertEqual(seed, generate_scenario("heldout", "stock_loss", 0)[1])
        self.assertEqual(scenario["scenario_id"], "graph-v1-heldout-stock_loss-00")
        self.assertEqual([item["kind"] for item in scenario["disturbances"]], ["stock_loss"])

    def test_registry_binds_protocol_generator_and_exact_manifest(self) -> None:
        for field, replacement in (
            ("protocol_sha256", "0" * 64),
            ("generator_sha256", "0" * 64),
            ("split_sizes", {"train": 55, "development": 14, "heldout": 57}),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                registry = build_registry(root)
                registry[field] = replacement
                (root / "input_registry.json").write_text(
                    json.dumps(registry, ensure_ascii=False, sort_keys=True), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    validate_registry(root)

    def test_self_consistent_scenario_hash_cannot_replace_generator_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = build_registry(root)
            entry = registry["parents"][0]
            scenario_path = root / entry["path"]
            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            scenario["tasks"][0]["priority"] = 5 if scenario["tasks"][0]["priority"] != 5 else 4
            encoded = (json.dumps(scenario, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            scenario_path.write_bytes(encoded)
            entry["scenario_sha256"] = hashlib.sha256(encoded).hexdigest()
            (root / "input_registry.json").write_text(
                json.dumps(registry, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "frozen generator"):
                validate_registry(root)

    def test_manifest_only_validation_does_not_open_heldout_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = build_registry(root)
            heldout = next(row for row in registry["parents"] if row["split"] == "heldout")
            (root / heldout["path"]).unlink()

            summary = validate_registry(root, verify_scenarios=False)
            self.assertFalse(summary["scenarios_verified"])
            with self.assertRaises(FileNotFoundError):
                validate_registry(root)

    def test_split_loading_verifies_only_requested_split(self) -> None:
        from ppo_trainer import load_registered_scenarios

        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            data_root = package / "registered_data"
            registry = build_registry(data_root)
            heldout = next(row for row in registry["parents"] if row["split"] == "heldout")
            (data_root / heldout["path"]).unlink()

            train, _ = load_registered_scenarios(package, "train")
            development, _ = load_registered_scenarios(package, "development")
            self.assertEqual(len(train), 56)
            self.assertEqual(len(development), 14)
            with self.assertRaises(PermissionError):
                load_registered_scenarios(package, "heldout")
            with self.assertRaises(FileNotFoundError):
                load_registered_scenarios(package, "heldout", allow_heldout=True)


if __name__ == "__main__":
    unittest.main()
