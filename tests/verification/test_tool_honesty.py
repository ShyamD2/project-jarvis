"""
Tool Honesty and False-Success Invariant Tests (Phase 36 Stage 36.5).
Verifies:
  1. Process launch with fake/non-existent PID is caught and failed.
  2. File write where file does not exist on disk is caught and failed.
  3. Container run where container is dead/non-existent is caught and failed.
  4. Logical tool success is rejected when ground-truth sensory verification fails.
"""

import unittest
from unittest.mock import patch, MagicMock
from services.verification.verification_engine import verification_engine
from shared.schemas.verification_contract import VerificationStatus


class TestToolHonesty(unittest.TestCase):
    def test_process_launch_fake_pid_rejected(self):
        """Tool returns success=True with fake non-existent PID; verification engine must reject as FAILED."""
        fake_pid = 99999999  # Guaranteed non-existent PID
        tool_result = {"success": True, "pid": fake_pid, "message": "App launched successfully"}
        params = {"app": "notepad.exe"}

        res = verification_engine.verify_action_execution("launch_app", params, tool_result)
        self.assertEqual(res.status, VerificationStatus.FAILED)
        self.assertFalse(res.match)
        self.assertIn("does not exist in host process table", res.failure_reason)

    def test_file_write_missing_file_rejected(self):
        """Tool claims file written, but file does not exist on disk; verification engine must reject."""
        missing_file = "C:\\non_existent_folder_xyz_123\\missing_test_file.txt"
        tool_result = {"success": True, "path": missing_file, "bytes_written": 1024}
        params = {"action": "write_file", "path": missing_file}

        res = verification_engine.verify_action_execution("file_manager", params, tool_result)
        self.assertEqual(res.status, VerificationStatus.FAILED)
        self.assertFalse(res.match)
        self.assertIn("was not found on disk", res.failure_reason)

    def test_docker_container_dead_rejected(self):
        """Tool claims container started, but container inspection fails; verification engine must reject."""
        tool_result = {"success": True, "container_id": "c_fake_dead_container_123"}
        params = {"action": "run", "container_id": "c_fake_dead_container_123"}

        res = verification_engine.verify_action_execution("docker", params, tool_result)
        self.assertEqual(res.status, VerificationStatus.FAILED)
        self.assertFalse(res.match)

    def test_zero_trust_contract_population(self):
        """Verifies that all contract fields (observed_state, expected_state, evidence, match) are strictly populated."""
        tool_result = {"success": True, "status": "online"}
        params = {"query_type": "battery"}

        res = verification_engine.verify_action_execution("query_system_telemetry", params, tool_result)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.match)
        self.assertIn("sensory_ok", res.observed_state)
        self.assertIn("action", res.expected_state)
        self.assertIn("tool_result", res.evidence)
        self.assertEqual(res.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
