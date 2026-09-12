"""
Workflow and Task DAG models for J.A.R.V.I.S. Master Planner.
Represents multi-step plans with explicit dependencies, blast-radius tiers, and verification specs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time
from typing import List, Dict, Any, Optional
from shared.schemas.action_envelope import ActionTier, TargetWorld


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    VERIFIED = "verified"


@dataclass
class WorkflowStep:
    name: str
    target_world: TargetWorld
    target_agent: str
    command: str
    tier: ActionTier = ActionTier.TIER_1_SOFT
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list) # List of step_ids this step depends on
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class WorkflowPlan:
    goal: str
    steps: List[WorkflowStep] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    created_at: float = field(default_factory=time.time)
    completed: bool = False
    success: bool = False

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Returns steps that are PENDING and have all dependencies completed"""
        completed_step_ids = {s.step_id for s in self.steps if s.status in [StepStatus.COMPLETED, StepStatus.VERIFIED]}
        ready = []
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                if all(dep in completed_step_ids for dep in step.depends_on):
                    ready.append(step)
        return ready

    def is_finished(self) -> bool:
        return all(s.status in [StepStatus.COMPLETED, StepStatus.VERIFIED, StepStatus.FAILED, StepStatus.SKIPPED] for s in self.steps)
