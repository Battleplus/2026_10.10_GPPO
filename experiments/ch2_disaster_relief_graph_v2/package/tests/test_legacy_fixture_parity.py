from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from relief_env import ReliefEnv
from evaluator import _evaluate_baseline


LEGACY_SHA256 = {
    "combined__C0": "04f4c01495927a9faab5428bd4a80c1ddb978a6a681fea2894c63242be5611dd",
    "combined__C1": "a0dea0af554f88adcd523c82e11ff4eb019b9c25dba99fa957783a9a08a6692d",
    "control__C0": "f38fd48bd856155c1a0f67f4d940cafe98c7d0d970660a2fcaf3a878d36376ae",
    "control__C1": "6a99021141a87d1813d5ae6e3d6201be57068191e61fd74efc8e2e2f722c85ce",
    "energy_change__C0": "414ddac92404421c8aa869f97b76d56160efb7cf8d71483dc01a7a2ba5111e85",
    "energy_change__C1": "ea891f82062f7b34a17a9b3b7c631c2b9bb58b8271c1ba1fd1a1c8e1bc4eabc3",
    "external_commitment__C0": "8098e43896557ad6109b871ea7c3fc2673dd982721470172e2caed9dd065f2b2",
    "external_commitment__C1": "b8e9657a9a637aa94491e5c7c3d1adfc320e305da09300e10d734fd7d4b65c5d",
    "failure__C0": "0eab6ca0dbf5b8bf9a6e1979576730dc2e5e9844db212ef8df6cf65544f0a6e8",
    "failure__C1": "93ed200af92f3fbc2c165edadedba40c741e1d1697214f0b22d6c9412f5e744c",
    "report_delay__C0": "d51e0515b358b746f1c2d03a362bc920b558eed6659b96be25dd1de3580649eb",
    "report_delay__C1": "5c0cedc3cd3f416ab5df698a7f160ff929d7f90021e39e163a03f0a75383989c",
    "stock_loss__C0": "b8aa8ffc9bc2d849efcf20230dd486556acf58250098c6cf6cac761cd7d23e1b",
    "stock_loss__C1": "9d12d9dafb962f871c29181b20d5040edd05265d0c02d5ad279305db8ae17d04",
}


def _fingerprint(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


class LegacyFixtureParityTests(unittest.TestCase):
    def test_all_seven_fixture_runs_match_pre_migration_hashes(self):
        observed = {}
        for fixture_path in sorted((ROOT / "fixtures").glob("*.json")):
            scenario = json.loads(fixture_path.read_text(encoding="utf-8"))
            for policy in ("C0", "C1"):
                key = f"{fixture_path.stem}__{policy}"
                legacy_result = ReliefEnv(scenario).run(policy)
                step_result, timings = _evaluate_baseline(scenario, policy)
                self.assertEqual(step_result, legacy_result, key)
                self.assertEqual(timings["decisions"], int(scenario["horizon"]), key)
                observed[key] = _fingerprint(step_result)
        self.assertEqual(observed, LEGACY_SHA256)


if __name__ == "__main__":
    unittest.main()
