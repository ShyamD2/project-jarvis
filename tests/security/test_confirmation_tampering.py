"""
Security Regression Test: Confirmation Ticket Parameter Tampering Defenses (Item 10).
Invariant:
  Valid Approval / Ticket Issued for Parameters A
      ↓
  Attacker Modifies Parameters to B (post-approval parameter tampering)
      ↓
  HMAC Signature Check Mismatch
      ↓
  EXECUTION MUST STRICTLY FAIL (SECURITY_VIOLATION)
"""

import unittest
from agents.intelligence.safety_guard import safety_guard, StrictTier
from services.permission_engine.engine import permission_engine


class TestConfirmationTampering(unittest.TestCase):
    def test_safety_guard_parameter_tampering_rejected(self):
        """Invariant: Modifying parameters after ticket creation invalidates HMAC signature and is rejected."""
        original_params = {"action": "delete", "path": "C:\\safe\\file.txt"}
        tampered_params = {"action": "delete", "path": "C:\\Windows\\System32\\critical.dll"}

        # 1. Create and approve ticket for original_params
        ticket = safety_guard._create_ticket("delete_file", StrictTier.TIER_2_DISRUPTIVE, original_params, "Harmless delete")
        safety_guard.confirm_ticket(ticket.approval_id, approver="operator")

        # 2. Attacker attempts to execute with tampered_params using original approval_id
        decision = safety_guard.evaluate_request("delete_file", tampered_params, approval_id=ticket.approval_id)

        self.assertFalse(decision["authorized"], "Execution with tampered parameters must be rejected.")
        self.assertIn("SECURITY VIOLATION", decision["rationale"])
        self.assertIn("Parameters altered", decision["rationale"])

    def test_permission_engine_action_lease_parameter_tampering_rejected(self):
        """Invariant: Modifying parameters after ActionLease issuance fails parameter hash check."""
        original_params = {"action": "destroy", "target": "dev_env"}
        tampered_params = {"action": "destroy", "target": "prod_production_database"}

        lease = permission_engine.issue_action_lease(
            tool_name="devops_tool",
            parameters=original_params,
            issued_by="security_tester"
        )

        # Attempt to use lease with tampered parameters
        decision = permission_engine.evaluate_action(
            action_name="devops_tool",
            parameters=tampered_params,
            approval_token=lease.lease_id
        )

        self.assertFalse(decision.authorized, "Lease parameter hash mismatch must reject execution.")
        self.assertIn("LEASE_MISMATCH", decision.rationale)


if __name__ == "__main__":
    unittest.main()
