"""
Project J.A.R.V.I.S. Secure Remote Mobile Gateway (Telegram Bot).
Enables remote workstation monitoring, screenshots, volume control, workstation lock,
and natural language conversational command execution via mobile Telegram.
"""

from __future__ import annotations
import os
import sys
import time
import asyncio
import httpx
from typing import Optional, Dict, Any, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisTelegramGateway")


class JarvisTelegramGateway:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.allowed_users = [
            u.strip()
            for u in os.getenv("TELEGRAM_ALLOWED_USER_ID", "").split(",")
            if u.strip()
        ]
        self._running = False
        self._offset = 0
        self._base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def is_authorized(self, user_id: Any) -> bool:
        if not self.allowed_users:
            # If no allowed users explicitly set, allow owner or log notice
            return True
        return str(user_id) in self.allowed_users

    async def send_message(self, chat_id: int | str, text: str, parse_mode: Optional[str] = None) -> bool:
        """Sends a text message to a Telegram chat"""
        if not self.token:
            return False
        url = f"{self._base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[TelegramGateway] Failed to send message to {chat_id}: {e}")
            return False

    async def send_photo(self, chat_id: int | str, photo_path: str, caption: Optional[str] = None) -> bool:
        """Sends a photo/screenshot to a Telegram chat"""
        if not self.token or not os.path.exists(photo_path):
            return False
        url = f"{self._base_url}/sendPhoto"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(photo_path, "rb") as f:
                    files = {"photo": (os.path.basename(photo_path), f, "image/png")}
                    data = {"chat_id": chat_id}
                    if caption:
                        data["caption"] = caption
                    resp = await client.post(url, data=data, files=files)
                    return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[TelegramGateway] Failed to send photo: {e}")
            return False

    async def handle_update(self, update: Dict[str, Any]):
        """Processes an incoming Telegram message update"""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        text = message.get("text", "").strip()

        if not chat_id or not text:
            return

        # Security check: User authorization
        if not self.is_authorized(user_id):
            logger.warning(f"[TelegramGateway] Unauthorized access attempt blocked from User ID: {user_id}")
            await self.send_message(chat_id, "⛔ Access Denied. You are not authorized to command Project J.A.R.V.I.S.")
            return

        lower = text.lower().strip()
        logger.info(f"[TelegramGateway] Authorized command received from {user_id}: '{text}'")

        # 1. /start or /help
        if lower in ["/start", "/help", "help"]:
            help_msg = (
                "🛡️ *Project J.A.R.V.I.S. Remote Mobile Terminal*\n\n"
                "• `/status` - Live PC vitals & active window\n"
                "• `/screen` - Desktop screenshot snapshot\n"
                "• `/lock` - Initiate Lockdown Protocol (lock PC)\n"
                "• `/volume <0-100>` - Set audio volume\n"
                "• `Any natural prompt` - Autonomous execution via Brain"
            )
            await self.send_message(chat_id, help_msg, parse_mode="Markdown")
            return

        # 2. /status
        if lower in ["/status", "status"]:
            import psutil
            from datetime import datetime
            from agents.computer.windows_agent import windows_agent

            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            bat = psutil.sensors_battery()
            bat_str = f"{int(bat.percent)}% ({'Charging' if bat.power_plugged else 'Battery'})" if bat else "AC Power"
            active_win = windows_agent.get_active_window_info()

            status_text = (
                "📊 *J.A.R.V.I.S. Core Vitals:*\n\n"
                f"• *CPU Utilization:* `{cpu:.1f}%`\n"
                f"• *Memory Load:* `{mem:.1f}%`\n"
                f"• *Power Reserve:* `{bat_str}`\n"
                f"• *Active Window:* `{active_win.get('title', 'Unknown')}`\n"
                f"• *Active App:* `{active_win.get('process', 'Unknown')}`\n"
                f"• *Timestamp:* `{datetime.now().strftime('%H:%M:%S, %d %b %Y')}`"
            )
            await self.send_message(chat_id, status_text, parse_mode="Markdown")
            return

        # 3. /screen or /screenshot
        if lower in ["/screen", "/screenshot", "screen", "screenshot"]:
            await self.send_message(chat_id, "📸 Capturing desktop snapshot, sir...")
            from agents.computer.screen_agent import screen_agent
            from agents.computer.windows_agent import windows_agent

            snap = screen_agent.capture_screenshot()
            if snap.get("success") and snap.get("screenshot_path"):
                win_info = windows_agent.get_active_window_info()
                caption = f"🖥️ Active: {win_info.get('title', 'Desktop')} ({win_info.get('process', '')})"
                await self.send_photo(chat_id, snap["screenshot_path"], caption=caption)
            else:
                await self.send_message(chat_id, "❌ Failed to capture screenshot.")
            return

        # 4. /lock or lockdown
        if lower in ["/lock", "lock", "protocol lockdown", "lockdown"]:
            from agents.intelligence.planner import planner
            res = await planner.execute_workflow("lockdown_protocol")
            await self.send_message(chat_id, f"🔒 {res.get('message', 'Lockdown protocol engaged.')}")
            return

        # 5. /volume <num>
        if lower.startswith("/volume"):
            parts = lower.split()
            if len(parts) > 1 and parts[1].isdigit():
                val = int(parts[1])
                from agents.computer.audio_agent import audio_agent
                audio_agent.set_volume_percent(val)
                await self.send_message(chat_id, f"🔊 Master volume adjusted to {val}%, sir.")
            else:
                await self.send_message(chat_id, "Usage: `/volume <0-100>`")
            return

        # 6. Natural Language Query via Conversation Engine
        try:
            from services.brain.conversation_engine import conversation_engine
            turn_res = await conversation_engine.process_turn(text)
            reply = turn_res.get("response") or "Instruction processed, sir."
            await self.send_message(chat_id, f"🤖 *J.A.R.V.I.S.:*\n{reply}", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[TelegramGateway] Turn execution error: {e}")
            await self.send_message(chat_id, f"⚠️ Error processing instruction: {e}")

    async def start(self):
        """Main polling background task"""
        if not self.is_configured:
            logger.info("⚡ [Telegram Gateway] Standing by (TELEGRAM_BOT_TOKEN not configured in .env).")
            return

        self._running = True
        logger.info(f"⚡ [Telegram Gateway] Online. Authorized users: {self.allowed_users or 'ALL'}")

        async with httpx.AsyncClient(timeout=40.0) as client:
            while self._running:
                try:
                    url = f"{self._base_url}/getUpdates"
                    params = {"offset": self._offset, "timeout": 25}
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for u in updates:
                            update_id = u.get("update_id")
                            if update_id:
                                self._offset = update_id + 1
                            await self.handle_update(u)
                    elif resp.status_code in [401, 404]:
                        logger.error(f"[TelegramGateway] Invalid bot token: HTTP {resp.status_code}")
                        break
                    else:
                        await asyncio.sleep(3.0)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"[TelegramGateway] Polling cycle notice: {e}")
                    await asyncio.sleep(4.0)

        logger.info("[Telegram Gateway] Standby / Shutdown complete.")

    def stop(self):
        self._running = False


telegram_gateway = JarvisTelegramGateway()
