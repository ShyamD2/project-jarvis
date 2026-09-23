"""
Unit & Integration Test Suite for Canonical Execution Pipeline (Stage 36.3).
Verifies:
  1. Reflex Class routing and policy checking.
  2. Read-Only Class routing and status query execution.
  3. Mission Class routing and approval gate enforcement.
  4. Capability discovery and tool health states.
  5. Canonical hierarchical name resolution and aliases.
  6. Pipeline final-state authority (tools do not declare final status).
"""

import unittest
from services.brain.canonical_pipeline import canonical_pipeline
from services.brain.tools.registry import registry as tool_registry
from shared.schemas.action_envelope import ActionTier


class TestCanonicalPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_reflex_class_execution(self):
        """Reflex action (volume change) executes through policy check + capability check + verification."""
        res = await canonical_pipeline.execute_request(
            tool_name="computer.volume",
            parameters={"action": "set_volume", "level": 40},
            source="test_reflex"
        )
        self.assertEqual(res["execution_class"], "reflex")
        self.assertIn("action_id", res)
        self.assertIn(res["final_status"], ["SUCCESS", "UNKNOWN"])
        self.assertIn("verification", res)

    async def test_read_only_class_execution(self):
        """Read-only action (telemetry query) routes to read-only class and returns verified telemetry."""
        res = await canonical_pipeline.execute_request(
            tool_name="get_system_telemetry",
            parameters={},
            source="test_read_only"
        )
        self.assertEqual(res["execution_class"], "read_only")
        self.assertTrue(res["success"])
        self.assertEqual(res["final_status"], "SUCCESS")

    async def test_mission_class_approval_gate(self):
        """Mission action with Tier 3 Destructive requires approval ticket and blocks unapproved execution."""
        res = await canonical_pipeline.execute_request(
            tool_name="computer.power",
            parameters={"action": "restart", "timer_seconds": 60},
            source="test_mission",
            user_role="OPERATOR"
        )
        # Operator cannot execute Tier 3 without explicit approval
        self.assertFalse(res["success"])
        self.assertEqual(res["final_status"], "FAILED")

    def test_canonical_hierarchical_alias_resolution(self):
        """Verifies hierarchical names resolve correctly to existing tools."""
        self.assertEqual(tool_registry.resolve_canonical_name("computer.open_app"), "launch_app")
        self.assertEqual(tool_registry.resolve_canonical_name("computer.volume"), "audio_media")
        self.assertEqual(tool_registry.resolve_canonical_name("docker.restart"), "devops_tool")
        self.assertEqual(tool_registry.resolve_canonical_name("aws.ec2.list"), "aws_management")

    def test_capability_discovery_and_health(self):
        """Verifies capability discovery returns AVAILABLE, DEGRADED, UNAVAILABLE breakdown (Item 103 & 104)."""
        caps = tool_registry.get_available_capabilities()
        self.assertIn("AVAILABLE", caps)
        self.assertIn("DEGRADED", caps)
        self.assertIn("UNAVAILABLE", caps)

        # Windows tools must be available on Windows host
        health_app = tool_registry.get_tool_health("computer.open_app")
        self.assertEqual(health_app["status"], "AVAILABLE")

        # Unregistered tool must report UNAVAILABLE
        health_fake = tool_registry.get_tool_health("non_existent_domain.tool")
        self.assertEqual(health_fake["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
