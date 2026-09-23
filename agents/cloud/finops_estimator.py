"""
FinOps Cost Estimator for Cloud Deployments (Phase 36 Stage 36.6).
Estimates projected delta monthly costs from infrastructure definitions
and enforces policy budget gates for financial safety.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisFinOpsEstimator")

# Standard AWS on-demand estimated monthly rates (USD) in us-east-1
RESOURCE_PRICING = {
    # EC2 Instances (730 hours/month)
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
    # RDS Databases
    "db.t3.micro": 12.50,
    "db.t3.small": 25.00,
    "db.t3.medium": 50.00,
    "db.m5.large": 131.40,
    # Managed Services
    "aws_nat_gateway": 32.40,
    "aws_lb": 18.25,
    "aws_s3_bucket": 5.00,
    "aws_ebs_volume_per_gb": 0.10,
}


class FinOpsEstimator:
    def __init__(self, default_budget_threshold_usd: float = 50.0):
        self.default_budget_threshold_usd = default_budget_threshold_usd

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

        return 10.0  # Conservative default baseline for unknown resources

    def estimate_plan_cost(
        self,
        plan_summary: Dict[str, Any],
        budget_threshold_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates monthly delta cost across additions, destructions, and modifications.
        Flags threshold violations requiring operator financial approval.
        """
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

        # Replaced resources typically break even or add marginal delta
        for item in to_replace:
            added_cost += self.estimate_resource(item.get("type", ""), item.get("attributes")) * 0.1

        net_delta = round(added_cost - destroyed_cost, 2)
        requires_financial_approval = net_delta > threshold

        logger.info(
            f"💰 [FinOps] Plan Cost Delta: +${added_cost:.2f} / -${destroyed_cost:.2f} -> Net: ${net_delta:+.2f}/mo "
            f"(Threshold: ${threshold:.2f}, Approval Required: {requires_financial_approval})"
        )

        return {
            "currency": "USD",
            "added_monthly_cost": round(added_cost, 2),
            "destroyed_monthly_cost": round(destroyed_cost, 2),
            "net_delta_monthly_cost": net_delta,
            "budget_threshold": threshold,
            "requires_financial_approval": requires_financial_approval,
            "cost_summary": f"Estimated Net Cost Change: ${net_delta:+.2f}/month"
        }


finops_estimator = FinOpsEstimator()
