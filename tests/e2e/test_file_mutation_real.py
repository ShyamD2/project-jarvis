"""
Reproducible E2E Proof: Real Filesystem Mutation & Ground-Truth Inode Verification
Pattern:
  COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT RECORD
"""

import unittest
import os
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestFileMutationReal")


class TestFileMutationReal(unittest.TestCase):
    def setUp(self):
        self.test_file_path = os.path.abspath(os.path.join(os.getcwd(), "e2e_mutation_proof.txt"))
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def tearDown(self):
        if os.path.exists(self.test_file_path):
            try:
                os.remove(self.test_file_path)
            except Exception:
                pass

    def test_e2e_file_mutation_evidence_chain(self):
        """
        Executes real filesystem mutation and validates ground-truth disk state:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        test_payload = "REAL_GROUND_TRUTH_E2E_PAYLOAD_VERIFIED_BY_JARVIS"
        command = f"Write payload to {self.test_file_path}"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "file_manager"
        tool_params = {
            "action": "create_file",
            "path": self.test_file_path,
            "content": test_payload
        }
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        self.assertFalse(os.path.exists(self.test_file_path), "Pre-condition failed: File must not exist prior to write.")
        logger.info(f"3. [PRE-CONDITION]: Target path verified absent from physical storage.")

        # 4. EXECUTION
        res = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name=tool_name,
                parameters=tool_params,
                source="e2e_test_runner",
                user_role="ADMIN"
            )
        )
        logger.info(f"4. [EXECUTION]: Status={res.get('final_status')}, Result={res.get('result')}")

        # 5. POST-CONDITION (OS Ground-Truth)
        self.assertTrue(os.path.exists(self.test_file_path), "Post-condition failed: File was not created on physical disk.")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertEqual(disk_content, test_payload, "Post-condition failed: Disk content does not match write payload.")
        logger.info(f"5. [POST-CONDITION]: Physical disk read-back confirmed ({len(disk_content)} bytes).")

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertEqual(res.get("final_status"), "SUCCESS")
        self.assertIn(str(verification.get("status")).lower(), ["verified", "verificationstatus.verified"])
        logger.info(f"6. [VERIFICATION]: Verification Engine Contract Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        self.assertIsNotNone(res.get("traceparent"))
        logger.info(f"7. [AUDIT RECORD]: Trace={res.get('traceparent')}, ActionID={res.get('action_id')}")


if __name__ == "__main__":
    unittest.main()
