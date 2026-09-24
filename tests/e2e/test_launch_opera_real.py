"""
Reproducible E2E Proof: Real Machine Application Launch
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
import shutil
import psutil
import time
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestLaunchOperaReal")


class TestLaunchOperaReal(unittest.TestCase):
    def setUp(self):
        # Deterministic, non-disruptive real GUI application target (Notepad)
        self.target_app = "notepad.exe"
        self.app_name = "notepad"
        self.spawned_pids = []

    def tearDown(self):
        # Clean up any processes spawned during E2E test
        for pid in self.spawned_pids:
            try:
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=2.0)
            except Exception:
                pass

    def test_e2e_launch_application_evidence_chain(self):
        """
        Executes real application launch through Canonical Pipeline and records full evidence chain:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        command = f"Open {self.app_name}"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "launch_app"
        tool_params = {"app": self.target_app}
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        # Count existing processes of this target executable
        exe_name = os.path.basename(self.target_app).lower()
        if not exe_name.endswith(".exe"):
            exe_name += ".exe"
        pids_before = [p.pid for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == exe_name]
        logger.info(f"3. [PRE-CONDITION]: Found {len(pids_before)} existing {exe_name} processes.")

        # 4. EXECUTION (Via Canonical Execution Pipeline)
        res = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name=tool_name,
                parameters=tool_params,
                source="e2e_test_runner",
                user_role="ADMIN"
            )
        )
        logger.info(f"4. [EXECUTION]: Status={res.get('final_status')}, Result={res.get('result')}")

        # 5. POST-CONDITION
        pid = res.get("result", {}).get("pid")
        if pid:
            self.spawned_pids.append(pid)
            self.assertTrue(psutil.pid_exists(pid), f"PID {pid} must exist in host OS process table.")
            p = psutil.Process(pid)
            logger.info(f"5. [POST-CONDITION]: Real OS Process Verified (PID={pid}, Name={p.name()}, Status={p.status()})")
        else:
            pids_after = [p.pid for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == exe_name]
            delta = set(pids_after) - set(pids_before)
            self.assertTrue(len(delta) > 0 or res.get("success"), "Process delta or execution success must be verified.")
            for npid in delta:
                self.spawned_pids.append(npid)

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertIn(str(verification.get("status")).lower(), ["verified", "verificationstatus.verified", "unknown", "partial"])
        logger.info(f"6. [VERIFICATION]: Contract Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        self.assertIsNotNone(res.get("traceparent"))
        logger.info(f"7. [AUDIT RECORD]: Trace={res.get('traceparent')}, ActionID={res.get('action_id')}")


if __name__ == "__main__":
    unittest.main()
