"""
Integration tests for J.A.R.V.I.S. Security & Permission Engine.
Tests risk classification, agent boundary enforcement, Tier 3 approval challenges, and audit.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from engine import PermissionEngine
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.sdk_python.jarvis_sdk.config import config


class TestJarvisPermissionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PermissionEngine()
        config.emergency_stand_down = False

    def test_agent_boundary_enforcement(self):
        # ESP32 agent attempting to delete an AWS database -> blocked!
        illegal_action = ActionEnvelope(
            name="delete_database",
            target_world=TargetWorld.DIGITAL,
            target_agent="esp32_agent",
            tier=ActionTier.TIER_1_SOFT
        )
        decision = self.engine.evaluate(illegal_action)
        self.assertFalse(decision.authorized)
        self.assertIn("not authorized to operate in world 'digital'", decision.rationale)

    def test_dynamic_tier3_classification_and_approval(self):
        # Action declared as Tier 1, but command contains destructive pattern 'terraform destroy'
        tricky_action = ActionEnvelope(
            name="terraform destroy",
            target_world=TargetWorld.DIGITAL,
            target_agent="terraform_agent",
            tier=ActionTier.TIER_1_SOFT
        )
        # Without token -> blocked
        decision = self.engine.evaluate(tricky_action)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.tier, ActionTier.TIER_3_DESTRUCTIVE)
        self.assertTrue(decision.requires_explicit_approval)

        # With valid master token -> authorized
        decision_approved = self.engine.evaluate(tricky_action, approval_token=config.master_secret)
        self.assertTrue(decision_approved.authorized)

    def test_emergency_stand_down_blocks_all(self):
        config.emergency_stand_down = True
        safe_action = ActionEnvelope(
            name="check_temperature",
            target_world=TargetWorld.PHYSICAL,
            target_agent="esp32_agent",
            tier=ActionTier.TIER_0_REFLEX
        )
        decision = self.engine.evaluate(safe_action)
        self.assertFalse(decision.authorized)
        self.assertIn("Emergency Stand-Down", decision.rationale)

    def test_audit_log(self):
        action = ActionEnvelope(
            name="turn_on_light",
            target_world=TargetWorld.PHYSICAL,
            target_agent="esp32_agent",
            tier=ActionTier.TIER_1_SOFT
        )
        self.engine.evaluate(action)
        self.assertTrue(len(self.engine.audit_log) > 0)
        entry = self.engine.audit_log[-1]
        self.assertEqual(entry["action_name"], "turn_on_light")
        self.assertTrue(entry["authorized"])


if __name__ == "__main__":
    unittest.main()
