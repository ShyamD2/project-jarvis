"""
Subsystem Health Monitor and Watchdog for Project J.A.R.V.I.S.
Tracks heartbeats, subsystem statuses, and degradation warnings.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List


class SubsystemHealth:
    def __init__(self, name: str):
        self.name = name
        self.status = "ONLINE"  # ONLINE, DEGRADED, OFFLINE
        self.last_heartbeat = time.time()
        self.error_count = 0
        self.details: Dict[str, Any] = {}

    def heartbeat(self, status: str = "ONLINE", details: Dict[str, Any] = None):
        self.last_heartbeat = time.time()
        self.status = status
        if details:
            self.details.update(details)

    def record_error(self, err_msg: str):
        self.error_count += 1
        self.status = "DEGRADED"
        self.details["last_error"] = err_msg
        self.details["last_error_time"] = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat,
            "seconds_since_heartbeat": round(time.time() - self.last_heartbeat, 1),
            "error_count": self.error_count,
            "details": self.details
        }


class ObservabilityHealthMonitor:
    def __init__(self):
        self._subsystems: Dict[str, SubsystemHealth] = {}
        # Pre-register primary subsystems
        default_subsystems = [
            "core_runtime",
            "tool_registry",
            "permission_engine",
            "event_fabric",
            "hierarchical_memory",
            "mission_control",
            "agent_swarm",
            "windows_gateway",
            "screen_vision",
            "aws_cloud",
            "observability_subsystem"
        ]
        for name in default_subsystems:
            self._subsystems[name] = SubsystemHealth(name)

    def ping(self, subsystem_name: str, status: str = "ONLINE", details: Dict[str, Any] = None):
        if subsystem_name not in self._subsystems:
            self._subsystems[subsystem_name] = SubsystemHealth(subsystem_name)
        self._subsystems[subsystem_name].heartbeat(status, details)

    def record_subsystem_error(self, subsystem_name: str, err: str):
        if subsystem_name not in self._subsystems:
            self._subsystems[subsystem_name] = SubsystemHealth(subsystem_name)
        self._subsystems[subsystem_name].record_error(err)

    def get_health_report(self) -> Dict[str, Any]:
        all_online = True
        subs = {}
        for name, sub in self._subsystems.items():
            subs[name] = sub.to_dict()
            if sub.status != "ONLINE":
                all_online = False

        return {
            "overall_status": "NOMINAL" if all_online else "DEGRADED",
            "subsystems": subs,
            "timestamp": time.time()
        }


obs_health = ObservabilityHealthMonitor()
