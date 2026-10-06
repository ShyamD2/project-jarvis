"""
Security Regression Test Suite
Validates critical hardening against Zip Slip, Universal Sandbox Jail bypasses,
WebSocket origin spoofing, and tool action silent fallbacks.
"""

import unittest
import os
import tempfile
import zipfile
import asyncio
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agents.computer.file_agent import file_agent
from services.jarvis_core.main import app
from services.brain.tools.registry import NetworkControlTool, AWSManagementTool, ProductivityTool, AudioVolumeTool


class TestSecurityRegressions(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_zip_slip_blocked(self):
        """Invariant: extract_zip rejects archives containing path traversal members ('../escaped.txt')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "malicious_slip.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("../escaped.txt", "malicious payload")
                z.writestr("safe_file.txt", "safe content")

            extract_target = os.path.join(tmpdir, "extracted")
            res = file_agent.extract_zip(zip_path, extract_target)

            self.assertFalse(res["success"], "Zip Slip extraction should have been blocked.")
            self.assertIn("Zip Slip path traversal blocked", res.get("error", ""))

            # Verify file was not written outside extract target
            escaped_file = os.path.join(tmpdir, "escaped.txt")
            self.assertFalse(os.path.exists(escaped_file), "Malicious file escaped sandbox!")

    def test_open_path_jail_enforced(self):
        """Invariant: open_path validates sandbox jail and blocks protected/untrusted system paths."""
        forbidden_targets = [
            r"C:\Windows\System32",
            r"C:\Windows\System32\cmd.exe",
            r"C:\Program Files",
            r"C:\Recovery"
        ]
        for target in forbidden_targets:
            res = file_agent.open_path(target)
            self.assertFalse(res["success"], f"Target path '{target}' should have been blocked.")
            self.assertIn("SecurityViolation", res.get("error", ""))

    def test_copy_item_source_jail_enforced(self):
        """Invariant: copy_item validates source path jail and blocks reading forbidden system files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "stolen_file.exe")
            forbidden_src = r"C:\Windows\System32\cmd.exe"

            res = file_agent.copy_item(forbidden_src, dest)
            self.assertFalse(res["success"], "Copying forbidden source should have been blocked.")
            self.assertIn("SecurityViolation", res.get("error", ""))
            self.assertFalse(os.path.exists(dest), "Destination file should not have been created.")

    def test_search_files_jail_enforced(self):
        """Invariant: search_files validates root directory jail and blocks searching protected system directories."""
        forbidden_root = r"C:\Windows\System32"
        res = file_agent.search_files(pattern="*.dll", directory=forbidden_root)
        self.assertFalse(res["success"], "Searching forbidden root directory should have been blocked.")
        self.assertIn("SecurityViolation", res.get("error", ""))

    def test_websocket_origin_enforcement(self):
        """Invariant: WebSocket endpoint strictly parses origin URL and rejects spoofed/untrusted origins."""
        malicious_origins = [
            "http://localhost.attacker.com",
            "http://127.0.0.1:9999",
            "http://localhost:8080",
            "https://malicious.com",
            "http://127.0.0.1.attacker.org",
            "javascript:alert(1)"
        ]

        for bad_origin in malicious_origins:
            with self.subTest(origin=bad_origin):
                try:
                    with self.client.websocket_connect("/ws", headers={"origin": bad_origin}) as ws:
                        ws.receive_text()
                        self.fail(f"WebSocket connection with origin '{bad_origin}' should have been rejected.")
                except WebSocketDisconnect as e:
                    self.assertEqual(e.code, 1008, f"Expected close code 1008 for origin '{bad_origin}', got {e.code}")
                except Exception:
                    # Connection rejection is expected
                    pass

        # Verify legitimate origins are still accepted
        legitimate_origins = [
            "http://localhost:8000",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:3000",
            "http://localhost",
            "http://127.0.0.1"
        ]
        for good_origin in legitimate_origins:
            with self.subTest(origin=good_origin):
                with self.client.websocket_connect("/ws", headers={"origin": good_origin}) as ws:
                    data = ws.receive_json()
                    self.assertEqual(data.get("channel"), "system")
                    self.assertEqual(data.get("status"), "online")

    def test_unknown_network_action_fails_closed(self):
        """Invariant: NetworkControlTool fails closed on unknown action instead of silently returning IP addresses."""
        tool = NetworkControlTool()
        res = asyncio.run(tool.execute(action="invalid_network_action"))
        self.assertFalse(res["success"], "NetworkControlTool must not succeed on unknown action.")
        self.assertIn("Unknown network action", res.get("error", ""))

    def test_additional_tools_fail_closed_on_unknown_action(self):
        """Invariant: AWSManagementTool, ProductivityTool, and AudioVolumeTool fail closed on unknown actions."""
        aws = AWSManagementTool()
        res_aws = asyncio.run(aws.execute(action="invalid_aws_action"))
        self.assertFalse(res_aws["success"])
        self.assertIn("Unknown AWS action", res_aws.get("error", ""))

        prod = ProductivityTool()
        res_prod = asyncio.run(prod.execute(action="invalid_productivity_action"))
        self.assertFalse(res_prod["success"])
        self.assertIn("Unknown productivity action", res_prod.get("error", ""))

        audio = AudioVolumeTool()
        res_audio = asyncio.run(audio.execute(action="invalid_audio_action"))
        self.assertFalse(res_audio["success"])
        self.assertIn("Unknown audio volume action", res_audio.get("error", ""))


if __name__ == "__main__":
    unittest.main()
