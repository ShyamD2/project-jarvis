"""
Unit Tests: FinOps Hard Budget Guardrails & Auto-Degrade to Local Reflex (Item 4).
Verifies:
  1. Per-task token ceilings (> max_tokens_per_task blocked).
  2. Rate limiting (max_llm_calls_per_min enforced).
  3. Daily budget ceiling -> triggers degrade_to_local_reflex = True.
  4. Monthly budget ceiling -> triggers degrade_to_local_reflex = True.
  5. Infrastructure cost delta estimation correctly flags approvals.
"""

import unittest
from services.cloud.finops_estimator import HardBudgetGuard, FinOpsEstimator, finops_estimator


class TestFinOpsHardLimits(unittest.TestCase):
    def setUp(self):
        self.guard = HardBudgetGuard(
            daily_budget_usd=5.00,
            monthly_budget_usd=50.00,
            max_llm_calls_per_min=5,
            max_tokens_per_task=8000
        )

    def test_token_ceiling_enforced(self):
        """Invariant: Tasks requesting more tokens than max_tokens_per_task are blocked."""
        allowed, reason, degrade = self.guard.check_request(estimated_tokens=10000)
        self.assertFalse(allowed)
        self.assertIn("TOKEN_CEILING_EXCEEDED", reason)
        self.assertFalse(degrade)

        # Within limit
        allowed, reason, degrade = self.guard.check_request(estimated_tokens=4000)
        self.assertTrue(allowed)

    def test_rate_limiting_calls_per_minute(self):
        """Invariant: Bursting past max_llm_calls_per_min triggers rate limiting."""
        for _ in range(5):
            self.guard.record_llm_call(tokens=100, cost_usd=0.01)

        allowed, reason, degrade = self.guard.check_request(estimated_tokens=500)
        self.assertFalse(allowed)
        self.assertIn("RATE_LIMIT_EXCEEDED", reason)

    def test_daily_budget_exhaustion_auto_degrades_to_reflex(self):
        """Invariant: When daily spend exceeds budget, auto-degrade to local reflex triggers."""
        self.assertFalse(self.guard.should_degrade_to_local_reflex())

        # Exceed daily budget of $5.00
        self.guard.record_llm_call(tokens=50000, cost_usd=5.50)

        self.assertTrue(self.guard.is_daily_budget_exhausted())
        self.assertTrue(self.guard.should_degrade_to_local_reflex())

        allowed, reason, degrade = self.guard.check_request(estimated_tokens=500)
        self.assertFalse(allowed)
        self.assertTrue(degrade, "Exhausted daily budget must trigger degrade_to_reflex.")
        self.assertIn("DAILY_BUDGET_EXHAUSTED", reason)

    def test_monthly_budget_exhaustion_auto_degrades_to_reflex(self):
        """Invariant: When monthly spend exceeds budget, auto-degrade to local reflex triggers."""
        # Set daily budget high so only monthly triggers
        self.guard.daily_budget_usd = 100.00
        self.guard.record_llm_call(tokens=500000, cost_usd=52.00)

        self.assertTrue(self.guard.is_monthly_budget_exhausted())
        self.assertTrue(self.guard.should_degrade_to_local_reflex())

        allowed, reason, degrade = self.guard.check_request(estimated_tokens=500)
        self.assertFalse(allowed)
        self.assertTrue(degrade, "Exhausted monthly budget must trigger degrade_to_reflex.")
        self.assertIn("MONTHLY_BUDGET_EXHAUSTED", reason)

    def test_cloud_delta_cost_estimation(self):
        """Invariant: FinOpsEstimator flags plans that exceed financial thresholds."""
        estimator = FinOpsEstimator(default_budget_threshold_usd=30.0)
        plan = {
            "to_add": [
                {"type": "aws_instance", "attributes": {"instance_type": "m5.large"}},  # $70.08
                {"type": "aws_nat_gateway", "attributes": {}}                            # $32.40
            ],
            "to_destroy": []
        }
        res = estimator.estimate_plan_cost(plan)
        self.assertTrue(res["requires_financial_approval"])
        self.assertEqual(res["status"], "REQUIRES_APPROVAL")
        self.assertGreater(res["net_monthly_delta_usd"], 30.0)


if __name__ == "__main__":
    unittest.main()
