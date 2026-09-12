"""
Risk Classifier for J.A.R.V.I.S. Permission Engine.
Analyzes commands, parameters, and intents to assign strict 4-Tier Blast Radius ratings.
"""

import re
from typing import Dict, Any, Tuple
from shared.schemas.action_envelope import ActionTier, TargetWorld


class RiskClassifier:
    def __init__(self):
        # Tier 3 (Destructive / Critical) patterns - requires explicit MFA / Master Secret
        self.tier3_patterns = [
            r"\b(destroy|drop\s+database|delete\s+bucket|rm\s+-rf|format\s+[c-z]:|mkfs|shutdown|erase|wipe)\b",
            r"\b(terraform\s+destroy|force\s+push|truncate\s+table|modify\s+aws\s+iam|alter\s+iam|delete\s+\d+\s+files)\b",
            r"\b(iam|root_access|elevate_privileges|revoke_all|format_drive)\b"
        ]
        # Tier 2 (Mutating / High) patterns - requires interactive user approval
        self.tier2_patterns = [
            r"\b(terraform\s+apply|docker\s+restart|reboot|deploy|modify|update|restart\s+service)\b",
            r"\b(delete\s+file|remove\s+file|kill\s+process|terminate|close_app|purge_cache)\b"
        ]
        # Tier 0 (Reflex / Low) patterns - immediate execution
        self.tier0_patterns = [
            r"\b(status|get|query|read|check|describe|list|lux|temperature|time|date|battery|disk|ip)\b",
            r"\b(open\s+chrome|open\s+opera|open\s+browser|launch_app|control_system_audio|volume)\b"
        ]

    def classify(self, name: str, command: str, target_world: TargetWorld, parameters: Dict[str, Any]) -> Tuple[ActionTier, str]:
        """
        Classifies the blast radius of an action into:
        TIER_0_REFLEX (LOW): Execute immediately
        TIER_1_SOFT (MEDIUM): Execute with soft voice log
        TIER_2_MUTATING (HIGH): Requires interactive user approval
        TIER_3_DESTRUCTIVE (CRITICAL): Requires explicit approval token + MFA verification
        """
        target_str = f"{name} {command} {str(parameters)}".lower()

        # 1. Check Critical / Tier 3
        for pat in self.tier3_patterns:
            if re.search(pat, target_str):
                return ActionTier.TIER_3_DESTRUCTIVE, f"CRITICAL: Matches high-consequence pattern '{pat}'"

        # 2. Check High / Tier 2
        for pat in self.tier2_patterns:
            if re.search(pat, target_str):
                return ActionTier.TIER_2_MUTATING, f"HIGH: Matches mutating pattern '{pat}'"

        # 3. Check Low / Tier 0
        for pat in self.tier0_patterns:
            if re.search(pat, target_str):
                return ActionTier.TIER_0_REFLEX, "LOW: Read-only or safe reflex action"

        # Default to Tier 1 Soft / Medium Action
        return ActionTier.TIER_1_SOFT, "MEDIUM: Standard non-destructive operational action"

    @staticmethod
    def tier_to_risk(tier: ActionTier) -> str:
        mapping = {
            ActionTier.TIER_0_REFLEX: "LOW",
            ActionTier.TIER_1_SOFT: "MEDIUM",
            ActionTier.TIER_2_MUTATING: "HIGH",
            ActionTier.TIER_3_DESTRUCTIVE: "CRITICAL"
        }
        return mapping.get(tier, "MEDIUM")

    @staticmethod
    def risk_to_tier(risk: str) -> ActionTier:
        mapping = {
            "LOW": ActionTier.TIER_0_REFLEX,
            "MEDIUM": ActionTier.TIER_1_SOFT,
            "HIGH": ActionTier.TIER_2_MUTATING,
            "CRITICAL": ActionTier.TIER_3_DESTRUCTIVE
        }
        return mapping.get(risk.upper(), ActionTier.TIER_1_SOFT)


classifier = RiskClassifier()
