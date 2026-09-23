"""
Base Tool Interface for J.A.R.V.I.S. Agent Runtime.
Every capability across Digital, Computer, and Physical worlds implements this contract.
Phase 36: Adds ExecutionResult, abstract verify(), tool versioning, and input schema.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
import uuid
from typing import Dict, Any, Optional, List, Type

from shared.schemas.action_envelope import ActionTier, TargetWorld
from shared.schemas.verification_contract import VerificationResult, VerificationStatus


@dataclass
class ExecutionResult:
    """
    Standardized result emitted by tool execution.
    The tool NEVER declares final success; the pipeline alone determines outcome.
    """
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    started_at: float = field(default_factory=time.time)
    completed_at: float = field(default_factory=time.time)
    tool_name: str = ""
    target: str = ""
    attempt: int = 1
    transport_status: str = "COMPLETED"       # "COMPLETED", "TIMEOUT", "TRANSPORT_ERROR"
    raw_result: Dict[str, Any] = field(default_factory=dict)
    side_effect_claim: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.completed_at - self.started_at) * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "tool_name": self.tool_name,
            "target": self.target,
            "attempt": self.attempt,
            "transport_status": self.transport_status,
            "raw_result": self.raw_result,
            "side_effect_claim": self.side_effect_claim,
            "error": self.error
        }


@dataclass
class ToolDefinition:
    name: str
    description: str
    target_world: TargetWorld
    tier: ActionTier
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    risk_level: str = "LOW"                   # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    timeout_seconds: int = 30
    sandbox: bool = True
    rollback_capability: bool = False
    audit_logging: bool = True
    tool_api_version: str = "2.0"
    tool_version: str = "1.0.0"
    schema_version: int = 2
    input_schema: Optional[Any] = None


class JarvisTool(ABC):
    def __init__(self, definition: ToolDefinition):
        self.definition = definition

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def tier(self) -> ActionTier:
        return self.definition.tier

    @property
    def target_world(self) -> TargetWorld:
        return self.definition.target_world

    @property
    def risk_level(self) -> str:
        return self.definition.risk_level

    @property
    def timeout_seconds(self) -> int:
        return self.definition.timeout_seconds

    @property
    def rollback_capability(self) -> bool:
        return self.definition.rollback_capability

    @property
    def tool_api_version(self) -> str:
        return self.definition.tool_api_version

    @property
    def tool_version(self) -> str:
        return self.definition.tool_version

    @property
    def schema_version(self) -> int:
        return self.definition.schema_version

    @property
    def input_schema(self) -> Optional[Any]:
        return self.definition.input_schema

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool action and return ExecutionResult or raw execution dict.
        Tools must NOT declare final system success.
        """
        pass

    async def verify(self, execution_result: Any, **kwargs) -> VerificationResult:
        """
        Default verification contract. Mutating tools override with ground-truth checks.
        """
        action_id = getattr(execution_result, "execution_id", f"act_{self.name}_{int(time.time()*1000)}")
        raw = getattr(execution_result, "raw_result", execution_result) if isinstance(execution_result, ExecutionResult) else execution_result
        success = bool(raw.get("success", True)) if isinstance(raw, dict) else bool(raw)

        return VerificationResult(
            action_id=action_id,
            status=VerificationStatus.VERIFIED if success else VerificationStatus.FAILED,
            logical_verified=success,
            sensory_verified=success,
            match=success,
            observed_state=raw if isinstance(raw, dict) else {"raw": raw},
            verifier=f"{self.name}.verify"
        )

    async def rollback(self, checkpoint: Dict[str, Any]) -> bool:
        """Default rollback operation. Override in mutating tools if rollback is supported."""
        return True
