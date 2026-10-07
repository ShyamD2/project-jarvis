"""
Action Dispatcher and Verification Router for J.A.R.V.I.S. Core.
Enforces blast-radius safety tiers, dispatches authorized actions,
and serves cryptographic Proof-of-Execution receipts from the immutable ledger.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import uuid
import json
import hashlib
from datetime import datetime, timezone

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from agents.action_dispatcher import action_dispatcher
from services.verification.proof_of_execution import proof_engine

logger = get_logger("JarvisActionsAPI")

# Dedicated router for verification receipts
verification_router = APIRouter(prefix="/api/v1/verification", tags=["Verification"])


@verification_router.get("/receipts")
async def get_verification_receipts(limit: int = Query(default=50, ge=1, le=500)):
    """
    Returns recent cryptographic ExecutionReceipt objects from the immutable ledger.
    """
    receipts = proof_engine.list_receipts(limit=limit)
    return {
        "status": "success",
        "count": len(receipts),
        "receipts": receipts
    }


@verification_router.get("/receipts/{action_id}")
async def get_verification_receipt(action_id: str):
    """
    Returns a specific cryptographic ExecutionReceipt by action_id with integrity verification.
    """
    receipt = proof_engine.get_receipt(action_id)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail=f"Execution receipt for action '{action_id}' not found."
        )

    is_valid = proof_engine.verify_receipt_integrity(receipt)

    resp = dict(receipt)
    resp["status"] = "success"
    resp["action_id"] = action_id
    resp["integrity_verified"] = is_valid
    resp["receipt"] = receipt
    return resp


# Main actions router
router = APIRouter(tags=["Actions"])
router.include_router(verification_router)


class ActionRequest(BaseModel):
    name: str
    target_world: str
    target_agent: str
    tier: str = "tier_1_soft"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    approval_token: Optional[str] = None
    idempotency_key: Optional[str] = None
    device_id: Optional[str] = "local_node"
    user_role: Optional[str] = "OPERATOR"


@router.post("/api/v1/actions")
@router.post("/actions", include_in_schema=False)
async def dispatch_action(req: ActionRequest, background_tasks: BackgroundTasks):
    """
    Evaluates blast radius and executes action via ActionDispatcher / Canonical Pipeline.
    Enforces risk policies, executes real agent calls, and returns verified results with
    cryptographic Proof-of-Execution receipts.
    """
    if config.emergency_stand_down:
        raise HTTPException(
            status_code=403,
            detail="EMERGENCY_STAND_DOWN_ACTIVE: All action execution is frozen."
        )

    try:
        tier_enum = ActionTier(req.tier)
        world_enum = TargetWorld(req.target_world)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    action = ActionEnvelope(
        name=req.name,
        target_world=world_enum,
        target_agent=req.target_agent,
        tier=tier_enum,
        parameters=req.parameters
    )

    logger.info(f"Dispatching action [{action.tier.value}] '{action.name}' to {action.target_agent} ({action.target_world.value})")

    # Execute action through Canonical Pipeline (Phase 36 Stage 36.3)
    from services.brain.canonical_pipeline import canonical_pipeline
    result = await canonical_pipeline.execute_request(
        tool_name=action.name,
        parameters=action.parameters,
        source="core_api",
        approval_token=req.approval_token,
        idempotency_key=req.idempotency_key,
        device_id=req.device_id or "local_node",
        user_role=req.user_role or "OPERATOR"
    )

    # Attach proof of execution if not already attached
    if "proof_of_execution" not in result and result.get("action_id"):
        existing_receipt = proof_engine.get_receipt(result["action_id"])
        if existing_receipt:
            result["proof_of_execution"] = existing_receipt
        else:
            param_hash = hashlib.sha256(
                json.dumps(action.parameters or {}, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            receipt = proof_engine.generate_receipt(
                action_id=result["action_id"],
                request=action.name,
                planned_action=f"{action.target_world.value}:{action.name}",
                risk_tier=result.get("tier", action.tier.value),
                authorization={
                    "lease_id": req.approval_token,
                    "nonce": uuid.uuid4().hex,
                    "authorized_by": req.user_role or "OPERATOR",
                    "parameter_hash": param_hash
                },
                execution={
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": float(result.get("duration_ms", 0.0)),
                    "exit_code": 0 if result.get("success") else 1
                },
                before_state={"parameters": action.parameters},
                after_state={"result": result.get("result", {})},
                verification={
                    "logical": bool(result.get("success", False)),
                    "sensory": False,
                    "state_match": bool(result.get("success", False)),
                    "contract_mode": "canonical_pipeline"
                },
                rollback={"available": False, "executed": False},
                final_status="VERIFIED" if result.get("success") else ("BLOCKED" if result.get("status") == "confirmation_required" else "FAILED"),
                store=True
            )
            result["proof_of_execution"] = receipt.to_dict()

    # Publish action execution event to Mesh
    event = JarvisEvent(
        source="core.action_dispatcher",
        type="action.executed",
        data={
            "action": action.to_dict(),
            "result": result
        }
    )
    background_tasks.add_task(mesh.publish, event)

    # If action was blocked due to pending approval, return structured approval payload
    if not result.get("success") and result.get("requires_confirmation"):
        logger.warning(f"Action requires approval: {action.name}")
        return {
            "status": "requires_approval",
            "action_id": result.get("action_id", action.action_id),
            "tier": result.get("tier", action.tier.value),
            "rationale": result.get("rationale", "Explicit approval token required."),
            "ticket_id": result.get("ticket_id"),
            "message": "Action is Tier 3 (Destructive) or Mutating. Explicit cryptographic/voice approval token required.",
            "proof_of_execution": result.get("proof_of_execution")
        }

    return result


# Convenience aliases for action receipts
@router.get("/api/v1/actions/receipts", include_in_schema=False)
async def get_actions_receipts_alias(limit: int = 50):
    return await get_verification_receipts(limit=limit)


@router.get("/api/v1/actions/receipts/{action_id}", include_in_schema=False)
async def get_action_receipt_alias(action_id: str):
    return await get_verification_receipt(action_id)
