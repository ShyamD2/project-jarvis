"""
Fault Injection & Chaos Resilience Suite for Project J.A.R.V.I.S.
Tests critical safety, reliability, and fail-closed invariants under simulated system faults:
  1. test_llm_timeout_handled_gracefully: LLM timeout handled safely in degraded state without crash.
  2. test_malformed_tool_call_fails_closed: Malformed tool calls fail closed without false success.
  3. test_offline_dependency_degraded_state: External service outage reports DEGRADED state.
  4. test_expired_action_lease_rejected: Expired or replayed leases/nonces are rejected by permission engine.
  5. test_database_lock_recovery: Concurrent SQLite transactions and lock recovery.
"""

import asyncio
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from typing import Dict, Any, Optional, List, AsyncGenerator
from unittest.mock import AsyncMock, patch

from services.brain.agent_runtime import AgentRuntime
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from services.brain.tools.registry import registry as tool_registry
from services.observability.health_monitor import obs_health
from services.permission_engine.engine import permission_engine, PermissionEngine
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.database import get_sqlite_connection
from shared.sdk_python.jarvis_sdk.config import config


class TimeoutLLMProvider(BaseLLMProvider):
    """Simulates an external LLM provider that times out or disconnects."""
    name = "timeout_simulated_provider"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        await asyncio.sleep(0.01)
        raise asyncio.TimeoutError("Simulated LLM API network timeout (upstream gateway unresponsive)")

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        await asyncio.sleep(0.01)
        raise asyncio.TimeoutError("Simulated LLM streaming network timeout")
        if False:
            yield ""


class TestFaultInjectionResilience(unittest.IsolatedAsyncioTestCase):

    async def test_llm_timeout_handled_gracefully(self):
        """
        Simulate LLM upstream timeout.
        Assert that AgentRuntime catches the timeout, enters DEGRADED state,
        and returns a safe fallback message without crashing the process.
        """
        runtime = AgentRuntime(fast_provider=TimeoutLLMProvider(), deep_provider=TimeoutLLMProvider())

        # Execute turn with an instruction that requires LLM generation
        result = await runtime.execute_turn("Analyze cognitive trajectory and summarize system status")

        # Must not raise an unhandled exception or crash
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "DEGRADED")
        self.assertFalse(result.get("verified", True))
        self.assertEqual(result.get("actions_executed"), [])
        self.assertIn("response", result)
        response_lower = result["response"].lower()
        self.assertTrue(
            any(term in response_lower for term in ["timeout", "degraded", "fallback", "safe"]),
            f"Expected graceful degradation message, got: {result['response']}"
        )
        self.assertIn("latency_ms", result)

    async def test_malformed_tool_call_fails_closed(self):
        """
        Simulate malformed tool call arguments.
        Assert that the execution pipeline fails closed:
        - Rejects invalid parameter schema / types.
        - Fails on missing required parameters.
        - Returns success=False and verified=False.
        - Never produces a false success.
        """
        # Test 1: Invalid enum/type for tool parameters schema (e.g. string for integer, invalid enum)
        res_schema_invalid = await tool_registry.execute_tool(
            name="pc_power",
            parameters={"action": "INVALID_INJECTION_ACTION_DROP_TABLES", "timer_seconds": "not_an_int"},
            caller_agent="chaos_test"
        )
        self.assertFalse(res_schema_invalid["success"])
        self.assertFalse(res_schema_invalid["verified"])
        self.assertEqual(res_schema_invalid["status"], "validation_error")
        self.assertIn("error", res_schema_invalid)

        # Test 2: Missing required parameters on tools that mandate parameters (devops_tool requires subsystem & action)
        res_missing = await tool_registry.execute_tool(
            name="devops_tool",
            parameters={"invalid_field": 123},
            caller_agent="chaos_test"
        )
        self.assertFalse(res_missing["success"])
        self.assertFalse(res_missing["verified"])
        self.assertEqual(res_missing["status"], "validation_error")
        self.assertIn("subsystem", res_missing["error"])

        # Test 3: Unregistered tool lookup fails closed
        res_not_found = await tool_registry.execute_tool(
            name="malicious_unregistered_exploit",
            parameters={},
            caller_agent="chaos_test"
        )
        self.assertFalse(res_not_found["success"])
        self.assertFalse(res_not_found["verified"])
        self.assertEqual(res_not_found["status"], "not_found")

        # Test 4: Tool that throws an execution-time exception fails closed
        with patch.object(
            tool_registry.get_tool("pc_power"),
            "execute",
            side_effect=ValueError("Corrupted hardware register payload")
        ):
            res_exec_fail = await tool_registry.execute_tool(
                name="pc_power",
                parameters={"action": "temperatures"},
                caller_agent="canonical_pipeline"  # Bypass confirmation gate to test execution failure
            )
            self.assertFalse(res_exec_fail["success"])
            self.assertFalse(res_exec_fail["verified"])
            self.assertEqual(res_exec_fail["status"], "error")
            self.assertIn("Corrupted hardware register payload", res_exec_fail["error"])

    def test_offline_dependency_degraded_state(self):
        """
        Simulate external dependency / subsystem outage.
        Assert that health monitoring transitions to DEGRADED state,
        accurately tracking the outage without crashing or reporting false nominal health.
        """
        dependency_name = "aws_cloud"
        error_message = "Simulated outage: Connection reset by peer (AWS STS endpoint unreachable)"

        # Record external failure in health monitor
        obs_health.record_subsystem_error(dependency_name, error_message)

        report = obs_health.get_health_report()
        self.assertIsInstance(report, dict)
        self.assertEqual(report["overall_status"], "DEGRADED")

        subsystems = report.get("subsystems", {})
        self.assertIn(dependency_name, subsystems)
        self.assertEqual(subsystems[dependency_name]["status"], "DEGRADED")
        self.assertGreaterEqual(subsystems[dependency_name]["error_count"], 1)
        self.assertEqual(subsystems[dependency_name]["details"]["last_error"], error_message)

        # Restore subsystem to verify recovery
        obs_health.ping(dependency_name, status="ONLINE", details={"status": "Restored"})
        report_recovered = obs_health.get_health_report()
        self.assertEqual(report_recovered["subsystems"][dependency_name]["status"], "ONLINE")

    def test_expired_action_lease_rejected(self):
        """
        Verify expired or replayed nonces/leases are rejected by the permission engine.
        Ensures fail-closed security invariants:
        - Expired ActionLeases are rejected immediately with BLOCKED_EXPIRED.
        - Consumed ActionLeases cannot be replayed (BLOCKED_REPLAY).
        - Expired capability leases in PermissionEngine.evaluate are blocked.
        - Replay attacks on nonces are detected and blocked.
        """
        engine = PermissionEngine()

        # 1. Test Expired Universal ActionLease evaluated via engine.evaluate
        lease = engine.issue_action_lease(
            tool_name="pc_power",
            parameters={"action": "shutdown"},
            ttl_seconds=300.0
        )
        lease.expires_at = time.time() - 10.0  # Force expiration

        action_expired_lease = ActionEnvelope(
            name="pc_power",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"action": "shutdown"}
        )
        dec_lease_expired = engine.evaluate(action_expired_lease, approval_token=lease.lease_id, user_role="OWNER")
        self.assertFalse(dec_lease_expired.authorized)
        self.assertIn("BLOCKED_EXPIRED", dec_lease_expired.rationale)

        # 2. Test Replayed Universal ActionLease (Single-use consumption)
        fresh_lease = engine.issue_action_lease(
            tool_name="pc_power",
            parameters={"action": "shutdown"},
            ttl_seconds=300.0
        )
        action_valid_lease = ActionEnvelope(
            name="pc_power",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"action": "shutdown"}
        )
        dec_lease_first = engine.evaluate(action_valid_lease, approval_token=fresh_lease.lease_id, user_role="OWNER")
        self.assertTrue(dec_lease_first.authorized)

        # Replay attempt -> Must be BLOCKED_REPLAY
        action_replay_lease = ActionEnvelope(
            name="pc_power",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"action": "shutdown"}
        )
        dec_lease_replay = engine.evaluate(action_replay_lease, approval_token=fresh_lease.lease_id, user_role="OWNER")
        self.assertFalse(dec_lease_replay.authorized)
        self.assertIn("BLOCKED_REPLAY", dec_lease_replay.rationale)

        # 3. Test Expired Capability Lease in PermissionEngine (action_id matching)
        action = ActionEnvelope(
            name="pc_power",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"action": "shutdown"}
        )
        dec_1 = engine.evaluate(action, user_role="OWNER")
        self.assertFalse(dec_1.authorized)
        self.assertTrue(dec_1.requires_explicit_approval)
        appr_id = dec_1.approval_id
        self.assertIsNotNone(appr_id)

        # Operator approves the request
        self.assertTrue(engine.approve_request(appr_id, token=config.master_secret))

        # Test Expired: manipulate approved timestamp past lease TTL
        pending_obj = engine._pending_approvals[appr_id]
        pending_obj.approved_at = time.time() - 600.0  # 10 minutes ago (> 300s TTL)

        dec_expired = engine.evaluate(action, user_role="OWNER")
        self.assertFalse(dec_expired.authorized)
        self.assertIn("BLOCKED_EXPIRED", dec_expired.rationale)

        # 4. Test Nonce Replay in PermissionEngine
        action_replay = ActionEnvelope(
            name="pc_power",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_3_DESTRUCTIVE,
            parameters={"action": "shutdown"}
        )
        dec_init = engine.evaluate(action_replay, user_role="OWNER")
        appr_id_replay = dec_init.approval_id
        self.assertTrue(engine.approve_request(appr_id_replay, token=config.master_secret))

        # First consumption succeeds
        dec_authorized = engine.evaluate(action_replay, user_role="OWNER")
        self.assertTrue(dec_authorized.authorized)
        self.assertIn("AUTHORIZED_BY_LEASE", dec_authorized.rationale)

        # Simulated replay attack: attacker attempts to reuse consumed nonce
        lease_replay_obj = engine._pending_approvals[appr_id_replay]
        engine._active_leases[action_replay.action_id] = lease_replay_obj

        dec_replayed = engine.evaluate(action_replay, user_role="OWNER")
        self.assertFalse(dec_replayed.authorized)
        self.assertIn("BLOCKED_REPLAY", dec_replayed.rationale)

    def test_database_lock_recovery(self):
        """
        Verify SQLite concurrency resilience, WAL mode, and lock contention recovery.
        Under concurrent write transactions across multiple threads, ensure
        transactions recover cleanly via busy_timeout without unhandled database crashes.
        """
        temp_dir = tempfile.mkdtemp(prefix="jarvis_chaos_db_")
        db_path = os.path.join(temp_dir, "test_chaos_concurrency.db")

        try:
            # Initialize database schema
            with get_sqlite_connection(db_path, timeout=10.0, enable_wal=True) as conn:
                conn.execute("CREATE TABLE test_ledger (id INTEGER PRIMARY KEY, worker_id TEXT, val TEXT);")
                conn.commit()

            errors = []
            successful_writes = []

            def worker(worker_id: str, count: int):
                try:
                    conn = get_sqlite_connection(db_path, timeout=10.0, enable_wal=True)
                    for i in range(count):
                        with conn:
                            conn.execute(
                                "INSERT INTO test_ledger (worker_id, val) VALUES (?, ?);",
                                (worker_id, f"payload_{i}")
                            )
                        time.sleep(0.005)
                    conn.close()
                    successful_writes.append(worker_id)
                except Exception as e:
                    errors.append((worker_id, str(e)))

            # Launch 5 concurrent threads hammering the SQLite database simultaneously
            threads = []
            for t_idx in range(5):
                t = threading.Thread(target=worker, args=(f"worker_{t_idx}", 10))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=15.0)

            # All 5 workers must succeed without lock starvation or crash
            self.assertEqual(len(errors), 0, f"Concurrent SQLite workers failed with errors: {errors}")
            self.assertEqual(len(successful_writes), 5)

            # Verify all 50 records were written ACID-safely
            with get_sqlite_connection(db_path, timeout=5.0, enable_wal=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM test_ledger;")
                count = cursor.fetchone()[0]
                self.assertEqual(count, 50)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
