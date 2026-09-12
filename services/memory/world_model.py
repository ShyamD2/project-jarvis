"""
World Model Engine for Project J.A.R.V.I.S.
Maintains a real-time Digital Twin of Physical Devices, Computer Environment, and Cloud Infrastructure.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWorldModel")


@dataclass
class DeviceState:
    device_id: str
    online: bool = True
    relays: Dict[str, bool] = field(default_factory=dict)
    sensors: Dict[str, float] = field(default_factory=dict)
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class PCState:
    os: str = "Windows"
    hostname: str = "localhost"
    active_window: str = "Desktop"
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    focus_mode: bool = False
    in_meeting: bool = False
    last_updated: float = field(default_factory=time.time)


@dataclass
class CloudState:
    region: str = "us-east-1"
    connected: bool = True
    active_deployments: int = 0
    active_alerts: int = 0
    last_synced: float = field(default_factory=time.time)


class WorldModel:
    def __init__(self):
        self.devices: Dict[str, DeviceState] = {}
        self.pc: PCState = PCState()
        self.cloud: CloudState = CloudState()
        self.system_status: str = "operational"

    def update_device(self, device_id: str, relays: Optional[Dict[str, bool]] = None, sensors: Optional[Dict[str, float]] = None):
        """Update or register an IoT device state"""
        if device_id not in self.devices:
            self.devices[device_id] = DeviceState(device_id=device_id)

        dev = self.devices[device_id]
        dev.online = True
        dev.last_heartbeat = time.time()
        if relays is not None:
            dev.relays.update(relays)
        if sensors is not None:
            dev.sensors.update(sensors)

        logger.debug(f"Updated device {device_id}: {dev.relays}, {dev.sensors}")

    def update_pc(self, **kwargs):
        """Update local Windows PC environment state"""
        for k, v in kwargs.items():
            if hasattr(self.pc, k):
                setattr(self.pc, k, v)
        self.pc.last_updated = time.time()

    def update_cloud(self, **kwargs):
        """Update Cloud / AWS state"""
        for k, v in kwargs.items():
            if hasattr(self.cloud, k):
                setattr(self.cloud, k, v)
        self.cloud.last_synced = time.time()

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns comprehensive digital twin snapshot"""
        return {
            "status": self.system_status,
            "timestamp": time.time(),
            "devices": {k: asdict(v) for k, v in self.devices.items()},
            "pc": asdict(self.pc),
            "cloud": asdict(self.cloud)
        }


world_model = WorldModel()
