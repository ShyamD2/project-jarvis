"""
Integration tests for J.A.R.V.I.S. Brain & Agent Runtime.
Tests intent routing, tool execution, dual-channel verification, and emergency handling.
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.brain.agent_runtime import AgentRuntime
from services.brain.intent_router import IntentRouter, IntentType
from services.brain.providers.mock_provider import MockLLMProvider
from shared.sdk_python.jarvis_sdk.config import config


class TestJarvisBrain(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.runtime = AgentRuntime(
            fast_provider=MockLLMProvider("fast-brain"),
            deep_provider=MockLLMProvider("deep-brain")
        )
        config.emergency_stand_down = False
        from mocks.virtual_esp32.simulator import VirtualESP32
        self.sim = VirtualESP32()
        self.sim.start()

    def test_intent_classification(self):
        # Emergency
        r1 = self.router.route("JARVIS, stand down immediately!")
        self.assertEqual(r1.intent_type, IntentType.EMERGENCY)

        # Direct Action (Physical)
        r2 = self.router.route("JARVIS, turn on the light")
        self.assertEqual(r2.intent_type, IntentType.DIRECT_ACTION)
        self.assertEqual(r2.target_tool, "control_physical_device")

        # Complex Plan
        r3 = self.router.route("JARVIS, deploy my application using terraform")
        self.assertEqual(r3.intent_type, IntentType.COMPLEX_PLAN)

        # Conversation
        r4 = self.router.route("Good morning Jarvis, what is the protocol today?")
        self.assertEqual(r4.intent_type, IntentType.CONVERSATION)

    async def test_physical_action_execution_and_verification(self):
        result = await self.runtime.execute_turn("JARVIS, turn on the desk lamp")
        self.assertEqual(result["intent"], "direct_action")
        self.assertTrue(len(result["actions_executed"]) > 0)
        action = result["actions_executed"][0]
        self.assertEqual(action["tool"], "control_physical_device")
        self.assertTrue(action["result"]["success"])
        self.assertTrue(action["verified"])
        self.assertIn("desk lamp", result["response"].lower())

    async def test_prepare_workspace_execution(self):
        result = await self.runtime.execute_turn("JARVIS, prepare my workspace")
        self.assertTrue(len(result["actions_executed"]) > 0)
        action = result["actions_executed"][0]
        self.assertEqual(action["tool"], "prepare_workspace")
        self.assertTrue(action["verified"])
        self.assertIn("workspace", result["response"].lower())

    async def test_emergency_stand_down(self):
        result = await self.runtime.execute_turn("JARVIS, stand down!")
        self.assertEqual(result["intent"], "emergency")
        self.assertTrue(config.emergency_stand_down)
        self.assertIn("Standing down", result["response"])


if __name__ == "__main__":
    unittest.main()
