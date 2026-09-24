"""
Pipeline Final-State Authority & Reality Reconciliation Invariant Tests (Phase 36 Stage 36.5).
Verifies:
  1. Pipeline Final-State Authority (Cardinal Principle 1 & Item 122):
     Tools cannot declare SUCCESS. Only the canonical pipeline assigns final_status.
  2. Observation != Correction Principle (Item 116 & Item 121):
     World model reconciles observed drift without autonomous production mutation.
  3. Autonomous mutation attempts without operator lease token raise PermissionError.
"""

import unittest
from unittest.mock import patch, AsyncMock
from services.brain.canonical_pipeline import canonical_pipeline
from services.memory.reality_reconciliation import reality_reconciliation
from services.memory.world_model import world_model
from shared.schemas.verification_contract import VerificationResult, VerificationStatus


class TestPipelineAuthority(unittest.IsolatedAsyncioTestCase):
    async def test_tool_cannot_declare_success_on_verification_failure(self):
        """Even if the tool returns success=True, verification failure forces pipeline final_status=FAILED."""
        with patch("services.brain.canonical_pipeline.tool_registry.execute_tool") as mock_exec:
            mock_exec.return_value = {
                "success": True,
                "status": "success",
                "result": {"success": True, "pid": 9999999}
            }
            res = await canonical_pipeline.execute_request(
                tool_name="computer.open_app",
                parameters={"app": "non_existent_fake_app_xyz_999.exe"},
                source="test_authority",
                user_role="OWNER"
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["final_status"], "FAILED")
            self.assertEqual(res["verification"]["status"], "failed")
            self.assertFalse(res["verification"]["match"])

    def test_observation_not_equal_to_correction_drift_detection(self):
        """World model updates belief state on drift without modifying external production (Item 116)."""
        expected = {"cpu_percent": 10.0, "status": "nominal"}
        observed = {"cpu_percent": 88.5, "status": "degraded"}

        report = reality_reconciliation.reconcile(
            entity_id="host_pc",
            expected=expected,
            observed=observed,
            autonomous_correct=False
        )

        self.assertTrue(report["drift_detected"])
        self.assertEqual(report["drift_count"], 2)
        self.assertTrue(report["world_model_reconciled"])
        self.assertFalse(report["autonomous_mutation_executed"])

        # World model should have the updated reality
        self.assertEqual(world_model.pc.cpu_percent, 88.5)

    def test_autonomous_correction_prohibited_without_approval_token(self):
        """Autonomous production mutation without operator approval token is strictly prohibited by policy (Item 121)."""
        expected = {"service_state": "running"}
        observed = {"service_state": "stopped"}

        with self.assertRaises(PermissionError) as ctx:
            reality_reconciliation.reconcile(
                entity_id="cloud_service_nginx",
                expected=expected,
                observed=observed,
                autonomous_correct=True,
                operator_approval_token=None  # Missing ticket
            )
        self.assertIn("Autonomous production mutation prohibited", str(ctx.exception))

    def test_operator_authorized_correction_allowed(self):
        """Operator-authorized correction with single-use lease token succeeds."""
        expected = {"service_state": "running"}
        observed = {"service_state": "stopped"}

        report = reality_reconciliation.reconcile(
            entity_id="cloud_service_nginx",
            expected=expected,
            observed=observed,
            autonomous_correct=True,
            operator_approval_token="lease_operator_single_use_valid"
        )
        self.assertTrue(report["drift_detected"])
        self.assertTrue(report["autonomous_mutation_executed"])


if __name__ == "__main__":
    unittest.main()
