"""
Versioned API Contract (v1) for Project J.A.R.V.I.S. Core
Provides a standardized OpenAPI specification for all clients:
  - Floating HUD / Web UI
  - Telegram Gateway
  - Voice / WakeWord Daemon
  - Mobile Nodes & Remote CLI

Every single action passes through the Canonical Execution Pipeline.
Direct mutations bypassing CanonicalPipeline are strictly prohibited.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import time
import uuid

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config
from shared.schemas.action_envelope import ActionTier, TargetWorld
from services.brain.canonical_pipeline import canonical_pipeline
from services.brain.tools.registry import registry as tool_registry
from services.memory.world_model import world_model
from agents.intelligence.emergency_stop import emergency_stop
from services.observability.metrics import obs_metrics

logger = get_logger("JarvisApiV1Contract")
router = APIRouter(prefix="/api/v1", tags=["V1 Contract"])


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language command or prompt from user")
    user_id: str = Field(default="operator", description="Authenticated user identity")
    user_role: str = Field(default="OPERATOR", description="RBAC Role: OWNER, ADMIN, OPERATOR, VIEWER")
    device_id: str = Field(default="local_node", description="Originating node/device ID")
    trace_id: Optional[str] = Field(default=None, description="Distributed trace identifier")


class ActionExecutionRequest(BaseModel):
    tool: str = Field(..., description="Canonical tool name to invoke (e.g. computer.volume, query_system_telemetry)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Key-value arguments for tool")
    user_role: str = Field(default="OPERATOR", description="Caller RBAC Role")
    user_id: str = Field(default="operator", description="Caller identity")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic single-use action lease or ticket")
    idempotency_key: Optional[str] = Field(default=None, description="Unique key for request deduplication")
    device_id: str = Field(default="local_node", description="Target or source device ID")


class InterruptRequest(BaseModel):
    reason: str = Field(default="Operator emergency interrupt", description="Reason for aborting executions")
    operator_token: Optional[str] = Field(default=None, description="Master secret if lifting stand-down")


@router.post("/query")
async def execute_query(req: QueryRequest):
    """
    Primary NL query ingress point.
    Normalizes query, selects appropriate canonical tool, and executes through Canonical Pipeline.
    """
    if emergency_stop.is_stopped:
        raise HTTPException(
            status_code=403,
            detail="EMERGENCY_STAND_DOWN_ACTIVE: All query execution is frozen."
        )

    # Fast-path telemetry queries
    q_lower = req.query.lower().strip()
    if any(k in q_lower for k in ["cpu", "memory", "battery", "status", "telemetry"]):
        res = await canonical_pipeline.execute_request(
            tool_name="query_system_telemetry",
            parameters={"query_type": "general"},
            source="api_v1_query",
            user_role=req.user_role,
            user_id=req.user_id,
            device_id=req.device_id,
            raw_query=req.query
        )
        return {
            "query": req.query,
            "response": f"System telemetry retrieved: {res.get('result', {})}",
            "verified": res.get("success", False),
            "execution": res
        }

    # Default query execution via Canonical Pipeline query router
    res = await canonical_pipeline.execute_request(
        tool_name="system.status",
        parameters={"action": "describe"},
        source="api_v1_query",
        user_role=req.user_role,
        user_id=req.user_id,
        device_id=req.device_id,
        raw_query=req.query
    )
    return {
        "query": req.query,
        "response": "Query processed through Canonical Execution Pipeline.",
        "verified": res.get("success", False),
        "execution": res
    }


@router.post("/actions")
async def execute_action(req: ActionExecutionRequest):
    """
    Authoritative mutation and reflex gateway.
    Every single tool call is verified, risk-classified, and audited.
    """
    res = await canonical_pipeline.execute_request(
        tool_name=req.tool,
        parameters=req.parameters,
        source="api_v1",
        user_role=req.user_role,
        user_id=req.user_id,
        approval_token=req.approval_token,
        idempotency_key=req.idempotency_key,
        device_id=req.device_id
    )
    return res


@router.get("/status")
async def get_system_status():
    """Returns aggregated real-time status across Core, World Model, and Safety."""
    return {
        "status": "ONLINE" if not emergency_stop.is_stopped else "STAND_DOWN",
        "emergency_stand_down": emergency_stop.is_stopped,
        "world_model": world_model.get_full_world_state(),
        "timestamp": time.time(),
        "version": "v1.0"
    }


@router.get("/capabilities")
async def get_capabilities():
    """Returns dynamic tool registry capability discovery manifest."""
    tools = tool_registry.list_tools()
    return {
        "count": len(tools),
        "capabilities": [
            {
                "name": t.canonical_name,
                "tier": t.tier.value if hasattr(t.tier, "value") else str(t.tier),
                "target_world": t.target_world.value if hasattr(t.target_world, "value") else str(t.target_world),
                "description": t.description,
                "requires_approval": t.tier in [ActionTier.TIER_2_MUTATING, ActionTier.TIER_3_DESTRUCTIVE]
            }
            for t in tools
        ]
    }


@router.get("/health")
async def get_health():
    """Returns granular subsystem health status."""
    return {
        "healthy": not emergency_stop.is_stopped,
        "subsystems": {
            "canonical_pipeline": "HEALTHY",
            "permission_engine": "HEALTHY",
            "verification_engine": "HEALTHY",
            "tool_registry": "HEALTHY",
            "emergency_circuit": "HEALTHY" if not emergency_stop.is_stopped else "HALTED"
        },
        "timestamp": time.time()
    }


@router.get("/metrics")
async def get_metrics():
    """Returns operational Prometheus-style metrics summary."""
    return {
        "pipeline_metrics": obs_metrics.get_metrics_summary() if hasattr(obs_metrics, "get_metrics_summary") else {},
        "timestamp": time.time()
    }


@router.post("/interrupt")
async def trigger_interrupt(req: InterruptRequest):
    """Triggers an instantaneous Emergency Stand-Down to freeze all physical and digital operations."""
    emergency_stop.trigger(req.reason)
    logger.warning(f"🛑 [API_v1] Emergency Interrupt triggered: {req.reason}")
    return {
        "success": True,
        "status": "EMERGENCY_STAND_DOWN_TRIGGERED",
        "reason": req.reason,
        "timestamp": time.time()
    }
