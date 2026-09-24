"""
Reality Discrepancy & Ground-Truth Verification Tests (Phase 36 Stage 36.5).
Proves the invariant: When a tool claims success (logical success=True) but the physical/OS
world contradicts it (process exited, file vanished, container died), J.A.R.V.I.S.
Verification Engine and Canonical Pipeline reject false-success and mark the mission FAILED.
"""

import unittest
import os
import tempfile
import asyncio
from unittest.mock import patch, MagicMock
import psutil

from services.verification.verification_engine import verification_engine
from shared.schemas.verification_contract import VerificationStatus, VerificationResult
from services.brain.canonical_pipeline import canonical_pipeline


class TestRealityDiscrepancy(unittest.TestCase):
    def test_process_immediate_crash_rejected(self):
        """
        Tool returns success=True with a PID, but the process crashed/exited immediately.
        Verification Engine must reject with FAILED status and record discrepancy.
        """
        # Pick a PID that does not exist in host process table
        non_existent_pid = 999999
        while psutil.pid_exists(non_existent_pid):
            non_existent_pid += 1

        tool_result = {
            "success": True,
            "status": "running",
            "pid": non_existent_pid,
            "channel_1_logical": True
        }
        params = {"app": "notepad.exe"}

        verif: VerificationResult = verification_engine.verify_action_execution(
            "launch_app", params, tool_result
        )
        self.assertEqual(verif.status, VerificationStatus.FAILED)
        self.assertFalse(verif.match)
        self.assertIn("does not exist in host process table", verif.failure_reason)

    def test_file_ghost_write_rejected(self):
        """
        Tool claims file was created and written to disk, but the file does not exist.
        Verification Engine must reject with FAILED status and record discrepancy.
        """
        phantom_path = os.path.join(tempfile.gettempdir(), "phantom_jarvis_file_never_written.txt")
        if os.path.exists(phantom_path):
            os.remove(phantom_path)

        tool_result = {
            "success": True,
            "path": phantom_path,
            "bytes_written": 2048
        }
        params = {"action": "create_file", "path": phantom_path}

        verif: VerificationResult = verification_engine.verify_action_execution(
            "file_manager", params, tool_result
        )
        self.assertEqual(verif.status, VerificationStatus.FAILED)
        self.assertFalse(verif.match)
        self.assertIn("was not found on disk", verif.failure_reason)

    def test_container_silent_death_rejected(self):
        """
        Tool claims docker container is running, but docker inspection reports exited/dead.
        Verification Engine must reject with FAILED status.
        """
        tool_result = {
            "success": True,
            "container_id": "c_dead_container_deadbeef",
            "status": "started"
        }
        params = {"action": "run", "container_id": "c_dead_container_deadbeef"}

        verif: VerificationResult = verification_engine.verify_action_execution(
            "docker", params, tool_result
        )
        self.assertEqual(verif.status, VerificationStatus.FAILED)
        self.assertFalse(verif.match)

    def test_canonical_pipeline_false_success_settlement(self):
        """
        When tool execution returns success=True but verification engine fails it,
        CanonicalPipeline must classify final_status as 'FAILED', preserving 0% false-success invariant.
        """
        non_existent_pid = 999998
        while psutil.pid_exists(non_existent_pid):
            non_existent_pid += 1

        mock_tool_result = {
            "success": True,
            "pid": non_existent_pid,
            "message": "Tool thinks it succeeded"
        }

        with patch("services.brain.canonical_pipeline.tool_registry.execute_tool") as mock_exec:
            mock_exec.return_value = {
                "success": True,
                "status": "success",
                "result": mock_tool_result
            }

            res = asyncio.run(
                canonical_pipeline.execute_request(
                    tool_name="launch_app",
                    parameters={"app": "phantom_app.exe"},
                    source="reality_discrepancy_test",
                    user_role="ADMIN"
                )
            )

            # Assert Pipeline caught the lie and rejected false success
            self.assertEqual(res.get("final_status"), "FAILED")
            self.assertEqual(res.get("verification", {}).get("status"), VerificationStatus.FAILED.value)
            self.assertFalse(res.get("verification", {}).get("match"))


if __name__ == "__main__":
    unittest.main()
