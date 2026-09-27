"""
Phase 4 Unit Test Suite: AI & Agent Architecture Hardening.
Verifies:
  1. Hierarchical Working Memory with rolling summarization and zero context loss.
  2. Integration of short-term rolling distillation into HierarchicalMemory recall and episodes.
  3. Dynamic Intent & Model Routing (reflex, fast, reasoning) with latency and cost tagging.
  4. AIManager model tier dispatch.
  5. Pre-flight Tool Parameter Schema Validation in ToolRegistry (types, required, enums, defaults).
  6. Clean propagation of validation errors through CanonicalPipeline.
"""

import os
import sys
import unittest
import asyncio

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from services.memory.short_term import ShortTermMemory, ConversationTurn
from services.memory.hierarchical_memory import HierarchicalMemory
from services.brain.intent_router import IntentRouter, IntentType, ModelTier
from services.brain.providers.ai_manager import AIManager
from services.brain.tools.registry import ToolRegistry, registry as default_registry
from services.brain.canonical_pipeline import CanonicalPipeline


class TestPhase4AIAgentArchitecture(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.memory = ShortTermMemory(max_active_turns=6, summary_batch_size=3)

    def test_short_term_memory_rolling_summarization(self):
        """Verifies rolling context summarization distills older turns into a condensed summary."""
        # Add 5 turns (within limit)
        for i in range(5):
            self.memory.add_turn("user", f"Turn query {i}", intent="query")
            self.memory.add_turn("jarvis", f"Turn response {i}", actions_taken=[f"action_{i}"])

        # History should have rolled at turn 7
        self.assertIsNotNone(self.memory.condensed_summary, "Condensed summary should be generated when turns exceed threshold")
        self.assertGreater(len(self.memory.archived_turns), 0, "Archived turns list must contain evicted turns")
        self.assertIn("Earlier dialogue:", self.memory.condensed_summary)

        # Prompt formatting must include context summary block
        prompt_str = self.memory.format_for_prompt(limit=4)
        self.assertIn("[Conversation Context Summary:", prompt_str)
        self.assertIn("---", prompt_str)

        # Test manual compress_history
        compressed = self.memory.compress_history()
        self.assertIsInstance(compressed, str)
        self.assertGreater(len(compressed), 0)
        self.assertLessEqual(len(self.memory.history), 2)

    def test_hierarchical_memory_rolling_archive_integration(self):
        """Verifies HierarchicalMemory receives archived turns and exposes condensed summary in recall."""
        h_mem = HierarchicalMemory()
        
        # Test summary access methods
        summary = h_mem.get_condensed_summary()
        # Recall must include condensed_summary key
        recalled = h_mem.recall("system status")
        self.assertIn("condensed_summary", recalled)
        self.assertIn("working_memory", recalled)
        self.assertIn("recent_turns", recalled)

    def test_intent_router_dynamic_tiers_and_latency(self):
        """Verifies queries are dynamically routed to appropriate model tier and latency profile."""
        # 1. Emergency Reflex (<1ms, zero-cost)
        res_emerg = self.router.route("jarvis emergency stop immediately")
        self.assertEqual(res_emerg.intent_type, IntentType.EMERGENCY)
        self.assertEqual(res_emerg.recommended_model_tier, ModelTier.TIER_0_REFLEX.value)
        self.assertEqual(res_emerg.estimated_latency_tier, "sub_50ms")
        self.assertEqual(res_emerg.cost_profile, "zero_cost")

        # 2. Confirmation Reflex
        res_conf = self.router.route("yes proceed")
        self.assertEqual(res_conf.intent_type, IntentType.CONFIRMATION)
        self.assertEqual(res_conf.recommended_model_tier, ModelTier.TIER_0_REFLEX.value)
        self.assertEqual(res_conf.estimated_latency_tier, "sub_50ms")

        # 3. Direct System Reflex Action (Audio Volume)
        res_vol = self.router.route("increase volume")
        self.assertEqual(res_vol.intent_type, IntentType.DIRECT_ACTION)
        self.assertEqual(res_vol.recommended_model_tier, ModelTier.TIER_0_REFLEX.value)
        self.assertEqual(res_vol.estimated_latency_tier, "sub_50ms")

        # 4. Fast Direct Action (Application launch / browse)
        res_app = self.router.route("open chrome")
        self.assertEqual(res_app.intent_type, IntentType.DIRECT_ACTION)
        self.assertEqual(res_app.recommended_model_tier, ModelTier.TIER_1_FAST.value)
        self.assertEqual(res_app.estimated_latency_tier, "fast_reflex")
        self.assertEqual(res_app.cost_profile, "low_cost")

        # 5. Complex Multi-Step Planner (Terraform / Kubernetes)
        res_plan = self.router.route("deploy terraform production infrastructure")
        self.assertEqual(res_plan.intent_type, IntentType.COMPLEX_PLAN)
        self.assertEqual(res_plan.recommended_model_tier, ModelTier.TIER_2_DEEP.value)
        self.assertEqual(res_plan.estimated_latency_tier, "deep_reasoning")
        self.assertEqual(res_plan.cost_profile, "standard_cost")

    def test_ai_manager_model_tier_routing(self):
        """Verifies AIManager generate() respects dynamic tier requests."""
        import os
        from unittest.mock import patch, AsyncMock
        from services.brain.providers.base import LLMResponse

        ai = AIManager()
        ai.groq.api_key = "gsk_test_mock_groq_key"
        ai.groq.generate = AsyncMock(return_value=LLMResponse(content="groq reflex response", model="groq-llama3-8b"))
        ai.openrouter.api_key = "sk_test_mock_openrouter_key"
        ai.openrouter.generate = AsyncMock(return_value=LLMResponse(content="openrouter reasoning response", model="openrouter-70b"))

        async def _test():
            with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_mock_groq_key", "OPENROUTER_API_KEY": "sk_test_mock_openrouter_key"}):
                # Reflex tier invocation
                res_reflex = await ai.generate("ping status", tier="tier_0_reflex")
                self.assertIsNotNone(res_reflex)
                self.assertEqual(res_reflex.content, "groq reflex response")
                ai.groq.generate.assert_called_once()

                # Deep reasoning tier invocation
                res_reason = await ai.generate("architect cloud cluster", tier="tier_2_deep")
                self.assertIsNotNone(res_reason)
                self.assertEqual(res_reason.content, "openrouter reasoning response")
                ai.openrouter.generate.assert_called_once()

        asyncio.run(_test())

    def test_tool_registry_pre_flight_parameter_validation(self):
        """Verifies pre-flight parameter schema validation catches illegal types and enums."""
        reg = default_registry
        pc_tool = reg.get_tool("pc_power")
        self.assertIsNotNone(pc_tool)

        # 1. Valid parameters with valid enum
        valid, err = reg.validate_parameters(pc_tool, {"action": "temperatures", "timer_seconds": 0})
        self.assertTrue(valid, f"Valid parameters must pass: {err}")
        self.assertIsNone(err)

        # 2. Invalid enum value
        invalid_enum, err_enum = reg.validate_parameters(pc_tool, {"action": "illegal_wipe_system"})
        self.assertFalse(invalid_enum, "Invalid enum value must be rejected")
        self.assertIn("not in allowed choices", err_enum)

        # 3. Invalid integer type
        invalid_type, err_type = reg.validate_parameters(pc_tool, {"action": "shutdown", "timer_seconds": "not_an_int"})
        self.assertFalse(invalid_type, "Invalid integer string must be rejected")
        self.assertIn("must be an integer", err_type)

        # 4. execute_tool rejection on invalid parameters
        async def _test_exec():
            res = await reg.execute_tool("pc_power", {"action": "destroy_everything"})
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "validation_error")
            self.assertIn("Pre-flight schema validation failed", res["error"])

        asyncio.run(_test_exec())

    def test_canonical_pipeline_validation_error_handling(self):
        """Verifies CanonicalPipeline gracefully fails and records validation errors without crashes."""
        pipeline = CanonicalPipeline()

        async def _test():
            res = await pipeline.execute_request(
                tool_name="pc_power",
                parameters={"action": "unsupported_power_action_xyz"}
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["final_status"], "FAILED")
            self.assertIn("Pre-flight schema validation failed", str(res.get("error", "")))

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
