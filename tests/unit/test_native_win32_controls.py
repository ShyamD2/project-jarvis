"""
Unit Test Suite for Native Win32 API Controls (Zero-Subprocess Hardening).
Verifies:
  1. test_native_audio_control_no_powershell:
     set_volume, mute, unmute execute natively without invoking powershell.exe.
  2. test_native_window_control_no_powershell:
     find_window, list_windows, focus_window execute via ctypes Win32 with zero subprocess.
  3. test_raw_powershell_remains_tier3_guarded:
     execute_powershell strictly requires Tier 3 authorization/tickets and blocks unapproved calls.
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from agents.computer.audio_agent import audio_agent, AudioAgent
from agents.computer.windows_agent import windows_agent, WindowsAgent, find_window, list_windows, focus_window
from services.pc_agent.system_control import system_control, SystemControl
from services.pc_agent.native_audio import get_master_volume, set_master_volume, get_mute, set_mute
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from services.permission_engine.engine import permission_engine
from services.permission_engine.risk_classifier import classifier
from agents.intelligence.safety_guard import safety_guard, StrictTier
from agents.action_dispatcher import ActionDispatcher
from shared.sdk_python.jarvis_sdk.config import config


def _assert_no_powershell(mock_run, mock_popen=None):
    """Helper to ensure powershell.exe was never invoked in any subprocess call."""
    for call in mock_run.call_args_list:
        args = call[0] if call[0] else []
        flat = " ".join(str(a) for a in args).lower()
        if "powershell" in flat:
            raise AssertionError(f"powershell.exe was unexpectedly invoked via subprocess.run: {call}")
    if mock_popen:
        for call in mock_popen.call_args_list:
            args = call[0] if call[0] else []
            flat = " ".join(str(a) for a in args).lower()
            if "powershell" in flat:
                raise AssertionError(f"powershell.exe was unexpectedly invoked via subprocess.Popen: {call}")


class TestNativeWin32Controls(unittest.TestCase):
    def setUp(self):
        config.emergency_stand_down = False

    def test_native_audio_control_no_powershell(self):
        """Verify set_volume, mute, unmute execute without invoking powershell.exe."""
        agent = AudioAgent()
        sys_ctrl = SystemControl()

        with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
            # 1. Test AudioAgent volume get/set
            vol_res = agent.get_volume()
            self.assertTrue(vol_res["success"], "get_volume must succeed natively")
            self.assertIn("volume", vol_res)

            set_res = agent.set_volume(45)
            self.assertTrue(set_res["success"], "set_volume must succeed natively")
            self.assertEqual(set_res["target_percent"], 45)

            set_pct_res = agent.set_volume_percent(50)
            self.assertTrue(set_pct_res["success"])
            self.assertEqual(set_pct_res["target_percent"], 50)

            # 2. Test AudioAgent mute / unmute
            mute_res = agent.mute()
            self.assertTrue(mute_res["success"], "mute must succeed natively")
            self.assertTrue(mute_res["muted"])

            unmute_res = agent.unmute()
            self.assertTrue(unmute_res["success"], "unmute must succeed natively")
            self.assertFalse(unmute_res["muted"])

            get_mute_res = agent.get_mute()
            self.assertTrue(get_mute_res["success"])

            # 3. Test SystemControl native audio methods
            sys_vol_res = sys_ctrl.set_volume(40)
            self.assertTrue(sys_vol_res["success"])
            self.assertEqual(sys_vol_res["volume_set"], 40)

            sys_mute_res = sys_ctrl.mute()
            self.assertTrue(sys_mute_res["success"])

            sys_unmute_res = sys_ctrl.unmute()
            self.assertTrue(sys_unmute_res["success"])

            sys_get_vol = sys_ctrl.get_volume()
            self.assertTrue(sys_get_vol["success"])

            # 4. Strict assertion: zero powershell.exe calls across all operations
            _assert_no_powershell(mock_run, mock_popen)
            self.assertEqual(mock_run.call_count, 0, "Audio control must perform zero subprocess.run calls")
            self.assertEqual(mock_popen.call_count, 0, "Audio control must perform zero subprocess.Popen calls")

    def test_native_audio_fallback_no_powershell(self):
        """Verify audio controls succeed via pure Win32 fallbacks (winmm / SendMessageW) without powershell when COM is simulated offline."""
        with patch("services.pc_agent.native_audio._init_core_audio", return_value=None):
            with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
                # set_master_volume fallback
                ok_vol = set_master_volume(35.0)
                self.assertTrue(ok_vol, "set_master_volume fallback must succeed without COM")

                # set_mute fallback
                ok_mute = set_mute(True)
                self.assertTrue(ok_mute, "set_mute fallback must succeed without COM")

                ok_unmute = set_mute(False)
                self.assertTrue(ok_unmute, "set_mute(False) fallback must succeed without COM")

                # Ensure zero powershell invocations
                _assert_no_powershell(mock_run, mock_popen)
                self.assertEqual(mock_run.call_count, 0)
                self.assertEqual(mock_popen.call_count, 0)

    def test_native_window_control_no_powershell(self):
        """Verify find_window, list_windows, focus_window execute via ctypes Win32 with zero subprocess."""
        if sys.platform != "win32":
            self.skipTest("Windows-specific native Win32 controls test")

        agent = WindowsAgent()
        sys_ctrl = SystemControl()

        with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
            # 1. list_windows via ctypes EnumWindows
            win_list = agent.list_windows(visible_only=True)
            self.assertIsInstance(win_list, list, "list_windows must return a list")
            if win_list:
                first = win_list[0]
                self.assertIn("hwnd", first)
                self.assertIn("title", first)
                self.assertIn("pid", first)
                self.assertIsInstance(first["hwnd"], int)

            # SystemControl.list_windows
            sys_win_list = sys_ctrl.list_windows(visible_only=True)
            self.assertIsInstance(sys_win_list, list)

            # 2. find_window via ctypes FindWindowW / EnumWindows
            found_hwnd = agent.find_window("Program Manager")
            # Program Manager is always present on Windows desktop sessions
            if found_hwnd:
                self.assertIsInstance(found_hwnd, int)
                self.assertGreater(found_hwnd, 0)

            # Nonexistent window lookup returns None cleanly
            none_hwnd = agent.find_window("NonExistentWindow_xyz_123456789")
            self.assertIsNil_or_None = self.assertIsNone(none_hwnd)

            # SystemControl.find_window
            sys_none = sys_ctrl.find_window("NonExistentWindow_xyz_123456789")
            self.assertIsNone(sys_none)

            # 3. focus_window via ctypes SetForegroundWindow
            if found_hwnd:
                focused = agent.focus_window(found_hwnd)
                self.assertTrue(focused, "focus_window on valid HWND must succeed")

            # 4. Window state methods (minimize, maximize, restore, close)
            # Test minimize / restore with invalid target gracefully fails or handles HWND cleanly
            min_res = agent.minimize_window("NonExistentWindow_xyz_123456789")
            self.assertFalse(min_res["success"])
            self.assertIn("error", min_res)

            max_res = agent.maximize_window("NonExistentWindow_xyz_123456789")
            self.assertFalse(max_res["success"])

            restore_res = agent.restore_window("NonExistentWindow_xyz_123456789")
            self.assertFalse(restore_res["success"])

            close_res = agent.close_window("NonExistentWindow_xyz_123456789")
            self.assertFalse(close_res["success"])

            # 5. Top-level wrappers
            tw_list = list_windows()
            self.assertIsInstance(tw_list, list)
            tw_find = find_window("NonExistentWindow_xyz_123456789")
            self.assertIsNone(tw_find)

            # 6. get_power_info via kernel32.GetSystemPowerStatus
            power_info = agent.get_power_info()
            self.assertTrue(power_info["success"])
            self.assertIn("power_plugged", power_info)
            self.assertIn("ac_line_status", power_info)
            self.assertIn("battery_percent", power_info)

            sys_power_info = sys_ctrl.get_power_info()
            self.assertTrue(sys_power_info["success"])
            self.assertIn("power_plugged", sys_power_info)

            # Strict assertion: zero powershell.exe or subprocess calls
            _assert_no_powershell(mock_run, mock_popen)
            self.assertEqual(mock_run.call_count, 0)
            self.assertEqual(mock_popen.call_count, 0)

    def test_raw_powershell_remains_tier3_guarded(self):
        """Verify execute_powershell strictly requires Tier 3 authorization and blocks unapproved execution."""
        agent = WindowsAgent()

        # 1. Direct call to windows_agent.execute_powershell without approval must be blocked
        blocked_res = agent.execute_powershell("Get-Process")
        self.assertFalse(blocked_res["success"], "Unapproved execute_powershell must be blocked")
        self.assertEqual(blocked_res["status"], "gatekeeper_blocked")
        self.assertEqual(blocked_res["tier"], 3)
        self.assertIn("TIER_3_GUARD", blocked_res["error"])

        # 2. Call with invalid/missing ticket must be blocked
        blocked_ticket_res = agent.execute_powershell("Get-Process", ticket_id="invalid-ticket-xyz")
        self.assertFalse(blocked_ticket_res["success"])
        self.assertEqual(blocked_ticket_res["status"], "gatekeeper_blocked")

        # 3. Direct call with explicit operator_approved=True executes
        approved_res = agent.execute_powershell("Write-Output 'approved_ok'", operator_approved=True)
        self.assertTrue(approved_res["success"])
        self.assertIn("approved_ok", approved_res["stdout"])

        # 4. RiskClassifier must classify execute_powershell as TIER_3_DESTRUCTIVE
        tier, rationale = classifier.classify("execute_powershell", "Get-Process", TargetWorld.COMPUTER, {})
        self.assertEqual(tier, ActionTier.TIER_3_DESTRUCTIVE, "execute_powershell must be classified as Tier 3 Destructive")

        # 5. SafetyGuard must classify execute_powershell as TIER_3_DESTRUCTIVE
        strict_tier, _ = safety_guard.classify_action("execute_powershell", {"script": "Get-Process"})
        self.assertEqual(strict_tier, StrictTier.TIER_3_DESTRUCTIVE, "SafetyGuard must classify execute_powershell as Tier 3")

        # 6. PermissionEngine must deny execute_powershell without valid capability token / lease
        action = ActionEnvelope(
            name="execute_powershell",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_0_REFLEX,  # Attempting to disguise as Tier 0
            parameters={"script": "Get-Date"}
        )
        decision = permission_engine.evaluate(action, user_role="OWNER")
        self.assertFalse(decision.authorized, "Unapproved execute_powershell action must be denied by PermissionEngine")
        self.assertEqual(decision.tier, ActionTier.TIER_3_DESTRUCTIVE, "Action must escalate to Tier 3 Destructive")
        self.assertTrue(decision.requires_explicit_approval, "Must require explicit approval")
        self.assertTrue(decision.requires_mfa, "Tier 3 must require MFA")

        # 7. ActionDispatcher dispatch without approval must fail closed
        dispatcher = ActionDispatcher()
        res_dispatched = asyncio.run(dispatcher.dispatch(action, user_role="OWNER"))
        self.assertFalse(res_dispatched["success"])
        self.assertEqual(res_dispatched["status"], "denied")
        self.assertTrue(res_dispatched["requires_approval"])

        # 8. ActionDispatcher dispatch with valid master approval token must succeed
        res_approved = asyncio.run(dispatcher.dispatch(action, approval_token=config.master_secret))
        self.assertTrue(res_approved["success"], "Authorized execute_powershell dispatch must succeed")
        self.assertEqual(res_approved["status"], "dispatched")


if __name__ == "__main__":
    unittest.main()
