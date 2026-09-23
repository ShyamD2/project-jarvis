"""
Terraform Plan Parser & Blast Radius Classifier (Phase 36 Stage 36.6).
Safely parses Terraform JSON plan outputs, extracts resource deltas,
and classifies blast radius according to ActionTier security policies.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from shared.schemas.action_envelope import ActionTier
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisTerraformParser")


class TerraformPlanParser:
    def __init__(self):
        pass

    def parse_plan(self, plan_data: Dict[str, Any] | str) -> Dict[str, Any]:
        """
        Parses Terraform plan dictionary or JSON string.
        Extracts resource changes, classifies blast radius, and detects destructive actions.
        """
        if isinstance(plan_data, str):
            try:
                plan = json.loads(plan_data)
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Invalid Terraform JSON: {e}",
                    "blast_radius_tier": ActionTier.TIER_3_DESTRUCTIVE.value,
                    "has_destructive_changes": True
                }
        else:
            plan = plan_data

        resource_changes = plan.get("resource_changes", [])
        to_add: List[Dict[str, Any]] = []
        to_change: List[Dict[str, Any]] = []
        to_destroy: List[Dict[str, Any]] = []
        to_replace: List[Dict[str, Any]] = []

        for rc in resource_changes:
            actions = rc.get("change", {}).get("actions", [])
            addr = rc.get("address", "unknown")
            r_type = rc.get("type", "unknown")

            item = {"address": addr, "type": r_type, "actions": actions}

            if actions == ["create"]:
                to_add.append(item)
            elif actions == ["update"]:
                to_change.append(item)
            elif actions == ["delete"]:
                to_destroy.append(item)
            elif "delete" in actions and "create" in actions:
                to_replace.append(item)

        has_destructive = bool(to_destroy or to_replace)

        # Blast Radius Classification
        if has_destructive:
            tier = ActionTier.TIER_3_DESTRUCTIVE
        elif to_add or to_change:
            tier = ActionTier.TIER_2_MUTATING
        else:
            tier = ActionTier.TIER_0_REFLEX

        summary = f"Plan: {len(to_add)} to add, {len(to_change)} to change, {len(to_destroy)} to destroy, {len(to_replace)} to replace."

        return {
            "valid": True,
            "add_count": len(to_add),
            "change_count": len(to_change),
            "destroy_count": len(to_destroy),
            "replace_count": len(to_replace),
            "has_destructive_changes": has_destructive,
            "blast_radius_tier": tier.value,
            "tier_enum": tier,
            "to_add": to_add,
            "to_change": to_change,
            "to_destroy": to_destroy,
            "to_replace": to_replace,
            "summary": summary
        }


terraform_parser = TerraformPlanParser()
