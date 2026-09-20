"""
Security Policy & Approval Queue API Router for J.A.R.V.I.S. Core.
Exposes approval requests, authorization actions, and security audit log.
"""

import os
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/permission_engine"))

from engine import permission_engine
try:
    from services.observability import obs_audit
except ImportError:
    obs_audit = None

router = APIRouter(prefix="/api/v1/policy", tags=["Security & Policy"])


class ApproveRequest(BaseModel):
    approval_id: str
    token: Optional[str] = None
    approver: str = "user"


class RejectRequest(BaseModel):
    approval_id: str
    reason: str = "Rejected by user"


@router.get("/approvals")
async def get_pending_approvals():
    """Returns list of actions awaiting human-in-the-loop or MFA approval"""
    return {
        "status": "success",
        "pending_approvals": permission_engine.get_pending_approvals()
    }


@router.post("/approve")
async def approve_pending_action(req: ApproveRequest):
    """Authorizes a pending High or Critical action"""
    success = permission_engine.approve_request(
        approval_id=req.approval_id,
        approver=req.approver,
        token=req.token
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Approval failed: Invalid approval ID or missing MFA master secret for critical action"
        )
    return {
        "status": "approved",
        "approval_id": req.approval_id,
        "message": "Action successfully authorized for execution."
    }


@router.post("/reject")
async def reject_pending_action(req: RejectRequest):
    """Rejects and aborts a pending action"""
    success = permission_engine.reject_request(req.approval_id, req.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return {
        "status": "rejected",
        "approval_id": req.approval_id,
        "message": "Action rejected and cancelled."
    }


@router.get("/audit")
async def get_security_audit_log(limit: int = 50, event_type: Optional[str] = None, risk_level: Optional[str] = None):
    """Queries the immutable security and policy audit trail"""
    if obs_audit:
        entries = obs_audit.query_audit_trail(event_type=event_type, risk_level=risk_level, limit=limit)
    else:
        entries = permission_engine.audit_log[-limit:]
    return {
        "status": "success",
        "count": len(entries),
        "audit_entries": entries
    }
