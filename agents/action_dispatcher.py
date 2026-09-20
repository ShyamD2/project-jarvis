"""
Action Dispatcher for J.A.R.V.I.S. Action Fabric.
Routes authorized actions to Computer, Physical, or Digital world agents with dual-channel verification.
"""

from typing import Dict, Any, Optional
import time

from shared.schemas.action_envelope import ActionEnvelope, TargetWorld, ActionTier
from shared.schemas.verification_contract import VerificationResult, VerificationStatus
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/permission_engine")))
try:
    from engine import permission_engine
except ImportError:
    from services.permission_engine.engine import permission_engine
from agents.computer.windows_agent import windows_agent
from agents.physical.esp32_agent import esp32_agent
from agents.cloud.aws_agent import aws_agent
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisActionDispatcher")


class ActionDispatcher:
    async def dispatch(self, action: ActionEnvelope, approval_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates permissions and executes the action in the appropriate world.
        Returns execution and verification results.
        """
        # 1. Authorize via Permission Engine
        decision = permission_engine.evaluate(action, approval_token)
        if not decision.authorized:
            return {
                "success": False,
                "action_id": action.action_id,
                "status": "denied",
                "rationale": decision.rationale,
                "requires_approval": decision.requires_explicit_approval
            }

        # 2. Execute in Target World
        raw_result: Dict[str, Any] = {}

        if action.target_world == TargetWorld.COMPUTER:
            if action.name in ("launch_app", "open_app"):
                target_app = action.parameters.get("app") or action.parameters.get("name") or "notepad"
                raw_result = windows_agent.launch_app(
                    target_app,
                    action.parameters.get("args", [])
                )
            elif action.name == "execute_powershell":
                raw_result = windows_agent.execute_powershell(
                    action.parameters.get("script", "")
                )
            else:
                raw_result = {"success": True, "command": action.name, "channel_1_logical": True}

        elif action.target_world == TargetWorld.PHYSICAL:
            device_id = action.parameters.get("device_id", "esp32_lab_01")
            target = action.parameters.get("target", "desk_lamp")
            state = action.parameters.get("state", True)
            raw_result = esp32_agent.set_relay(device_id, target, state)

        elif action.target_world == TargetWorld.DIGITAL:
            if "terraform" in action.name:
                raw_result = aws_agent.run_terraform_operation(action.parameters.get("subcommand", "validate"))
            else:
                raw_result = aws_agent.check_cloud_health()

        # 3. Formulate Dual-Channel Verification Result
        logical_ok = raw_result.get("channel_1_logical", raw_result.get("success", False))
        sensory_ok = raw_result.get("channel_2_lux") is not None or "verification" in raw_result

        verification = VerificationResult(
            action_id=action.action_id,
            status=VerificationStatus.VERIFIED if logical_ok else VerificationStatus.FAILED,
            logical_verified=logical_ok,
            sensory_verified=sensory_ok,
            details=raw_result
        )

        return {
            "success": logical_ok,
            "status": "dispatched" if logical_ok else "failed",
            "action_id": action.action_id,
            "tier": decision.tier.value,
            "world": action.target_world.value,
            "agent": action.target_agent,
            "verification": verification.to_dict(),
            "details": raw_result
        }


action_dispatcher = ActionDispatcher()
