from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ENGINEERING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINEERING))

import n2_linux_runner


class RuntimeAdmissionContractTests(unittest.TestCase):
    def _report(self, checks: list[dict[str, object]]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        output = Path(directory.name) / "runtime.stdout.log"
        output.write_text(json.dumps({"schema": "n2-runtime-admission-checks/1", "checks": checks}),
                          encoding="utf-8")
        return output

    def test_runtime_probe_has_structured_identity_and_post_pin_checks(self):
        command = n2_linux_runner._runtime_probe(Path("python"), 0, "ru-server-MS-1", "user1")
        source = command[-1]
        self.assertNotIn("assert ", source)
        for key in ("host", "user", "python_version", "torch_version", "numpy_version",
                    "python_executable", "cpu_affinity_after_runner_pin"):
            self.assertIn(f'"name": "{key}"', source)
        self.assertIn("runner-called-sched_setaffinity-before-stage", source)
        self.assertIn("pwd.getpwuid(os.geteuid()).pw_name", source)
        self.assertNotIn("getpass.getuser", source)

    def test_structured_check_report_passes_only_when_actuals_match(self):
        passing_checks = [{"name": name, "actual": name, "expected": name, "passed": True}
                          for name in n2_linux_runner.RUNTIME_CHECK_NAMES]
        passing = self._report(passing_checks)
        checks, error = n2_linux_runner._runtime_checks(passing)
        self.assertIsNone(error)
        self.assertEqual(len(checks), len(n2_linux_runner.RUNTIME_CHECK_NAMES))

        incomplete = self._report(passing_checks[:-1])
        _, error = n2_linux_runner._runtime_checks(incomplete)
        self.assertEqual(error, "RUNTIME_CHECK_REPORT_NAMES_MISMATCH")

        failing_checks = [{"name": name, "actual": name, "expected": name, "passed": True}
                          for name in n2_linux_runner.RUNTIME_CHECK_NAMES]
        failing_checks[1] = {"name": "user", "actual": "other", "expected": "user1", "passed": False}
        failing = self._report(failing_checks)
        checks, error = n2_linux_runner._runtime_checks(failing)
        self.assertEqual(error, "RUNTIME_CHECK_FAILED")
        self.assertEqual(checks[1]["actual"], "other")

    def test_ssh_affinity_is_a_required_observation_and_not_the_runner_gate(self):
        self.assertEqual(n2_linux_runner._parse_cpu_list("3,0,1,1"), [0, 1, 3])
        with self.assertRaises(argparse.ArgumentTypeError):
            n2_linux_runner._parse_cpu_list("-1,0")


if __name__ == "__main__":
    unittest.main()
