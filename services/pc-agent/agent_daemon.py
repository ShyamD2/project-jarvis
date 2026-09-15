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

        # Sentry Mode Settings
        self.sentry_mode_enabled = True
        self._alert_cooldowns: Dict[str, float] = {}
        self._cooldown_seconds = 900.0  # 15 minutes between identical warnings

        # Proximity Presence Settings
        import os
        self.proximity_enabled = os.getenv("ENABLE_PROXIMITY_LOCK", "false").lower() in ("true", "1")
        self.proximity_target = os.getenv("PROXIMITY_PHONE_IP", "").strip()
        self._proximity_unreachable_count = 0
        self._device_present = True
        self._last_proximity_check = 0.0

    def enable_sentry_mode(self) -> Dict[str, Any]:
        self.sentry_mode_enabled = True
        logger.info("🛡️ [PCDaemon] Sentry Mode armed.")
        return {"status": "armed", "message": "Sentry Mode activated, sir. Hardware telemetry and proactive monitoring engaged."}

    def disable_sentry_mode(self) -> Dict[str, Any]:
        self.sentry_mode_enabled = False
        logger.info("🛡️ [PCDaemon] Sentry Mode disarmed.")
        return {"status": "disarmed", "message": "Sentry Mode standing down, sir."}

    def get_sentry_status(self) -> Dict[str, Any]:
        return {
            "sentry_mode": "ARMED" if self.sentry_mode_enabled else "STANDBY",
            "cooldown_seconds": self._cooldown_seconds,
            "active_alerts_in_cooldown": list(self._alert_cooldowns.keys())
        }

    def enable_proximity_lock(self, target_ip: Optional[str] = None) -> Dict[str, Any]:
        if target_ip:
            self.proximity_target = target_ip.strip()
        if not self.proximity_target:
            return {"success": False, "message": "Please specify a device IP address for proximity tracking, sir."}
        self.proximity_enabled = True
        self._proximity_unreachable_count = 0
        self._device_present = True
        logger.info(f"🔒 [PCDaemon] Proximity Watchdog armed targeting {self.proximity_target}")
        return {"success": True, "target": self.proximity_target, "message": f"Proximity watchdog armed for {self.proximity_target}. Auto-lock enabled."}

    def disable_proximity_lock(self) -> Dict[str, Any]:
        self.proximity_enabled = False
        logger.info("🔒 [PCDaemon] Proximity Watchdog disabled.")
        return {"success": True, "message": "Proximity auto-lock standing down, sir."}

    def get_proximity_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.proximity_enabled,
            "target": self.proximity_target or "Not configured",
            "present": self._device_present,
            "unreachable_streak": self._proximity_unreachable_count
        }

    async def _check_sentry_alerts(self, vitals: Dict[str, Any]):
        """Evaluates system vitals and fires proactive notifications if thresholds are breached"""
        if not self.sentry_mode_enabled:
            return

        alerts = system_monitor.evaluate_health_thresholds(vitals)
        now = time.time()

        for alert in alerts:
            alert_id = alert["id"]
            last_fired = self._alert_cooldowns.get(alert_id, 0.0)
            if now - last_fired < self._cooldown_seconds:
                continue

            self._alert_cooldowns[alert_id] = now
            logger.warning(f"🛡️ [Sentry Mode Triggered] {alert_id}: {alert['spoken']}")

            mesh.publish(JarvisEvent(
                source="pc.sentry",
                type="sentry.alert",
                data=alert
            ), fast_path=True)

            # Spoken warning via TTS
            try:
                from services.sensory.voice_synthesizer import voice_synthesizer
                asyncio.create_task(voice_synthesizer.speak(alert["spoken"], play_audio=True))
            except Exception as e:
                logger.debug(f"[Sentry Mode] TTS alert notice: {e}")

            # Proactive Telegram Broadcast
            try:
                from services.gateway.telegram_bot import telegram_gateway
                if telegram_gateway.is_configured:
                    asyncio.create_task(telegram_gateway.broadcast_to_authorized(alert["telegram"], parse_mode="HTML"))
            except Exception as e:
                logger.debug(f"[Sentry Mode] Telegram broadcast notice: {e}")

    async def _check_proximity(self):
        """Pings user mobile device; auto-locks workstation if unreachable after grace period"""
        if not self.proximity_enabled or not self.proximity_target:
            return

        now = time.time()
        if now - self._last_proximity_check < 25.0:
            return
        self._last_proximity_check = now

        import subprocess
        is_reachable = False
        try:
            res = subprocess.run(
                ["ping", "-n", "1", "-w", "600", self.proximity_target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            is_reachable = (res.returncode == 0)
        except Exception:
            pass

        if is_reachable:
            if not self._device_present:
                self._device_present = True
                self._proximity_unreachable_count = 0
                logger.info("👋 [Proximity Watchdog] Device reappeared in range. Welcome back.")
                try:
                    from services.sensory.voice_synthesizer import voice_synthesizer
                    asyncio.create_task(voice_synthesizer.speak("Welcome back, sir. Workstation ready.", play_audio=True))
                except Exception:
                    pass
                try:
                    from services.gateway.telegram_bot import telegram_gateway
                    if telegram_gateway.is_configured:
                        asyncio.create_task(telegram_gateway.broadcast_to_authorized(
                            "👋 <b>Welcome Back, Sir</b>\nDevice reconnected to workstation range.",
                            parse_mode="HTML"
                        ))
                except Exception:
                    pass
            else:
                self._proximity_unreachable_count = 0
        else:
            self._proximity_unreachable_count += 1
            logger.debug(f"[Proximity] Ping missed ({self._proximity_unreachable_count}/3)")
            if self._proximity_unreachable_count >= 3 and self._device_present:
                self._device_present = False
                logger.warning(f"🔒 [Proximity Watchdog] Device {self.proximity_target} out of range! Locking workstation...")
                system_control.lock_workstation()

                try:
                    from services.gateway.telegram_bot import telegram_gateway
                    if telegram_gateway.is_configured:
                        asyncio.create_task(telegram_gateway.broadcast_to_authorized(
                            "🔒 <b>Proximity Auto-Lock Engaged</b>\nWorkstation secured because your device moved out of range.",
                            parse_mode="HTML"
                        ))
                except Exception:
                    pass

    async def start(self):
        """Starts the PC background daemon telemetry loop with Sentry & Proximity engines"""
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

                # Execute watchdogs
                await self._check_sentry_alerts(vitals)
                await self._check_proximity()

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
        elif cmd == "sentry_arm":
            self.enable_sentry_mode()
        elif cmd == "sentry_disarm":
            self.disable_sentry_mode()


pc_daemon = PCDaemon()
