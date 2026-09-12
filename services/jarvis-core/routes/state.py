"""
World Model & System State Router for J.A.R.V.I.S. Core.
Exposes live state of IoT devices, PC daemon, and Cloud resources.
"""

import os
import sys
from fastapi import APIRouter
from typing import Dict, Any
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc-agent"))

try:
    from system_monitor import system_monitor
except ImportError:
    system_monitor = None

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisStateAPI")
router = APIRouter(prefix="/api/v1/state", tags=["State"])

# In-memory fast state store (synchronized with Redis/DynamoDB)
_LIVE_WORLD_STATE: Dict[str, Any] = {
    "system": {
        "status": "operational",
        "stand_down": False,
        "mode": "autonomous",
        "uptime_seconds": 0
    },
    "devices": {
        "esp32_lab_01": {
            "online": True,
            "relays": {"light_main": False, "desk_lamp": False, "aux_power": False},
            "sensors": {"lux": 150.0, "temperature_c": 24.5, "humidity": 50.0}
        }
    },
    "pc": {
        "os": "Windows",
        "agent_connected": True,
        "active_window": "VS Code",
        "cpu_percent": 12.4,
        "memory_percent": 45.8,
        "focus_mode": False
    },
    "cloud": {
        "aws_connected": True,
        "event_bus": "jarvis-event-bus",
        "active_deployments": 0
    }
}

START_TIME = time.time()


try:
    from agents.physical.esp32_agent import esp32_agent
except ImportError:
    esp32_agent = None

try:
    from agents.cloud.aws_agent import aws_agent
except ImportError:
    aws_agent = None

@router.get("")
async def get_full_world_state():
    """Retrieve current comprehensive world state snapshot with live telemetry"""
    _LIVE_WORLD_STATE["system"]["uptime_seconds"] = int(time.time() - START_TIME)

    # Real PC vitals
    if system_monitor:
        try:
            vitals = system_monitor.collect_telemetry()
            _LIVE_WORLD_STATE["pc"].update(vitals)
        except Exception as e:
            logger.warning(f"Error reading system vitals: {e}")

    # Real IoT device states from esp32_agent
    if esp32_agent:
        _LIVE_WORLD_STATE["devices"] = esp32_agent.device_states

    # Real cloud connection from aws_agent
    if aws_agent:
        health = aws_agent.check_cloud_health()
        _LIVE_WORLD_STATE["cloud"]["aws_connected"] = health.get("success", False)
        _LIVE_WORLD_STATE["cloud"]["account"] = health.get("account")
        _LIVE_WORLD_STATE["cloud"]["region"] = health.get("region")

    return _LIVE_WORLD_STATE


@router.get("/devices")
async def get_device_states():
    """Retrieve IoT device states"""
    return _LIVE_WORLD_STATE.get("devices", {})


@router.get("/pc")
async def get_pc_state():
    """Retrieve local Windows PC agent telemetry"""
    if system_monitor:
        try:
            vitals = system_monitor.collect_telemetry()
            _LIVE_WORLD_STATE["pc"].update(vitals)
        except Exception as e:
            logger.warning(f"Error reading system vitals: {e}")
    return _LIVE_WORLD_STATE.get("pc", {})


def update_world_state(domain: str, entity_id: str, data: Dict[str, Any]):
    """Internal helper to update the live world state"""
    if domain in _LIVE_WORLD_STATE:
        if domain == "devices":
            _LIVE_WORLD_STATE["devices"][entity_id] = data
        elif domain == "pc":
            _LIVE_WORLD_STATE["pc"].update(data)
