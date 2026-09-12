"""
Immutable Security & Policy Audit Subsystem for Project J.A.R.V.I.S.
Records every command, tool invocation, policy check, approval decision, rollback, and security alert.
"""

from __future__ import annotations
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisAudit")

AUDIT_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(AUDIT_DIR, exist_ok=True)
AUDIT_FILE = os.path.join(AUDIT_DIR, "audit_log.jsonl")


class ObservabilityAudit:
    def __init__(self, log_path: str = AUDIT_FILE):
        self.log_path = log_path
        self._cache: List[Dict[str, Any]] = []
        self._max_cache = 1000
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._cache.append(json.loads(line))
                if len(self._cache) > self._max_cache:
                    self._cache = self._cache[-self._max_cache:]
            except Exception as e:
                logger.warning(f"Error loading audit cache from {self.log_path}: {e}")

    def record_event(
        self,
        event_type: str,
        actor: str,
        target: str,
        risk_level: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records an immutable audit entry.
        Event types: POLICY_DECISION, APPROVAL_REQUEST, APPROVAL_GRANTED, APPROVAL_DENIED,
                     TOOL_INVOCATION, COMMAND_EXECUTED, ROLLBACK_INITIATED, SECURITY_ALERT, AWS_OPERATION.
        """
        entry = {
            "audit_id": f"aud_{uuid.uuid4().hex[:10]}",
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "event_type": event_type,
            "actor": actor,
            "target": target,
            "risk_level": risk_level,
            "status": status,
            "details": details or {},
            "approval_token_present": approval_token is not None
        }

        self._cache.append(entry)
        if len(self._cache) > self._max_cache:
            self._cache.pop(0)

        # Append to jsonl
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to append entry to audit log {self.log_path}: {e}")

        return entry

    def query_audit_trail(
        self,
        event_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        results = self._cache
        if event_type:
            results = [e for e in results if e.get("event_type") == event_type]
        if risk_level:
            results = [e for e in results if e.get("risk_level") == risk_level]
        if actor:
            results = [e for e in results if e.get("actor") == actor]
        return results[-limit:]


obs_audit = ObservabilityAudit()
