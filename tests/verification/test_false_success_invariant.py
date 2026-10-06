"""
False-Success Invariant & Verification Hardening Tests.
Verifies that:
  1. Unknown / unsupported actions can NEVER report success or VERIFIED status.
  2. Execution failures can NEVER report VERIFIED status.
  3. Physical actions without ground-truth sensory proof can NEVER report VERIFIED status.
  4. Computer actions with state verification contracts strictly fail if process/file state is unverified.
  5. Permission-denied actions can NEVER report VERIFIED status.
  6. Parameter sweep over invalid/unknown actions guarantees 0 false successes.
"""

import asyncio
from unittest.mock import patch, MagicMock
import pytest

from agents.action_dispatcher import ActionDispatcher
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.schemas.verification_contract import VerificationStatus, VerificationMode


def test_unknown_action_can_never_report_success():
    """Dispatch an unknown/unsupported action and assert result['success'] is False and status != 'VERIFIED'."""
    dispatcher = ActionDispatcher()
    action = ActionEnvelope(
        name="completely_unknown_computer_tool_xyz_999",
        target_world=TargetWorld.COMPUTER,
        target_agent="windows_agent",
        tier=ActionTier.TIER_0_REFLEX
    )

    result = asyncio.run(dispatcher.dispatch(action))

    assert result["success"] is False, "Unknown action must not report success=True"
    assert result["status"] != "VERIFIED", "Unknown action status must not be VERIFIED"
    assert result["status"] != "verified", "Unknown action status must not be verified"
    assert result["status"] == "failed"
    assert "verification" in result
    assert result["verification"]["status"] != "VERIFIED"
    assert result["verification"]["status"] != "verified"
    assert result["verification"]["status"] == VerificationStatus.FAILED.value
    assert result["verification"]["logical_verified"] is False


def test_execution_failure_can_never_report_verified():
    """When an action fails, assert verification status is FAILED."""
    dispatcher = ActionDispatcher()

    # Scenario A: Tool execution explicitly returns success=False
    with patch("agents.action_dispatcher.windows_agent.launch_app") as mock_launch:
        mock_launch.return_value = {
            "success": False,
            "error": "Failed to launch application: process terminated abruptly",
            "channel_1_logical": False
        }
        action = ActionEnvelope(
            name="launch_app",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_0_REFLEX,
            parameters={"app": "broken_app.exe"}
        )

        result = asyncio.run(dispatcher.dispatch(action))

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["verification"]["status"] == VerificationStatus.FAILED.value
        assert result["verification"]["status"] != "VERIFIED"
        assert result["verification"]["status"] != "verified"
        assert result["verification"]["match"] is False

    # Scenario B: Script execution failure
    with patch("agents.action_dispatcher.windows_agent.execute_powershell") as mock_ps:
        mock_ps.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Script execution halted with non-zero exit code",
            "returncode": 1,
            "channel_1_logical": False
        }
        action_ps = ActionEnvelope(
            name="execute_powershell",
            target_world=TargetWorld.COMPUTER,
            target_agent="windows_agent",
            tier=ActionTier.TIER_0_REFLEX,
            parameters={"script": "fail-script"}
        )
        with patch("agents.action_dispatcher.permission_engine.evaluate") as mock_eval:
            mock_eval.return_value = MagicMock(
                authorized=True,
                tier=ActionTier.TIER_0_REFLEX,
                rationale="Authorized for test"
            )
            result_ps = asyncio.run(dispatcher.dispatch(action_ps))

            assert result_ps["success"] is False
            assert result_ps["status"] == "failed"
            assert result_ps["verification"]["status"] == VerificationStatus.FAILED.value
            assert result_ps["verification"]["status"] != "VERIFIED"
            assert result_ps["verification"]["status"] != "verified"


def test_missing_verification_can_never_report_verified():
    """Assert physical actions without sensory proof cannot be VERIFIED."""
    dispatcher = ActionDispatcher()

    # Physical action where logical tool claims success, but sensory proof (lux) is None
    with patch("agents.action_dispatcher.esp32_agent.set_relay") as mock_relay:
        mock_relay.return_value = {
            "success": True,
            "device_id": "esp32_lab_01",
            "relay": "desk_lamp",
            "state": True,
            "channel_1_logical": True,
            "channel_2_lux": None,
            "sensory_verified": False
        }
        action = ActionEnvelope(
            name="toggle_light",
            target_world=TargetWorld.PHYSICAL,
            target_agent="esp32_agent",
            tier=ActionTier.TIER_1_SOFT,
            parameters={"device_id": "esp32_lab_01", "target": "desk_lamp", "state": True}
        )
        with patch("agents.action_dispatcher.permission_engine.evaluate") as mock_eval:
            mock_eval.return_value = MagicMock(
                authorized=True,
                tier=ActionTier.TIER_1_SOFT,
                rationale="Authorized for test"
            )
            result = asyncio.run(dispatcher.dispatch(action))

            assert result["success"] is False, "Physical action without sensory proof must fail"
            assert result["status"] == "failed"
            assert result["verification"]["status"] == VerificationStatus.FAILED.value
            assert result["verification"]["status"] != "VERIFIED"
            assert result["verification"]["status"] != "verified"
            assert result["verification"]["sensory_verified"] is False
            assert "sensory" in result["verification"]["failure_reason"].lower()


@pytest.mark.parametrize("invalid_action_name,world,agent,params", [
    ("format_c_drive", TargetWorld.COMPUTER, "windows_agent", {}),
    ("drop_all_tables", TargetWorld.COMPUTER, "windows_agent", {}),
    ("run_malware", TargetWorld.COMPUTER, "windows_agent", {}),
    ("unsupported_fake_tool_1", TargetWorld.COMPUTER, "windows_agent", {"arg": 1}),
    ("unsupported_fake_tool_2", TargetWorld.COMPUTER, "windows_agent", {"cmd": "test"}),
    ("arbitrary_unknown_cmd", TargetWorld.COMPUTER, "windows_agent", {}),
    ("unknown_physical_device_toggle", TargetWorld.PHYSICAL, "esp32_agent", {}),
    ("fake_digital_terraform_destroy", TargetWorld.DIGITAL, "aws_agent", {}),
])
def test_false_success_invariant(invalid_action_name, world, agent, params):
    """Comprehensive parameter sweep over invalid/unknown actions ensuring 0 false successes."""
    dispatcher = ActionDispatcher()
    action = ActionEnvelope(
        name=invalid_action_name,
        target_world=world,
        target_agent=agent,
        tier=ActionTier.TIER_0_REFLEX,
        parameters=params
    )

    # If physical, simulate hardware without sensory verification to test fail-closed invariant
    if world == TargetWorld.PHYSICAL:
        with patch("agents.action_dispatcher.esp32_agent.set_relay") as mock_relay:
            mock_relay.return_value = {
                "success": False,
                "error": "Device offline",
                "channel_1_logical": False,
                "channel_2_lux": None
            }
            result = asyncio.run(dispatcher.dispatch(action))
    else:
        result = asyncio.run(dispatcher.dispatch(action))

    # Invariant: 0% false success tolerance
    assert result["success"] is False, f"Action '{invalid_action_name}' reported false success!"
    assert result["status"] != "VERIFIED", f"Action '{invalid_action_name}' reported status=VERIFIED!"
    assert result["status"] != "verified", f"Action '{invalid_action_name}' reported status=verified!"
    assert result["status"] in ("failed", "denied"), f"Unexpected status: {result['status']}"
    if "verification" in result:
        v_status = result["verification"]["status"]
        assert v_status != "VERIFIED", f"Action '{invalid_action_name}' verification was VERIFIED!"
        assert v_status != "verified", f"Action '{invalid_action_name}' verification was verified!"
        assert v_status == VerificationStatus.FAILED.value


def test_computer_action_state_verification_contract_rejection():
    """Assert computer action with state verification contract fails if process state is unverified."""
    dispatcher = ActionDispatcher()
    action = ActionEnvelope(
        name="launch_app",
        target_world=TargetWorld.COMPUTER,
        target_agent="windows_agent",
        tier=ActionTier.TIER_0_REFLEX,
        parameters={"app": "notepad.exe"},
        verification_spec={
            "mode": VerificationMode.PROCESS_STATE,
            "process_name": "definitely_non_existent_fake_process_99999999.exe",
            "expected_running": True
        }
    )

    with patch("agents.action_dispatcher.windows_agent.launch_app") as mock_launch:
        # Tool logically claims it succeeded
        mock_launch.return_value = {
            "success": True,
            "app": "notepad",
            "pid": 99999,
            "channel_1_logical": True
        }
        result = asyncio.run(dispatcher.dispatch(action))

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["verification"]["status"] == VerificationStatus.FAILED.value
        assert result["verification"]["status"] != "VERIFIED"
        assert result["verification"]["status"] != "verified"
        assert "contract" in result["verification"]["failure_reason"].lower()


def test_permission_denial_can_never_report_verified():
    """Assert actions blocked by permission engine can never report verified status."""
    dispatcher = ActionDispatcher()
    action = ActionEnvelope(
        name="delete_all_files",
        target_world=TargetWorld.COMPUTER,
        target_agent="windows_agent",
        tier=ActionTier.TIER_3_DESTRUCTIVE
    )

    # Dispatched without approval token, permission engine denies it
    result = asyncio.run(dispatcher.dispatch(action))

    assert result["success"] is False
    assert result["status"] == "denied"
    assert result["status"] != "VERIFIED"
    assert result["status"] != "verified"
    assert "verification" in result
    assert result["verification"]["status"] == VerificationStatus.FAILED.value
    assert result["verification"]["status"] != "VERIFIED"
    assert result["verification"]["status"] != "verified"
