"""
System Diagnostics & Real-Time Probing Router for Project J.A.R.V.I.S.
Performs live health checks across MQTT Fast-Path, Ollama Local LLM, AWS Cloud, and Host Hardware.
"""

import os
import sys
import time
import socket
import urllib.request
import urllib.error
import json
from fastapi import APIRouter
from typing import Dict, Any

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents/cloud"))

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger

try:
    from aws_agent import aws_agent
except ImportError:
    aws_agent = None

logger = get_logger("JarvisDiagnosticsAPI")
router = APIRouter(prefix="/api/v1/diagnostics", tags=["Diagnostics & System Health"])


def probe_mqtt(host: str, port: int, timeout: float = 0.5) -> Dict[str, Any]:
    """Probes local MQTT broker with a raw TCP socket"""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "online",
                "host": host,
                "port": port,
                "latency_ms": latency_ms,
                "reachable": True
            }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "offline",
            "host": host,
            "port": port,
            "latency_ms": latency_ms,
            "reachable": False,
            "error": str(e)
        }


def probe_ollama(endpoint: str = "http://127.0.0.1:11434/api/tags", timeout: float = 1.0) -> Dict[str, Any]:
    """Probes local Ollama instance for installed models"""
    t0 = time.perf_counter()
    req = urllib.request.Request(endpoint, headers={"User-Agent": "JARVIS-Diagnostics/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in body.get("models", [])]
                return {
                    "status": "online",
                    "latency_ms": latency_ms,
                    "reachable": True,
                    "models_loaded": models,
                    "model_count": len(models)
                }
    except urllib.error.URLError as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "offline",
            "latency_ms": latency_ms,
            "reachable": False,
            "models_loaded": [],
            "error": f"Ollama not running: {e.reason}"
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "offline",
            "latency_ms": latency_ms,
            "reachable": False,
            "models_loaded": [],
            "error": str(e)
        }


def probe_host_vitals() -> Dict[str, Any]:
    """Queries live host OS metrics via psutil"""
    if not PSUTIL_AVAILABLE:
        return {"status": "unavailable", "error": "psutil not installed"}

    try:
        mem = psutil.virtual_memory()
        disk_path = "C:\\" if os.name == "nt" else "/"
        disk = psutil.disk_usage(disk_path)
        return {
            "status": "online",
            "cpu_percent": psutil.cpu_percent(interval=None),
            "cpu_cores": psutil.cpu_count(logical=True),
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent": mem.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "percent": disk.percent
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("")
async def get_system_diagnostics():
    """Returns comprehensive live diagnostics of all local and cloud dependencies"""
    mqtt_info = probe_mqtt(config.mqtt_broker, config.mqtt_port)
    ollama_info = probe_ollama()
    host_info = probe_host_vitals()

    cloud_info = {"status": "unconfigured"}
    if aws_agent:
        health = aws_agent.check_cloud_health()
        cloud_info = {
            "status": "online" if health.get("success") else "offline",
            "connected": health.get("success", False),
            "account": health.get("account"),
            "arn": health.get("arn"),
            "region": health.get("region"),
            "ec2_count": len(health.get("ec2_instances", [])),
            "s3_count": len(health.get("s3_buckets", [])),
            "error": health.get("error")
        }

    return {
        "status": "success",
        "timestamp": time.time(),
        "probes": {
            "mqtt_broker": mqtt_info,
            "ollama_local_llm": ollama_info,
            "aws_cloud": cloud_info,
            "host_hardware": host_info
        }
    }
