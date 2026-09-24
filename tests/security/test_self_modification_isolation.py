"""
Security Regression Test: Autonomous Self-Modification Isolation & Guardrails (Item 8).
Invariant:
  Autonomous code evolution (DarwinianOptimizer) and dynamic skill synthesis (SkillSynthesizer)
  are strictly classified as TIER_3_DESTRUCTIVE and SUPERVISED_ONLY.
  Execution without an immutable cryptographic ActionLease operator approval token
  MUST strictly fail with SECURITY_VIOLATION.
"""

import unittest
import asyncio
from services.brain.darwinian_optimizer import darwinian_optimizer
from services.brain.skill_synthesizer import skill_synthesizer
from services.permission_engine.engine import permission_engine


class TestSelfModificationIsolation(unittest.TestCase):
    def test_skill_synthesizer_rejects_unauthorized_execution(self):
        """Invariant: Synthesizing a skill without an ActionLease fails immediately."""
        res = asyncio.run(
            skill_synthesizer.synthesize_skill(
                name="unauthorized_test_tool",
                description="Should be rejected",
                prompt_or_commands=["dir"],
                approval_token=None
            )
        )
        self.assertFalse(res["success"])
        self.assertIn("SECURITY_VIOLATION", res["error"])

    def test_skill_synthesizer_rejects_replayed_token(self):
        """Invariant: Replayed ActionLease cannot be reused to synthesize skills."""
        lease = permission_engine.issue_action_lease("synthesize_skill", {"name": "replay_tool"})
        token = lease.lease_id

        # First use succeeds
        res1 = asyncio.run(
            skill_synthesizer.synthesize_skill(
                name="replay_tool_1",
                description="First use",
                prompt_or_commands=["echo 1"],
                approval_token=token
            )
        )
        self.assertTrue(res1["success"])

        # Second use with same token must fail
        res2 = asyncio.run(
            skill_synthesizer.synthesize_skill(
                name="replay_tool_2",
                description="Second use (replay)",
                prompt_or_commands=["echo 2"],
                approval_token=token
            )
        )
        self.assertFalse(res2["success"])
        self.assertIn("SECURITY_VIOLATION", res2["error"])

    def test_darwinian_optimizer_rejects_unauthorized_evolution(self):
        """Invariant: Evolving tool code without an ActionLease raises PermissionError."""
        def dummy_tool():
            return "ok"

        with self.assertRaises(PermissionError) as ctx:
            darwinian_optimizer.evolve_tool_wrapper("dummy_tool", dummy_tool, approval_token=None)
        self.assertIn("SECURITY_VIOLATION", str(ctx.exception))

    def test_darwinian_optimizer_rejects_replayed_token(self):
        """Invariant: Replaying ActionLease on DarwinianOptimizer fails."""
        def dummy_tool():
            return "ok"

        lease = permission_engine.issue_action_lease("evolve_tool", {"tool": "dummy_tool"})
        token = lease.lease_id

        # First evolution succeeds
        wrapped = darwinian_optimizer.evolve_tool_wrapper("dummy_tool", dummy_tool, approval_token=token)
        self.assertTrue(callable(wrapped))

        # Replay attempt fails
        with self.assertRaises(PermissionError) as ctx:
            darwinian_optimizer.evolve_tool_wrapper("dummy_tool", dummy_tool, approval_token=token)
        self.assertIn("SECURITY_VIOLATION", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
