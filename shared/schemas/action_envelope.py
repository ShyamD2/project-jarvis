"""
Action Envelope and Blast-Radius Classification for J.A.R.V.I.S. Action Fabric.
Strictly regulates what actions can be executed and what confirmation levels they mandate.
Phase 36: Adds ExecutionClass, UniversalTransactionRecord, and Versioning.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import uuid
import time
from typing import Any, Dict, Optional, List


class ActionTier(str, Enum):
    TIER_0_REFLEX = "tier_0_reflex"          # Idempotent queries, volume, light reading. 0 confirmation.
    TIER_1_SOFT = "tier_1_soft"              # Lights, app launch, git commit. Soft voice ack.
    TIER_2_MUTATING = "tier_2_mutating"      # Dev deployment, container restart. Proactive notify + timeout.
    TIER_3_DESTRUCTIVE = "tier_3_destructive" # Prod changes, file deletes, terraform destroy. Explicit MFA/Voice confirm.


class TargetWorld(str, Enum):
    DIGITAL = "digital"    # AWS, APIs, GitHub, Cloud, Email, Calendar
    COMPUTER = "computer"  # Windows OS, Apps, Files, Terminals, Docker, VS Code
    PHYSICAL = "physical"  # ESP32, Raspberry Pi, Relays, Lights, Motors, Sensors


class ExecutionClass(str, Enum):
    REFLEX = "reflex"          # Immediate low-risk action: policy checked, zero DAG planning
    READ_ONLY = "read_only"    # Pure telemetry/state query: zero mutation, freshness verified
    MISSION = "mission"        # Multi-step/mutating task: Planner + DAG + Approval Lease + Sandbox


@dataclass
class UniversalTransactionRecord:
    """
    Universal Transaction Context (Item 4) tracking every action across its full lifecycle.
    """
    mission_id: str
    task_id: str
    action_id: str
    trace_id: str
    user_id: str
    source: str                                # "voice", "telegram", "hud", "api", "cli"
    tool: str                                  # Hierarchical tool name e.g. "computer.open_app"
    arguments_hash: str
    risk_tier: str
    timestamp: float = field(default_factory=time.time)
    parent_action_id: Optional[str] = None
    approval_token_id: Optional[str] = None
    pre_state_hash: Optional[str] = None
    post_state_hash: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    rollback_result: Optional[Dict[str, Any]] = None
    stage_latencies: Optional[Dict[str, float]] = None
    final_status: str = "PENDING"              # "SUCCESS", "FAILED", "UNKNOWN", "PENDING"
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


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
    execution_class: ExecutionClass = ExecutionClass.MISSION
    version: str = "2.0"
    schema_version: int = 2
    idempotency_key: Optional[str] = None
    trace_id: Optional[str] = None
    mission_id: Optional[str] = None

    def __post_init__(self):
        # Enforce automatic approval requirements for mutating and destructive actions
        if self.tier in (ActionTier.TIER_2_MUTATING, ActionTier.TIER_3_DESTRUCTIVE):
            self.requires_approval = True
        # If tier is reflex, classify default as REFLEX
        if self.tier == ActionTier.TIER_0_REFLEX and self.execution_class == ExecutionClass.MISSION:
            self.execution_class = ExecutionClass.REFLEX

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_world"] = self.target_world.value
        d["tier"] = self.tier.value
        d["execution_class"] = self.execution_class.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionEnvelope:
        exec_class = ExecutionClass(data.get("execution_class", ExecutionClass.MISSION.value))
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
            verification_spec=data.get("verification_spec"),
            execution_class=exec_class,
            version=data.get("version", "2.0"),
            schema_version=data.get("schema_version", 2),
            idempotency_key=data.get("idempotency_key"),
            trace_id=data.get("trace_id"),
            mission_id=data.get("mission_id")
        )
