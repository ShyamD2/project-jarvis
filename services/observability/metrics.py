"""
System & Operational Metrics Engine for Project J.A.R.V.I.S.
Collects counters, gauges, latencies, and real-time host resource metrics.
"""

from __future__ import annotations
import time
import psutil
from collections import defaultdict
from typing import Dict, Any, List


class ObservabilityMetrics:
    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._gauges: Dict[str, float] = {}
        self._max_latency_history = 500

    def increment(self, metric: str, value: int = 1):
        self._counters[metric] += value

    def set_gauge(self, metric: str, value: float):
        self._gauges[metric] = value

    def record_latency(self, metric: str, duration_ms: float):
        self._latencies[metric].append(duration_ms)
        if len(self._latencies[metric]) > self._max_latency_history:
            self._latencies[metric].pop(0)

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Collects real-time hardware telemetry: CPU, RAM, Disk, Network"""
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        net = psutil.net_io_counters()

        # Update gauges
        self.set_gauge("system.cpu_percent", cpu_pct)
        self.set_gauge("system.memory_percent", mem.percent)
        self.set_gauge("system.disk_percent", disk.percent)

        return {
            "timestamp": time.time(),
            "cpu_percent": cpu_pct,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv
        }

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Returns consolidated metrics snapshot for dashboard & telemetry"""
        stats = {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "latencies": {}
        }
        for name, vals in self._latencies.items():
            if vals:
                stats["latencies"][name] = {
                    "count": len(vals),
                    "avg_ms": round(sum(vals) / len(vals), 2),
                    "min_ms": round(min(vals), 2),
                    "max_ms": round(max(vals), 2),
                    "p95_ms": round(sorted(vals)[int(len(vals) * 0.95)], 2)
                }
        stats["telemetry"] = self.get_system_telemetry()
        return stats


obs_metrics = ObservabilityMetrics()
