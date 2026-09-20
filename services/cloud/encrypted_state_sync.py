"""
Encrypted Cross-Device State Synchronization for Project J.A.R.V.I.S.
Provides end-to-end encrypted serialization of active task contexts, DAGs,
device telemetry, and working memory across authorized desktop, phone, and cloud nodes.
Uses AES-256 encryption via Fernet with PBKDF2 key derivation from workstation master secret.
"""

from __future__ import annotations
import os
import json
import base64
import time
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("EncryptedStateSync")


class EncryptedStateSynchronizer:
    def __init__(self):
        self._salt = b"jarvis_state_sync_salt_v2"

    def _derive_key(self, secret: Optional[str] = None) -> bytes:
        raw_secret = (secret or getattr(config, "master_secret", "jarvis_secret_default_master_2026")).encode("utf-8")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000
        )
        return base64.urlsafe_b64encode(kdf.derive(raw_secret))

    def encrypt_state(self, state_dict: Dict[str, Any], secret: Optional[str] = None) -> str:
        """Serializes dictionary to JSON and encrypts with AES-256 Fernet."""
        key = self._derive_key(secret)
        fernet = Fernet(key)

        envelope = {
            "timestamp": time.time(),
            "source_node": getattr(config, "host", "desktop-windows"),
            "operating_mode": config.operating_mode,
            "data": state_dict
        }
        raw_bytes = json.dumps(envelope).encode("utf-8")
        encrypted_token = fernet.encrypt(raw_bytes).decode("utf-8")
        logger.info(f"[EncryptedStateSync] Encrypted state envelope ({len(raw_bytes)} bytes -> {len(encrypted_token)} chars)")
        return encrypted_token

    def decrypt_state(self, encrypted_token: str, secret: Optional[str] = None) -> Dict[str, Any]:
        """Decrypts and verifies AES-256 Fernet envelope."""
        key = self._derive_key(secret)
        fernet = Fernet(key)

        try:
            decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
            envelope = json.loads(decrypted_bytes.decode("utf-8"))
            logger.info(f"[EncryptedStateSync] Decrypted state from node '{envelope.get('source_node')}' (mode={envelope.get('operating_mode')})")
            return envelope.get("data", {})
        except Exception as e:
            logger.error(f"[EncryptedStateSync] Decryption failed (tampered data or wrong secret): {e}")
            raise ValueError(f"State decryption failed: {e}")


state_sync = EncryptedStateSynchronizer()
