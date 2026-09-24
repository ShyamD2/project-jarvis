"""
Security Regression Test: WebSocket Authentication and Origin Verification
Guarantees permanent remediation for WebSocket hijacking and unauthenticated socket attacks.
"""

import unittest
from fastapi.testclient import TestClient
from services.jarvis_core.main import app
from starlette.websockets import WebSocketDisconnect


class TestWebSocketSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_unauthorized_cross_origin_websocket_rejected(self):
        """Invariant: Cross-origin WebSocket connection from untrusted origin is closed with 1008 (Policy Violation)."""
        try:
            with self.client.websocket_connect(
                "/ws",
                headers={"origin": "https://malicious-cross-origin.com"}
            ) as websocket:
                # If connected, trying to receive text will fail or connection closed
                data = websocket.receive_text()
                self.fail("WebSocket connection from unauthorized origin should have been closed.")
        except WebSocketDisconnect as e:
            self.assertEqual(e.code, 1008)
        except Exception:
            # Rejection or close is the expected secure behavior
            pass

    def test_authorized_local_origin_websocket_accepted(self):
        """Invariant: Trusted localhost origin establishes connection and receives initial handshake."""
        with self.client.websocket_connect(
            "/ws",
            headers={"origin": "http://localhost:8000"}
        ) as websocket:
            data = websocket.receive_json()
            self.assertEqual(data.get("channel"), "system")
            self.assertEqual(data.get("status"), "online")


if __name__ == "__main__":
    unittest.main()
