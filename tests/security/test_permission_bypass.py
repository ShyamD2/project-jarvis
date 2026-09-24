"""
Security Regression Test: Zero Permission Engine Bypass
Guarantees permanent remediation for direct mutation endpoints and approval bypasses.
"""

import unittest
import asyncio
from services.permission_engine.engine import permission_engine, PermissionDecision
from services.brain.canonical_pipeline import canonical_pipeline
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld


class TestPermissionBypass(unittest.TestCase):
    def test_direct_destructive_action_blocked_without_lease(self):
        """Invariant: TIER_3_DESTRUCTIVE actions cannot execute without cryptographic approval lease."""
        action = ActionEnvelope(
            name="terraform.destroy",
            target_world=TargetWorld.DIGITAL,
            target_agent="aws_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"target": "production"}
        )
        decision: PermissionDecision = permission_engine.evaluate(action, user_role="OPERATOR")
        self.assertFalse(decision.authorized)
        self.assertTrue(decision.requires_explicit_approval or "BLOCKED" in decision.rationale)

    def test_universal_action_lease_issuance_and_consumption(self):
        """Invariant: Universal Action Leases are strictly single-use and bound to tool/parameters."""
        # 1. Issue lease for docker.restart
        lease = permission_engine.issue_action_lease(
            tool_name="docker.restart",
            parameters={"container": "gateway"},
            ttl_seconds=300.0,
            issued_by="security_admin"
        )
        self.assertIsNotNone(lease.lease_id)
        self.assertFalse(lease.consumed)

        action = ActionEnvelope(
            name="docker.restart",
            target_world=TargetWorld.COMPUTER,
            target_agent="docker_agent",
            tier=ActionTier.TIER_2_MUTATING,
            parameters={"container": "gateway"}
        )

        # 2. Evaluation with lease succeeds
        decision1 = permission_engine.evaluate(
            action=action,
            approval_token=lease.lease_id,
            user_role="ADMIN"
        )
        self.assertTrue(decision1.authorized)
        self.assertEqual(decision1.single_use_lease_id, lease.lease_id)

        # 3. Second attempt with same lease must be REJECTED (Replay Protection)
        decision2 = permission_engine.evaluate(
            action=action,
            approval_token=lease.lease_id,
            user_role="ADMIN"
        )
        self.assertFalse(decision2.authorized)
        self.assertIn("REPLAY", decision2.rationale)

    def test_lease_parameter_tampering_rejected(self):
        """Invariant: An action lease cannot be used for parameters other than those leased."""
        lease = permission_engine.issue_action_lease(
            tool_name="file_manager",
            parameters={"action": "delete", "path": "test.txt"},
            ttl_seconds=300.0
        )

        # Attacker attempts to use lease to delete system file instead
        tampered_action = ActionEnvelope(
            name="file_manager",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_2_MUTATING,
            parameters={"action": "delete", "path": "critical_database.db"}
        )

        decision = permission_engine.evaluate(
            action=tampered_action,
            approval_token=lease.lease_id,
            user_role="ADMIN"
        )
        self.assertFalse(decision.authorized)
        self.assertIn("MISMATCH", decision.rationale)


if __name__ == "__main__":
    unittest.main()
