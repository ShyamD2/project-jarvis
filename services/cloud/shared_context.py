"""
Shared Context & Cross-Device Workflow Handoff Store for J.A.R.V.I.S. Cloud.
Synchronizes active application context, browser URLs, and clipboard state across devices
to support seamless continuity: "JARVIS, continue what I was doing on my laptop on my phone."
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSharedContext")


class SharedContextStore:
    def __init__(self):
        self._device_states: Dict[str, Dict[str, Any]] = {}
        self._global_clipboard: str = ""
        self._last_active_device: str = "desktop-shyam"

    def record_device_state(
        self,
        device_id: str,
        active_window: str,
        active_app: str,
        active_url: Optional[str] = None,
        clipboard_snippet: Optional[str] = None
    ):
        """Updates the live working state of a device."""
        now = time.time()
        self._device_states[device_id] = {
            "device_id": device_id,
            "active_window": active_window,
            "active_app": active_app,
            "active_url": active_url,
            "updated_at": now,
            "updated_at_str": time.strftime("%I:%M:%S %p", time.localtime(now))
        }
        self._last_active_device = device_id
        if clipboard_snippet:
            self._global_clipboard = clipboard_snippet
        logger.debug(f"[SharedContext] Updated state for {device_id}: App='{active_app}' Window='{active_window}'")

    def get_latest_state(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves state for a specific device, or the most recently active device."""
        dev_id = device_id or self._last_active_device
        return self._device_states.get(dev_id, {
            "device_id": dev_id,
            "active_window": "Desktop",
            "active_app": "explorer",
            "active_url": None,
            "updated_at": time.time()
        })

    def request_handoff(self, source_device_id: str, target_device_id: str) -> Dict[str, Any]:
        """
        Executes workflow continuity handoff between devices.
        e.g., transfers active browser URL or document from laptop to phone.
        """
        src_state = self.get_latest_state(source_device_id)
        active_url = src_state.get("active_url")
        active_app = src_state.get("active_app", "general workflow")

        logger.info(f"🔄 [SharedContext] Handoff requested: '{source_device_id}' -> '{target_device_id}' (App: {active_app}, URL: {active_url})")

        return {
            "success": True,
            "source_device": source_device_id,
            "target_device": target_device_id,
            "active_app": active_app,
            "active_url": active_url,
            "clipboard": self._global_clipboard[:200] if self._global_clipboard else None,
            "message": f"Handoff primed, sir. Transferred active context from {source_device_id} to {target_device_id}."
        }


shared_context = SharedContextStore()
