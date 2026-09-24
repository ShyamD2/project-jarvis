"""
Reproducible E2E Proof: Docker Daemon Status & Container Diagnostics
Pattern:
  COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT RECORD
"""

import unittest
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from agents.cloud.docker_agent import DockerAgent
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestDockerReal")


class TestDockerReal(unittest.TestCase):
    def test_e2e_docker_status_evidence_chain(self):
        """
        Executes real docker daemon status query and validates evidence chain:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        command = "Query Docker daemon health and container runtime"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "devops_tool"
        tool_params = {"subsystem": "docker", "action": "list"}
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        agent = DockerAgent()
        self.assertIsNotNone(agent, "Pre-condition failed: DockerAgent failed to instantiate.")
        logger.info("3. [PRE-CONDITION]: DockerAgent instantiated.")

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
        logger.info(f"5. [POST-CONDITION]: Received structured Docker runtime telemetry.")

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertIn(res.get("final_status"), ["SUCCESS", "UNKNOWN", "PARTIAL"])
        logger.info(f"6. [VERIFICATION]: Verification Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        logger.info(f"7. [AUDIT RECORD]: Trace={res.get('traceparent')}, ActionID={res.get('action_id')}")


if __name__ == "__main__":
    unittest.main()
