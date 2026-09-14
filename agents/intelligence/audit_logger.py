"""
J.A.R.V.I.S. Execution Audit Logger.
Maintains an immutable, structured JSONL audit trail of every utterance, intent, risk evaluation, and tool execution.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisAuditLogger")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
AUDIT_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "audit_execution.jsonl")


class AuditLogger:
    def __init__(self, log_path: str = AUDIT_LOG_FILE):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def record_entry(
        self,
        user_query: str,
        intent: str,
        tool: str,
        parameters: Dict[str, Any],
        risk_tier: str,
        result: str,
        duration_ms: float,
        confirmation_state: str = "NONE",
        caller: str = "jarvis_core_agent",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Records a structured audit event into JSONL log file.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_query": user_query,
            "intent": intent,
            "tool": tool,
            "parameters": parameters,
            "risk_tier": risk_tier,
            "confirmation_state": confirmation_state,
            "result": result,
            "duration_ms": round(duration_ms, 2),
            "caller": caller,
            "details": details or {}
        }

        try:
            line = json.dumps(entry) + "\n"
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.error(f"Failed to write to audit log file: {e}")

        logger.info(f"📋 [AUDIT] {entry['timestamp']} | USER: '{user_query}' | TOOL: {tool} | RISK: {risk_tier} | RESULT: {result} ({duration_ms:.1f}ms)")
        return entry

    def read_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Reads recent audit log entries"""
        if not os.path.exists(self.log_path):
            return []

        entries = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    line_str = line.strip()
                    if line_str:
                        entries.append(json.loads(line_str))
        except Exception as e:
            logger.warning(f"Error reading audit log: {e}")
        return entries


audit_logger = AuditLogger()
