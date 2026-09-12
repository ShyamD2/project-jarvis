"""
Integration tests for J.A.R.V.I.S. Master Planner and Orchestrator.
Tests task DAG dependencies, parallel step execution, and verification.
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.planner.workflow import WorkflowPlan, WorkflowStep, StepStatus
from services.planner.decomposer import TaskDecomposer
from services.planner.orchestrator import MasterOrchestrator
from shared.schemas.action_envelope import ActionTier, TargetWorld


class TestJarvisPlanner(unittest.IsolatedAsyncioTestCase):
    def test_workflow_dag_dependency_resolution(self):
        plan = WorkflowPlan(goal="Test DAG")
        s1 = WorkflowStep(name="Step 1", target_world=TargetWorld.PHYSICAL, target_agent="esp32", command="cmd1")
        s2 = WorkflowStep(name="Step 2", target_world=TargetWorld.COMPUTER, target_agent="win", command="cmd2", depends_on=[s1.step_id])

        plan.steps = [s1, s2]

        # Initially, only Step 1 is ready
        ready = plan.get_ready_steps()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].name, "Step 1")

        # Once Step 1 completes, Step 2 becomes ready
        s1.status = StepStatus.COMPLETED
        ready2 = plan.get_ready_steps()
        self.assertEqual(len(ready2), 1)
        self.assertEqual(ready2[0].name, "Step 2")

    async def test_full_orchestrator_execution(self):
        orchestrator = MasterOrchestrator()
        plan = await orchestrator.execute_goal("JARVIS, prepare my workspace")

        self.assertTrue(plan.completed)
        self.assertTrue(plan.success)
        self.assertEqual(len(plan.steps), 4)

        # Check all steps verified
        for s in plan.steps:
            self.assertIn(s.status, [StepStatus.COMPLETED, StepStatus.VERIFIED])
            self.assertIsNotNone(s.started_at)
            self.assertIsNotNone(s.completed_at)

        # Verify dependency order: Step 4 must have started AFTER Step 2 and Step 3 completed
        step2 = next(s for s in plan.steps if s.name == "Launch Visual Studio Code")
        step3 = next(s for s in plan.steps if s.name == "Launch Windows Terminal")
        step4 = next(s for s in plan.steps if s.name == "Verify Workspace Readiness")

        self.assertGreaterEqual(step4.started_at, step2.completed_at)
        self.assertGreaterEqual(step4.started_at, step3.completed_at)


if __name__ == "__main__":
    unittest.main()
