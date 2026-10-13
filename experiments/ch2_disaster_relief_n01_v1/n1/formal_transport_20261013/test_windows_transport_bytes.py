from __future__ import annotations

import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import formal_transport_envelope as transport
import test_formal_transport_envelope as envelope_tests


@unittest.skipUnless(os.name == "nt", "verifies Windows subprocess stdin semantics")
class WindowsTransportBytes(unittest.TestCase):
    def test_windows_ssh_stdin_is_lf_bytes_accepted_by_real_bash(self) -> None:
        # The envelope fixture invokes the exact captured bytes through real
        # ``wsl.exe ... bash -s`` and supplies fake system services in WSL.
        fixture = envelope_tests.TransportEnvelopeAcceptance(
            "test_actual_ssh_stdin_is_exported_and_runs_one_start"
        )
        fixture.setUp()
        try:
            code, state = fixture.invoke()
            self.assertEqual(code, 0, getattr(fixture, "last_stderr", b"").decode(errors="replace"))
            self.assertEqual(state["starts"], 1)
            payload = fixture.capture.read_bytes()
            self.assertNotIn(b"\r", payload)
            self.assertIn(b"approval_bound=yes", getattr(fixture, "last_stdout", b""))
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
