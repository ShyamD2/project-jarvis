"""
Remote Mobile Node Engine for Project J.A.R.V.I.S.
Transforms personal mobile devices into first-class authenticated nodes in the JARVIS mesh
without requiring physical USB tethering or manual local ADB debugging.
Provides token-authenticated command dispatch and bidirectional telemetry ingestion.
"""

from __future__ import annotations
import os
import time
import secrets
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("RemoteMobileNode")


@dataclass
class ConnectedMobileNode:
    device_id: str
    device_name: str
    ip_address: str
    auth_token: str
    battery_level: int = 100
    is_charging: bool = False
    last_heartbeat: float = field(default_factory=time.time)
    is_online: bool = True


class RemoteMobileNodeManager:
    def __init__(self):
        self._nodes: Dict[str, ConnectedMobileNode] = {}

    def register_node(self, device_id: str, device_name: str, ip_address: str) -> str:
        """Generates cryptographically secure bearer token and registers remote phone node."""
        token = f"mb_{secrets.token_hex(16)}"
        node = ConnectedMobileNode(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            auth_token=token
        )
        self._nodes[device_id] = node
        logger.info(f"[RemoteMobileNode] Registered node '{device_name}' [{device_id}] at {ip_address}")
        return token

    def authenticate_node(self, device_id: str, token: str) -> bool:
        node = self._nodes.get(device_id)
        if node and secrets.compare_digest(node.auth_token, token):
            node.last_heartbeat = time.time()
            node.is_online = True
            return True
        return False

    def update_telemetry(self, device_id: str, battery: int, is_charging: bool):
        if device_id in self._nodes:
            self._nodes[device_id].battery_level = battery
            self._nodes[device_id].is_charging = is_charging
            self._nodes[device_id].last_heartbeat = time.time()

    def get_node(self, device_id: str) -> Optional[ConnectedMobileNode]:
        node = self._nodes.get(device_id)
        if node and (time.time() - node.last_heartbeat > 60.0):
            node.is_online = False
        return node

    def list_active_nodes(self) -> List[Dict[str, Any]]:
        now = time.time()
        active = []
        for n in self._nodes.values():
            is_active = (now - n.last_heartbeat < 45.0)
            active.append({
                "device_id": n.device_id,
                "device_name": n.device_name,
                "ip_address": n.ip_address,
                "is_online": is_active,
                "battery": n.battery_level,
                "charging": n.is_charging
            })
        return active


remote_mobile_manager = RemoteMobileNodeManager()
