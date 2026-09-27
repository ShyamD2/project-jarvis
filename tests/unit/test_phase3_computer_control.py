"""
Phase 3 Unit Test Suite: Computer Control & Automation Hardening.
Verifies:
  1. Native Windows Core Audio (IAudioEndpointVolume) zero-SendKeys volume control.
  2. Per-Monitor v2 High-DPI awareness initialization for pixel-perfect coordinates.
  3. Structured DuckDuckGo JSON API web search in BrowserAgent.
  4. Truthful failure reporting in Kubernetes Agent (removal of failure masking).
  5. SystemControl and AudioAgent integration with native Core Audio.
"""

import os
import sys
import unittest
import asyncio

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from services.pc_agent.native_audio import get_master_volume, set_master_volume, get_mute, set_mute
from services.pc_agent.system_control import SystemControl
from agents.computer.audio_agent import AudioAgent
from agents.computer.windows_agent import WindowsAgent, ensure_high_dpi_aware
from services.pc_agent.browser_agent import browser_agent
from agents.cloud.k8s_agent import k8s_agent


class TestPhase3ComputerControl(unittest.TestCase):
    def test_native_audio_endpoint_volume(self):
        """Verifies master volume reading and direct setting via Core Audio API."""
        if sys.platform != "win32":
            self.skipTest("Windows-specific Core Audio test")

        vol = get_master_volume()
        if vol is None:
            self.skipTest("No audio render endpoint available on headless CI runner")
        self.assertIsNotNone(vol, "Master volume must be readable on Windows")
        self.assertGreaterEqual(vol, 0.0)
        self.assertLessEqual(vol, 100.0)

        # Roundtrip set and restore
        ok = set_master_volume(vol)
        self.assertTrue(ok, "Setting master volume via Core Audio must succeed")

        mute_state = get_mute()
        if mute_state is None:
            self.skipTest("No audio endpoint mute state available on headless CI runner")
        self.assertIsNotNone(mute_state, "Mute status must be a boolean on Windows")
        self.assertIsInstance(mute_state, bool)

    def test_system_control_and_audio_agent_integration(self):
        """Verifies SystemControl and AudioAgent utilize native audio without focus-stealing."""
        sys_ctrl = SystemControl()
        audio_agent = AudioAgent()

        curr_vol = get_master_volume() or 50.0

        # SystemControl.set_volume
        res_sys = sys_ctrl.set_volume(int(curr_vol))
        self.assertTrue(res_sys["success"])
        self.assertEqual(res_sys["volume_set"], int(curr_vol))

        # AudioAgent.set_volume_percent
        res_agent = audio_agent.set_volume_percent(int(curr_vol))
        self.assertTrue(res_agent["success"])
        self.assertEqual(res_agent["target_percent"], int(curr_vol))

    def test_high_dpi_awareness_initialization(self):
        """Verifies Per-Monitor v2 High-DPI awareness sets successfully on Windows."""
        if sys.platform != "win32":
            self.skipTest("Windows-specific DPI awareness test")

        dpi_ok = ensure_high_dpi_aware()
        self.assertTrue(dpi_ok, "Per-Monitor v2 DPI awareness must be accepted by Windows")

        # WindowsAgent instantiation must initialize DPI without errors
        agent = WindowsAgent()
        self.assertIsNotNone(agent)

    def test_browser_agent_structured_web_search(self):
        """Verifies BrowserAgent web search returns structured, validated JSON results."""
        async def _test():
            results = await browser_agent.search_web("Python software foundation", max_results=3)
            self.assertIsInstance(results, list)
            self.assertGreaterEqual(len(results), 1, "Must return at least 1 search result")
            for item in results:
                self.assertIn("url", item)
                self.assertIn("snippet", item)
                self.assertTrue(
                    item["url"].startswith("http://") or item["url"].startswith("https://"),
                    f"Result URL must be absolute HTTP(S): {item['url']}"
                )
                self.assertGreater(len(item["snippet"]), 0)

        asyncio.run(_test())

    def test_k8s_agent_truthful_failure_reporting(self):
        """Verifies that k8s_agent does not mask offline cluster errors with success=True."""
        pods_res = k8s_agent.get_pods()
        self.assertIn("success", pods_res)
        self.assertIn("connected", pods_res)

        # If kubectl is not running or connected, success must be False
        if not pods_res.get("connected"):
            self.assertFalse(pods_res["success"], "Offline cluster query must honestly return success=False")
            self.assertIn("error", pods_res)

        nodes_res = k8s_agent.get_nodes()
        if not nodes_res.get("connected"):
            self.assertFalse(nodes_res["success"], "Offline nodes query must honestly return success=False")


if __name__ == "__main__":
    unittest.main()
