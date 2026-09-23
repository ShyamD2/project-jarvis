"""
Pre-Logging Secret Redactor for Project J.A.R.V.I.S. (Phase 36 Item 12).
Redacts API keys, Bearer tokens, private keys, AWS credentials, JWTs, and passwords
BEFORE text enters logs, console output, telemetry streams, or audit files.
"""

from __future__ import annotations
import re
import logging
from typing import List, Pattern, Dict, Any

REDACTION_PATTERNS: List[tuple[Pattern, str]] = [
    # Authorization: Bearer <token>
    (re.compile(r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{12,}", re.IGNORECASE), r"\1[REDACTED_BEARER_TOKEN]"),
    # AWS Access Key ID (AKIA...)
    (re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY_ID]"),
    # AWS Secret Key (40 chars)
    (re.compile(r"(?i)(aws_secret_access_key\s*[:=]\s*)['\"]?[A-Za-z0-9/+=]{40}['\"]?"), r"\1[REDACTED_AWS_SECRET]"),
    # Standard API Keys (groq, openai, telegram, etc.)
    (re.compile(r"(?i)(gsk_[a-zA-Z0-9]{32,})"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"(?i)(sk-[a-zA-Z0-9]{32,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(AIzaSy[a-zA-Z0-9_\-]{33})"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"(?i)([0-9]{9,10}:[a-zA-Z0-9_\-]{35})"), "[REDACTED_TELEGRAM_TOKEN]"),
    # Generic password / secret / token assignments (quoted or unquoted)
    (re.compile(r"(?i)\b(password|secret|token|api_key|master_secret)\s*[:=]\s*['\"]?([^\s'\",;&]{4,})['\"]?"), r"\1=[REDACTED]"),
    # RSA / EC Private Keys
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[^-]+-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
]


class SecretRedactor:
    def __init__(self):
        self._patterns = REDACTION_PATTERNS

    def redact(self, text: Any) -> str:
        """Sanitizes text by replacing all matched secrets with [REDACTED] markers."""
        if not isinstance(text, str):
            text = str(text)

        sanitized = text
        for pattern, replacement in self._patterns:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def redact_text(self, text: Any) -> str:
        """Alias for redact()."""
        return self.redact(text)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that sanitizes every record message before formatting."""
    def __init__(self):
        super().__init__()
        self.redactor = SecretRedactor()

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redactor.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redactor.redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redactor.redact(a) if isinstance(a, str) else a for a in record.args)
        return True


secret_redactor = SecretRedactor()
redacting_filter = SecretRedactingFilter()
