"""
Emergency Circuit Breaker Router for J.A.R.V.I.S.
Provides instant "Stand Down" kill-switch freezing all autonomous agent execution.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisEmergencyAPI")
router = APIRouter(prefix="/api/v1/emergency", tags=["Emergency"])


class EmergencyRequest(BaseModel):
    passphrase: str
    reason: Optional[str] = "Manual operator intervention"


@router.post("/stand-down")
async def trigger_stand_down(req: EmergencyRequest):
    """
    EMERGENCY KILL-SWITCH:
    Immediately freezes all agent write tokens and cancels running autonomous workflows.
    """
    if req.passphrase != config.master_secret:
        logger.warning("Unauthorized attempt to trigger Stand Down.")
        raise HTTPException(status_code=401, detail="Invalid master passphrase.")

    config.emergency_stand_down = True
    logger.critical(f"EMERGENCY STAND DOWN ACTIVATED. Reason: {req.reason}")

    # Broadcast emergency event across fast-path and cloud
    event = JarvisEvent(
        source="security.circuit_breaker",
        type="system.emergency_stand_down",
        data={"reason": req.reason, "status": "FROZEN"}
    )
    mesh.publish(event)

    return {
        "status": "frozen",
        "emergency_stand_down": True,
        "message": "JARVIS has stood down. All agent write-tokens are revoked."
    }


@router.post("/resume")
async def resume_operations(req: EmergencyRequest):
    """Resumes normal autonomous operations after emergency freeze."""
    if req.passphrase != config.master_secret:
        raise HTTPException(status_code=401, detail="Invalid master passphrase.")

    config.emergency_stand_down = False
    logger.info("Emergency stand-down lifted. Resuming normal operations.")

    event = JarvisEvent(
        source="security.circuit_breaker",
        type="system.operations_resumed",
        data={"status": "OPERATIONAL"}
    )
    mesh.publish(event)

    return {
        "status": "operational",
        "emergency_stand_down": False,
        "message": "Operations resumed, sir."
    }
