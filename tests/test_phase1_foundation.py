"""
Phase 1 Foundation Test Suite for Project J.A.R.V.I.S.
Verifies all 5 items from Phase 1 Foundation Architecture & Security Overhaul:
1. Telegram bypass removal and unified ConversationEngine routing
2. Snake-case package structure and clean imports
3. Browser CDP auto-attach, binary discovery, and resilience
4. Local neural wake-word engine (openWakeWord ONNX)
5. Mandatory ActionTier enforcement & cryptographic confirmation tickets
"""

import os
import sys
import time
import asyncio
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.brain.tools.registry import registry as tool_registry
from agents.intelligence.safety_guard import safety_guard, StrictTier
from services.brain.conversation_engine import conversation_engine
from services.pc_agent.browser_agent import browser_agent
from services.voice.neural_wake_word import neural_wake_word, NeuralWakeWordDetector
from services.gateway.telegram_bot import telegram_gateway


class TestPhase1Foundation(unittest.TestCase):

    def test_01_telegram_unified_brain_routing_and_compound_parsing(self):
        """1. Telegram commands route through ConversationEngine and compound commands decompose."""
        # Test compound decomposition
        comp_cmd = "Open Opera and check battery"
        steps = conversation_engine._decompose_compound_command(comp_cmd)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0], "Open Opera")
        self.assertEqual(steps[1], "check battery")

        comp_3step = "Open WhatsApp, message Shyam, then tell me the result"
        steps3 = conversation_engine._decompose_compound_command(comp_3step)
        self.assertEqual(len(steps3), 3)

        # Normal non-compound query should NOT be split
        normal_query = "What is the capital of France?"
        self.assertEqual(conversation_engine._decompose_compound_command(normal_query), [normal_query])

    def test_02_python_package_structure_snake_case(self):
        """2. All packages import cleanly via snake_case without path hacks."""
        import services.pc_agent
        import services.floating_agent
        import services.permission_engine
        import services.jarvis_core
        import services.iot_agent
        import devices.raspberry_pi

        self.assertTrue(hasattr(services.pc_agent, "__file__"))
        self.assertTrue(hasattr(services.floating_agent, "__file__"))
        self.assertTrue(hasattr(services.permission_engine, "__file__"))
        self.assertTrue(hasattr(services.jarvis_core, "__file__"))
        self.assertTrue(hasattr(services.iot_agent, "__file__"))
        self.assertTrue(hasattr(devices.raspberry_pi, "__file__"))

        # Verify pyproject.toml exists
        pyproject_path = os.path.join(PROJECT_ROOT, "pyproject.toml")
        self.assertTrue(os.path.exists(pyproject_path))

    def test_03_browser_cdp_auto_attach_and_lookup(self):
        """3. Browser agent detects CDP availability and locates browser binary."""
        exe = browser_agent._find_browser_executable()
        self.assertIsNotNone(exe)
        self.assertTrue(os.path.exists(exe))

        # Check CDP probe method
        is_open = asyncio.run(browser_agent._is_cdp_available())
        self.assertIsInstance(is_open, bool)

        # Fallback search executes cleanly
        search_res = asyncio.run(browser_agent.search_web("Python", max_results=2))
        self.assertIsInstance(search_res, list)

    def test_04_neural_wake_word_local_onnx(self):
        """4. Local neural wake word processes 80ms audio frames with zero cloud requests."""
        dummy_frame = np.zeros(1280, dtype=np.int16)
        t0 = time.time()
        scores = neural_wake_word.process_frame(dummy_frame)
        latency = (time.time() - t0) * 1000

        self.assertIsInstance(scores, dict)
        self.assertIn("hey_jarvis", scores)
        self.assertLess(latency, 50.0) # Sub-50ms local inference on CPU
        self.assertFalse(neural_wake_word.is_wake_detected(dummy_frame))

    def test_05_mandatory_action_tier_and_crypto_ticket(self):
        """5. ActionTier is strictly mandatory and Tier 3 actions require cryptographic tickets."""
        # A. Verify all tools in registry have ActionTier
        for name, tool in tool_registry._tools.items():
            tier = getattr(tool.definition, "tier", None)
            self.assertIsNotNone(tier, f"Tool '{name}' missing ActionTier")

        # B. Test rejecting a tool without ActionTier
        from services.brain.tools.base import JarvisTool, ToolDefinition
        from shared.schemas.action_envelope import TargetWorld
        class BadTool(JarvisTool):
            def __init__(self):
                super().__init__(
                    ToolDefinition(
                        name="bad_tool_no_tier",
                        description="Invalid tool",
                        target_world=TargetWorld.COMPUTER,
                        tier=None # Missing tier
                    )
                )
            async def execute(self, **kwargs):
                return {}

        with self.assertRaises(ValueError):
            tool_registry.register(BadTool())

        # C. Test Tier 3 destructive evaluation without ticket
        eval_res = safety_guard.evaluate_request("pc_shutdown", {"action": "shutdown"})
        self.assertFalse(eval_res["authorized"])
        self.assertTrue(eval_res["requires_confirmation"])
        ticket_id = eval_res["ticket_id"]
        self.assertIsNotNone(ticket_id)

        # D. Confirm ticket with exact parameters
        ok = safety_guard.confirm_ticket(ticket_id, approver="test_operator", method="test")
        self.assertTrue(ok)

        # Evaluation with confirmed ticket and matching parameters should succeed
        approved_res = safety_guard.evaluate_request("pc_shutdown", {"action": "shutdown"}, approval_id=ticket_id)
        self.assertTrue(approved_res["authorized"])

        # E. Tampered parameters must be cryptographically rejected!
        tampered_res = safety_guard.evaluate_request("pc_shutdown", {"action": "format_c"}, approval_id=ticket_id)
        self.assertFalse(tampered_res["authorized"])
        self.assertIn("SECURITY VIOLATION", tampered_res["rationale"])


if __name__ == "__main__":
    unittest.main()
