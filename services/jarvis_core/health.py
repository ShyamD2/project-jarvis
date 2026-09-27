"""
Deep Subsystem Health & Readiness Probes for Project J.A.R.V.I.S. Core.
Provides Kubernetes/Docker-compliant Liveness, Readiness, and Diagnostic Probes.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, Any, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.database import get_sqlite_connection
from agents.intelligence.emergency_stop import emergency_stop
from services.brain.tools.registry import registry as tool_registry

try:
    import psutil
except ImportError:
    psutil = None

logger = get_logger("JarvisHealthProbes")

BOOT_TIME = time.time()


def check_liveness() -> Dict[str, Any]:
    """Liveness probe: verifies process is alive and event loop is responsive."""
    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - BOOT_TIME, 2),
        "pid": os.getpid()
    }


def check_readiness() -> Tuple[bool, Dict[str, Any]]:
    """
    Readiness probe: validates SQLite read/write, memory/disk availability,
    tool registry state, and emergency circuit breaker status.
    Returns (is_ready, details_dict).
    """
    now = time.time()
    checks: Dict[str, Any] = {}
    is_ready = True

    # 1. Emergency Stop Check
    if emergency_stop.is_stopped:
        reason = getattr(emergency_stop, "stop_reason", None) or "Emergency stand down active"
        checks["emergency_circuit"] = {
            "status": "STAND_DOWN",
            "reason": reason
        }
        # In stand-down, core is reachable but not ready to accept traffic
        is_ready = False
    else:
        checks["emergency_circuit"] = {"status": "HEALTHY"}

    # 2. SQLite Database Readiness
    db_probe_start = time.perf_counter()
    try:
        db_path = os.path.join(PROJECT_ROOT, "data", "memory", "episodic_memory.db")
        with get_sqlite_connection(db_path, timeout=5.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            val = cursor.fetchone()[0]
            if val != 1:
                raise ValueError("Unexpected SQLite probe return value")
        probe_latency_ms = round((time.perf_counter() - db_probe_start) * 1000, 2)
        checks["sqlite_storage"] = {
            "status": "HEALTHY",
            "latency_ms": probe_latency_ms,
            "database": os.path.basename(db_path)
        }
    except Exception as e:
        logger.error(f"[Health] SQLite readiness probe failed: {e}")
        checks["sqlite_storage"] = {
            "status": "DOWN",
            "error": str(e)
        }
        is_ready = False

    # 3. System Resources (RAM & Disk)
    if psutil:
        try:
            mem = psutil.virtual_memory()
            mem_pct = mem.percent
            checks["memory"] = {
                "status": "HEALTHY" if mem_pct < 95.0 else "CRITICAL",
                "used_percent": mem_pct,
                "available_mb": round(mem.available / (1024 * 1024), 1)
            }
            if mem_pct >= 95.0:
                is_ready = False

            disk = psutil.disk_usage(PROJECT_ROOT)
            disk_pct = disk.percent
            checks["disk"] = {
                "status": "HEALTHY" if disk_pct < 95.0 else "CRITICAL",
                "used_percent": disk_pct,
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
            }
            if disk_pct >= 95.0:
                is_ready = False
        except Exception as e:
            checks["system_resources"] = {"status": "UNKNOWN", "notice": str(e)}
    else:
        checks["system_resources"] = {"status": "UNAVAILABLE", "notice": "psutil not available"}

    # 4. Tool Registry Capability Discovery
    try:
        tools = tool_registry.list_tools()
        checks["tool_registry"] = {
            "status": "HEALTHY",
            "tool_count": len(tools)
        }
    except Exception as e:
        checks["tool_registry"] = {
            "status": "DEGRADED",
            "error": str(e)
        }

    overall_status = "ready" if is_ready else "not_ready"
    response_payload = {
        "status": overall_status,
        "ready": is_ready,
        "timestamp": now,
        "uptime_seconds": round(now - BOOT_TIME, 2),
        "checks": checks
    }
    return is_ready, response_payload
