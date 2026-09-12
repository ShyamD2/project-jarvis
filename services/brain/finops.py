"""
FinOps & Resource Cost Optimizer for Project J.A.R.V.I.S.
Enforces daily token and cloud cost limits, preventing runaway agent loops and unexpected bills.
"""

from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Any
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFinOps")


@dataclass
class CostTracker:
    daily_budget_usd: float = 5.00
    monthly_cloud_budget_usd: float = 50.00
    current_spend_usd: float = 0.00
    tokens_consumed: int = 0
    frugal_mode: bool = False
    last_reset: float = time.time()

    # Pricing per 1k tokens (approximate)
    PRICING_PER_1K = {
        "gemini-2.5-flash": 0.000075,
        "claude-3-7-sonnet": 0.003,
        "ollama-local": 0.00000,
        "mock": 0.00000
    }

    # AWS estimated monthly run rates (USD) per active resource type (labeled estimation)
    ESTIMATED_RATES = {
        "ec2_t3_micro_hourly": 0.0104,
        "ec2_default_monthly": 15.00,
        "s3_gb_monthly": 0.023,
        "s3_bucket_base_monthly": 0.50
    }

    def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> Dict[str, Any]:
        """Calculates cost, increments spend, and checks circuit breaker"""
        rate = self.PRICING_PER_1K.get(model, 0.001)
        total_tokens = prompt_tokens + completion_tokens
        cost = (total_tokens / 1000.0) * rate

        self.tokens_consumed += total_tokens
        self.current_spend_usd += cost

        # Check if approaching budget threshold (> 80%)
        if self.current_spend_usd >= (self.daily_budget_usd * 0.80):
            if not self.frugal_mode:
                self.frugal_mode = True
                logger.warning(f"⚡ [FinOps Alert] Spend (${self.current_spend_usd:.3f}) exceeded 80% of daily budget (${self.daily_budget_usd:.2f}). Activating Frugal Mode.")

        return {
            "model": model,
            "cost_usd": round(cost, 5),
            "total_spend_usd": round(self.current_spend_usd, 4),
            "frugal_mode": self.frugal_mode,
            "within_budget": self.current_spend_usd < self.daily_budget_usd
        }

    def estimate_cloud_spend(self, cloud_health: Dict[str, Any]) -> Dict[str, Any]:
        """Computes labeled infrastructure cost estimates derived from live cloud topology"""
        ec2_instances = cloud_health.get("ec2_instances", [])
        s3_buckets = cloud_health.get("s3_buckets", [])
        ec2_count = len(ec2_instances)
        s3_count = len(s3_buckets)

        ec2_spend = round(ec2_count * self.ESTIMATED_RATES["ec2_default_monthly"], 2)
        s3_spend = round(s3_count * self.ESTIMATED_RATES["s3_bucket_base_monthly"], 2)
        total_cloud = round(ec2_spend + s3_spend, 2)
        util_pct = round((total_cloud / self.monthly_cloud_budget_usd) * 100, 1) if self.monthly_cloud_budget_usd > 0 else 0.0

        return {
            "status": "success",
            "is_estimation": True,
            "estimation_method": "Active AWS Resource Inventory Multiplier",
            "currency": "USD",
            "account": cloud_health.get("account") or "Not Connected",
            "month_to_date_spend": total_cloud,
            "projected_month_end": round(total_cloud * 1.2, 2),
            "monthly_budget": self.monthly_cloud_budget_usd,
            "budget_utilized_percent": util_pct,
            "active_ec2_count": ec2_count,
            "active_s3_count": s3_count,
            "breakdown": {
                "EC2": ec2_spend,
                "S3": s3_spend,
                "Lambda": 0.00,
                "EventBridge": 0.00
            }
        }


finops = CostTracker()
finops_tracker = finops
