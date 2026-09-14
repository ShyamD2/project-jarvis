"""
Emergency Circuit Breaker & Safety Audit Router for J.A.R.V.I.S.
Provides instant "Stand Down" kill-switch, pending ticket confirmation, and audit log inspection.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger
from agents.intelligence.emergency_stop import emergency_stop
from agents.intelligence.safety_guard import safety_guard
from agents.intelligence.audit_logger import audit_logger

logger = get_logger("JarvisEmergencyAPI")
router = APIRouter(prefix="/api/v1/emergency", tags=["Emergency"])


class EmergencyRequest(BaseModel):
    passphrase: Optional[str] = None
    reason: Optional[str] = "Manual operator intervention"


class TicketConfirmationRequest(BaseModel):
    ticket_id: str
    approver: Optional[str] = "ui_operator"
    method: Optional[str] = "hud_button"


@router.get("/status")
async def get_emergency_status():
    """Returns whether emergency stand-down is currently active"""
    return {
        "is_stopped": emergency_stop.is_stopped,
        "emergency_stand_down": config.emergency_stand_down
    }


@router.post("/stand-down")
async def trigger_stand_down(req: EmergencyRequest):
    """
    EMERGENCY KILL-SWITCH:
    Immediately freezes all agent write tokens and cancels running autonomous workflows.
    """
    res = emergency_stop.trigger_emergency_stop(source="api_request", reason=req.reason or "API call")
    return res


@router.post("/resume")
async def resume_operations(req: EmergencyRequest):
    """Resumes normal autonomous operations after emergency freeze."""
    res = emergency_stop.resume_operations()
    return res


@router.get("/safety/pending")
async def get_pending_safety_tickets():
    """Returns active pending tickets awaiting user confirmation"""
    ticket = safety_guard.get_latest_pending_ticket()
    if ticket:
        return {
            "has_pending": True,
            "ticket": {
                "approval_id": ticket.approval_id,
                "action_name": ticket.action_name,
                "tier": ticket.tier.value,
                "rationale": ticket.rationale,
                "parameters": ticket.parameters,
                "expires_at": ticket.expires_at
            }
        }
    return {"has_pending": False, "ticket": None}


@router.post("/safety/confirm")
async def confirm_safety_ticket(req: TicketConfirmationRequest):
    """Confirms a pending safety ticket from HUD / UI"""
    success = safety_guard.confirm_ticket(req.ticket_id, approver=req.approver or "operator", method=req.method or "hud")
    if not success:
        raise HTTPException(status_code=400, detail="Ticket not found or expired")
    return {"success": True, "ticket_id": req.ticket_id, "status": "APPROVED"}


@router.post("/safety/reject")
async def reject_safety_ticket(req: TicketConfirmationRequest):
    """Rejects a pending safety ticket"""
    success = safety_guard.reject_ticket(req.ticket_id, reason="Rejected by UI operator")
    return {"success": success, "ticket_id": req.ticket_id, "status": "REJECTED"}


@router.get("/audit/logs")
async def get_audit_logs(limit: int = 50):
    """Returns recent structured execution audit logs"""
    logs = audit_logger.read_recent_logs(limit=limit)
    return {"count": len(logs), "logs": logs}
