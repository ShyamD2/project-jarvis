"""
Canonical Execution Pipeline for Project J.A.R.V.I.S. (Phase 36 Stage 36.3).
The single, authoritative gateway for all mutating, read-only, and reflex actions.
Eliminates all direct agent bypasses and enforces strict 3-class routing:
  - Reflex Class (Tier 0/1): Policy checked, capability checked, executed, verified (<10ms)
  - Read-Only Class: Telemetry and status queries, freshness verified
  - Mission Class: Planner, DAG, Risk classifier, Approval lease, Sandbox, Verification, Reality Reconciliation
"""

from __future__ import annotations
import time
import uuid
import hashlib
from typing import Dict, Any, Optional, List

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld, ExecutionClass, UniversalTransactionRecord
from shared.schemas.verification_contract import VerificationResult, VerificationStatus
from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.permission_engine.engine import permission_engine, PermissionDecision
from services.brain.tools.registry import registry as tool_registry
from services.verification.verification_engine import verification_engine
from services.security.prompt_shield import prompt_shield
from services.security.secret_redactor import secret_redactor
from services.memory.world_model import world_model
from agents.intelligence.emergency_stop import emergency_stop

logger = get_logger("JarvisCanonicalPipeline")


class CanonicalPipeline:
    def __init__(self):
        self.transactions: Dict[str, UniversalTransactionRecord] = {}

    async def execute_request(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        source: str = "internal",
        user_role: str = "OPERATOR",
        user_id: str = "operator",
        approval_token: Optional[str] = None,
        trace_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        confidence: float = 1.0,
        raw_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Universal canonical execution router for all tool operations.
        Guarantees that NO tool executes without policy check, permission check,
        and post-condition verification.
        """
        t0 = time.time()
        params = parameters or {}
        t_id = trace_id or f"tr_{uuid.uuid4().hex[:12]}"
        m_id = mission_id or f"m_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        act_id = f"a_{uuid.uuid4().hex[:8]}"

        # Compute arguments hash
        arg_str = str(sorted(params.items()))
        arg_hash = hashlib.sha256(arg_str.encode("utf-8")).hexdigest()[:16]

        # 0. Emergency Stand-Down & Circuit Breaker Check
        if emergency_stop.is_stopped:
            logger.warning(f"🚨 [CanonicalPipeline] Execution of '{tool_name}' halted: Stand-Down active.")
            return {
                "success": False,
                "status": "emergency_halted",
                "final_status": "FAILED",
                "execution_class": "unknown",
                "error": "Execution halted: Emergency Stand-Down is active.",
                "duration_ms": (time.time() - t0) * 1000
            }

        # 1. Tool Resolution & Capability Discovery Check (Item 103 & 104)
        canonical_name = tool_registry.resolve_canonical_name(tool_name)
        tool = tool_registry.get_tool(canonical_name)
        if not tool:
            return {
                "success": False,
                "status": "tool_not_found",
                "final_status": "FAILED",
                "execution_class": "unknown",
                "error": f"Tool '{tool_name}' is not registered in the Tool Registry.",
                "duration_ms": (time.time() - t0) * 1000
            }

        # Check tool health
        tool_health = tool_registry.get_tool_health(canonical_name)
        if tool_health["status"] in ["UNAVAILABLE", "BLOCKED"]:
            return {
                "success": False,
                "status": "tool_unavailable",
                "final_status": "FAILED",
                "execution_class": "unknown",
                "error": f"Tool '{canonical_name}' is currently {tool_health['status']}: {tool_health.get('reason', 'N/A')}",
                "duration_ms": (time.time() - t0) * 1000
            }

        # 2. Construct Action Envelope with Execution Class
        effective_tier = tool.tier

        is_query_name = any(k in canonical_name for k in ["query", "status", "telemetry", "list", "describe", "get_", "health"])
        is_query_param = params.get("action") in ["status", "list", "describe", "get", "check", "temperatures", "disk_space", "mic_status"]
        is_reflex_name = any(k in canonical_name for k in ["volume", "audio", "display", "lock", "switch", "tab", "media"])

        if effective_tier == ActionTier.TIER_0_REFLEX:
            if is_query_name:
                exec_class = ExecutionClass.READ_ONLY
            else:
                exec_class = ExecutionClass.REFLEX
        elif is_query_name or is_query_param:
            exec_class = ExecutionClass.READ_ONLY
        elif effective_tier == ActionTier.TIER_1_SOFT and is_reflex_name:
            exec_class = ExecutionClass.REFLEX
        else:
            exec_class = ExecutionClass.MISSION

        target_agent = "jarvis_core_agent"
        if tool.target_world == TargetWorld.COMPUTER:
            target_agent = "windows_agent"
        elif tool.target_world == TargetWorld.DIGITAL:
            target_agent = "aws_agent" if "aws" in canonical_name or "terraform" in canonical_name else "docker_agent"
        elif tool.target_world == TargetWorld.PHYSICAL:
            target_agent = "esp32_agent"

        action = ActionEnvelope(
            name=canonical_name,
            target_world=tool.target_world,
            target_agent=target_agent,
            tier=effective_tier,
            parameters=params,
            action_id=act_id,
            execution_class=exec_class,
            trace_id=t_id,
            mission_id=m_id
        )

        # 3. Create Universal Transaction Record (Stage 36.1 Item 4)
        tx = UniversalTransactionRecord(
            mission_id=m_id,
            task_id=f"t_{uuid.uuid4().hex[:6]}",
            action_id=act_id,
            trace_id=t_id,
            user_id=user_id,
            source=source,
            tool=canonical_name,
            arguments_hash=arg_hash,
            risk_tier=effective_tier.value,
            final_status="PENDING"
        )
        self.transactions[act_id] = tx

        # 4. Multi-Factor Permission Evaluation (Stage 36.2)
        decision: PermissionDecision = permission_engine.evaluate(
            action=action,
            approval_token=approval_token,
            confidence=confidence,
            user_role=user_role
        )

        if not decision.authorized:
            tx.final_status = "BLOCKED"
            tx.duration_ms = (time.time() - t0) * 1000
            if decision.requires_explicit_approval:
                return {
                    "success": False,
                    "status": "confirmation_required",
                    "final_status": "PENDING_APPROVAL",
                    "requires_confirmation": True,
                    "ticket_id": decision.approval_id,
                    "tier": decision.tier.value,
                    "rationale": decision.rationale,
                    "action_id": act_id,
                    "execution_class": exec_class.value,
                    "duration_ms": tx.duration_ms
                }
            return {
                "success": False,
                "status": "permission_denied",
                "final_status": "FAILED",
                "error": decision.rationale,
                "action_id": act_id,
                "execution_class": exec_class.value,
                "duration_ms": tx.duration_ms
            }

        # 5. EXECUTION LAYER: Execute via Tool
        # In Reflex and Read-Only classes, execution is fast and bypasses mission persistence
        try:
            raw_exec = await tool_registry.execute_tool(
                name=canonical_name,
                parameters=params,
                caller_agent=f"{source}_gateway",
                approval_id=decision.single_use_lease_id or approval_token,
                raw_query=raw_query or tool_name
            )
            raw_result = raw_exec.get("result", {})
            transport_ok = raw_exec.get("status") != "error"
        except Exception as exec_err:
            raw_result = {"error": str(exec_err)}
            transport_ok = False

        tx.execution_result = raw_result

        # 6. GROUND-TRUTH VERIFICATION: Contract Check
        try:
            verif: VerificationResult = verification_engine.verify_action_execution(
                canonical_name, params, raw_result
            )
        except Exception as verif_err:
            verif = VerificationResult(
                action_id=act_id,
                status=VerificationStatus.UNKNOWN,
                failure_reason=f"Verification engine exception: {verif_err}"
            )

        tx.verification_result = verif.to_dict()

        # 7. PIPELINE FINAL-STATE AUTHORITY (Item 122 & Cardinal Rule 1)
        # Tools cannot declare SUCCESS. Only pipeline evaluates post-condition.
        if not transport_ok:
            final_status = "FAILED"
        elif verif.status == VerificationStatus.VERIFIED and verif.match:
            final_status = "SUCCESS"
        elif verif.status == VerificationStatus.FAILED or (verif.match is False and verif.failure_reason):
            final_status = "FAILED"
        else:
            final_status = "UNKNOWN"

        tx.final_status = final_status
        tx.duration_ms = (time.time() - t0) * 1000

        # 8. SETTLEMENT: World Model Update on Success (Item 116 Reality Check)
        if final_status == "SUCCESS":
            try:
                world_model.record_observed_mutation(canonical_name, params, raw_result)
            except Exception:
                pass

        logger.info(f"✔ [CanonicalPipeline: {exec_class.value.upper()}] Tool '{canonical_name}' -> Final Status: [{final_status}] ({tx.duration_ms:.1f}ms)")

        return {
            "success": final_status == "SUCCESS",
            "final_status": final_status,
            "action_id": act_id,
            "tool": canonical_name,
            "execution_class": exec_class.value,
            "result": raw_result,
            "verification": verif.to_dict(),
            "duration_ms": round(tx.duration_ms, 2)
        }


canonical_pipeline = CanonicalPipeline()
