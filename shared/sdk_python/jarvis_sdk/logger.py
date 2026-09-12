"""
Structured Logging utility for J.A.R.V.I.S.
Emits clean, traceable logs for both console and telemetry systems.
"""

import logging
import sys
from datetime import datetime, timezone
import json
from typing import Any, Dict


class JarvisJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(name: str, json_format: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception as e:
                # stdout may be a custom stream or redirected without reconfigure support
                pass
        handler = logging.StreamHandler(sys.stdout)
        if json_format:
            handler.setFormatter(JarvisJSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
                    datefmt="%H:%M:%S"
                )
            )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
