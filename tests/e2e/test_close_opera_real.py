"""
Reproducible E2E Proof: Real Machine Application Termination
Pattern:
  COMMAND
    ↓
  ACTION
    ↓
  PRE-CONDITION
    ↓
  EXECUTION
    ↓
  POST-CONDITION
    ↓
  VERIFICATION
    ↓
  AUDIT RECORD
"""

import unittest
import os
import subprocess
import psutil
import time
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from services.permission_engine.engine import permission_engine
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestCloseOperaReal")


class TestCloseOperaReal(unittest.TestCase):
    def setUp(self):
        # Spawn a real, lightweight target process for deterministic termination proof
        self.proc = subprocess.Popen(["notepad.exe"])
        self.target_pid = self.proc.pid
        time.sleep(0.5)

    def tearDown(self):
        try:
            if psutil.pid_exists(self.target_pid):
                p = psutil.Process(self.target_pid)
                p.kill()
        except Exception:
            pass

    def test_e2e_close_application_evidence_chain(self):
        """
        Executes real application termination through Canonical Pipeline and records full evidence chain:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        command = f"Close process with PID {self.target_pid}"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "close_app"
        tool_params = {"pid": self.target_pid}
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        self.assertTrue(psutil.pid_exists(self.target_pid), f"Pre-condition failed: PID {self.target_pid} does not exist.")
        p = psutil.Process(self.target_pid)
        logger.info(f"3. [PRE-CONDITION]: Target PID {self.target_pid} verified running ({p.name()}).")

        # 4. EXECUTION
        lease = permission_engine.issue_action_lease(
            tool_name=tool_name,
            parameters=tool_params,
            issued_by="admin_e2e"
        )
        res = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name=tool_name,
                parameters=tool_params,
                source="e2e_test_runner",
                user_role="ADMIN",
                approval_token=lease.lease_id
            )
        )
        logger.info(f"4. [EXECUTION]: Status={res.get('final_status')}, Result={res.get('result')}")

        # Wait briefly for OS process cleanup
        time.sleep(0.5)

        # 5. POST-CONDITION
        self.assertFalse(psutil.pid_exists(self.target_pid), f"Post-condition failed: PID {self.target_pid} still exists in process table.")
        logger.info(f"5. [POST-CONDITION]: Confirmed PID {self.target_pid} completely eliminated from host OS.")

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertEqual(res.get("final_status"), "SUCCESS")
        logger.info(f"6. [VERIFICATION]: Ground-Truth Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        logger.info(f"7. [AUDIT RECORD]: ActionID={res.get('action_id')}, Trace={res.get('traceparent')}")


if __name__ == "__main__":
    unittest.main()
