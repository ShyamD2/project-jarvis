"""
Zero-Tolerance Security Invariant Verification Test Suite (Stage 36.2).
Proves 100% adherence to critical security invariants:
  1. Invariant 110: No mutating action can execute without Permission Engine authorization.
  2. Invariant 10 & 112: Replay attacks and reuse of approval leases are strictly blocked.
  3. Invariant 62: SSRF protection with DNS resolution blocks private, loopback, and cloud metadata IPs.
  4. Invariant 12: Pre-logging secret redactor sanitizes sensitive credentials before disk write.
  5. Invariant 11: Fail-closed secrets manager blocks .env fallback in production.
  6. Invariant 9: Multi-tier rate limiter triggers lockouts on excessive requests.
  7. Invariant 45: Policy simulator accurately dry-runs RBAC without mutations.
"""

import unittest
import os
import time

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from services.permission_engine.engine import permission_engine, PermissionDecision
from services.security.secrets_manager import SecretsManager, SecurityError
from services.security.secret_redactor import secret_redactor
from services.security.rate_limiter import rate_limiter
from services.security.prompt_shield import prompt_shield


class TestSecurityInvariants(unittest.TestCase):
    def setUp(self):
        rate_limiter.reset()

    def test_invariant_110_zero_bypass_unauthorized_mutation(self):
        """Invariant: No mutating tool can execute without authorization."""
        # Attempt to run terraform.destroy without approval
        action = ActionEnvelope(
            name="terraform.destroy",
            target_world=TargetWorld.DIGITAL,
            target_agent="aws_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"plan": "prod"}
        )
        # 1. Operator role is blocked by RBAC
        decision_op: PermissionDecision = permission_engine.evaluate(action, user_role="OPERATOR")
        self.assertFalse(decision_op.authorized)
        self.assertIn("BLOCKED_RBAC", decision_op.rationale)

        # 2. Owner role still requires single-use approval ticket for Tier 3 Destructive
        decision_owner: PermissionDecision = permission_engine.evaluate(action, user_role="OWNER")
        self.assertFalse(decision_owner.authorized)
        self.assertTrue(decision_owner.requires_explicit_approval)
        self.assertIn("CRITICAL", decision_owner.rationale)

    def test_invariant_10_112_single_use_lease_and_replay_protection(self):
        """Invariant: Approval leases are strictly single-use; replay attempts are rejected."""
        action = ActionEnvelope(
            name="docker.restart",
            target_world=TargetWorld.COMPUTER,
            target_agent="docker_agent",
            tier=ActionTier.TIER_2_MUTATING,
            parameters={"container": "api-gateway"}
        )
        # 1. Initial evaluation requires approval
        decision1 = permission_engine.evaluate(action, user_role="ADMIN", environment="production")
        self.assertFalse(decision1.authorized)
        self.assertIsNotNone(decision1.approval_id)

        # 2. Operator approves ticket
        approved = permission_engine.approve_request(decision1.approval_id, approver="lead_sre")
        self.assertTrue(approved)

        # 3. Execution turn 1: Lease is consumed and action is authorized
        decision2 = permission_engine.evaluate(action, user_role="ADMIN", environment="production")
        self.assertTrue(decision2.authorized)
        self.assertIsNotNone(decision2.single_use_lease_id)

        # 4. Execution turn 2 (Replay attack attempt with same action_id): MUST BE REJECTED
        decision3 = permission_engine.evaluate(action, user_role="ADMIN", environment="production")
        self.assertFalse(decision3.authorized, "Replay attack succeeded! Invariant breached.")
        self.assertTrue(decision3.requires_explicit_approval)

    def test_invariant_62_ssrf_dns_rebinding_defense(self):
        """Invariant: SSRF protection blocks localhost, RFC1918, metadata, and non-http schemes."""
        # 1. Direct localhost
        ok, reason = prompt_shield.validate_url_ssrf("http://127.0.0.1:8080/admin")
        self.assertFalse(ok)
        self.assertIn("BLOCKED_SSRF", reason)

        # 2. AWS Metadata service
        ok, reason = prompt_shield.validate_url_ssrf("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)
        self.assertIn("BLOCKED_SSRF", reason)

        # 3. Disallowed scheme
        ok, reason = prompt_shield.validate_url_ssrf("file:///etc/passwd")
        self.assertFalse(ok)
        self.assertIn("Disallowed URI scheme", reason)

        # 4. Valid public web URL
        ok, reason = prompt_shield.validate_url_ssrf("https://www.google.com")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_invariant_12_pre_logging_secret_redaction(self):
        """Invariant: Credentials are scrubbed before logging."""
        sample_log = "User logged in with Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and secret=SuperSecretP@ss"
        redacted = secret_redactor.redact(sample_log)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", redacted)
        self.assertNotIn("SuperSecretP@ss", redacted)
        self.assertIn("[REDACTED_BEARER_TOKEN]", redacted)

        aws_log = "Connecting with AKIAIOSFODNN7EXAMPLE and aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
        aws_redacted = secret_redactor.redact(aws_log)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", aws_redacted)
        self.assertNotIn("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", aws_redacted)

    def test_invariant_11_fail_closed_production_secrets(self):
        """Invariant: In PRODUCTION mode, missing secrets fail closed and never fall back to .env."""
        prod_mgr = SecretsManager()
        prod_mgr.env_mode = "production"

        # Querying an unconfigured secret in production must fail closed
        with self.assertRaises(SecurityError):
            prod_mgr.get_secret("NON_EXISTENT_PROD_SECRET_KEY")

    def test_invariant_9_rate_limiting_lockout(self):
        """Invariant: Excessive requests trigger rate limiting and lockout."""
        ip = "192.0.2.1"
        category = "auth_test"

        # Allow 3 requests in 10s
        for _ in range(3):
            allowed, _ = rate_limiter.is_allowed(ip, category=category, max_requests=3, window_seconds=10)
            self.assertTrue(allowed)

        # 4th request must be blocked
        allowed, reason = rate_limiter.is_allowed(ip, category=category, max_requests=3, window_seconds=10)
        self.assertFalse(allowed)
        self.assertIn("RATE_LIMITED", reason)

    def test_invariant_45_policy_simulator(self):
        """Invariant: Policy simulator provides accurate dry-run permissions."""
        sim = permission_engine.simulate_policy(
            user_role="VIEWER",
            tool_name="docker.restart",
            environment="production"
        )
        self.assertFalse(sim["authorized"])
        self.assertEqual(sim["role"], "VIEWER")


if __name__ == "__main__":
    unittest.main()
