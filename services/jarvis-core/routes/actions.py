"""
Action Dispatcher Router for J.A.R.V.I.S. Core.
Enforces blast-radius safety tiers and dispatches authorized actions.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uuid

from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from agents.action_dispatcher import action_dispatcher

logger = get_logger("JarvisActionsAPI")
router = APIRouter(prefix="/api/v1/actions", tags=["Actions"])


class ActionRequest(BaseModel):
    name: str
    target_world: str
    target_agent: str
    tier: str = "tier_1_soft"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    approval_token: Optional[str] = None


@router.post("")
async def dispatch_action(req: ActionRequest, background_tasks: BackgroundTasks):
    """
    Evaluates blast radius and executes action via ActionDispatcher.
    Enforces risk policies, executes real agent calls, and returns verified results.
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

    # Execute action through Permission Engine and Target Agent
    result = await action_dispatcher.dispatch(action, req.approval_token)

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
    if not result.get("success") and result.get("requires_approval"):
        logger.warning(f"Action requires approval: {action.name}")
        return {
            "status": "requires_approval",
            "action_id": action.action_id,
            "tier": action.tier.value,
            "rationale": result.get("rationale", "Explicit approval token required."),
            "message": "Action is Tier 3 (Destructive) or Mutating. Explicit cryptographic/voice approval token required."
        }

    return result
