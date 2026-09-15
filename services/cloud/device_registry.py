"""
Secure Device Registry Manager for J.A.R.V.I.S. Cloud.
Maintains authorized fleet metadata, capabilities, and cryptographic token verification.
Strictly ensures zero raw tokens are stored in the persistent JSON registry.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hashlib
import hmac
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.schemas.device_envelope import JarvisDevice, DeviceType, DeviceStatus, DeviceCapability
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDeviceRegistry")

REGISTRY_FILE = os.path.join(PROJECT_ROOT, "data", "device_registry.json")
SALT = os.getenv("JARVIS_DEVICE_SALT", "jarvis_hypervisor_salt_2026")


def hash_token(raw_token: str) -> str:
    """Produces cryptographic salted SHA-256 hash of device authorization token."""
    return hashlib.sha256(f"{SALT}:{raw_token}".encode("utf-8")).hexdigest()


def verify_token(raw_token: str, stored_hash: Optional[str]) -> bool:
    """Verifies token against stored hash using constant-time comparison."""
    if not raw_token or not stored_hash:
        return False
    computed = hash_token(raw_token)
    return hmac.compare_digest(computed, stored_hash)


class DeviceRegistryManager:
    def __init__(self, file_path: str = REGISTRY_FILE):
        self.file_path = file_path
        self.devices: Dict[str, JarvisDevice] = {}
        self._active_connections: Dict[str, Any] = {}
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Loads registry from disk or initializes default authorized fleet for Shyam."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        dev = JarvisDevice.from_dict(item)
                        self.devices[dev.device_id] = dev
                logger.info(f"📱 [DeviceRegistry] Loaded {len(self.devices)} registered devices.")
                return
            except Exception as e:
                logger.warning(f"[DeviceRegistry] Failed to load registry: {e}. Reinitializing.")

        self._seed_default_fleet()

    def _seed_default_fleet(self):
        """Pre-seeds Shyam's authorized personal fleet with cryptographic token hashes."""
        fleet = [
            JarvisDevice(
                device_id="desktop-shyam",
                name="Shyam's Desktop",
                device_type=DeviceType.DESKTOP,
                status=DeviceStatus.ONLINE,
                ip_address="127.0.0.1",
                capabilities=[
                    DeviceCapability.APP_LAUNCH,
                    DeviceCapability.APP_TERMINATE,
                    DeviceCapability.BROWSER_CONTROL,
                    DeviceCapability.FILE_SYSTEM,
                    DeviceCapability.VOLUME_CONTROL,
                    DeviceCapability.WINDOW_MANAGEMENT,
                    DeviceCapability.SCREEN_CAPTURE,
                    DeviceCapability.SYSTEM_POWER,
                    DeviceCapability.CLIPBOARD_SYNC
                ],
                token_hash=hash_token(os.getenv("DESKTOP_DEVICE_TOKEN", "jarvis_token_desktop_primary_key")),
                metadata={"os": "Windows 11 Pro", "role": "primary_workstation"}
            ),
            JarvisDevice(
                device_id="laptop-shyam",
                name="Shyam's Laptop",
                device_type=DeviceType.LAPTOP,
                status=DeviceStatus.ONLINE,
                ip_address="192.168.1.51",
                capabilities=[
                    DeviceCapability.APP_LAUNCH,
                    DeviceCapability.APP_TERMINATE,
                    DeviceCapability.BROWSER_CONTROL,
                    DeviceCapability.FILE_SYSTEM,
                    DeviceCapability.VOLUME_CONTROL,
                    DeviceCapability.WINDOW_MANAGEMENT,
                    DeviceCapability.SCREEN_CAPTURE,
                    DeviceCapability.SYSTEM_POWER,
                    DeviceCapability.CLIPBOARD_SYNC
                ],
                token_hash=hash_token(os.getenv("LAPTOP_DEVICE_TOKEN", "jarvis_token_laptop_roaming_key")),
                metadata={"os": "Windows 11 Home", "role": "mobile_workstation"}
            ),
            JarvisDevice(
                device_id="mobile-shyam",
                name="Shyam's Phone",
                device_type=DeviceType.MOBILE,
                status=DeviceStatus.ONLINE,
                ip_address="192.168.1.50",
                capabilities=[
                    DeviceCapability.APP_LAUNCH,
                    DeviceCapability.MOBILE_APPS,
                    DeviceCapability.NOTIFICATIONS,
                    DeviceCapability.MESSAGES,
                    DeviceCapability.CALLS,
                    DeviceCapability.CAMERA,
                    DeviceCapability.VOLUME_CONTROL,
                    DeviceCapability.CLIPBOARD_SYNC
                ],
                token_hash=hash_token(os.getenv("MOBILE_DEVICE_TOKEN", "jarvis_token_mobile_android_key")),
                metadata={"os": "Android 14", "role": "personal_mobile"}
            ),
            JarvisDevice(
                device_id="tablet-shyam",
                name="Shyam's Tablet",
                device_type=DeviceType.TABLET,
                status=DeviceStatus.STANDBY,
                capabilities=[
                    DeviceCapability.APP_LAUNCH,
                    DeviceCapability.MOBILE_APPS,
                    DeviceCapability.BROWSER_CONTROL,
                    DeviceCapability.NOTIFICATIONS,
                    DeviceCapability.VOLUME_CONTROL,
                    DeviceCapability.CLIPBOARD_SYNC
                ],
                token_hash=hash_token(os.getenv("TABLET_DEVICE_TOKEN", "jarvis_token_tablet_companion_key")),
                metadata={"os": "iPadOS / Android", "role": "secondary_companion"}
            )
        ]

        for d in fleet:
            self.devices[d.device_id] = d
        self._save_to_disk()
        logger.info("📱 [DeviceRegistry] Pre-seeded Shyam's authorized personal fleet.")

    def _save_to_disk(self):
        """Persists metadata to disk. Token hashes are preserved; no plaintext secrets."""
        try:
            payload = [d.to_dict() for d in self.devices.values()]
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error(f"[DeviceRegistry] Error persisting registry to disk: {e}")

    def authenticate_device(self, device_id: str, raw_token: str) -> bool:
        """Validates connecting device against stored cryptographic hash."""
        dev = self.devices.get(device_id)
        if not dev or not dev.token_hash:
            logger.warning(f"🔒 [DeviceRegistry] Authentication failed: Unknown device '{device_id}'")
            return False
        is_valid = verify_token(raw_token, dev.token_hash)
        if is_valid:
            logger.info(f"🔑 [DeviceRegistry] Device '{dev.name}' ({device_id}) successfully authenticated.")
        else:
            logger.warning(f"🔒 [DeviceRegistry] Device '{device_id}' provided invalid auth token.")
        return is_valid

    def register_connection(self, device_id: str, websocket_or_handler: Any, ip_address: Optional[str] = None):
        """Marks device online and binds active communication socket."""
        dev = self.devices.get(device_id)
        if dev:
            dev.status = DeviceStatus.ONLINE
            dev.last_seen = time.time()
            if ip_address:
                dev.ip_address = ip_address
            self._active_connections[device_id] = websocket_or_handler
            self._save_to_disk()
            logger.info(f"⚡ [DeviceRegistry] Device online: {dev.name} ({device_id}) @ {dev.ip_address}")

    def unregister_connection(self, device_id: str):
        """Marks device offline upon socket disconnect."""
        dev = self.devices.get(device_id)
        if dev:
            dev.status = DeviceStatus.OFFLINE
            dev.last_seen = time.time()
            self._active_connections.pop(device_id, None)
            self._save_to_disk()
            logger.info(f"🔌 [DeviceRegistry] Device offline: {dev.name} ({device_id})")

    def get_connection(self, device_id: str) -> Optional[Any]:
        return self._active_connections.get(device_id)

    def get_device(self, device_id: str) -> Optional[JarvisDevice]:
        return self.devices.get(device_id)

    def is_device_online(self, device_id: str) -> bool:
        dev = self.devices.get(device_id)
        if not dev:
            return False
        return dev.status == DeviceStatus.ONLINE

    def set_device_status(self, device_id: str, status: DeviceStatus):
        dev = self.devices.get(device_id)
        if dev:
            dev.status = status
            dev.last_seen = time.time()
            self._save_to_disk()

    def list_devices(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.devices.values()]

    def find_capable_device(
        self,
        capability: DeviceCapability,
        preferred_type: Optional[DeviceType] = None
    ) -> Optional[JarvisDevice]:
        """Discovers authorized online device capable of performing the task."""
        candidates = [
            d for d in self.devices.values()
            if capability in d.capabilities and d.status == DeviceStatus.ONLINE
        ]
        if preferred_type:
            for d in candidates:
                if d.device_type == preferred_type:
                    return d
        return candidates[0] if candidates else None


device_registry = DeviceRegistryManager()
