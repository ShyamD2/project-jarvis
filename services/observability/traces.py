"""
Distributed Tracing Engine for Project J.A.R.V.I.S. (Phase 36 Stage 36.4).
Implements W3C TraceContext (traceparent), span hierarchies, and per-stage latency tracking.
"""

from __future__ import annotations
import time
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager


def normalize_trace_id(t_id: Optional[str] = None) -> str:
    """Ensures trace ID is a valid 32-character lowercase hex string (16 bytes)."""
    if not t_id:
        return uuid.uuid4().hex
    cleaned = t_id.replace("-", "").replace("trace_", "").replace("tr_", "")
    if len(cleaned) == 32 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return cleaned.lower()
    return hashlib.md5(t_id.encode("utf-8")).hexdigest()


def normalize_span_id(s_id: Optional[str] = None) -> str:
    """Ensures span ID is a valid 16-character lowercase hex string (8 bytes)."""
    if not s_id:
        return uuid.uuid4().hex[:16]
    cleaned = s_id.replace("-", "").replace("span_", "").replace("sp_", "")
    if len(cleaned) == 16 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return cleaned.lower()
    return hashlib.md5(s_id.encode("utf-8")).hexdigest()[:16]


class Span:
    def __init__(self, name: str, trace_id: Optional[str] = None, parent_span_id: Optional[str] = None, tags: Optional[Dict[str, Any]] = None):
        self.trace_id = normalize_trace_id(trace_id)
        self.span_id = normalize_span_id()
        self.parent_span_id = normalize_span_id(parent_span_id) if parent_span_id else None
        self.name = name
        self.tags = tags or {}
        self.stage_latencies: Dict[str, float] = {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status = "ACTIVE"
        self.error: Optional[str] = None

    def record_stage_latency(self, stage: str, duration_ms: float):
        """Records latency breakdown for individual pipeline stages (Item 114)."""
        self.stage_latencies[stage] = round(duration_ms, 2)

    def to_traceparent(self) -> str:
        """Generates W3C traceparent header: 00-{trace_id}-{span_id}-01"""
        return f"00-{self.trace_id}-{self.span_id}-01"

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
            "traceparent": self.to_traceparent(),
            "tags": self.tags,
            "stage_latencies": self.stage_latencies,
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

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None
    ) -> Span:
        span = Span(name, trace_id, parent_span_id, tags)
        self._spans.append(span)
        if len(self._spans) > self._max_traces:
            self._spans.pop(0)
        return span

    @contextmanager
    def trace(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None
    ):
        span = self.start_span(name, trace_id, parent_span_id, tags)
        try:
            yield span
            span.finish("SUCCESS")
        except Exception as e:
            span.finish("ERROR", str(e))
            raise

    def parse_traceparent(self, header: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parses W3C traceparent header: 00-{trace_id}-{parent_id}-{flags}"""
        if not header or not isinstance(header, str):
            return None, None, None
        parts = header.strip().split("-")
        if len(parts) == 4 and parts[0] == "00":
            trace_id = parts[1]
            parent_id = parts[2]
            flags = parts[3]
            if len(trace_id) == 32 and len(parent_id) == 16:
                return trace_id, parent_id, flags
        return None, None, None

    def inject_traceparent(self, headers: Dict[str, str], span: Optional[Span] = None) -> Dict[str, str]:
        """Injects W3C traceparent and correlation ID into HTTP / event headers."""
        if span:
            headers["traceparent"] = span.to_traceparent()
            headers["x-trace-id"] = span.trace_id
        return headers

    def extract_traceparent(self, headers: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Extracts trace_id and parent_span_id from HTTP / event headers."""
        header = headers.get("traceparent") or headers.get("TRACEPARENT") or headers.get("Traceparent")
        if header:
            t_id, p_id, _ = self.parse_traceparent(header)
            if t_id and p_id:
                return t_id, p_id
        alt = headers.get("x-trace-id") or headers.get("X-Trace-Id")
        if alt:
            return normalize_trace_id(alt), None
        return None, None

    def get_recent_spans(self, limit: int = 50, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        spans = self._spans
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        return [s.to_dict() for s in spans[-limit:]]


obs_tracer = ObservabilityTracer()
