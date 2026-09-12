"""
Standard CloudEvents v1.0 Envelope for J.A.R.V.I.S. Event Fabric.
Ensures strict typing across Sensory, Event, Brain, and Action layers.
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JarvisEvent:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            specversion=data.get("specversion", "1.0"),
            source=data["source"],
            type=data["type"],
            time=data.get("time", datetime.now(timezone.utc).isoformat()),
            datacontenttype=data.get("datacontenttype", "application/json"),
            data=data.get("data", {}),
            traceparent=data.get("traceparent")
        )

    @classmethod
    def from_json(cls, json_str: str) -> JarvisEvent:
        return cls.from_dict(json.loads(json_str))
