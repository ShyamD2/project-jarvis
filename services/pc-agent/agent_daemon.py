"""
Windows PC Agent Daemon for J.A.R.V.I.S.
Runs continuously on the Windows host, streaming vitals and executing local commands.
"""

from __future__ import annotations
import asyncio
import time
from typing import Dict, Any

try:
    from .system_monitor import system_monitor
    from .window_manager import window_manager
    from .system_control import system_control
    from .screen_vision import screen_vision
except ImportError:
    from system_monitor import system_monitor
    from window_manager import window_manager
    from system_control import system_control
    from screen_vision import screen_vision
from shared.schemas.event_envelope import JarvisEvent
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisPCDaemon")


class PCDaemon:
    def __init__(self, heartbeat_interval: float = 5.0):
        self.heartbeat_interval = heartbeat_interval
        self.running = False

    async def start(self):
        """Starts the PC background daemon telemetry loop"""
        self.running = True
        logger.info("⚡ [PCDaemon] Windows Local PC Agent Daemon initialized.")

        # Register event handlers for incoming computer actions
        mesh.subscribe("action.computer.*", self._handle_incoming_action)

        while self.running:
            try:
                vitals = system_monitor.collect_telemetry()
                event = JarvisEvent(
                    source="pc.agent.windows",
                    type="pc.telemetry",
                    data=vitals
                )
                mesh.publish(event, fast_path=True, cloud_sync=False)
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[PCDaemon] Telemetry loop error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    def stop(self):
        self.running = False
        logger.info("[PCDaemon] Daemon stopped.")

    def _handle_incoming_action(self, event: JarvisEvent):
        logger.info(f"[PCDaemon] Handling PC action: {event.type}")
        cmd = event.data.get("command")
        if cmd == "lock_screen":
            system_control.lock_workstation()
        elif cmd == "set_volume":
            system_control.set_volume(event.data.get("level", 50))


pc_daemon = PCDaemon()
