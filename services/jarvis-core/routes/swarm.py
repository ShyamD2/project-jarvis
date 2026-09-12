"""
Swarm Agents REST API Router for Project J.A.R.V.I.S.
Exposes multi-agent swarm status, task dispatch, and collaborative telemetry.
"""

import os
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents/swarm"))

from swarm_manager import swarm_manager

router = APIRouter(prefix="/api/v1/swarm", tags=["Agent Swarm"])


class DispatchTaskRequest(BaseModel):
    agent_id: str
    task: str


@router.get("/agents")
async def get_all_agents():
    """Returns status and capabilities of all 12 specialized persona agents"""
    return {
        "status": "success",
        "count": len(swarm_manager.get_all_agents()),
        "agents": swarm_manager.get_all_agents()
    }


@router.post("/dispatch")
async def dispatch_agent_task(req: DispatchTaskRequest):
    """Dispatches a task to a specialized agent"""
    success = swarm_manager.dispatch_task(req.agent_id, req.task)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")
    return {"status": "dispatched", "agent_id": req.agent_id, "task": req.task}
