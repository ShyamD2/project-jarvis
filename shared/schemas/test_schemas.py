"""
Unit tests for J.A.R.V.I.S. Shared Schemas & Contracts.
Verifies CloudEvents envelope, Action classification, and Verification contract.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.schemas.event_envelope import JarvisEvent
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.schemas.verification_contract import VerificationResult, VerificationStatus


class TestJarvisSchemas(unittest.TestCase):
    def test_event_envelope(self):
        event = JarvisEvent(
            source="sensory.microphone",
            type="sensory.clap",
            data={"confidence": 0.96, "clap_count": 2}
        )
        json_str = event.to_json()
        deserialized = JarvisEvent.from_json(json_str)

        self.assertEqual(deserialized.id, event.id)
        self.assertEqual(deserialized.source, "sensory.microphone")
        self.assertEqual(deserialized.type, "sensory.clap")
        self.assertEqual(deserialized.data["clap_count"], 2)
        self.assertEqual(deserialized.specversion, "1.0")

    def test_action_envelope_blast_radius(self):
        # Tier 0 Reflex
        action_reflex = ActionEnvelope(
            name="query_time",
            target_world=TargetWorld.DIGITAL,
            target_agent="core_agent",
            tier=ActionTier.TIER_0_REFLEX
        )
        self.assertFalse(action_reflex.requires_approval)

        # Tier 3 Destructive: must auto-require approval
        action_destructive = ActionEnvelope(
            name="terraform_destroy",
            target_world=TargetWorld.DIGITAL,
            target_agent="terraform_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE
        )
        self.assertTrue(action_destructive.requires_approval)

    def test_verification_contract(self):
        result = VerificationResult(
            action_id="test_act_01",
            status=VerificationStatus.VERIFIED,
            logical_verified=True,
            sensory_verified=True,
            details={"lux_before": 120.0, "lux_after": 645.0}
        )
        d = result.to_dict()
        self.assertEqual(d["status"], "verified")
        self.assertTrue(d["logical_verified"])
        self.assertTrue(d["sensory_verified"])


if __name__ == "__main__":
    unittest.main()
