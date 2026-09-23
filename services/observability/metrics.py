"""
System & Operational Metrics Engine for Project J.A.R.V.I.S. (Phase 36 Stage 36.4).
Collects counters, gauges, latencies, and exports Prometheus exposition format for Grafana.
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

    def increment(self, metric: str, value: int = 1, labels: Dict[str, str] = None):
        key = metric
        if labels:
            lbl_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            key = f"{metric}{{{lbl_str}}}"
        self._counters[key] += value

    def set_gauge(self, metric: str, value: float, labels: Dict[str, str] = None):
        key = metric
        if labels:
            lbl_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            key = f"{metric}{{{lbl_str}}}"
        self._gauges[key] = float(value)

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
        self.set_gauge("jarvis_system_cpu_percent", cpu_pct)
        self.set_gauge("jarvis_system_memory_percent", mem.percent)
        self.set_gauge("jarvis_system_disk_percent", disk.percent)

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

    def get_prometheus_metrics(self) -> str:
        """
        Exports metrics in standard Prometheus text format (version 0.0.4) for scraping.
        """
        self.get_system_telemetry()  # Refresh system gauges
        lines = []

        # System Gauges
        lines.append("# HELP jarvis_system_cpu_percent Host CPU utilization percentage")
        lines.append("# TYPE jarvis_system_cpu_percent gauge")
        lines.append(f"jarvis_system_cpu_percent {self._gauges.get('jarvis_system_cpu_percent', 0.0)}")

        lines.append("# HELP jarvis_system_memory_percent Host RAM utilization percentage")
        lines.append("# TYPE jarvis_system_memory_percent gauge")
        lines.append(f"jarvis_system_memory_percent {self._gauges.get('jarvis_system_memory_percent', 0.0)}")

        lines.append("# HELP jarvis_system_disk_percent Host primary disk utilization percentage")
        lines.append("# TYPE jarvis_system_disk_percent gauge")
        lines.append(f"jarvis_system_disk_percent {self._gauges.get('jarvis_system_disk_percent', 0.0)}")

        # Other gauges
        for k, v in sorted(self._gauges.items()):
            if not k.startswith("jarvis_system_"):
                lines.append(f"{k} {v}")

        # Counters
        lines.append("# HELP jarvis_pipeline_requests_total Total number of canonical pipeline execution requests")
        lines.append("# TYPE jarvis_pipeline_requests_total counter")
        for k, v in sorted(self._counters.items()):
            lines.append(f"{k} {v}")

        # Latency summaries
        for metric_name, vals in sorted(self._latencies.items()):
            if vals:
                sanitized_name = metric_name.replace(".", "_")
                lines.append(f"# HELP {sanitized_name}_seconds Latency summary for {metric_name}")
                lines.append(f"# TYPE {sanitized_name}_seconds summary")
                lines.append(f'{sanitized_name}_seconds{{quantile="0.5"}} {round(sorted(vals)[int(len(vals)*0.5)] / 1000.0, 4)}')
                lines.append(f'{sanitized_name}_seconds{{quantile="0.95"}} {round(sorted(vals)[int(len(vals)*0.95)] / 1000.0, 4)}')
                lines.append(f"{sanitized_name}_seconds_count {len(vals)}")
                lines.append(f"{sanitized_name}_seconds_sum {round(sum(vals) / 1000.0, 4)}")

        return "\n".join(lines) + "\n"


obs_metrics = ObservabilityMetrics()
