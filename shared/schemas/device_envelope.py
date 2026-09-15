"""
Device Envelope and Cross-Device Action Protocol for Project J.A.R.V.I.S.
Defines device metadata, capabilities, task packets, and security abstractions.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import json
import uuid
import time


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    MOBILE = "mobile"
    TABLET = "tablet"
    IOT = "iot"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    STANDBY = "standby"
    BUSY = "busy"


class DeviceCapability(str, Enum):
    # Computer Capabilities
    APP_LAUNCH = "app_launch"
    APP_TERMINATE = "app_terminate"
    BROWSER_CONTROL = "browser_control"
    FILE_SYSTEM = "file_system"
    VOLUME_CONTROL = "volume_control"
    WINDOW_MANAGEMENT = "window_management"
    SCREEN_CAPTURE = "screen_capture"
    SCREEN_RECOGNITION = "screen_recognition"
    KEYBOARD_INPUT = "keyboard_input"
    SYSTEM_POWER = "system_power"
    CLIPBOARD_SYNC = "clipboard_sync"

    # Mobile Capabilities
    NOTIFICATIONS = "notifications"
    MESSAGES = "messages"
    MESSAGING = "messages"
    CALLS = "calls"
    TELEPHONY = "calls"
    CAMERA = "camera"
    MOBILE_APPS = "mobile_apps"


@dataclass
class JarvisDevice:
    device_id: str
    name: str
    device_type: DeviceType
    status: DeviceStatus = DeviceStatus.OFFLINE
    ip_address: Optional[str] = None
    last_seen: float = field(default_factory=time.time)
    capabilities: List[DeviceCapability] = field(default_factory=list)
    token_hash: Optional[str] = None # Salted SHA-256 hash; NO plaintext secrets in JSON
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "status": self.status.value,
            "ip_address": self.ip_address,
            "last_seen": self.last_seen,
            "last_seen_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_seen)),
            "capabilities": [c.value for c in self.capabilities],
            "token_hash": self.token_hash,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JarvisDevice:
        caps = [DeviceCapability(c) for c in data.get("capabilities", []) if c in DeviceCapability._value2member_map_]
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            device_type=DeviceType(data["device_type"]),
            status=DeviceStatus(data.get("status", DeviceStatus.OFFLINE)),
            ip_address=data.get("ip_address"),
            last_seen=data.get("last_seen", time.time()),
            capabilities=caps,
            token_hash=data.get("token_hash"),
            metadata=data.get("metadata", {})
        )


@dataclass
class AgentTaskPacket:
    """Task packet issued by JARVIS Cloud to a target device agent."""
    action: str                                    # e.g., "open_app", "set_volume", "browse_url"
    target_device_id: str                          # Device authorized to execute
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_device_id: str = "cloud"                # Originating device or cloud
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    tier: str = "tier_1_soft"                      # Blast-radius tier
    requires_confirmation: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentTaskPacket:
        return cls(
            action=data["action"],
            target_device_id=data["target_device_id"],
            parameters=data.get("parameters", {}),
            source_device_id=data.get("source_device_id", "cloud"),
            task_id=data.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
            tier=data.get("tier", "tier_1_soft"),
            requires_confirmation=data.get("requires_confirmation", False),
            created_at=data.get("created_at", time.time())
        )


@dataclass
class AgentTaskResult:
    """Result report returned by local device agent to Central Cloud."""
    task_id: str
    device_id: str
    success: bool
    status: str                                    # COMPLETED, FAILED, CONFIRMATION_REQUIRED
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
