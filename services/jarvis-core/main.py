"""
Project J.A.R.V.I.S. Core API Server
Main entrance for the Master Orchestrator, Fast-Path Router, and Sensory Hub.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from websocket.manager import ws_manager
from routes.events import router as events_router
from routes.actions import router as actions_router
from routes.state import router as state_router
from routes.emergency import router as emergency_router
from routes.query import router as query_router
from routes.sensory import router as sensory_router
from routes.missions import router as missions_router
from routes.security_policy import router as security_policy_router
from routes.swarm import router as swarm_router
from routes.vision import router as vision_router
from routes.cloud import router as cloud_router
from routes.devops import router as devops_router
from routes.security import router as security_router
from routes.knowledge import router as knowledge_router
from routes.web_research import router as web_research_router
from routes.diagnostics import router as diagnostics_router

logger = get_logger("JarvisCoreService")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=========================================")
    logger.info("   J.A.R.V.I.S. CORE ENGINE INITIALIZING ")
    logger.info("=========================================")
    logger.info(f"Environment: {config.env}")
    logger.info(f"Local MQTT Fast-Path: {config.mqtt_broker}:{config.mqtt_port}")
    if sys.platform == "win32":
        try:
            from agents.computer.windows_agent import ensure_interactive_desktop
            ensure_interactive_desktop()
            logger.info("⚡ [Lifespan] Bound J.A.R.V.I.S. engine to WinSta0\\Default interactive desktop.")
        except Exception:
            pass
    logger.info(f"AWS Event Bus: {config.event_bus_name}")
    logger.info(f"Emergency Stand Down: {config.emergency_stand_down}")

    # Start PCDaemon background telemetry loop
    pc_task = None
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../pc-agent")))
        from agent_daemon import pc_daemon
        import asyncio
        pc_task = asyncio.create_task(pc_daemon.start())
        logger.info("⚡ [Lifespan] Started PCDaemon background telemetry loop.")
    except Exception as e:
        logger.warning(f"[Lifespan] PCDaemon background task could not be started: {e}")

    yield

    if 'pc_daemon' in locals() and pc_daemon:
        pc_daemon.stop()
    if pc_task:
        pc_task.cancel()
    logger.info("J.A.R.V.I.S. Core Engine shutting down.")


app = FastAPI(
    title="Project J.A.R.V.I.S. Core API",
    version="1.0.0",
    description="Central nervous system for autonomous cyber-physical coordination",
    lifespan=lifespan
)

# Trusted CORS origins: Local workstation endpoints only (prevents cross-origin browser attacks)
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1",
    "http://localhost",
]
custom_origins = os.getenv("JARVIS_ALLOWED_ORIGINS", "")
if custom_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(events_router)
app.include_router(actions_router)
app.include_router(state_router)
app.include_router(emergency_router)
app.include_router(query_router)
app.include_router(sensory_router)
app.include_router(missions_router)
app.include_router(security_policy_router)
app.include_router(swarm_router)
app.include_router(vision_router)
app.include_router(cloud_router)
app.include_router(devops_router)
app.include_router(security_router)
app.include_router(knowledge_router)
app.include_router(web_research_router)
app.include_router(diagnostics_router)

# Mount Static Dashboard
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/", include_in_schema=False)
    async def get_dashboard():
        return FileResponse(
            os.path.join(static_path, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "service": "jarvis-core",
        "status": "healthy",
        "env": config.env,
        "emergency_stand_down": config.emergency_stand_down,
        "fast_path_mesh": "connected"
    }


@app.get("/api/v1/voice/state", tags=["Voice"])
async def get_voice_state():
    from services.voice.voice_session import voice_session
    return {
        "status": "success",
        "state": voice_session.state.value,
        "last_interaction": voice_session.last_interaction_time
    }


@app.post("/api/v1/voice/reset", tags=["Voice"])
async def reset_voice_session():
    from services.voice.voice_session import voice_session
    voice_session.reset()
    return {"status": "success", "state": voice_session.state.value}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time full-duplex WebSocket stream for Live Dashboard HUD,
    voice audio chunks, and event subscriptions.
    """
    origin = websocket.headers.get("origin")
    if origin and not any(origin.startswith(prefix) for prefix in ["http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost", "vscode-webview:"]):
        logger.warning(f"[Security] Rejected unauthorized cross-origin WebSocket connection from: {origin}")
        await websocket.close(code=1008)
        return

    await ws_manager.connect(websocket)
    await ws_manager.send_personal_message(
        {"channel": "system", "message": "J.A.R.V.I.S. HUD Connected", "status": "online"},
        websocket
    )
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming ping or client events
            await ws_manager.send_personal_message(
                {"channel": "ack", "received": data},
                websocket
            )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=True
    )
