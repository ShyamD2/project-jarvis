"""
Event Ingestion Router for J.A.R.V.I.S. Core.
Receives events from Sensory, Agent, and External triggers.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone

from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger
try:
    from websocket.manager import ws_manager
except ImportError:
    try:
        from services.jarvis_core.websocket.manager import ws_manager
    except ImportError:
        from services.jarvis_core.websocket.manager import ws_manager

logger = get_logger("JarvisEventsAPI")
router = APIRouter(prefix="/api/v1/events", tags=["Events"])


class IngestEventRequest(BaseModel):
    source: str = Field(..., description="Source of the event (e.g. sensory.mic, agent.pc)")
    type: str = Field(..., description="Event type (e.g. sensory.clap, sensory.voice)")
    data: Dict[str, Any] = Field(default_factory=dict)
    traceparent: Optional[str] = None


@router.post("")
async def ingest_event(req: IngestEventRequest, background_tasks: BackgroundTasks):
    """
    Ingests an event, dispatches it to the Hybrid Event Mesh,
    and broadcasts to connected HUDs/dashboards in real time.
    """
    event = JarvisEvent(
        source=req.source,
        type=req.type,
        data=req.data,
        traceparent=req.traceparent
    )

    logger.info(f"Ingested event: {event.type} from {event.source}")

    # Dispatch to hybrid mesh in background
    background_tasks.add_task(mesh.publish, event)

    # Broadcast to live UI WebSocket
    background_tasks.add_task(
        ws_manager.broadcast,
        {"channel": "events", "event": event.to_dict()}
    )

    return {
        "status": "accepted",
        "event_id": event.id,
        "timestamp": event.time
    }
