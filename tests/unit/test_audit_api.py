"""
Unit Test: Audit Ledger First-Class API Endpoints (/api/v1/audit/events, /api/v1/audit/recent).
Verifies:
  1. GET /api/v1/audit/events returns mathematical hash integrity validation and event list.
  2. GET /api/v1/audit/recent filters operations within the specified time window.
"""

import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from services.jarvis_core.routes.api_v1 import router as api_v1_router
from services.observability.chained_audit_ledger import chained_audit_ledger

app = FastAPI()
app.include_router(api_v1_router)
client = TestClient(app)


class TestAuditAPI(unittest.TestCase):
    def setUp(self):
        # Record a test entry
        chained_audit_ledger.record_action(
            intent="Test audit endpoint",
            tool="system_status_report",
            parameters={"test": True},
            authorization_ticket="ticket_test_audit",
            verification_status=True,
            result="SUCCESS"
        )

    def test_get_audit_events(self):
        """Invariant: /api/v1/audit/events returns verified ledger continuity."""
        resp = client.get("/api/v1/audit/events?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["integrity"]["valid"])
        self.assertGreater(data["total_events"], 0)

    def test_get_recent_audit_actions(self):
        """Invariant: /api/v1/audit/recent answers what JARVIS did recently."""
        resp = client.get("/api/v1/audit/recent?hours=1.0")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["window_hours"], 1.0)
        self.assertGreater(data["total_actions"], 0)
        self.assertTrue(any(a["tool"] == "system_status_report" for a in data["actions"]))


if __name__ == "__main__":
    unittest.main()
