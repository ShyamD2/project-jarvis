"""
Autonomous Workstation SRE Daemon for Project J.A.R.V.I.S. (Pillar 2).
Runs a lightweight, event-driven background watcher that:
1. Detects and resolves hung dev ports (8000, 3000, 8088, etc.)
2. Auto-cleans stale Git/Terraform lockfiles (>120s old)
3. Monitors workstation memory/CPU spikes to protect low-end i3 host
4. Publishes SRE incidents and self-healing events to the Jarvis Event Mesh
"""

from __future__ import annotations
import os
import sys
import time
import threading
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services", "pc_agent"))
from workstation_sre import workstation_sre

logger = get_logger("JarvisSREDaemon")


class WorkstationSREDaemon:
    def __init__(self, check_interval_seconds: float = 60.0, auto_heal_stale_locks: bool = True):
        self.check_interval = check_interval_seconds
        self.auto_heal_stale_locks = auto_heal_stale_locks
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def run_sre_cycle(self) -> Dict[str, Any]:
        """Runs a single SRE monitoring and self-healing cycle."""
        scan = workstation_sre.run_sre_health_scan()
        actions_taken = []

        # 1. Auto-clean stale lockfiles
        if self.auto_heal_stale_locks:
            for lock in scan.get("stale_locks", []):
                if lock.get("is_stale", False):
                    res = workstation_sre.clear_lockfile(lock["file_path"])
                    if res.get("success"):
                        msg = f"Auto-healed stale lockfile: {lock['relative_path']} (age: {lock['age_seconds']}s)"
                        logger.warning(f"🔧 [SREDaemon] {msg}")
                        actions_taken.append(msg)

        # 2. Publish health event to Event Mesh
        event = JarvisEvent(
            source="observability.sre_daemon",
            type="workstation.sre_status",
            data={
                "status": scan.get("status"),
                "occupied_ports": scan.get("occupied_ports", []),
                "runaway_count": len(scan.get("runaways", [])),
                "actions_taken": actions_taken,
                "timestamp": time.time()
            }
        )
        try:
            mesh.publish(event)
        except Exception:
            pass

        return {
            "scan": scan,
            "actions_taken": actions_taken
        }

    def start_daemon(self):
        """Starts background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="JarvisSREDaemon")
        self._thread.start()
        logger.info(f"✔ [SREDaemon] Autonomous Workstation SRE Daemon started (interval={self.check_interval}s)")

    def stop_daemon(self):
        """Stops the daemon."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[SREDaemon] Autonomous Workstation SRE Daemon stopped.")

    def _worker(self):
        while self._running:
            try:
                self.run_sre_cycle()
            except Exception as e:
                logger.error(f"[SREDaemon] Error in SRE cycle: {e}")
            time.sleep(self.check_interval)


sre_daemon = WorkstationSREDaemon()
