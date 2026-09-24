"""
Security Regression Test: Strict CORS & Origin Policy
Guarantees permanent remediation for wildcard CORS and unauthorized browser origin hijacking.
"""

import unittest
from fastapi.testclient import TestClient
from services.jarvis_core.main import app, ALLOWED_ORIGINS


class TestCORSSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_wildcard_cors_strictly_forbidden(self):
        """Invariant: Wildcard '*' is never in allowed origins when credentials are enabled."""
        self.assertNotIn("*", ALLOWED_ORIGINS, "Wildcard '*' origin detected in ALLOWED_ORIGINS! High security risk.")

    def test_trusted_local_origin_allowed(self):
        """Invariant: Trusted localhost origins receive appropriate Access-Control-Allow-Origin."""
        response = self.client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:8000"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:8000")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_untrusted_third_party_origin_rejected(self):
        """Invariant: Untrusted external web origins must NOT be granted Access-Control-Allow-Origin."""
        response = self.client.get(
            "/api/v1/health",
            headers={"Origin": "https://malicious-attacker-site.com"}
        )
        self.assertEqual(response.status_code, 200)
        # Untrusted origin must NOT be reflected in access-control-allow-origin
        allow_origin = response.headers.get("access-control-allow-origin")
        self.assertNotEqual(allow_origin, "https://malicious-attacker-site.com")
        self.assertNotEqual(allow_origin, "*")


if __name__ == "__main__":
    unittest.main()
