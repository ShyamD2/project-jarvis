"""
Unit & integration tests for the Observability & Audit Engine.
"""

import unittest
import time
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.observability import (
    obs_logger,
    obs_metrics,
    obs_tracer,
    obs_audit,
    obs_recorder,
    obs_health
)


class TestObservabilitySubsystem(unittest.TestCase):
    def test_logger(self):
        obs_logger.info("Test info message", key="val")
        logs = obs_logger.get_recent_logs(limit=5)
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[-1]["level"], "INFO")

    def test_metrics(self):
        obs_metrics.increment("test.counter", 3)
        obs_metrics.record_latency("test.latency", 45.2)
        snap = obs_metrics.get_metrics_snapshot()
        self.assertIn("test.counter", snap["counters"])
        self.assertEqual(snap["counters"]["test.counter"], 3)
        self.assertIn("test.latency", snap["latencies"])
        self.assertIn("telemetry", snap)
        self.assertIn("cpu_percent", snap["telemetry"])

    def test_tracing(self):
        with obs_tracer.trace("test_operation", tags={"env": "test"}) as span:
            time.sleep(0.01)
            self.assertEqual(span.status, "ACTIVE")
        self.assertEqual(span.status, "SUCCESS")
        self.assertGreater(span.duration_ms, 0)

    def test_audit(self):
        event = obs_audit.record_event(
            event_type="POLICY_DECISION",
            actor="test_agent",
            target="test_resource",
            risk_level="HIGH",
            status="BLOCKED",
            details={"reason": "approval required"}
        )
        self.assertIn("audit_id", event)
        history = obs_audit.query_audit_trail(event_type="POLICY_DECISION", limit=5)
        self.assertGreater(len(history), 0)

    def test_event_recorder(self):
        m_entry = obs_recorder.record_mission_event("m_test_99", "PHASE_CHANGED", "execute")
        self.assertEqual(m_entry["entity_id"], "m_test_99")
        timeline = obs_recorder.get_mission_timeline("m_test_99")
        self.assertEqual(len(timeline), 1)

    def test_health_monitor(self):
        obs_health.ping("test_subsystem", "ONLINE")
        rep = obs_health.get_health_report()
        self.assertIn("test_subsystem", rep["subsystems"])
        self.assertEqual(rep["subsystems"]["test_subsystem"]["status"], "ONLINE")


if __name__ == "__main__":
    unittest.main()
