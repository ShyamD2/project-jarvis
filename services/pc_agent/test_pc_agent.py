"""
Integration tests for J.A.R.V.I.S. Windows PC Agent & UI Vision.
Tests system telemetry, window enumeration, file search, browser search, and screen vision.
"""

import sys
import os
import unittest
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from system_monitor import system_monitor
from window_manager import window_manager
from system_control import system_control
from browser_agent import browser_agent
from screen_vision import screen_vision


class TestJarvisPCAgent(unittest.IsolatedAsyncioTestCase):
    def test_telemetry_collection(self):
        vitals = system_monitor.collect_telemetry()
        self.assertEqual(vitals["os"], "Windows")
        self.assertGreater(vitals["memory_percent"], 0)
        self.assertIn("cpu_percent", vitals)
        self.assertIn("active_window", vitals)
        self.assertIsInstance(vitals["in_meeting"], bool)

    def test_window_enumeration(self):
        windows = window_manager.get_open_windows()
        self.assertIsInstance(windows, list)

    def test_file_automation(self):
        # Search for .py files in current directory
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        py_files = system_control.search_files(project_dir, "*.py")
        self.assertTrue(len(py_files) > 0)

        # Test preview
        preview = system_control.read_file_preview(py_files[0])
        self.assertTrue(preview["success"])
        self.assertGreater(len(preview["preview"]), 0)

    async def test_browser_agent_search(self):
        results = await browser_agent.search_web("Project Jarvis AI", max_results=2)
        self.assertTrue(len(results) > 0)
        self.assertIn("url", results[0])

    async def test_screen_vision(self):
        analysis = await screen_vision.analyze_screen("Verify active display")
        if os.getenv("GEMINI_API_KEY"):
            self.assertTrue(analysis["success"])
            self.assertTrue(os.path.exists(analysis["image_path"]))
        else:
            self.assertFalse(analysis["success"])
            err = analysis.get("error", "")
            self.assertTrue("GEMINI_API_KEY unset" in err or "Desktop screen capture" in err)


if __name__ == "__main__":
    unittest.main()
