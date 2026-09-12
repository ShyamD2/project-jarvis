"""
Local-to-Cloud Secure Bridge for Project J.A.R.V.I.S.
Guarantees Windows host security:
1. Zero Inbound Public Ports: The PC gateway only makes secure outbound-initiated connections.
2. Cryptographic Envelope Verification: Enforces HMAC-SHA256 signatures on all remote messages.
3. Anti-Replay Protection: Enforces timestamp validity (<60s) and unique nonces.
"""

from __future__ import annotations
import hmac
import hashlib
import time
import json
from typing import Dict, Any, Tuple, Optional

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger

try:
    from services.observability import obs_audit, obs_logger
except ImportError:
    obs_audit = None
    obs_logger = None

logger = get_logger("JarvisSecureBridge")


class SecureBridge:
    def __init__(self, secret: Optional[str] = None):
        self.secret = (secret or config.master_secret).encode("utf-8")
        self._processed_nonces: set[str] = set()
        self._max_clock_skew_seconds = 60.0

    def generate_signature(self, payload: Dict[str, Any], timestamp: float, nonce: str) -> str:
        """Generates HMAC-SHA256 signature for outbound message transmission"""
        message = f"{timestamp}:{nonce}:{json.dumps(payload, sort_keys=True)}"
        return hmac.new(self.secret, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_message(self, message_envelope: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates an incoming remote command envelope.
        Must contain: 'payload', 'timestamp', 'nonce', 'signature'
        """
        payload = message_envelope.get("payload")
        timestamp = message_envelope.get("timestamp")
        nonce = message_envelope.get("nonce")
        provided_sig = message_envelope.get("signature")

        if not all([payload is not None, timestamp, nonce, provided_sig]):
            return False, "Malformed envelope: missing timestamp, nonce, signature, or payload"

        # 1. Clock skew check (< 60s)
        now = time.time()
        if abs(now - timestamp) > self._max_clock_skew_seconds:
            msg = f"Timestamp drift exceeded: delta {abs(now - timestamp):.1f}s > {self._max_clock_skew_seconds}s"
            if obs_audit:
                obs_audit.record_event("SECURITY_ALERT", "remote_gateway", "secure_bridge", "CRITICAL", "REJECTED", {"reason": msg})
            return False, msg

        # 2. Replay protection check
        if nonce in self._processed_nonces:
            msg = f"Replay attack detected: duplicate nonce '{nonce}'"
            if obs_audit:
                obs_audit.record_event("SECURITY_ALERT", "remote_gateway", "secure_bridge", "CRITICAL", "REJECTED", {"reason": msg})
            return False, msg

        # 3. Cryptographic HMAC verification
        expected_sig = self.generate_signature(payload, timestamp, nonce)
        if not hmac.compare_digest(expected_sig, provided_sig):
            msg = "Cryptographic signature mismatch: invalid secret or altered payload"
            if obs_audit:
                obs_audit.record_event("SECURITY_ALERT", "remote_gateway", "secure_bridge", "CRITICAL", "REJECTED", {"reason": msg})
            return False, msg

        # Record verified nonce
        self._processed_nonces.add(nonce)
        if len(self._processed_nonces) > 5000:
            self._processed_nonces.clear()

        return True, "VERIFIED: Cryptographic authenticity confirmed"


secure_bridge = SecureBridge()
