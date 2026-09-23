"""
Unit Test Suite for Mission Resilience & State Recovery (Phase 36 Stage 36.8).
Verifies:
  1. ACID SQLite mission persistence and checkpoint snapshots.
  2. Crash recovery scan, idempotent resume, and safe abort.
  3. Circuit breaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
"""

import unittest
import time
import os
from services.planner.mission_persistence import MissionPersistenceManager
from services.planner.crash_recovery import crash_recovery
from services.security.circuit_breaker import CircuitBreakerRegistry, CircuitState


class TestPhase36MissionResilience(unittest.TestCase):
    def setUp(self):
        # Dedicated test DB path
        self.test_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_missions.db"))
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        self.persistence = MissionPersistenceManager(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_sqlite_mission_persistence_and_checkpoints(self):
        """Verifies mission saving, retrieval, checkpointing, and interrupted mission detection."""
        mission_data = {
            "id": "m_test_persistence_123",
            "name": "Deploy Kubernetes Cluster",
            "objective": "Setup production cluster in us-east-1",
            "current_phase": "execute",
            "progress_percent": 60,
            "risk_level": "TIER_2_MUTATING",
            "live_actions": [{"action": "init_vpc", "status": "verified"}]
        }
        self.persistence.save_mission(mission_data)

        # Retrieve
        saved = self.persistence.get_mission("m_test_persistence_123")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["name"], "Deploy Kubernetes Cluster")
        self.assertEqual(saved["current_phase"], "execute")

        # Save Checkpoint
        cp_id = self.persistence.save_checkpoint(
            mission_id="m_test_persistence_123",
            step_index=3,
            snapshot={"completed_actions": ["init_vpc", "create_subnets", "launch_nodes"]}
        )
        self.assertIsNotNone(cp_id)

        # Get latest checkpoint
        latest_cp = self.persistence.get_latest_checkpoint("m_test_persistence_123")
        self.assertIsNotNone(latest_cp)
        self.assertEqual(latest_cp["step_index"], 3)
        self.assertEqual(len(latest_cp["snapshot"]["completed_actions"]), 3)

        # Interrupted mission detection (since phase is 'execute')
        interrupted = self.persistence.get_interrupted_missions()
        self.assertTrue(any(m["mission_id"] == "m_test_persistence_123" for m in interrupted))

    def test_crash_recovery_engine_scan_and_resume(self):
        """Verifies crash recovery detects orphaned mission and resumes from next step."""
        from services.planner.mission_persistence import mission_persistence
        # Save a mission directly in global persistence
        m_id = "m_crash_sim_456"
        mission_persistence.save_mission({
            "id": m_id,
            "name": "Simulated Crashed Mission",
            "objective": "Test recovery",
            "current_phase": "execute",
            "progress_percent": 50
        })
        mission_persistence.save_checkpoint(m_id, step_index=2, snapshot={"completed_actions": ["step_0", "step_1"]})

        # Scan for crashes
        crashed = crash_recovery.scan_for_crashed_missions()
        self.assertTrue(any(c["mission_id"] == m_id for c in crashed))

        # Resume mission
        res = crash_recovery.resume_mission(m_id)
        self.assertTrue(res["success"])
        self.assertEqual(res["resumed_from_step"], 3)

        # Clean up by aborting
        abort_res = crash_recovery.abort_interrupted_mission(m_id)
        self.assertTrue(abort_res["success"])
        self.assertEqual(abort_res["status"], "ABORTED")

    def test_circuit_breaker_lifecycle(self):
        """Verifies CLOSED -> OPEN -> HALF_OPEN -> CLOSED state transitions."""
        cb_reg = CircuitBreakerRegistry(default_failure_threshold=3, default_recovery_timeout=0.1)
        tool_name = "test_flaky_service"

        # Initially CLOSED
        self.assertTrue(cb_reg.can_execute(tool_name))
        circuit = cb_reg.get_circuit(tool_name)
        self.assertEqual(circuit.state, CircuitState.CLOSED)

        # 1st failure
        cb_reg.record_failure(tool_name, "Timeout 1")
        self.assertEqual(circuit.state, CircuitState.CLOSED)
        self.assertTrue(cb_reg.can_execute(tool_name))

        # 2nd failure
        cb_reg.record_failure(tool_name, "Timeout 2")
        self.assertEqual(circuit.state, CircuitState.CLOSED)
        self.assertTrue(cb_reg.can_execute(tool_name))

        # 3rd failure: Must trip to OPEN
        cb_reg.record_failure(tool_name, "Timeout 3")
        self.assertEqual(circuit.state, CircuitState.OPEN)
        self.assertEqual(circuit.total_trips, 1)

        # Fast-fail while OPEN and timeout not elapsed
        # (temporarily set timeout higher to test fast-fail)
        circuit.recovery_timeout_seconds = 10.0
        self.assertFalse(cb_reg.can_execute(tool_name))

        # Wait for recovery timeout to elapse (reset to 0.05s)
        circuit.recovery_timeout_seconds = 0.05
        time.sleep(0.06)

        # Should transition to HALF_OPEN
        self.assertTrue(cb_reg.can_execute(tool_name))
        self.assertEqual(circuit.state, CircuitState.HALF_OPEN)

        # Successful probe call in HALF_OPEN resets to CLOSED
        cb_reg.record_success(tool_name)
        self.assertEqual(circuit.state, CircuitState.CLOSED)
        self.assertEqual(circuit.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
