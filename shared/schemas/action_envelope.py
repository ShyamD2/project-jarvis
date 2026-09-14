"""
Action Envelope and Blast-Radius Classification for J.A.R.V.I.S. Action Fabric.
Strictly regulates what actions can be executed and what confirmation levels they mandate.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import uuid
from typing import Any, Dict, Optional


class ActionTier(str, Enum):
    TIER_0_REFLEX = "tier_0_reflex"          # Idempotent queries, volume, light reading. 0 confirmation.
    TIER_1_SOFT = "tier_1_soft"              # Lights, app launch, git commit. Soft voice ack.
    TIER_2_MUTATING = "tier_2_mutating"      # Dev deployment, container restart. Proactive notify + timeout.
    TIER_3_DESTRUCTIVE = "tier_3_destructive" # Prod changes, file deletes, terraform destroy. Explicit MFA/Voice confirm.


class TargetWorld(str, Enum):
    DIGITAL = "digital"    # AWS, APIs, GitHub, Cloud, Email, Calendar
    COMPUTER = "computer"  # Windows OS, Apps, Files, Terminals, Docker, VS Code
    PHYSICAL = "physical"  # ESP32, Raspberry Pi, Relays, Lights, Motors, Sensors


@dataclass
class ActionEnvelope:
    name: str                                # Human-readable name, e.g., "turn_on_light"
    target_world: TargetWorld                # DIGITAL, COMPUTER, or PHYSICAL
    target_agent: str                        # e.g., "esp32_agent", "windows_agent", "aws_agent"
    tier: ActionTier                         # Blast-radius tier
    parameters: Dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requires_approval: bool = False
    approved_by: Optional[str] = None
    timeout_seconds: int = 30
    rollback_command: Optional[str] = None
    verification_spec: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        # Enforce automatic approval requirements for mutating and destructive actions
        if self.tier in (ActionTier.TIER_2_MUTATING, ActionTier.TIER_3_DESTRUCTIVE):
            self.requires_approval = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_world"] = self.target_world.value
        d["tier"] = self.tier.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionEnvelope:
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            name=data["name"],
            target_world=TargetWorld(data["target_world"]),
            target_agent=data["target_agent"],
            tier=ActionTier(data.get("tier", ActionTier.TIER_1_SOFT)),
            parameters=data.get("parameters", {}),
            requires_approval=data.get("requires_approval", False),
            approved_by=data.get("approved_by"),
            timeout_seconds=data.get("timeout_seconds", 30),
            rollback_command=data.get("rollback_command"),
            verification_spec=data.get("verification_spec")
        )
