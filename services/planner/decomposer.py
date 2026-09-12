"""
Task Decomposition Engine for J.A.R.V.I.S. Master Planner.
Decomposes high-level instructions into executable DAGs of steps.
"""

from services.planner.workflow import WorkflowPlan, WorkflowStep, StepStatus
from shared.schemas.action_envelope import ActionTier, TargetWorld
from typing import Optional


class TaskDecomposer:
    def decompose(self, goal: str) -> WorkflowPlan:
        g = goal.lower()
        plan = WorkflowPlan(goal=goal)

        # 1. Workspace Preparation Workflow
        if "workspace" in g or "developer setup" in g:
            # Step 1: Turn on desk light (Physical)
            s1 = WorkflowStep(
                name="Desk Lamp Illumination",
                target_world=TargetWorld.PHYSICAL,
                target_agent="esp32_agent",
                command="control_physical_device",
                tier=ActionTier.TIER_1_SOFT,
                parameters={"device_id": "esp32_lab_01", "target": "desk_lamp", "state": True}
            )
            # Step 2: Open VS Code (Computer - parallel with Step 1)
            s2 = WorkflowStep(
                name="Launch Visual Studio Code",
                target_world=TargetWorld.COMPUTER,
                target_agent="windows_agent",
                command="launch_app",
                tier=ActionTier.TIER_1_SOFT,
                parameters={"app": "code", "args": ["d:/Project J.A.R.V.I.S"]}
            )
            # Step 3: Open Terminal (Computer - parallel with Step 1 & 2)
            s3 = WorkflowStep(
                name="Launch Windows Terminal",
                target_world=TargetWorld.COMPUTER,
                target_agent="windows_agent",
                command="launch_app",
                tier=ActionTier.TIER_1_SOFT,
                parameters={"app": "wt", "args": []}
            )
            # Step 4: Verification & Readiness Check (depends on s2 and s3)
            s4 = WorkflowStep(
                name="Verify Workspace Readiness",
                target_world=TargetWorld.COMPUTER,
                target_agent="windows_agent",
                command="verify_processes",
                tier=ActionTier.TIER_0_REFLEX,
                parameters={"process_names": ["Code", "WindowsTerminal"]},
                depends_on=[s2.step_id, s3.step_id]
            )
            plan.steps = [s1, s2, s3, s4]

        # 2. Cloud Deployment Workflow
        elif "deploy" in g or "terraform" in g:
            s1 = WorkflowStep(
                name="Validate Terraform Syntax",
                target_world=TargetWorld.DIGITAL,
                target_agent="terraform_agent",
                command="terraform_validate",
                tier=ActionTier.TIER_0_REFLEX,
                parameters={"env": "dev"}
            )
            s2 = WorkflowStep(
                name="Generate Terraform Speculative Plan",
                target_world=TargetWorld.DIGITAL,
                target_agent="terraform_agent",
                command="terraform_plan",
                tier=ActionTier.TIER_1_SOFT,
                parameters={"env": "dev"},
                depends_on=[s1.step_id]
            )
            s3 = WorkflowStep(
                name="Execute Terraform Apply",
                target_world=TargetWorld.DIGITAL,
                target_agent="terraform_agent",
                command="terraform_apply",
                tier=ActionTier.TIER_2_MUTATING,
                parameters={"env": "dev"},
                depends_on=[s2.step_id]
            )
            s4 = WorkflowStep(
                name="Synthetic Endpoint Health Verification",
                target_world=TargetWorld.DIGITAL,
                target_agent="aws_agent",
                command="health_check",
                tier=ActionTier.TIER_0_REFLEX,
                parameters={"endpoint": "/health"},
                depends_on=[s3.step_id]
            )
            plan.steps = [s1, s2, s3, s4]

        # 3. Default Generic Single-Step Plan
        else:
            s1 = WorkflowStep(
                name=f"Execute: {goal}",
                target_world=TargetWorld.DIGITAL,
                target_agent="core_agent",
                command="general_instruction",
                tier=ActionTier.TIER_1_SOFT,
                parameters={"query": goal}
            )
            plan.steps = [s1]

        return plan


decomposer = TaskDecomposer()
