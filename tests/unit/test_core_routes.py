"""
Comprehensive Unit Tests for Core Routes (Phase 5).
Covers all 18 route modules in services/jarvis_core/routes/ and main.py:
  1. SecurityGuardMiddleware auth enforcement (401 unauthenticated, 403 invalid token, exempt endpoints).
  2. All route handlers:
     - Health & Probes (/health, /health/live, /health/ready, /metrics)
     - Diagnostics (/api/v1/diagnostics)
     - Emergency & Circuit Breaker (/api/v1/emergency/status, /api/v1/emergency/safety/pending)
     - State & World Model (/api/v1/state)
     - Cloud & FinOps (/api/v1/cloud/resources, /api/v1/cloud/finops)
     - DevOps & Docker (/api/v1/devops/docker/containers, /api/v1/devops/git/status)
     - Security & Port Scan (/api/v1/security/blast-radius, /api/v1/security/port-scan)
     - Policy & Approvals (/api/v1/policy/approvals)
     - Swarm Agents (/api/v1/swarm/agents)
     - Hierarchical Knowledge (/api/v1/knowledge/search, /api/v1/knowledge/remember)
     - Mission Control (/api/v1/missions)
     - Sensory Hub (/api/v1/sensory/status)
     - Query Interface (/api/v1/query/engine)
     - Event Ingestion (/api/v1/events)
     - Web Research (/api/v1/web/research)
     - Action Dispatch (/api/v1/actions)
     - Versioned V1 Contract (/api/v1/status, /api/v1/capabilities, /api/v1/query)
     - Computer Vision (/api/v1/vision/analyze)
"""

import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from services.jarvis_core.main import app
from services.brain.providers.base import LLMResponse


class TestCoreRoutes(unittest.TestCase):
    """Automated integration/unit tests for all FastAPI endpoints and security middleware."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.master_secret = "test_core_routes_secret_token_123"
        cls.auth_headers = {"Authorization": f"Bearer {cls.master_secret}"}

    def test_01_security_middleware_unauthenticated_rejection(self):
        """Verifies protected endpoints reject requests lacking credentials with 401."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/state")
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(resp.json()["error"], "UNAUTHORIZED")

    def test_02_security_middleware_invalid_token_rejection(self):
        """Verifies requests with incorrect credentials receive 403 Forbidden."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/state", headers={"Authorization": "Bearer wrong_token"})
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["error"], "FORBIDDEN")

    def test_03_security_middleware_exempt_endpoints(self):
        """Verifies health, metrics, and public status probes require no authentication."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            for path in ["/health", "/health/live", "/health/ready", "/metrics", "/api/v1/status"]:
                resp = self.client.get(path)
                self.assertIn(resp.status_code, [200, 503], f"Path {path} returned unexpected {resp.status_code}")

    def test_04_authenticated_state_route(self):
        """Verifies GET /api/v1/state returns real-time world state under valid auth."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/state", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("system", data)
            self.assertIn("devices", data)
            self.assertIn("pc", data)

    def test_05_diagnostics_routes(self):
        """Verifies /api/v1/diagnostics returns live probes for dependencies."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/diagnostics", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("probes", data)
            self.assertIn("mqtt_broker", data["probes"])
            self.assertIn("host_hardware", data["probes"])

    def test_06_emergency_routes(self):
        """Verifies /api/v1/emergency/status and safety pending tickets."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/emergency/status", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("is_stopped", resp.json())

            resp_tickets = self.client.get("/api/v1/emergency/safety/pending", headers=self.auth_headers)
            self.assertEqual(resp_tickets.status_code, 200)

    def test_07_cloud_routes(self):
        """Verifies /api/v1/cloud/resources and finops endpoints."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp_res = self.client.get("/api/v1/cloud/resources", headers=self.auth_headers)
            self.assertEqual(resp_res.status_code, 200)

            resp_finops = self.client.get("/api/v1/cloud/finops", headers=self.auth_headers)
            self.assertEqual(resp_finops.status_code, 200)
            self.assertEqual(resp_finops.json()["status"], "success")

    def test_08_devops_routes(self):
        """Verifies /api/v1/devops/docker/containers and git status."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp_docker = self.client.get("/api/v1/devops/docker/containers", headers=self.auth_headers)
            self.assertEqual(resp_docker.status_code, 200)
            self.assertIn("containers", resp_docker.json())

            resp_git = self.client.get("/api/v1/devops/git/status", headers=self.auth_headers)
            self.assertEqual(resp_git.status_code, 200)

    def test_09_security_routes(self):
        """Verifies /api/v1/security/blast-radius and port-scan."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp_blast = self.client.get("/api/v1/security/blast-radius", headers=self.auth_headers)
            self.assertEqual(resp_blast.status_code, 200)

            resp_scan = self.client.post(
                "/api/v1/security/port-scan",
                headers=self.auth_headers,
                json={"target_host": "127.0.0.1", "ports": [8000]}
            )
            self.assertEqual(resp_scan.status_code, 200)
            self.assertEqual(resp_scan.json()["status"], "success")

    def test_10_policy_routes(self):
        """Verifies /api/v1/policy/approvals and audit."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/policy/approvals", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("pending_approvals", resp.json())

    def test_11_swarm_routes(self):
        """Verifies /api/v1/swarm/agents returns specialized persona agents."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/swarm/agents", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertTrue(data["count"] > 0)

    def test_12_knowledge_routes(self):
        """Verifies /api/v1/knowledge/search and /remember."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp_search = self.client.get("/api/v1/knowledge/search?q=test_query", headers=self.auth_headers)
            self.assertEqual(resp_search.status_code, 200)
            self.assertEqual(resp_search.json()["status"], "success")

            resp_remember = self.client.post(
                "/api/v1/knowledge/remember",
                headers=self.auth_headers,
                json={"category": "preference", "key": "test_pref", "value": "test_val"}
            )
            self.assertEqual(resp_remember.status_code, 200)
            self.assertEqual(resp_remember.json()["status"], "stored")

    def test_13_missions_routes(self):
        """Verifies /api/v1/missions active and registry endpoints."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/missions", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "success")

            resp_active = self.client.get("/api/v1/missions/active", headers=self.auth_headers)
            self.assertEqual(resp_active.status_code, 200)

    def test_14_sensory_routes(self):
        """Verifies /api/v1/sensory/status."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/sensory/status", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "online")

    def test_15_query_routes(self):
        """Verifies /api/v1/query/engine."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.get("/api/v1/query/engine", headers=self.auth_headers)
            self.assertEqual(resp.status_code, 200)

    def test_16_events_routes(self):
        """Verifies POST /api/v1/events accepts CloudEvents and returns accepted status."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.post(
                "/api/v1/events",
                headers=self.auth_headers,
                json={"source": "test.unit", "type": "sensory.test_pulse", "data": {"val": 42}}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "accepted")
            self.assertIn("event_id", data)

    def test_17_web_research_route(self):
        """Verifies POST /api/v1/web/research with mocked AI response."""
        mock_resp = LLMResponse(
            content="Executive Summary: Autonomous research successful, sir.",
            tool_calls=[],
            model="test-research-model",
            tokens_prompt=10,
            tokens_completion=10,
            latency_ms=5.0
        )
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}), \
             patch("services.brain.providers.ai_manager.ai_manager.generate", new_callable=AsyncMock, return_value=mock_resp):
            resp = self.client.post(
                "/api/v1/web/research",
                headers=self.auth_headers,
                json={"query": "quantum computing architectures"}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("Executive Summary", data["briefing"])

    def test_18_actions_route(self):
        """Verifies POST /api/v1/actions executes read-only / reflex action via Canonical Pipeline."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp = self.client.post(
                "/api/v1/actions",
                headers=self.auth_headers,
                json={
                    "name": "query_system_telemetry",
                    "target_world": "computer",
                    "target_agent": "pc_agent",
                    "tier": "tier_1_soft",
                    "parameters": {"query_type": "time"}
                }
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data.get("success", False))

    def test_19_api_v1_contract_capabilities_and_query(self):
        """Verifies /api/v1/capabilities and /api/v1/query contract endpoints."""
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}):
            resp_cap = self.client.get("/api/v1/capabilities", headers=self.auth_headers)
            self.assertEqual(resp_cap.status_code, 200)
            self.assertTrue(resp_cap.json()["count"] > 0)

            resp_q = self.client.post(
                "/api/v1/query",
                headers=self.auth_headers,
                json={"query": "what is my cpu usage"}
            )
            self.assertEqual(resp_q.status_code, 200)
            self.assertTrue(resp_q.json()["verified"])

    def test_20_vision_analyze_route(self):
        """Verifies POST /api/v1/vision/analyze with mocked screen analysis."""
        mock_result = {
            "success": True,
            "prompt": "describe screen",
            "analysis": "Active window is Code editor, system is operating normally.",
            "grounded_elements": []
        }
        with patch.dict(os.environ, {"JARVIS_MASTER_SECRET": self.master_secret}), \
             patch("services.sensory.screen_vision.screen_vision.analyze_screen_context", new_callable=AsyncMock, return_value=mock_result):
            resp = self.client.post(
                "/api/v1/vision/analyze",
                headers=self.auth_headers,
                json={"prompt": "describe screen"}
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["success"])


if __name__ == "__main__":
    unittest.main()
