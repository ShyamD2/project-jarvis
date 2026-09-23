"""
Chaos Testing Suite for Project J.A.R.V.I.S. (Phase 36 Stage 36.9).
Injects harsh failure modes and verifies zero-crash fault tolerance:
  1. Subagent/tool unhandled exception and crash recovery.
  2. Circuit breaker auto-tripping under repeated failures.
  3. Emergency Stand-Down rapid engagement and recovery.
  4. Contract corruption / state tampering rejection.
  5. MQTT broker network partition and offline fallback.
"""

import unittest
from unittest.mock import patch, AsyncMock
from services.brain.canonical_pipeline import canonical_pipeline
from services.security.circuit_breaker import circuit_breaker
from agents.intelligence.emergency_stop import emergency_stop
from services.iot_agent.mqtt_buffer import mqtt_buffer
from shared.schemas.verification_contract import VerificationStatus, VerificationResult


class TestChaosResilience(unittest.IsolatedAsyncioTestCase):
    async def test_chaos_subagent_unhandled_exception_handled_safely(self):
        """Tool throws unhandled RuntimeError; pipeline must not crash, returning FAILED status cleanly."""
        with patch("services.brain.tools.registry.registry.execute_tool", side_effect=RuntimeError("Chaos crash: kernel panic simulated")):
            res = await canonical_pipeline.execute_request(
                tool_name="system.status",
                parameters={},
                source="test_chaos"
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["final_status"], "FAILED")
            self.assertIn("action_id", res)
            self.assertIn("Chaos crash", str(res.get("result", {}).get("error", "")))

    async def test_chaos_circuit_breaker_auto_tripping(self):
        """Tool fails repeatedly; circuit breaker trips to OPEN and fast-fails subsequent requests."""
        flaky_tool = "computer.power"
        canonical_name = "pc_power"
        circuit_breaker.reset(flaky_tool)
        circuit_breaker.reset(canonical_name)

        # Force 3 consecutive failures via circuit_breaker.record_failure
        circuit_breaker.record_failure(canonical_name, "Chaos fault 1")
        circuit_breaker.record_failure(canonical_name, "Chaos fault 2")
        circuit_breaker.record_failure(canonical_name, "Chaos fault 3")

        # Circuit must be OPEN
        self.assertFalse(circuit_breaker.can_execute(canonical_name))

        # Pipeline request must now fast-fail without invoking tool execution
        res = await canonical_pipeline.execute_request(
            tool_name=flaky_tool,
            parameters={"action": "temperatures"},
            source="test_chaos",
            user_role="OWNER"
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "circuit_tripped")
        self.assertEqual(res["final_status"], "FAILED")

        # Cleanup
        circuit_breaker.reset(flaky_tool)
        circuit_breaker.reset(canonical_name)

    async def test_chaos_emergency_stand_down_rapid_toggle(self):
        """Emergency Stand-Down halts all pipeline requests immediately; reset restores operation."""
        # 1. Trigger Stand-Down
        emergency_stop.trigger_emergency_stop(reason="Simulated physical hotkey trip")
        self.assertTrue(emergency_stop.is_stopped)

        # 2. Execution must be halted
        res_halted = await canonical_pipeline.execute_request(
            tool_name="system.status",
            parameters={},
            source="test_chaos"
        )
        self.assertFalse(res_halted["success"])
        self.assertEqual(res_halted["status"], "emergency_halted")
        self.assertEqual(res_halted["final_status"], "FAILED")

        # 3. Reset Stand-Down
        emergency_stop.resume_operations()
        self.assertFalse(emergency_stop.is_stopped)

        # 4. Pipeline resumes normal execution
        res_resumed = await canonical_pipeline.execute_request(
            tool_name="system.status",
            parameters={},
            source="test_chaos"
        )
        self.assertTrue(res_resumed["success"])
        self.assertEqual(res_resumed["final_status"], "SUCCESS")

    async def test_chaos_tampered_verification_contract(self):
        """Verification engine returns UNKNOWN or corrupted result; pipeline assigns UNKNOWN, never SUCCESS."""
        with patch("services.verification.verification_engine.verification_engine.verify_action_execution",
                   return_value=VerificationResult(
                       action_id="act_tampered",
                       status=VerificationStatus.UNKNOWN,
                       failure_reason="Corrupted verification state: telemetry checksum mismatch"
                   )):
            res = await canonical_pipeline.execute_request(
                tool_name="system.status",
                parameters={},
                source="test_chaos"
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["final_status"], "UNKNOWN")

    def test_chaos_mqtt_network_partition_buffering(self):
        """When MQTT broker connection drops, messages are buffered safely without data loss."""
        mqtt_buffer.clear()
        
        # Enqueue 5 telemetry packets during simulated partition
        for i in range(5):
            mqtt_buffer.enqueue(f"devices/iot/sensor_{i}", {"temperature": 22.5 + i})

        self.assertEqual(mqtt_buffer.get_buffered_count(), 5)

        # Reconnect drain
        drained_count = 0
        def sink(topic, payload):
            nonlocal drained_count
            drained_count += 1
            return True

        res = mqtt_buffer.drain(sink)
        self.assertEqual(res["sent_count"], 5)
        self.assertEqual(mqtt_buffer.get_buffered_count(), 0)


if __name__ == "__main__":
    unittest.main()
