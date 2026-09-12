"""
Integration tests for J.A.R.V.I.S. Action Fabric & Multi-World Agents.
Verifies action routing across Physical, Computer, and Digital domains with dual-channel verification.
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents.action_dispatcher import ActionDispatcher
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.sdk_python.jarvis_sdk.config import config


class TestActionFramework(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dispatcher = ActionDispatcher()
        config.emergency_stand_down = False
        from mocks.virtual_esp32.simulator import VirtualESP32
        self.sim = VirtualESP32()
        self.sim.start()

    async def test_physical_world_action(self):
        action = ActionEnvelope(
            name="toggle_light",
            target_world=TargetWorld.PHYSICAL,
            target_agent="esp32_agent",
            tier=ActionTier.TIER_1_SOFT,
            parameters={"device_id": "esp32_lab_01", "target": "desk_lamp", "state": True}
        )
        res = await self.dispatcher.dispatch(action)
        self.assertTrue(res["success"])
        self.assertEqual(res["world"], "physical")
        self.assertTrue(res["verification"]["logical_verified"])
        self.assertTrue(res["verification"]["sensory_verified"])
        self.assertGreater(res["verification"]["details"]["channel_2_lux"], 600.0)

    async def test_computer_world_action(self):
        action = ActionEnvelope(
            name="execute_powershell",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_1_SOFT,
            parameters={"script": "Write-Output 'JARVIS Windows Agent Nominal'"}
        )
        res = await self.dispatcher.dispatch(action)
        self.assertTrue(res["success"])
        self.assertEqual(res["world"], "computer")
        self.assertIn("JARVIS Windows Agent Nominal", res["verification"]["details"]["stdout"])

    async def test_digital_world_action(self):
        action = ActionEnvelope(
            name="check_cloud",
            target_world=TargetWorld.DIGITAL,
            target_agent="aws_agent",
            tier=ActionTier.TIER_0_REFLEX
        )
        res = await self.dispatcher.dispatch(action)
        self.assertTrue(res["success"])
        self.assertEqual(res["world"], "digital")
        self.assertEqual(res["verification"]["details"]["status"], "nominal")


if __name__ == "__main__":
    unittest.main()
