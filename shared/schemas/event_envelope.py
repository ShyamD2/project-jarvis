"""
Standard CloudEvents v1.0 Envelope for J.A.R.V.I.S. Event Fabric.
Ensures strict typing across Sensory, Event, Brain, and Action layers.
Phase 36: Adds correlation_id, causation_id, idempotency_key, mission_id, and schema_version.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, Optional


@dataclass
class JarvisEvent:
    source: str                          # e.g., "sensory.microphone", "iot.esp32.living_room", "pc.windows"
    type: str                            # e.g., "sensory.clap", "sensory.voice_transcript", "cloud.alarm"
    data: Dict[str, Any]                 # Event payload
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    specversion: str = "1.0"
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    datacontenttype: str = "application/json"
    traceparent: Optional[str] = None    # W3C distributed trace context: 00-traceid-spanid-01
    correlation_id: Optional[str] = None # Ties event to end-to-end operation
    causation_id: Optional[str] = None   # Event that directly triggered this event
    idempotency_key: Optional[str] = None# Prevents duplicate processing
    mission_id: Optional[str] = None     # Associated mission DAG identifier
    schema_version: int = 2

    # Canonical aliases for Item 23
    @property
    def event_id(self) -> str:
        return self.id

    @property
    def event_type(self) -> str:
        return self.type

    @property
    def timestamp(self) -> str:
        return self.time

    @property
    def payload(self) -> Dict[str, Any]:
        return self.data

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JarvisEvent:
        return cls(
            id=data.get("id") or data.get("event_id") or str(uuid.uuid4()),
            specversion=data.get("specversion", "1.0"),
            source=data.get("source", "unknown"),
            type=data.get("type") or data.get("event_type", "event.generic"),
            time=data.get("time") or data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            datacontenttype=data.get("datacontenttype", "application/json"),
            data=data.get("data") or data.get("payload", {}),
            traceparent=data.get("traceparent"),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            idempotency_key=data.get("idempotency_key"),
            mission_id=data.get("mission_id"),
            schema_version=data.get("schema_version", 2)
        )

    @classmethod
    def from_json(cls, json_str: str) -> JarvisEvent:
        return cls.from_dict(json.loads(json_str))
