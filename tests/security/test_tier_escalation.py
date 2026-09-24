"""
Security Regression Test: Anti-Tier Escalation and Blast Radius Enforcement
Guarantees permanent remediation for privilege escalation and caller-spoofed safety tiers.
"""

import unittest
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from services.permission_engine.engine import permission_engine, PermissionDecision
from services.brain.tools.registry import registry as tool_registry


class TestTierEscalationSecurity(unittest.TestCase):
    def test_client_spoofed_tier_reclassified_dynamically(self):
        """Invariant: Caller cannot claim Tier 0 Reflex for a Tier 3 Destructive action."""
        # Client maliciously claims terraform.destroy is harmless TIER_0_REFLEX
        spoofed_action = ActionEnvelope(
            name="terraform.destroy",
            target_world=TargetWorld.DIGITAL,
            target_agent="aws_agent",
            tier=ActionTier.TIER_0_REFLEX,  # Tampered tier claim
            parameters={"plan": "prod"}
        )

        decision: PermissionDecision = permission_engine.evaluate(
            action=spoofed_action,
            user_role="OPERATOR"
        )

        # Permission engine must dynamically evaluate the true risk and reject authorization
        self.assertFalse(decision.authorized, "Spoofed Tier 0 claim bypassed permission engine!")
        self.assertIn(decision.tier, [ActionTier.TIER_2_MUTATING, ActionTier.TIER_3_DESTRUCTIVE])
        self.assertIn("BLOCKED", decision.rationale)

    def test_viewer_role_cannot_execute_mutations(self):
        """Invariant: VIEWER role cannot execute mutating operations regardless of caller claimed tier."""
        action = ActionEnvelope(
            name="computer.volume",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_1_SOFT,
            parameters={"action": "set_volume", "level": 100}
        )

        decision = permission_engine.evaluate(
            action=action,
            user_role="VIEWER"
        )
        self.assertFalse(decision.authorized)
        self.assertIn("BLOCKED_RBAC", decision.rationale)


if __name__ == "__main__":
    unittest.main()
