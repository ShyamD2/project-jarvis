"""
Virtual ESP32 Device Simulator for J.A.R.V.I.S.
Simulates a physical microcontroller running relays (light, fan) and sensors (lux, temp).
Communicates via Local MQTT fast-path with zero hardware required.
"""

from __future__ import annotations
import json
import time
import threading
import random
import sys
from typing import Optional

from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

try:
    import paho.mqtt.client as mqtt
    MQTT_SUPPORT = True
except ImportError:
    MQTT_SUPPORT = False


class VirtualESP32:
    def __init__(self, device_id: str = "esp32_lab_01", broker_host: str = "127.0.0.1", broker_port: int = 1883):
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.relays = {
            "light_main": False,
            "desk_lamp": False,
            "aux_power": False
        }
        self.sensors = {
            "lux": 150.0,
            "temperature_c": 24.5,
            "humidity": 50.0
        }
        self.running = False
        self.client: Optional[mqtt.Client] = None

    def start(self):
        self.running = True
        print(f"[Virtual ESP32: {self.device_id}] Starting device simulation...")

        # Subscribe to in-process event mesh for local zero-broker operation
        mesh.subscribe("iot.command", self._on_mesh_command)

        if not MQTT_SUPPORT:
            print(f"[Virtual ESP32: {self.device_id}] paho-mqtt not found. Running in mesh-connected loop.")
            self._publish_state()
            return

        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.device_id)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()

            # Background sensor telemetry loop
            t = threading.Thread(target=self._telemetry_loop, daemon=True)
            t.start()
        except Exception as e:
            print(f"[Virtual ESP32: {self.device_id}] MQTT broker unreachable ({self.broker_host}:{self.broker_port}): {e}. Operating over local event mesh.")
            self._publish_state()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[Virtual ESP32: {self.device_id}] Connected to MQTT broker.")
            cmd_topic = f"jarvis/devices/{self.device_id}/command"
            client.subscribe(cmd_topic)
            client.subscribe("jarvis/devices/all/command")
            print(f"[Virtual ESP32: {self.device_id}] Subscribed to: {cmd_topic}")
            self._publish_state()
        else:
            print(f"[Virtual ESP32: {self.device_id}] MQTT Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self._handle_command_payload(payload)
        except Exception as e:
            print(f"[Virtual ESP32: {self.device_id}] Error handling MQTT message: {e}")

    def _on_mesh_command(self, event: JarvisEvent):
        try:
            payload = event.data or {}
            target_device = payload.get("device_id")
            if target_device in [self.device_id, "all"]:
                self._handle_command_payload(payload)
        except Exception as e:
            print(f"[Virtual ESP32: {self.device_id}] Error handling mesh command: {e}")

    def _handle_command_payload(self, payload: dict):
        action = payload.get("action")
        target = payload.get("target") or payload.get("relay")

        if action in ["set_relay", "toggle"]:
            state = payload.get("state")
            if target in self.relays:
                if action == "toggle":
                    self.relays[target] = not self.relays[target]
                else:
                    self.relays[target] = bool(state)

                # Realistic optical response: desk_lamp/light_main elevates ambient lux
                if self.relays.get("desk_lamp") or self.relays.get("light_main"):
                    self.sensors["lux"] = round(650.0 + random.uniform(-5.0, 5.0), 1)
                else:
                    self.sensors["lux"] = round(120.0 + random.uniform(-2.0, 2.0), 1)

                print(f"[Virtual ESP32: {self.device_id}] Relay '{target}' -> {'ON' if self.relays[target] else 'OFF'} (Sensory lux: {self.sensors['lux']})")
                self._publish_state()
                self._publish_ack(payload.get("action_id", "unknown"), success=True)
            else:
                self._publish_ack(payload.get("action_id", "unknown"), success=False, error=f"Unknown target relay '{target}'")

    def _publish_state(self):
        data = {
            "device_id": self.device_id,
            "relays": dict(self.relays),
            "sensors": dict(self.sensors),
            "timestamp": time.time()
        }
        # Publish to MQTT if connected
        if self.client and self.client.is_connected():
            state_topic = f"jarvis/devices/{self.device_id}/state"
            self.client.publish(state_topic, json.dumps(data), qos=1)

        # Publish to EventMesh for local coordination
        mesh.publish(
            JarvisEvent(
                source="simulator.esp32",
                type="iot.state",
                data=data
            )
        )

    def _publish_ack(self, action_id: str, success: bool, error: Optional[str] = None):
        ack = {
            "action_id": action_id,
            "device_id": self.device_id,
            "success": success,
            "relays": dict(self.relays),
            "sensors": dict(self.sensors),
            "error": error,
            "timestamp": time.time()
        }
        if self.client and self.client.is_connected():
            ack_topic = f"jarvis/devices/{self.device_id}/ack"
            self.client.publish(ack_topic, json.dumps(ack), qos=1)

        mesh.publish(
            JarvisEvent(
                source="simulator.esp32",
                type="iot.ack",
                data=ack
            )
        )

    def _telemetry_loop(self):
        while self.running:
            time.sleep(5)
            self.sensors["temperature_c"] = round(24.0 + random.uniform(-0.5, 0.5), 2)
            self._publish_state()

    def _standalone_loop(self):
        print(f"[Virtual ESP32: {self.device_id}] Running in local memory mode. Press Ctrl+C to stop.")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False


if __name__ == "__main__":
    device = VirtualESP32()
    device.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Virtual ESP32.")
