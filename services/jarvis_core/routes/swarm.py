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


class RunAgentRequest(BaseModel):
    agent_id: str
    task: Optional[str] = None


@router.post("/run")
async def run_agent_job(req: RunAgentRequest):
    """Executes a real agent operation and returns genuine results"""
    res = await swarm_manager.execute_agent_job(req.agent_id, req.task)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Agent execution failed"))
    return res
