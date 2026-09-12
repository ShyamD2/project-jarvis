"""
Timeline and Event Recorder for Project J.A.R.V.I.S.
Maintains chronological timelines for Missions, Agent Swarms, and System Events.
"""

from __future__ import annotations
import time
import uuid
from typing import Dict, Any, List, Optional
from collections import deque


class TimelineEntry:
    def __init__(self, timeline_type: str, entity_id: str, event: str, data: Optional[Dict[str, Any]] = None):
        self.entry_id = f"tl_{uuid.uuid4().hex[:8]}"
        self.timestamp = time.time()
        self.timeline_type = timeline_type  # "mission", "agent", "system"
        self.entity_id = entity_id
        self.event = event
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "iso_time": time.strftime("%H:%M:%S", time.localtime(self.timestamp)),
            "timeline_type": self.timeline_type,
            "entity_id": self.entity_id,
            "event": self.event,
            "data": self.data
        }


class ObservabilityEventRecorder:
    def __init__(self, max_entries: int = 2000):
        self._entries: deque[TimelineEntry] = deque(maxlen=max_entries)

    def record_mission_event(self, mission_id: str, event: str, phase: Optional[str] = None, meta: Optional[Dict[str, Any]] = None):
        d = meta or {}
        if phase:
            d["phase"] = phase
        entry = TimelineEntry("mission", mission_id, event, d)
        self._entries.append(entry)
        return entry.to_dict()

    def record_agent_event(self, agent_name: str, event: str, task: Optional[str] = None, meta: Optional[Dict[str, Any]] = None):
        d = meta or {}
        if task:
            d["task"] = task
        entry = TimelineEntry("agent", agent_name, event, d)
        self._entries.append(entry)
        return entry.to_dict()

    def record_system_event(self, category: str, event: str, data: Optional[Dict[str, Any]] = None):
        entry = TimelineEntry("system", category, event, data)
        self._entries.append(entry)
        return entry.to_dict()

    def get_mission_timeline(self, mission_id: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries if e.timeline_type == "mission" and e.entity_id == mission_id]

    def get_agent_timeline(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if agent_name:
            return [e.to_dict() for e in self._entries if e.timeline_type == "agent" and e.entity_id == agent_name]
        return [e.to_dict() for e in self._entries if e.timeline_type == "agent"]

    def get_recent_timeline(self, limit: int = 50, timeline_type: Optional[str] = None) -> List[Dict[str, Any]]:
        entries = list(self._entries)
        if timeline_type:
            entries = [e for e in entries if e.timeline_type == timeline_type]
        return [e.to_dict() for e in entries[-limit:]]


obs_recorder = ObservabilityEventRecorder()
