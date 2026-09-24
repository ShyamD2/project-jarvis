"""
Security Regression Test: Cryptographic Confirmation & Lease Replay Protection (Item 10).
Invariant:
  Valid Approval / Action Lease
      ↓
  Execute
      ↓
  Mark USED / CONSUMED
      ↓
  Replay Same Ticket / Lease
      ↓
  EXECUTION MUST STRICTLY FAIL (BLOCKED_REPLAY)
"""

import unittest
import time
import asyncio
from agents.intelligence.safety_guard import safety_guard, StrictTier
from services.permission_engine.engine import permission_engine
from services.brain.canonical_pipeline import canonical_pipeline


class TestConfirmationReplay(unittest.TestCase):
    def setUp(self):
        self.action = "delete_file"
        self.params = {"path": "C:\\temp\\safe_delete_test.txt"}

    def test_safety_guard_ticket_replay_blocked(self):
        """Invariant: Once an approval ticket is used, replaying the same ticket_id fails."""
        # 1. Create a ticket
        ticket = safety_guard._create_ticket(self.action, StrictTier.TIER_2_DISRUPTIVE, self.params, "Test delete")
        app_id = ticket.approval_id

        # 2. Confirm the ticket
        confirmed = safety_guard.confirm_ticket(app_id, approver="operator")
        self.assertTrue(confirmed)

        # 3. First execution succeeds
        dec1 = safety_guard.evaluate_request(self.action, self.params, approval_id=app_id)
        self.assertTrue(dec1["authorized"], "First use of approved ticket must succeed.")

        # 4. Replay attack: attempt to use the exact same ticket again
        dec2 = safety_guard.evaluate_request(self.action, self.params, approval_id=app_id)
        self.assertFalse(dec2["authorized"], "Replayed ticket must be strictly rejected.")
        self.assertIn("BLOCKED_REPLAY", dec2["rationale"])

    def test_permission_engine_action_lease_replay_blocked(self):
        """Invariant: Single-use ActionLease nonce cannot be reused after consumption."""
        lease = permission_engine.issue_action_lease(
            tool_name="close_app",
            parameters={"pid": 1234},
            issued_by="security_tester"
        )
        lease_id = lease.lease_id

        # First evaluation consumes the lease
        dec1 = permission_engine.evaluate_action(
            action_name="close_app",
            parameters={"pid": 1234},
            approval_token=lease_id
        )
        self.assertTrue(dec1.authorized)
        self.assertEqual(dec1.single_use_lease_id, lease_id)

        # Replay attempt with same lease_id must be rejected
        dec2 = permission_engine.evaluate_action(
            action_name="close_app",
            parameters={"pid": 1234},
            approval_token=lease_id
        )
        self.assertFalse(dec2.authorized, "Replayed Action Lease must be rejected.")
        self.assertIn("REPLAY", dec2.rationale)

    def test_canonical_pipeline_rejects_replayed_token(self):
        """Invariant: Canonical Pipeline halts execution on replayed lease token."""
        lease = permission_engine.issue_action_lease(
            tool_name="system.status",
            parameters={},
            issued_by="security_tester"
        )

        # Execute once
        res1 = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name="system.status",
                parameters={},
                approval_token=lease.lease_id
            )
        )
        self.assertEqual(res1.get("final_status"), "SUCCESS")

        # Replay execution
        res2 = asyncio.run(
            canonical_pipeline.execute_request(
                tool_name="system.status",
                parameters={},
                approval_token=lease.lease_id
            )
        )
        self.assertEqual(res2.get("final_status"), "FAILED")
        self.assertIn("REPLAY", res2.get("error", "").upper())


if __name__ == "__main__":
    unittest.main()
