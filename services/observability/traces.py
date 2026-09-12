"""
Distributed Tracing Engine for Project J.A.R.V.I.S.
Tracks spans for Agent ReAct turns, LLM generations, tool executions, and external API requests.
"""

from __future__ import annotations
import time
import uuid
from typing import Dict, Any, List, Optional
from contextlib import contextmanager


class Span:
    def __init__(self, name: str, trace_id: str, parent_span_id: Optional[str] = None, tags: Optional[Dict[str, Any]] = None):
        self.span_id = f"span_{uuid.uuid4().hex[:8]}"
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.name = name
        self.tags = tags or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status = "ACTIVE"
        self.error: Optional[str] = None

    def finish(self, status: str = "SUCCESS", error: Optional[str] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "tags": self.tags,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error
        }


class ObservabilityTracer:
    def __init__(self, max_traces: int = 500):
        self._spans: List[Span] = []
        self._max_traces = max_traces

    def start_span(self, name: str, trace_id: Optional[str] = None, parent_span_id: Optional[str] = None, tags: Optional[Dict[str, Any]] = None) -> Span:
        t_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        span = Span(name, t_id, parent_span_id, tags)
        self._spans.append(span)
        if len(self._spans) > self._max_traces:
            self._spans.pop(0)
        return span

    @contextmanager
    def trace(self, name: str, trace_id: Optional[str] = None, parent_span_id: Optional[str] = None, tags: Optional[Dict[str, Any]] = None):
        span = self.start_span(name, trace_id, parent_span_id, tags)
        try:
            yield span
            span.finish("SUCCESS")
        except Exception as e:
            span.finish("ERROR", str(e))
            raise

    def get_recent_spans(self, limit: int = 50, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        spans = self._spans
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        return [s.to_dict() for s in spans[-limit:]]


obs_tracer = ObservabilityTracer()
