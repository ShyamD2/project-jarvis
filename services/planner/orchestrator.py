"""
Master Orchestrator for J.A.R.V.I.S. Planner.
Executes task DAGs in parallel, resolves dependencies, and records execution audit.
"""

from __future__ import annotations
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from services.planner.workflow import WorkflowPlan, WorkflowStep, StepStatus
from services.planner.decomposer import decomposer
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisMasterOrchestrator")


class MasterOrchestrator:
    def __init__(self, step_executor: Optional[Callable[[WorkflowStep], Any]] = None):
        self.step_executor = step_executor or self._default_executor

    async def _default_executor(self, step: WorkflowStep) -> Dict[str, Any]:
        """Default step execution simulator for planner validation"""
        logger.info(f"Executing step '{step.name}' on [{step.target_agent}] ({step.target_world.value})")
        # Simulates minor step execution time
        await asyncio.sleep(0.05)
        return {
            "success": True,
            "command": step.command,
            "channel_1_logical": True,
            "channel_2_sensory": True
        }

    async def execute_goal(self, goal: str) -> WorkflowPlan:
        """Decomposes a goal into a DAG plan and orchestrates its execution"""
        plan = decomposer.decompose(goal)
        logger.info(f"Generated Workflow Plan [{plan.plan_id}] with {len(plan.steps)} steps for goal: '{goal}'")

        # Broadcast plan generation event
        mesh.publish(
            JarvisEvent(
                source="planner.orchestrator",
                type="plan.started",
                data={"plan_id": plan.plan_id, "goal": goal, "step_count": len(plan.steps)}
            )
        )

        while not plan.is_finished():
            ready_steps = plan.get_ready_steps()
            if not ready_steps:
                # Check for deadlocks / unresolvable dependencies
                pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
                if pending:
                    logger.error(f"Deadlock detected: {len(pending)} steps stuck pending with unmet dependencies.")
                    for s in pending:
                        s.status = StepStatus.FAILED
                        s.error = "Unmet dependency / deadlock"
                break

            logger.info(f"Running batch of {len(ready_steps)} parallel step(s): {[s.name for s in ready_steps]}")

            # Execute ready steps concurrently
            async def run_single_step(step: WorkflowStep):
                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                try:
                    res = await self.step_executor(step)
                    step.result = res
                    step.status = StepStatus.VERIFIED if res.get("channel_1_logical") else StepStatus.COMPLETED
                except Exception as ex:
                    logger.error(f"Step '{step.name}' failed: {ex}")
                    step.status = StepStatus.FAILED
                    step.error = str(ex)
                finally:
                    step.completed_at = time.time()

            await asyncio.gather(*(run_single_step(s) for s in ready_steps))

        plan.completed = True
        plan.success = all(s.status in [StepStatus.COMPLETED, StepStatus.VERIFIED] for s in plan.steps)
        logger.info(f"Plan [{plan.plan_id}] completed. Success: {plan.success}")

        # Broadcast plan completion
        mesh.publish(
            JarvisEvent(
                source="planner.orchestrator",
                type="plan.completed",
                data={"plan_id": plan.plan_id, "success": plan.success}
            )
        )
        return plan


orchestrator = MasterOrchestrator()
