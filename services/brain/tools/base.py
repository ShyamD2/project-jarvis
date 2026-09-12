"""
Base Tool Interface for J.A.R.V.I.S. Agent Runtime.
Every capability across Digital, Computer, and Physical worlds implements this contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from shared.schemas.action_envelope import ActionTier, TargetWorld


@dataclass
class ToolDefinition:
    name: str
    description: str
    target_world: TargetWorld
    tier: ActionTier
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    risk_level: str = "LOW"             # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    timeout_seconds: int = 30
    sandbox: bool = True
    rollback_capability: bool = False
    audit_logging: bool = True


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

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool and return the execution result dictionary"""
        pass

    async def rollback(self, checkpoint: Dict[str, Any]) -> bool:
        """Default rollback operation. Override in mutating tools if rollback is supported."""
        return True

