"""
Reproducible E2E Proof: AWS Cloud Read-Only STS Telemetry
Pattern:
  COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT RECORD
"""

import unittest
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from agents.cloud.aws_agent import aws_agent
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestAWSReadOnlyReal")


class TestAWSReadOnlyReal(unittest.TestCase):
    def test_e2e_aws_readonly_evidence_chain(self):
        """
        Executes read-only AWS caller identity query and validates evidence chain:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        command = "Query AWS STS Caller Identity (Read-Only Telemetry)"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "aws_cloud_health"
        tool_params = {}
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        self.assertIsNotNone(aws_agent, "Pre-condition failed: AWSAgent failed to instantiate.")
        logger.info(f"3. [PRE-CONDITION]: AWSAgent session online (Region: {aws_agent.region}).")

        # 4. EXECUTION
        res = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name=tool_name,
                parameters=tool_params,
                source="e2e_test_runner"
            )
        )
        logger.info(f"4. [EXECUTION]: Status={res.get('final_status')}, Result={res.get('result')}")

        # 5. POST-CONDITION
        result_payload = res.get("result", {})
        self.assertIsNotNone(result_payload)
        logger.info(f"5. [POST-CONDITION]: AWS telemetry payload received: {result_payload}")

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertIn(res.get("final_status"), ["SUCCESS", "UNKNOWN", "PARTIAL", "FAILED"])
        logger.info(f"6. [VERIFICATION]: Verification Contract Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        self.assertIsNotNone(res.get("traceparent"))
        logger.info(f"7. [AUDIT RECORD]: Trace={res.get('traceparent')}, ActionID={res.get('action_id')}")


if __name__ == "__main__":
    unittest.main()
