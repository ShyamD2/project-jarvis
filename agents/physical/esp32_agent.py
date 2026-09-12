"""
ESP32 Physical World Agent for J.A.R.V.I.S.
Communicates with microcontrollers to control relays, lights, appliances, and query sensors.
"""

from typing import Dict, Any, Optional
import os
import sys
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/iot-agent")))
try:
    from shadow_sync import shadow_sync
except ImportError:
    try:
        from services.iot_agent.shadow_sync import shadow_sync
    except ImportError:
        shadow_sync = None

logger = get_logger("ESP32Agent")


class ESP32Agent:
    def __init__(self):
        # Local cache of physical device states (updated strictly by genuine telemetry)
        self.device_states: Dict[str, Dict[str, Any]] = {
            "esp32_lab_01": {
                "relays": {"desk_lamp": False, "light_main": False},
                "sensors": {"lux": None, "temperature_c": None}
            }
        }
        # Subscribe to device state and ack events
        mesh.subscribe("iot.state", self._on_device_state_event)
        mesh.subscribe("iot.ack", self._on_device_ack_event)

    def _on_device_state_event(self, event: JarvisEvent):
        data = event.data or {}
        device_id = data.get("device_id")
        if device_id:
            self.update_device_telemetry(
                device_id=device_id,
                relays=data.get("relays", {}),
                sensors=data.get("sensors", {})
            )

    def _on_device_ack_event(self, event: JarvisEvent):
        data = event.data or {}
        device_id = data.get("device_id")
        if device_id:
            self.update_device_telemetry(
                device_id=device_id,
                relays=data.get("relays", {}),
                sensors=data.get("sensors", {})
            )

    def update_device_telemetry(self, device_id: str, relays: Dict[str, Any], sensors: Dict[str, Any]):
        """Updates internal device state cache and device shadow from real reported telemetry"""
        if device_id not in self.device_states:
            self.device_states[device_id] = {"relays": {}, "sensors": {}}

        if relays:
            self.device_states[device_id]["relays"].update(relays)
            if shadow_sync:
                shadow_sync.update_reported(device_id, relays)

        if sensors:
            self.device_states[device_id]["sensors"].update(sensors)

        logger.debug(f"[ESP32Agent] Telemetry updated for {device_id}: relays={relays}, sensors={sensors}")

    def set_relay(self, device_id: str, relay_name: str, state: bool) -> Dict[str, Any]:
        """Sets desired physical relay state and dispatches command to device/simulator"""
        logger.info(f"[ESP32Agent] Setting device {device_id} relay '{relay_name}' -> {'ON' if state else 'OFF'}")

        if device_id not in self.device_states:
            self.device_states[device_id] = {"relays": {}, "sensors": {}}

        # Update desired state in AWS IoT Device Shadow
        if shadow_sync:
            shadow_sync.set_desired(device_id, {relay_name: state})

        # Optimistically record in local cache until ACK confirms
        self.device_states[device_id]["relays"][relay_name] = state

        # Dispatch command across fast-path MQTT / Mesh
        event = JarvisEvent(
            source="agent.esp32",
            type="iot.command",
            data={
                "action": "set_relay",
                "device_id": device_id,
                "target": relay_name,
                "state": state
            }
        )
        mesh.publish(event)

        # Retrieve current genuine sensor reading (None if no hardware/simulator reported yet)
        current_lux = self.device_states[device_id].get("sensors", {}).get("lux")

        return {
            "success": True,
            "device_id": device_id,
            "relay": relay_name,
            "state": state,
            "channel_1_logical": True,
            "channel_2_lux": current_lux,
            "sensory_verified": current_lux is not None
        }

    def read_sensor(self, device_id: str, sensor_name: str) -> Optional[float]:
        """Reads physical sensor telemetry (lux, temperature, humidity)"""
        dev = self.device_states.get(device_id)
        if dev and sensor_name in dev.get("sensors", {}):
            return dev["sensors"][sensor_name]
        return None


esp32_agent = ESP32Agent()
