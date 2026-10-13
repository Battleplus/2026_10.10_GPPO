from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ENGINEERING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINEERING))

import n2_linux_runner


class LinuxRunnerIdentityTests(unittest.TestCase):
    def _package(self, root: Path) -> tuple[str, Path]:
        payload = root / "payload.txt"
        payload.write_text("frozen input\n", encoding="utf-8")
        manifest = {
            "identity": "n2-local-synthetic-engineering-linux-acceptance-v1",
            "files": ["payload.txt"],
            "hashing": {"file_sha256": {
                "payload.txt": hashlib.sha256(payload.read_bytes()).hexdigest().upper(),
            }},
        }
        manifest_path = root / n2_linux_runner.MANIFEST_PATH
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return n2_linux_runner._sha256(manifest_path), payload

    def test_manifest_and_exact_file_inventory_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected, _ = self._package(root)
            _, hashes, observed_manifest_hash = n2_linux_runner._load_package(root, expected)
            self.assertEqual(observed_manifest_hash, expected)
            self.assertEqual(set(hashes), {"payload.txt"})

    def test_package_hash_mismatch_and_unlisted_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected, payload = self._package(root)
            with self.assertRaisesRegex(ValueError, "PACKAGE_MANIFEST_SHA256_MISMATCH"):
                n2_linux_runner._load_package(root, "0" * 64)
            (root / "unexpected.txt").write_text("extra\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PACKAGE_INVENTORY_MISMATCH"):
                n2_linux_runner._load_package(root, expected)
            (root / "unexpected.txt").unlink()
            payload.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PACKAGE_FILE_SHA256_MISMATCH"):
                n2_linux_runner._load_package(root, expected)

    def test_runner_refuses_non_linux_before_target_access(self):
        with patch.object(n2_linux_runner.sys, "platform", "win32"):
            with self.assertRaisesRegex(RuntimeError, "N2_LINUX_RUNNER_REQUIRES_LINUX"):
                n2_linux_runner.run(Path("."), Path("work"), Path("python"), 0, "0" * 64, "n2.service")


if __name__ == "__main__":
    unittest.main()
