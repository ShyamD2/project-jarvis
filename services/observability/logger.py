"""
Structured Observability Logger for Project J.A.R.V.I.S.
Provides structured JSON logging, correlation IDs, and unified stdout formatting.
"""

from __future__ import annotations
import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional


class ObservabilityLogger:
    def __init__(self, name: str = "JARVIS-OBS"):
        self.name = name
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%H:%M:%S"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self._log_history = []
        self._max_history = 1000

    def info(self, msg: str, **kwargs):
        self._record("INFO", msg, **kwargs)
        self.logger.info(f"{msg} {json.dumps(kwargs) if kwargs else ''}")

    def warning(self, msg: str, **kwargs):
        self._record("WARNING", msg, **kwargs)
        self.logger.warning(f"{msg} {json.dumps(kwargs) if kwargs else ''}")

    def error(self, msg: str, **kwargs):
        self._record("ERROR", msg, **kwargs)
        self.logger.error(f"{msg} {json.dumps(kwargs) if kwargs else ''}")

    def debug(self, msg: str, **kwargs):
        self._record("DEBUG", msg, **kwargs)
        self.logger.debug(f"{msg} {json.dumps(kwargs) if kwargs else ''}")

    def _record(self, level: str, msg: str, **kwargs):
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": msg,
            "meta": kwargs
        }
        self._log_history.append(entry)
        if len(self._log_history) > self._max_history:
            self._log_history.pop(0)

    def get_recent_logs(self, limit: int = 100, level: Optional[str] = None):
        logs = self._log_history
        if level:
            logs = [l for l in logs if l["level"] == level.upper()]
        return logs[-limit:]


obs_logger = ObservabilityLogger()
