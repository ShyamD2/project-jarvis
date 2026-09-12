"""
Integration tests for J.A.R.V.I.S. Cloud Suite & Autonomous Remediation.
Tests Terraform runner, Git agent, SOC security audit, and Self-Healing remediation.
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from terraform_runner import terraform_agent
from git_agent import git_agent
from soc_security_agent import soc_agent
from remediation_agent import remediation_agent


class TestCloudSuite(unittest.IsolatedAsyncioTestCase):
    def test_terraform_validation(self):
        result = terraform_agent.validate()
        self.assertTrue(result["success"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["error_count"], 0)

    def test_git_agent(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        status = git_agent.get_status()
        self.assertTrue(status["success"])
        self.assertIn("changed_files_count", status)

    def test_soc_security_audit(self):
        tf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../infrastructure/terraform"))
        audit = soc_agent.scan_terraform_iam_policies(tf_dir)
        self.assertTrue(audit["success"])
        self.assertGreater(audit["scanned_files_count"], 0)
        self.assertTrue(audit["clean"]) # Our Phase 1 least-privilege IAM policy has NO wildcards!

    async def test_autonomous_remediation_self_healing(self):
        incident = await remediation_agent.handle_incident(
            incident_type="container_crashed",
            details={"container": "jarvis-localstack"}
        )
        self.assertTrue(incident["success"])
        self.assertTrue(incident["verified"])
        self.assertEqual(incident["remediation_action"], "restart_container")


if __name__ == "__main__":
    unittest.main()
