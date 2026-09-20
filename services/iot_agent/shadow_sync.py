"""
AWS IoT Device Shadow Synchronizer for J.A.R.V.I.S.
Maintains state alignment between cloud desired state and physical reported state.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent

logger = get_logger("JarvisIoTShadowSync")


class DeviceShadowSync:
    def __init__(self):
        # Maps device_id -> {"desired": {}, "reported": {}, "version": int}
        self.shadows: Dict[str, Dict[str, Any]] = {}

    def update_reported(self, device_id: str, reported_state: Dict[str, Any]):
        """Called when device publishes its real reported state"""
        if device_id not in self.shadows:
            self.shadows[device_id] = {"desired": {}, "reported": {}, "version": 1}

        shadow = self.shadows[device_id]
        shadow["reported"].update(reported_state)
        shadow["version"] += 1
        shadow["last_updated"] = time.time()

        # Check for delta
        delta = self._compute_delta(shadow["desired"], shadow["reported"])
        if delta:
            logger.info(f"[ShadowSync] Device {device_id} delta detected: {delta}")
        else:
            logger.debug(f"[ShadowSync] Device {device_id} reported state in sync with desired.")

    def set_desired(self, device_id: str, desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Sets target desired state from J.A.R.V.I.S. Brain"""
        if device_id not in self.shadows:
            self.shadows[device_id] = {"desired": {}, "reported": {}, "version": 1}

        shadow = self.shadows[device_id]
        shadow["desired"].update(desired_state)
        shadow["version"] += 1

        delta = self._compute_delta(shadow["desired"], shadow["reported"])
        if delta:
            logger.info(f"[ShadowSync] Dispatching shadow delta to device {device_id}: {delta}")
            # Emit shadow delta event
            mesh.publish(
                JarvisEvent(
                    source="iot.shadow",
                    type="iot.shadow_delta",
                    data={"device_id": device_id, "delta": delta}
                )
            )
        return shadow

    def _compute_delta(self, desired: Dict[str, Any], reported: Dict[str, Any]) -> Dict[str, Any]:
        delta = {}
        for k, v in desired.items():
            if k not in reported or reported[k] != v:
                delta[k] = v
        return delta


shadow_sync = DeviceShadowSync()
