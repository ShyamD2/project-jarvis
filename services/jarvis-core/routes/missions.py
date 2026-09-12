"""
Mission Control REST API Router for Project J.A.R.V.I.S.
Exposes mission lifecycle, phase progressions, approvals, and real-time objectives.
"""

import os
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/planner"))

from mission_control import mission_control

router = APIRouter(prefix="/api/v1/missions", tags=["Mission Control"])


class CreateMissionRequest(BaseModel):
    name: str = Field(..., description="Mission title, e.g. 'Production Readiness Audit'")
    objective: str = Field(..., description="High-level goal description")
    risk_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH, CRITICAL")


@router.get("")
async def get_missions():
    """Returns active mission and full mission registry"""
    return {
        "status": "success",
        "active_mission": mission_control.get_active_mission(),
        "missions": mission_control.get_all_missions()
    }


@router.get("/active")
async def get_active_mission():
    """Returns current active mission or idle state"""
    active = mission_control.get_active_mission()
    return {"status": "success" if active else "idle", "mission": active}


@router.post("")
async def create_mission(req: CreateMissionRequest):
    """Creates and starts an autonomous multi-phase mission"""
    res = await mission_control.create_mission(
        name=req.name,
        objective=req.objective,
        risk_level=req.risk_level
    )
    return {"status": "created", "mission": res}


@router.post("/{mission_id}/abort")
async def abort_mission(mission_id: str):
    """Aborts a running mission"""
    success = mission_control.abort_mission(mission_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
    return {"status": "aborted", "mission_id": mission_id}
