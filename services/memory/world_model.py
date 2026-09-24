"""
World Model Engine for Project J.A.R.V.I.S.
Maintains a real-time Digital Twin of Physical Devices, Computer Environment, and Cloud Infrastructure.
Item 7: Enforces entity states with confidence scoring, timestamped observation provenance,
process ID binding, and automatic confidence decay on stale observations.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWorldModel")


@dataclass
class EntityState:
    """Represents a specific tracked operating system, physical, or cloud entity."""
    entity_id: str
    entity_type: str  # "process", "device", "window", "service", "cloud_resource"
    state: Dict[str, Any]
    confidence: float = 1.0  # 0.0 to 1.0
    observed_at: float = field(default_factory=time.time)
    source: str = "direct_sensor"  # "psutil", "win32", "cloud_api", "agent_observation"
    pid: Optional[int] = None
    decay_rate_per_sec: float = 0.005  # Confidence decays linearly if observation is not refreshed

    def get_confidence(self) -> float:
        """Computes time-decayed confidence based on observation age."""
        age = max(0.0, time.time() - self.observed_at)
        decayed = max(0.0, self.confidence - (age * self.decay_rate_per_sec))
        return round(decayed, 3)

    def is_stale(self, threshold: float = 0.3) -> bool:
        """Flags entity as stale when confidence drops below threshold."""
        return self.get_confidence() < threshold

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["effective_confidence"] = self.get_confidence()
        d["is_stale"] = self.is_stale()
        return d


@dataclass
class DeviceState:
    device_id: str
    online: bool = True
    relays: Dict[str, bool] = field(default_factory=dict)
    sensors: Dict[str, float] = field(default_factory=dict)
    last_heartbeat: float = field(default_factory=time.time)
    confidence: float = 1.0
    observed_at: float = field(default_factory=time.time)
    source: str = "iot_telemetry"


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
    confidence: float = 1.0
    observed_at: float = field(default_factory=time.time)
    source: str = "local_telemetry"
    pid: Optional[int] = None


@dataclass
class CloudState:
    region: str = "us-east-1"
    connected: bool = True
    active_deployments: int = 0
    active_alerts: int = 0
    last_synced: float = field(default_factory=time.time)
    confidence: float = 1.0
    source: str = "aws_boto3"


class WorldModel:
    def __init__(self):
        self.devices: Dict[str, DeviceState] = {}
        self.pc: PCState = PCState()
        self.cloud: CloudState = CloudState()
        self.entities: Dict[str, EntityState] = {}
        self.system_status: str = "operational"

    def update_entity(
        self,
        entity_id: str,
        entity_type: str,
        state: Dict[str, Any],
        confidence: float = 1.0,
        source: str = "direct_sensor",
        pid: Optional[int] = None
    ) -> EntityState:
        """Updates or registers a tracked entity with provenance and confidence."""
        now = time.time()
        ent = EntityState(
            entity_id=entity_id,
            entity_type=entity_type,
            state=state,
            confidence=confidence,
            observed_at=now,
            source=source,
            pid=pid
        )
        self.entities[entity_id] = ent
        return ent

    def get_entity(self, entity_id: str) -> Optional[EntityState]:
        return self.entities.get(entity_id)

    def prune_stale_entities(self, threshold: float = 0.2) -> int:
        """Removes entities whose confidence has decayed below the threshold."""
        stale_keys = [k for k, v in self.entities.items() if v.is_stale(threshold)]
        for k in stale_keys:
            del self.entities[k]
        return len(stale_keys)

    def update_device(self, device_id: str, relays: Optional[Dict[str, bool]] = None, sensors: Optional[Dict[str, float]] = None):
        """Update or register an IoT device state"""
        now = time.time()
        if device_id not in self.devices:
            self.devices[device_id] = DeviceState(device_id=device_id)

        dev = self.devices[device_id]
        dev.online = True
        dev.last_heartbeat = now
        dev.observed_at = now
        dev.confidence = 1.0
        if relays is not None:
            dev.relays.update(relays)
        if sensors is not None:
            dev.sensors.update(sensors)

        logger.debug(f"Updated device {device_id}: {dev.relays}, {dev.sensors}")

    def update_pc(self, **kwargs):
        """Update local Windows PC environment state"""
        now = time.time()
        for k, v in kwargs.items():
            if hasattr(self.pc, k):
                setattr(self.pc, k, v)
        self.pc.last_updated = now
        self.pc.observed_at = now
        self.pc.confidence = 1.0

    def update_cloud(self, **kwargs):
        """Update Cloud / AWS state"""
        now = time.time()
        for k, v in kwargs.items():
            if hasattr(self.cloud, k):
                setattr(self.cloud, k, v)
        self.cloud.last_synced = now

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns comprehensive digital twin snapshot including entities and confidence."""
        return {
            "status": self.system_status,
            "timestamp": time.time(),
            "devices": {k: asdict(v) for k, v in self.devices.items()},
            "pc": asdict(self.pc),
            "cloud": asdict(self.cloud),
            "entities": {k: v.to_dict() for k, v in self.entities.items()}
        }


world_model = WorldModel()
