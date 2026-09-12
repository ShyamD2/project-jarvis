"""
Integration tests for J.A.R.V.I.S. Core API.
Tests event ingestion, action blast-radius filtering, state retrieval, and emergency circuit breaker.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app
from shared.sdk_python.jarvis_sdk.config import config


class TestJarvisCoreAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        config.emergency_stand_down = False

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["service"], "jarvis-core")
        self.assertEqual(data["status"], "healthy")

    def test_event_ingestion(self):
        payload = {
            "source": "sensory.microphone",
            "type": "sensory.clap",
            "data": {"count": 2, "confidence": 0.98}
        }
        response = self.client.post("/api/v1/events", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("event_id", data)

    def test_action_dispatch_tier1(self):
        payload = {
            "name": "turn_on_light",
            "target_world": "physical",
            "target_agent": "esp32_agent",
            "tier": "tier_1_soft",
            "parameters": {"relay": "desk_lamp", "state": True}
        }
        response = self.client.post("/api/v1/actions", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "dispatched")

    def test_action_dispatch_tier3_requires_approval(self):
        payload = {
            "name": "delete_database",
            "target_world": "digital",
            "target_agent": "aws_agent",
            "tier": "tier_3_destructive",
            "parameters": {"db_id": "prod-db"}
        }
        # Without approval token -> blocked
        response = self.client.post("/api/v1/actions", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "requires_approval")

        # With valid approval token -> dispatched
        payload["approval_token"] = config.master_secret
        response2 = self.client.post("/api/v1/actions", json=payload)
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2["status"], "dispatched")

    def test_world_state(self):
        response = self.client.get("/api/v1/state")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("system", data)
        self.assertIn("devices", data)
        self.assertIn("pc", data)

    def test_emergency_stand_down_circuit_breaker(self):
        # Trigger Stand Down
        sd_payload = {
            "passphrase": config.master_secret,
            "reason": "Test emergency freeze"
        }
        response = self.client.post("/api/v1/emergency/stand-down", json=sd_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["emergency_stand_down"])

        # Attempt an action while frozen -> must return 403 Forbidden
        action_payload = {
            "name": "open_app",
            "target_world": "computer",
            "target_agent": "windows_agent",
            "tier": "tier_1_soft",
            "parameters": {"app": "notepad"}
        }
        action_res = self.client.post("/api/v1/actions", json=action_payload)
        self.assertEqual(action_res.status_code, 403)

        # Resume Operations
        resume_res = self.client.post("/api/v1/emergency/resume", json=sd_payload)
        self.assertEqual(resume_res.status_code, 200)
        self.assertFalse(resume_res.json()["emergency_stand_down"])

    def test_missions_endpoint(self):
        # GET missions
        res = self.client.get("/api/v1/missions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("missions", data)

        # POST create mission
        create_res = self.client.post("/api/v1/missions", json={
            "name": "Test Integration Mission",
            "objective": "Verify autonomous mission loop",
            "risk_level": "LOW"
        })
        self.assertEqual(create_res.status_code, 200)
        c_data = create_res.json()
        self.assertEqual(c_data["status"], "created")
        self.assertIn("id", c_data["mission"])

    def test_policy_approvals_and_audit(self):
        # GET approvals
        res = self.client.get("/api/v1/policy/approvals")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        # GET audit
        audit_res = self.client.get("/api/v1/policy/audit")
        self.assertEqual(audit_res.status_code, 200)
        self.assertEqual(audit_res.json()["status"], "success")

    def test_swarm_endpoint(self):
        res = self.client.get("/api/v1/swarm/agents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 12)

    def test_vision_screenshot_endpoint(self):
        res = self.client.get("/api/v1/vision/screenshot")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "image/jpeg")


if __name__ == "__main__":
    unittest.main()

