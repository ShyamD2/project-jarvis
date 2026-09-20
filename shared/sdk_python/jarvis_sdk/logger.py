"""
Structured Logging utility for J.A.R.V.I.S.
Emits clean, traceable logs for both console and telemetry systems.
"""

import logging
import sys
from datetime import datetime, timezone
import json
from typing import Any, Dict


import re

SECRET_PATTERNS = [
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\b[0-9]{8,12}:[a-zA-Z0-9_-]{20,45}\b"), "[REDACTED_TELEGRAM_TOKEN]"),
    (re.compile(r"\b(?:gsk_|sk-proj-|sk-)[a-zA-Z0-9_-]{15,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)(api[-_]?key|secret|token|password)([\"']?\s*[:=]\s*[\"'])([^\"'\s]{8,})([\"']?)"), r'\1\2[REDACTED_SECRET]\4'),
]

def redact_secrets(text: str) -> str:
    """Scrubs sensitive API keys, tokens, and credentials from log strings."""
    if not isinstance(text, str) or not text:
        return text
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_secrets(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_secrets(v) if isinstance(v, str) else v for v in record.args)
        return True


class JarvisJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
        }
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if record.exc_info:
            log_entry["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(log_entry)


def get_logger(name: str, json_format: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        stream = sys.stdout if sys.stdout is not None else sys.stderr
        if stream is None:
            import io
            stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SecretRedactingFilter())
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
        logger.addFilter(SecretRedactingFilter())
        logger.setLevel(logging.INFO)
    return logger
