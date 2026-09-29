"""
Comprehensive Unit Tests for Core Subsystems (Phase 5).
Covers:
  1. SystemControl (services/pc_agent/system_control.py)
  2. BrowserAgent (services/pc_agent/browser_agent.py)
  3. SecretsManager (services/security/secrets_manager.py)
  4. RecoveryEngine (services/brain/recovery_engine.py)
"""

import os
import sys
import unittest
import tempfile
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from services.pc_agent.system_control import SystemControl, system_control
from services.pc_agent.browser_agent import BrowserAgent
from services.security.secrets_manager import SecretsManager, SecurityError
from services.brain.recovery_engine import RecoveryEngine


class TestSubsystemControl(unittest.TestCase):
    """Verifies SystemControl security boundaries, path protection, and hardware abstraction."""

    def setUp(self):
        self.sc = SystemControl()

    def test_sensitive_path_blocking(self):
        """Verifies access to private keys, .env, and OS critical stores is rejected."""
        blocked_paths = [
            r"C:\Users\User\.ssh\id_rsa",
            r"D:\Project\.env",
            r"C:\Windows\System32\config\SAM",
            r"/etc/passwd",
            r"/etc/shadow",
            r"C:\Users\User\.aws\credentials",
            r"D:\SafeDir\subfolder\.env.production"
        ]
        for path in blocked_paths:
            self.assertFalse(self.sc._is_path_permitted(path), f"Path should be blocked: {path}")

    def test_permitted_project_path(self):
        """Verifies standard project directories are allowed."""
        safe_paths = [
            os.path.abspath("data/memory"),
            os.path.abspath("services/pc_agent"),
            os.path.abspath("README.md")
        ]
        for path in safe_paths:
            self.assertTrue(self.sc._is_path_permitted(path), f"Path should be allowed: {path}")

    def test_read_file_preview_security_jail(self):
        """Verifies reading sensitive files fails immediately with SECURITY_ERROR."""
        res = self.sc.read_file_preview(r"C:\Users\User\.ssh\id_rsa")
        self.assertFalse(res["success"])
        self.assertIn("SECURITY_ERROR", res["error"])

    def test_read_file_preview_valid_file(self):
        """Verifies reading valid text file with max_chars boundary."""
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
            tf.write("J.A.R.V.I.S. Subsystem Operational Telemetry Test Data Content Line")
            temp_path = tf.name

        try:
            res = self.sc.read_file_preview(temp_path, max_chars=20)
            self.assertTrue(res["success"])
            self.assertEqual(len(res["preview"]), 20)
            self.assertEqual(res["preview"], "J.A.R.V.I.S. Subsyst")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_volume_bounds_and_clamping(self):
        """Verifies set_volume clamps to [0, 100] and handles type variations."""
        with patch("services.pc_agent.native_audio.set_master_volume", return_value=True):
            # Test over 100 clamped
            res_high = self.sc.set_volume(150)
            self.assertTrue(res_high["success"])
            self.assertEqual(res_high["volume_set"], 100)

            # Test under 0 clamped
            res_low = self.sc.set_volume(-20)
            self.assertTrue(res_low["success"])
            self.assertEqual(res_low["volume_set"], 0)

            # Test string conversion
            res_str = self.sc.set_volume("75")
            self.assertTrue(res_str["success"])
            self.assertEqual(res_str["volume_set"], 75)

    def test_volume_adjust_relative_actions(self):
        """Verifies relative volume up/down/mute requests."""
        if sys.platform != "win32":
            self.skipTest("Windows-only virtual key event test")
        
        with patch("ctypes.windll.user32.keybd_event"):
            res_up = self.sc.adjust_volume("up", steps=2)
            self.assertTrue(res_up["success"])
            self.assertEqual(res_up["action"], "volume_up")

            res_down = self.sc.adjust_volume("down", steps=3)
            self.assertTrue(res_down["success"])
            self.assertEqual(res_down["action"], "volume_down")

            res_mute = self.sc.adjust_volume("mute")
            self.assertTrue(res_mute["success"])
            self.assertEqual(res_mute["action"], "toggle_mute")


class TestBrowserAgent(unittest.IsolatedAsyncioTestCase):
    """Verifies BrowserAgent web searches, CDP probes, and DOM fallbacks."""

    def setUp(self):
        self.agent = BrowserAgent()

    async def test_is_cdp_available_probe(self):
        """Verifies non-blocking CDP port probe."""
        # 1. When port returns 200
        mock_resp = MagicMock(status_code=200)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            avail = await self.agent._is_cdp_available()
            self.assertTrue(avail)

        # 2. When port is closed/unreachable
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("Connection refused")):
            avail_down = await self.agent._is_cdp_available()
            self.assertFalse(avail_down)

    async def test_structured_web_search_with_mock_json(self):
        """Verifies DuckDuckGo Instant Answer JSON API parsing."""
        mock_data = {
            "Abstract": "Artificial intelligence is intelligence demonstrated by machines.",
            "AbstractURL": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "RelatedTopics": [
                {"Text": "Machine learning overview", "FirstURL": "https://en.wikipedia.org/wiki/Machine_learning"}
            ]
        }
        mock_resp = MagicMock(status_code=200, json=lambda: mock_data)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            results = await self.agent.search_web("what is artificial intelligence", max_results=2)
            self.assertTrue(len(results) >= 1)
            self.assertEqual(results[0]["url"], "https://en.wikipedia.org/wiki/Artificial_intelligence")
            self.assertIn("intelligence demonstrated by machines", results[0]["snippet"])

    async def test_fetch_page_summary_http_fallback(self):
        """Verifies HTML text extraction when CDP is unavailable."""
        html_payload = "<html><head><title>Test Title</title></head><body><h1>Hello World</h1><p>This is a test paragraph with meaningful information.</p></body></html>"
        mock_resp = MagicMock(status_code=200, text=html_payload)
        
        # Force CDP to return None to test resilient HTTP mode
        with patch.object(self.agent, "_get_cdp_page", new_callable=AsyncMock, return_value=None), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            summary = await self.agent.fetch_page_summary("https://example.com/info")
            self.assertTrue(summary["success"])
            self.assertIn("Hello World", summary["content"])
            self.assertEqual(summary["method"], "httpx_fallback")


class TestSecretsManager(unittest.TestCase):
    """Verifies fail-closed security hierarchy in SecretsManager."""

    def test_development_mode_env_lookup(self):
        """In development mode, environment variables are retrieved."""
        with patch.dict(os.environ, {"JARVIS_ENV": "development", "TEST_DEV_KEY": "dev_secret_value"}):
            sm = SecretsManager()
            val = sm.get_secret("TEST_DEV_KEY")
            self.assertEqual(val, "dev_secret_value")

    def test_development_mode_default_fallback(self):
        """In development mode, unset key returns default."""
        with patch.dict(os.environ, {"JARVIS_ENV": "development"}):
            sm = SecretsManager()
            val = sm.get_secret("NON_EXISTENT_KEY_123", default="my_default")
            self.assertEqual(val, "my_default")

    def test_production_mode_fails_closed_without_default(self):
        """In production mode, missing secret must FAIL CLOSED by raising SecurityError."""
        with patch.dict(os.environ, {"JARVIS_ENV": "production"}):
            sm = SecretsManager()
            sm._dpapi_available = False  # Disable DPAPI lookup for pure isolated test
            with self.assertRaises(SecurityError):
                sm.get_secret("UNSET_PRODUCTION_SECRET")

    def test_production_mode_with_explicit_default(self):
        """In production mode, explicit default is returned when provided."""
        with patch.dict(os.environ, {"JARVIS_ENV": "production"}):
            sm = SecretsManager()
            sm._dpapi_available = False
            val = sm.get_secret("UNSET_PRODUCTION_SECRET", default="safe_fallback")
            self.assertEqual(val, "safe_fallback")

    def test_store_and_cache_secret(self):
        """Verifies store_secret places item into memory cache."""
        with patch.dict(os.environ, {"JARVIS_ENV": "development"}):
            sm = SecretsManager()
            sm._dpapi_available = False
            ok = sm.store_secret("SESSION_KEY", "cached_token_abc")
            self.assertTrue(ok)
            self.assertEqual(sm.get_secret("SESSION_KEY"), "cached_token_abc")


class TestRecoveryEngine(unittest.IsolatedAsyncioTestCase):
    """Verifies autonomous failure diagnosis, alternate path execution, and fallbacks."""

    def setUp(self):
        self.engine = RecoveryEngine()

    async def test_app_launch_recovery_protocol_uri(self):
        """Verifies calculator protocol fallback when normal app launch and alias paths fail."""
        with patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False), \
             patch("os.startfile") as mock_start:
            res = await self.engine.attempt_recovery(
                tool_name="launch_app",
                parameters={"app_name": "calculator"},
                original_error="FileNotFoundError: calc.exe not in path"
            )
            self.assertTrue(res["recovered"])
            self.assertEqual(res["method"], "protocol_uri")
            self.assertEqual(res["uri"], "calculator:")
            mock_start.assert_called_once_with("calculator:")

    async def test_browser_action_recovery(self):
        """Verifies recovery for web page failure with URL normalization."""
        with patch("os.startfile") as mock_start:
            res = await self.engine.attempt_recovery(
                tool_name="browse_web",
                parameters={"url": "google.com"},
                original_error="NavigationTimeout: 30000ms exceeded"
            )
            self.assertTrue(res["recovered"])
            self.assertEqual(res["method"], "os_startfile")
            self.assertEqual(res["url"], "https://google.com")
            mock_start.assert_called_once_with("https://google.com")

    async def test_unhandled_tool_recovery_graceful_failure(self):
        """Verifies unknown tools return unrecovered status gracefully without unhandled exceptions."""
        res = await self.engine.attempt_recovery(
            tool_name="unknown_quantum_device_switch",
            parameters={"arg": 1},
            original_error="DeviceOffline"
        )
        self.assertFalse(res["recovered"])
        self.assertIn("No autonomous recovery strategy configured", res["error"])


if __name__ == "__main__":
    unittest.main()
