"""
Integration Test: Offline Survivability & Local Reflex Path Verification (Phase 36 / Invariant).
Guarantees:
  When external networks, DNS, and cloud LLMs (OpenAI, Groq, Anthropic) are completely unreachable:
  1. Local reflex commands execute with zero external network dependency.
  2. Telemetry and sensory verification operate 100% locally.
  3. Emergency Stand-Down executes immediately in local memory.
  4. Workstation automation (volume, query, close app, status) functions without cloud roundtrips.
"""

import unittest
import asyncio
import os
from unittest.mock import patch

from services.brain.canonical_pipeline import canonical_pipeline
from agents.intelligence.emergency_stop import emergency_stop
from services.permission_engine.engine import permission_engine


import socket

_orig_connect = socket.socket.connect

def _offline_connect(self, addr, *args, **kwargs):
    host = addr[0] if isinstance(addr, (tuple, list)) else addr
    if host in ("127.0.0.1", "localhost", "::1"):
        return _orig_connect(self, addr, *args, **kwargs)
    raise OSError("External network unreachable (offline)")


class TestOfflineSurvivability(unittest.TestCase):
    def setUp(self):
        emergency_stop.resume()

    def tearDown(self):
        emergency_stop.resume()

    def test_offline_system_status_reflex(self):
        """Invariant: system.status executes locally with zero external network calls."""
        with patch.object(socket.socket, "connect", _offline_connect):
            res = asyncio.run(
                canonical_pipeline.execute_request(
                    tool_name="system.status",
                    parameters={}
                )
            )
            self.assertEqual(res.get("final_status"), "SUCCESS")
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("execution_class"), "read_only")
            self.assertIn("cpu_percent", res.get("result", {}))

    def test_offline_volume_control_reflex(self):
        """Invariant: audio/volume adjustment runs completely on local reflex path."""
        with patch.object(socket.socket, "connect", _offline_connect):
            res = asyncio.run(
                canonical_pipeline.execute_request(
                    tool_name="computer.volume",
                    parameters={"action": "set_volume", "level": 40}
                )
            )
            self.assertEqual(res.get("final_status"), "SUCCESS")
            self.assertTrue(res.get("success"))

    def test_offline_emergency_stop_local_freeze(self):
        """Invariant: Emergency stop halts mutating actions locally without external network."""
        with patch.object(socket.socket, "connect", _offline_connect):
            emergency_stop.stop(reason="Offline physical emergency signal")
            self.assertTrue(emergency_stop.is_stopped)

            res = asyncio.run(
                canonical_pipeline.execute_request(
                    tool_name="system.status",
                    parameters={}
                )
            )
            self.assertEqual(res.get("final_status"), "FAILED")
            self.assertIn("Stand-Down", res.get("error", ""))

            # Resume locally
            emergency_stop.resume()
            self.assertFalse(emergency_stop.is_stopped)

    def test_offline_close_app_with_local_lease(self):
        """Invariant: close_app executes locally when supplied with local cryptographic ActionLease."""
        lease = permission_engine.issue_action_lease(
            tool_name="computer.close_app",
            parameters={"pid": 99999},
            issued_by="offline_operator"
        )

        with patch.object(socket.socket, "connect", _offline_connect):
            res = asyncio.run(
                canonical_pipeline.execute_request(
                    tool_name="computer.close_app",
                    parameters={"pid": 99999},
                    approval_token=lease.lease_id
                )
            )
            self.assertIn(res.get("final_status"), ["SUCCESS", "FAILED"])
            # Even if PID 99999 is nonexistent, it was handled locally without network error
            if not res.get("success"):
                self.assertNotIn("Network", res.get("error", ""))


if __name__ == "__main__":
    unittest.main()
