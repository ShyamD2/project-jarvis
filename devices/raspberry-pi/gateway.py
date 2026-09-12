"""
Raspberry Pi Edge Gateway Daemon for J.A.R.V.I.S.
Bridges local LAN MQTT devices (ESP32, sensors, smart plugs) with upstream AWS IoT Core.
Operates fully autonomous offline with local fast-path reflex logic.
"""

from __future__ import annotations
import json
import time
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
    MQTT_SUPPORT = True
except ImportError:
    MQTT_SUPPORT = False

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisRaspberryPiGateway")


class PiGateway:
    def __init__(self, broker_host: str = "127.0.0.1", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.known_devices: Dict[str, Any] = {}
        self.cloud_connected = False
        self.offline_queue = []

    def handle_device_telemetry(self, device_id: str, payload: Dict[str, Any]):
        """Processes telemetry from local ESP32 nodes"""
        self.known_devices[device_id] = {
            "last_seen": time.time(),
            "telemetry": payload
        }
        logger.info(f"[PiGateway] Received state from {device_id}: Lux={payload.get('sensors', {}).get('lux')}")

    def evaluate_offline_reflex(self, event_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        OFFLINE SURVIVABILITY FAST-PATH:
        If Internet / AWS is completely down, executes local reflexes instantly.
        """
        if event_type == "sensory.clap" and data.get("count") == 2:
            logger.info("⚡ [PiGateway: Offline Reflex] Double clap -> Toggling desk lamp locally!")
            return {
                "action": "set_relay",
                "device_id": "esp32_lab_01",
                "target": "desk_lamp",
                "state": True
            }
        return None


gateway = PiGateway()
