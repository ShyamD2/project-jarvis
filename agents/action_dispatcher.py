"""
Action Dispatcher for J.A.R.V.I.S. Action Fabric.
Routes authorized actions to Computer, Physical, or Digital world agents with dual-channel verification.
"""

from typing import Dict, Any, Optional
import time
import hashlib
import json
import uuid
from datetime import datetime, timezone

from shared.schemas.action_envelope import ActionEnvelope, TargetWorld, ActionTier
from shared.schemas.verification_contract import VerificationResult, VerificationStatus, VerificationMode
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
from services.verification.verification_engine import verification_engine
from services.verification.proof_of_execution import proof_engine

logger = get_logger("JarvisActionDispatcher")


class ActionDispatcher:
    def _capture_state_snapshot(self, action: ActionEnvelope, stage: str = "pre_execution") -> Dict[str, Any]:
        """Captures structured state snapshot before and after action execution."""
        world_val = action.target_world.value if hasattr(action.target_world, "value") else str(action.target_world)
        snapshot: Dict[str, Any] = {
            "world": world_val,
            "action": action.name,
            "stage": stage,
            "timestamp": time.time(),
            "parameters": dict(action.parameters or {})
        }
        try:
            if action.target_world == TargetWorld.COMPUTER:
                spec = action.verification_spec if isinstance(action.verification_spec, dict) else {}
                target_app = (
                    action.parameters.get("app")
                    or action.parameters.get("name")
                    or spec.get("process_name")
                )
                if target_app:
                    snapshot["target_app"] = target_app
                target_file = (
                    action.parameters.get("path")
                    or action.parameters.get("file_path")
                    or spec.get("path")
                )
                if target_file:
                    snapshot["target_file"] = target_file
                    snapshot["file_exists"] = os.path.exists(target_file)
            elif action.target_world == TargetWorld.PHYSICAL:
                snapshot["device_id"] = action.parameters.get("device_id", "esp32_lab_01")
                snapshot["target"] = action.parameters.get("target", "desk_lamp")
                snapshot["requested_state"] = action.parameters.get("state", True)
            elif action.target_world == TargetWorld.DIGITAL:
                snapshot["subcommand"] = action.parameters.get("subcommand", "status")
        except Exception as e:
            logger.debug(f"State snapshot non-fatal notice: {e}")
        return snapshot

    async def dispatch(
        self,
        action: ActionEnvelope,
        approval_token: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates permissions and executes the action in the appropriate world.
        Returns execution and verification results with cryptographic proof of execution.
        Fails closed on any unverified execution or unsupported action.
        """
        t_start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        before_state = self._capture_state_snapshot(action, stage="pre_execution")

        # 1. Authorize via Permission Engine
        role = user_role or ("OWNER" if action.approved_by else "OPERATOR")
        decision = permission_engine.evaluate(action, approval_token, user_role=role)
        if not decision.authorized:
            t_finish = time.time()
            finished_at = datetime.now(timezone.utc).isoformat()
            duration_ms = round((t_finish - t_start) * 1000, 2)

            verification = VerificationResult(
                action_id=action.action_id,
                status=VerificationStatus.FAILED,
                logical_verified=False,
                sensory_verified=False,
                failure_reason=decision.rationale or "Permission denied",
                details={
                    "authorized": False,
                    "rationale": decision.rationale,
                    "requires_approval": decision.requires_explicit_approval
                }
            )

            param_hash = hashlib.sha256(
                json.dumps(action.parameters or {}, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()

            tier_str = decision.tier.value if hasattr(decision.tier, 'value') else str(getattr(decision, 'tier', action.tier.value if hasattr(action.tier, 'value') else str(action.tier)))
            receipt = proof_engine.generate_receipt(
                action_id=action.action_id,
                request=action.name,
                planned_action=f"{action.target_world.value if hasattr(action.target_world, 'value') else str(action.target_world)}:{action.name}",
                risk_tier=tier_str,
                authorization={
                    "lease_id": getattr(decision, "single_use_lease_id", None) or approval_token,
                    "nonce": uuid.uuid4().hex,
                    "authorized_by": role,
                    "parameter_hash": param_hash
                },
                execution={
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                    "exit_code": 1
                },
                before_state=before_state,
                after_state=before_state,
                verification={
                    "logical": False,
                    "sensory": False,
                    "state_match": False,
                    "contract_mode": "none"
                },
                rollback={
                    "available": bool((action.parameters or {}).get("can_rollback", False)),
                    "executed": False
                },
                final_status="BLOCKED",
                store=True
            )

            return {
                "success": False,
                "action_id": action.action_id,
                "status": "denied",
                "rationale": decision.rationale,
                "requires_approval": decision.requires_explicit_approval,
                "verification": verification.to_dict(),
                "proof_of_execution": receipt.to_dict()
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
                    action.parameters.get("script", ""),
                    ticket_id=action.parameters.get("ticket_id"),
                    operator_approved=True
                )
            else:
                raw_result = {
                    "success": False,
                    "status": "unsupported_action",
                    "error": f"Unsupported computer action: {action.name}",
                    "channel_1_logical": False,
                    "channel_2_sensory": False
                }

        elif action.target_world == TargetWorld.PHYSICAL:
            if action.name in (
                "set_relay", "toggle_light", "switch_relay", "turn_on",
                "turn_off", "turn_on_light", "turn_off_light",
                "control_device", "control_physical_device"
            ):
                device_id = action.parameters.get("device_id", "esp32_lab_01")
                target = action.parameters.get("target", "desk_lamp")
                state = action.parameters.get("state", True)
                raw_result = esp32_agent.set_relay(device_id, target, state)
            else:
                raw_result = {
                    "success": False,
                    "status": "unsupported_action",
                    "error": f"Unsupported physical action: {action.name}",
                    "channel_1_logical": False,
                    "channel_2_sensory": False
                }

        elif action.target_world == TargetWorld.DIGITAL:
            if action.name in ("terraform", "run_terraform", "terraform_operation") or action.name.startswith("terraform."):
                subcommand = action.parameters.get("subcommand") or (action.name.split(".", 1)[1] if "." in action.name else "validate")
                raw_result = aws_agent.run_terraform_operation(subcommand)
            elif action.name in ("check_cloud", "cloud_health", "aws_health", "check_cloud_health"):
                raw_result = aws_agent.check_cloud_health()
            else:
                raw_result = {
                    "success": False,
                    "status": "unsupported_action",
                    "error": f"Unsupported digital action: {action.name}",
                    "channel_1_logical": False,
                    "channel_2_sensory": False
                }

        else:
            raw_result = {
                "success": False,
                "status": "unsupported_world",
                "error": f"Unsupported target world: {action.target_world}",
                "channel_1_logical": False,
                "channel_2_sensory": False
            }

        # 3. Capture Post-Execution State Snapshot
        after_state = self._capture_state_snapshot(action, stage="post_execution")
        after_state["raw_result"] = {k: v for k, v in raw_result.items() if k not in ("channel_1_logical", "channel_2_sensory")}
        after_state["success"] = raw_result.get("success", False)

        # 4. Formulate Dual-Channel Verification Result
        execution_ok = raw_result.get("success", False) is True
        logical_ok = raw_result.get("channel_1_logical", execution_ok) is True

        # Physical actions strictly require sensory proof (channel_2_lux or sensory_verified)
        sensory_ok = (raw_result.get("channel_2_lux") is not None) or bool(raw_result.get("sensory_verified", False)) or bool(raw_result.get("channel_2_sensory", False))

        # Computer actions with state verification contracts: process/file/ui state must be verified
        contract_ok = True
        verification_mode = None
        if action.target_world == TargetWorld.COMPUTER:
            if action.verification_spec:
                spec = action.verification_spec
                raw_mode = spec.get("mode") if isinstance(spec, dict) else str(spec)
                if raw_mode in (VerificationMode.PROCESS_STATE, VerificationMode.PROCESS_STATE.value, "process_state", "process"):
                    verification_mode = VerificationMode.PROCESS_STATE
                    proc_name = spec.get("process_name") or spec.get("app") or action.parameters.get("app") or action.parameters.get("name")
                    if proc_name:
                        contract_ok = verification_engine.verify_process_state(
                            proc_name,
                            expected_running=spec.get("expected_running", True),
                            timeout_seconds=spec.get("timeout_seconds", 1.0)
                        )
                    else:
                        contract_ok = False
                elif raw_mode in (VerificationMode.FILE_STATE, VerificationMode.FILE_STATE.value, "file_state", "file"):
                    verification_mode = VerificationMode.FILE_STATE
                    path = spec.get("path") or spec.get("file_path") or action.parameters.get("path")
                    if path:
                        contract_ok = verification_engine.verify_file_state(
                            path,
                            must_exist=spec.get("must_exist", True),
                            expected_min_size=spec.get("expected_min_size", 0),
                            expected_hash=spec.get("expected_hash")
                        )
                    else:
                        contract_ok = False
                elif raw_mode in (VerificationMode.UI_STATE, VerificationMode.UI_STATE.value, "ui_state", "ui"):
                    verification_mode = VerificationMode.UI_STATE
                    win_title = spec.get("window_title") or spec.get("title") or action.parameters.get("app")
                    if win_title:
                        contract_ok = verification_engine.verify_window_state(
                            win_title,
                            expected_visible=spec.get("expected_visible", True),
                            timeout_seconds=spec.get("timeout_seconds", 1.0)
                        )
                    else:
                        contract_ok = False
                elif raw_mode in (VerificationMode.LOGICAL_ONLY, VerificationMode.LOGICAL_ONLY.value, "logical_only"):
                    verification_mode = VerificationMode.LOGICAL_ONLY
                    contract_ok = logical_ok
            else:
                verification_mode = VerificationMode.LOGICAL_ONLY
        elif action.target_world == TargetWorld.PHYSICAL:
            verification_mode = VerificationMode.SENSOR_STATE
        elif action.target_world == TargetWorld.DIGITAL:
            verification_mode = VerificationMode.CLOUD_STATE

        physical_ok = sensory_ok if action.target_world == TargetWorld.PHYSICAL else True

        # Overall status is VERIFIED ONLY IF execution_ok and logical_ok and (sensory_ok if PHYSICAL else True) and contract_ok
        overall_verified = bool(execution_ok and logical_ok and physical_ok and contract_ok)
        status = VerificationStatus.VERIFIED if overall_verified else VerificationStatus.FAILED

        failure_reason = None
        if not overall_verified:
            if not execution_ok:
                failure_reason = raw_result.get("error") or "Execution failed"
            elif not logical_ok:
                failure_reason = "Channel 1 logical verification failed"
            elif action.target_world == TargetWorld.PHYSICAL and not sensory_ok:
                failure_reason = "Channel 2 sensory verification failed: physical action missing sensory proof"
            elif not contract_ok:
                failure_reason = "State verification contract validation failed"
            else:
                failure_reason = "Action verification failed"

        verification = VerificationResult(
            action_id=action.action_id,
            status=status,
            logical_verified=logical_ok,
            sensory_verified=sensory_ok if action.target_world == TargetWorld.PHYSICAL else raw_result.get("sensory_verified"),
            details=raw_result,
            failure_reason=failure_reason,
            verification_mode=verification_mode
        )

        t_finish = time.time()
        finished_at = datetime.now(timezone.utc).isoformat()
        duration_ms = round((t_finish - t_start) * 1000, 2)

        param_hash = hashlib.sha256(
            json.dumps(action.parameters or {}, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        final_status = "VERIFIED" if overall_verified else "FAILED"
        exit_code = 0 if overall_verified else (raw_result.get("exit_code", 1) if isinstance(raw_result.get("exit_code"), int) else 1)
        contract_mode_str = str(verification_mode.value if hasattr(verification_mode, 'value') else (verification_mode or "logical_only"))

        tier_str = decision.tier.value if hasattr(decision.tier, 'value') else str(getattr(decision, 'tier', action.tier.value if hasattr(action.tier, 'value') else str(action.tier)))
        receipt = proof_engine.generate_receipt(
            action_id=action.action_id,
            request=action.name,
            planned_action=f"{action.target_world.value if hasattr(action.target_world, 'value') else str(action.target_world)}:{action.name}",
            risk_tier=tier_str,
            authorization={
                "lease_id": getattr(decision, "single_use_lease_id", None) or approval_token,
                "nonce": uuid.uuid4().hex,
                "authorized_by": role,
                "parameter_hash": param_hash
            },
            execution={
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "exit_code": exit_code
            },
            before_state=before_state,
            after_state=after_state,
            verification={
                "logical": logical_ok,
                "sensory": sensory_ok if action.target_world == TargetWorld.PHYSICAL else bool(raw_result.get("sensory_verified", False)),
                "state_match": contract_ok,
                "contract_mode": contract_mode_str
            },
            rollback={
                "available": bool((action.parameters or {}).get("can_rollback", False)),
                "executed": False
            },
            final_status=final_status,
            store=True
        )

        return {
            "success": overall_verified,
            "status": "dispatched" if overall_verified else "failed",
            "action_id": action.action_id,
            "tier": decision.tier.value,
            "world": action.target_world.value,
            "agent": action.target_agent,
            "verification": verification.to_dict(),
            "details": raw_result,
            "proof_of_execution": receipt.to_dict()
        }


action_dispatcher = ActionDispatcher()
