"""
FinOps Cost Ceilings, Hard Budget Guard & Cloud Estimator (Phase 36 / FinOps Pillar).
Enforces hard budget limits and automatic degradation to local reflex on financial exhaustion:
- daily_budget_usd
- monthly_budget_usd
- max_llm_calls_per_min
- max_tokens_per_task
When daily or monthly budget is exhausted, external LLM calls are blocked and requests
automatically degrade to local reflex execution.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional, Tuple
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFinOpsEstimator")

# Standard AWS on-demand estimated monthly rates (USD) in us-east-1
RESOURCE_PRICING = {
    "t3.nano": 3.80,
    "t3.micro": 7.60,
    "t3.small": 15.20,
    "t3.medium": 30.40,
    "t3.large": 60.80,
    "t3.xlarge": 121.60,
    "m5.large": 70.08,
    "m5.xlarge": 140.16,
    "c5.large": 62.00,
    "c5.xlarge": 124.00,
    "db.t3.micro": 12.50,
    "db.t3.small": 25.00,
    "db.t3.medium": 50.00,
    "db.m5.large": 131.40,
    "aws_nat_gateway": 32.40,
    "aws_lb": 18.25,
    "aws_s3_bucket": 5.00,
    "aws_ebs_volume_per_gb": 0.10,
}


class HardBudgetGuard:
    def __init__(
        self,
        daily_budget_usd: float = 10.00,
        monthly_budget_usd: float = 100.00,
        max_llm_calls_per_min: int = 60,
        max_tokens_per_task: int = 16000
    ):
        self.daily_budget_usd = daily_budget_usd
        self.monthly_budget_usd = monthly_budget_usd
        self.max_llm_calls_per_min = max_llm_calls_per_min
        self.max_tokens_per_task = max_tokens_per_task

        self.current_daily_spend_usd = 0.00
        self.current_monthly_spend_usd = 0.00
        self.total_tokens_consumed = 0

        self._llm_call_timestamps: List[float] = []
        self._last_day_reset = time.time()
        self._last_month_reset = time.time()

    def _check_and_reset_windows(self):
        now = time.time()
        # Reset daily after 86400 seconds
        if now - self._last_day_reset >= 86400:
            self.current_daily_spend_usd = 0.00
            self._last_day_reset = now
        # Reset monthly after 30 days (2592000s)
        if now - self._last_month_reset >= 2592000:
            self.current_monthly_spend_usd = 0.00
            self._last_month_reset = now
        # Prune calls older than 60 seconds
        cutoff = now - 60.0
        self._llm_call_timestamps = [t for t in self._llm_call_timestamps if t >= cutoff]

    def is_daily_budget_exhausted(self) -> bool:
        self._check_and_reset_windows()
        return self.current_daily_spend_usd >= self.daily_budget_usd

    def is_monthly_budget_exhausted(self) -> bool:
        self._check_and_reset_windows()
        return self.current_monthly_spend_usd >= self.monthly_budget_usd

    def should_degrade_to_local_reflex(self) -> bool:
        """Returns True if financial limits require degrading external LLMs to local reflex."""
        return self.is_daily_budget_exhausted() or self.is_monthly_budget_exhausted()

    def check_request(self, estimated_tokens: int = 0) -> Tuple[bool, str, bool]:
        """
        Evaluates a prospective LLM invocation against hard budget limits.
        Returns: (allowed: bool, reason: str, degrade_to_reflex: bool)
        """
        self._check_and_reset_windows()

        # 1. Per-task token ceiling
        if estimated_tokens > self.max_tokens_per_task:
            return False, f"TOKEN_CEILING_EXCEEDED: Requested {estimated_tokens} tokens exceeds per-task cap ({self.max_tokens_per_task}).", False

        # 2. Rate limiting calls per minute
        if len(self._llm_call_timestamps) >= self.max_llm_calls_per_min:
            return False, f"RATE_LIMIT_EXCEEDED: Exceeded {self.max_llm_calls_per_min} LLM calls per minute.", False

        # 3. Daily cost ceiling -> auto degrade to local reflex
        if self.is_daily_budget_exhausted():
            logger.warning(f"⚡ [FinOps Alert] Daily budget exhausted (${self.current_daily_spend_usd:.2f} / ${self.daily_budget_usd:.2f}). Degrading to local reflex.")
            return False, f"DAILY_BUDGET_EXHAUSTED: Spend (${self.current_daily_spend_usd:.2f}) reached daily limit (${self.daily_budget_usd:.2f}).", True

        # 4. Monthly cost ceiling -> auto degrade to local reflex
        if self.is_monthly_budget_exhausted():
            logger.warning(f"⚡ [FinOps Alert] Monthly budget exhausted (${self.current_monthly_spend_usd:.2f} / ${self.monthly_budget_usd:.2f}). Degrading to local reflex.")
            return False, f"MONTHLY_BUDGET_EXHAUSTED: Spend (${self.current_monthly_spend_usd:.2f}) reached monthly limit (${self.monthly_budget_usd:.2f}).", True

        return True, "ALLOWED", False

    def record_llm_call(self, tokens: int, cost_usd: float):
        """Records spend and invocation timestamp."""
        self._check_and_reset_windows()
        now = time.time()
        self._llm_call_timestamps.append(now)
        self.total_tokens_consumed += tokens
        self.current_daily_spend_usd += cost_usd
        self.current_monthly_spend_usd += cost_usd

    def reset(self):
        """Resets all metrics (for unit testing)."""
        self.current_daily_spend_usd = 0.00
        self.current_monthly_spend_usd = 0.00
        self.total_tokens_consumed = 0
        self._llm_call_timestamps.clear()
        self._last_day_reset = time.time()
        self._last_month_reset = time.time()


class FinOpsEstimator:
    def __init__(self, default_budget_threshold_usd: float = 50.0):
        self.default_budget_threshold_usd = default_budget_threshold_usd
        self.guard = HardBudgetGuard()

    def estimate_resource(self, resource_type: str, attributes: Optional[Dict[str, Any]] = None) -> float:
        """Estimates monthly USD cost for a single cloud resource."""
        attrs = attributes or {}
        r_type = resource_type.lower()

        if "instance" in r_type or "aws_instance" in r_type:
            itype = attrs.get("instance_type", "t3.micro").lower()
            return RESOURCE_PRICING.get(itype, 20.0)

        elif "db_instance" in r_type or "aws_db_instance" in r_type:
            db_class = attrs.get("instance_class", "db.t3.micro").lower()
            return RESOURCE_PRICING.get(db_class, 30.0)

        elif "ebs" in r_type:
            size_gb = float(attrs.get("size", 20))
            return size_gb * RESOURCE_PRICING["aws_ebs_volume_per_gb"]

        elif "nat_gateway" in r_type:
            return RESOURCE_PRICING["aws_nat_gateway"]

        elif "lb" in r_type or "alb" in r_type:
            return RESOURCE_PRICING["aws_lb"]

        elif "s3" in r_type:
            return RESOURCE_PRICING["aws_s3_bucket"]

        return 10.0

    def estimate_plan_cost(
        self,
        plan_summary: Dict[str, Any],
        budget_threshold_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculates monthly delta cost across additions, destructions, and modifications."""
        threshold = budget_threshold_usd if budget_threshold_usd is not None else self.default_budget_threshold_usd

        to_add = plan_summary.get("to_add", [])
        to_destroy = plan_summary.get("to_destroy", [])
        to_replace = plan_summary.get("to_replace", [])

        added_cost = 0.0
        for item in to_add:
            added_cost += self.estimate_resource(item.get("type", ""), item.get("attributes"))

        destroyed_cost = 0.0
        for item in to_destroy:
            destroyed_cost += self.estimate_resource(item.get("type", ""), item.get("attributes"))

        for item in to_replace:
            added_cost += self.estimate_resource(item.get("type", ""), item.get("attributes")) * 0.1

        net_delta = round(added_cost - destroyed_cost, 2)
        requires_financial_approval = net_delta > threshold

        return {
            "net_monthly_delta_usd": net_delta,
            "projected_monthly_add_usd": round(added_cost, 2),
            "projected_monthly_destroy_usd": round(destroyed_cost, 2),
            "budget_threshold_usd": threshold,
            "requires_financial_approval": requires_financial_approval,
            "status": "REQUIRES_APPROVAL" if requires_financial_approval else "PASSED"
        }


finops_estimator = FinOpsEstimator()
hard_budget_guard = finops_estimator.guard
