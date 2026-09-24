"""
Reproducible E2E Proof: Real Browser Automation & Navigation
Pattern:
  COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT RECORD
"""

import unittest
import asyncio
from services.brain.canonical_pipeline import canonical_pipeline
from services.security.prompt_shield import prompt_shield
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("TestBrowserReal")


class TestBrowserReal(unittest.TestCase):
    def test_e2e_browser_navigation_evidence_chain(self):
        """
        Executes real browser navigation action and records full evidence chain:
        COMMAND -> ACTION -> PRE-CONDITION -> EXECUTION -> POST-CONDITION -> VERIFICATION -> AUDIT
        """
        # 1. COMMAND
        target_url = "https://www.google.com"
        command = f"Open {target_url} in browser"
        logger.info(f"1. [COMMAND]: '{command}'")

        # 2. ACTION
        tool_name = "browse_web"
        tool_params = {"url": target_url}
        logger.info(f"2. [ACTION]: {tool_name} with params={tool_params}")

        # 3. PRE-CONDITION
        is_safe_url, reason = prompt_shield.validate_url_ssrf(target_url)
        self.assertTrue(is_safe_url, f"Pre-condition failed: URL failed safety check: {reason}")
        logger.info(f"3. [PRE-CONDITION]: Target URL verified safe against SSRF.")

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
        self.assertTrue(res.get("success"), "Post-condition failed: Browser launch did not return success.")
        logger.info(f"5. [POST-CONDITION]: Browser successfully directed to target URL.")

        # 6. VERIFICATION
        verification = res.get("verification", {})
        self.assertEqual(res.get("final_status"), "SUCCESS")
        self.assertIn(str(verification.get("status")).lower(), ["verified", "verificationstatus.verified"])
        logger.info(f"6. [VERIFICATION]: Verification Status={verification.get('status')}")

        # 7. AUDIT RECORD
        self.assertIsNotNone(res.get("action_id"))
        self.assertIsNotNone(res.get("traceparent"))
        logger.info(f"7. [AUDIT RECORD]: Trace={res.get('traceparent')}, ActionID={res.get('action_id')}")


if __name__ == "__main__":
    unittest.main()
