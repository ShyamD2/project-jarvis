"""
Project J.A.R.V.I.S. Secure Remote Mobile Gateway (Telegram Bot).
Comprehensive mobile command center with full system access and simple, plain-English responses:
- 📸 Screen & Vision: Live desktop screenshots and plain-English screen context analysis
- ⌨️ Keyboard & Typing: Autonomous typing into apps, key presses, and shortcuts
- 🖱️ Mouse Control: Click, right-click, double-click, and scroll
- 📋 Clipboard: View clipboard, copy text to PC, paste into active app, diagnose errors
- 💻 Terminal & Shell: Run CMD / PowerShell commands directly on your PC
- 🚀 Apps & Windows: Launch apps, open websites, close windows, minimize, maximize, and focus
- 📁 Files & Folders: Browse project files, Downloads, Desktop, or open folders in File Explorer
- 🔊 Audio & Media: Master volume, mute/unmute, play/pause, next/prev track, PC speaker speech (/say)
- 📊 PC Health & Vitals: Simple, easy-to-understand status for CPU, RAM, battery, and active apps
- 🔒 Power & Security: Instantly lock PC, turn off screens, sleep, reboot, or shutdown
- 🎙️ Voice Notes: Send voice notes from Telegram for instant voice execution
- 💬 Everyday English: Works with natural conversational phrases without needing slash commands!
"""

from __future__ import annotations
import os
import sys
import time
import io
import asyncio
import subprocess
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc_agent"))

# If launched via pythonw.exe (Windows silent background mode), redirect stdout/stderr to gateway.log
if sys.stdout is None or sys.stderr is None:
    _log_dir = os.path.join(PROJECT_ROOT, "services", "gateway")
    os.makedirs(_log_dir, exist_ok=True)
    try:
        _log_f = open(os.path.join(_log_dir, "gateway.log"), "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = _log_f
        if sys.stderr is None:
            sys.stderr = _log_f
    except Exception:
        pass

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisTelegramGateway")

# SIMPLE INTERACTIVE REPLY KEYBOARD FOR INSTANT ONE-TAP CONTROL
MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "🚀 Start J.A.R.V.I.S."}, {"text": "🛑 Close HUD"}],
        [{"text": "🎥 Live Video Screen"}, {"text": "🖱️ Mouse Trackpad"}],
        [{"text": "🌙 Stealth Screen Off"}, {"text": "☀️ Wake Screen"}],
        [{"text": "✍️ Writing Space"}, {"text": "📸 Screen Snapshot"}],
        [{"text": "👁️ What's on Screen?"}, {"text": "💻 PC Status"}],
        [{"text": "🛡️ SRE Scan"}, {"text": "🔒 Lock PC"}],
        [{"text": "🛡️ Cyber Lock"}, {"text": "🌙 Delegate Mission"}],
        [{"text": "❓ Help & Commands"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

WRITING_KEYBOARD = {
    "keyboard": [
        [{"text": "🔙 Erase 1 Char"}, {"text": "🔙 Erase 5 Chars"}],
        [{"text": "🗑️ Clear Field"}, {"text": "⏎ Press Enter"}],
        [{"text": "📋 Paste Clipboard"}, {"text": "📸 Screen Snapshot"}],
        [{"text": "⬅️ Main Menu"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}


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
        self._file_url = f"https://api.telegram.org/file/bot{self.token}" if self.token else ""
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
        self._writing_mode: Dict[str, bool] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def is_authorized(self, user_id: Any) -> bool:
        if not self.allowed_users:
            return True
        return str(user_id) in self.allowed_users

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Sends a text message to a Telegram chat with optional interactive keyboard"""
        if not self.token:
            return False
        url = f"{self._base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[TelegramGateway] Failed to send message to {chat_id}: {e}")
            return False

    async def broadcast_to_authorized(self, text: str, parse_mode: Optional[str] = None) -> int:
        """Broadcasts a notification message to all authorized Telegram user IDs"""
        if not self.token or not self.allowed_users:
            return 0
        success_count = 0
        for uid in self.allowed_users:
            try:
                ok = await self.send_message(chat_id=uid, text=text, parse_mode=parse_mode, reply_markup=MAIN_KEYBOARD)
                if ok:
                    success_count += 1
            except Exception as e:
                logger.debug(f"[TelegramGateway] Broadcast to {uid} failed: {e}")
        return success_count

    async def send_photo(
        self,
        chat_id: int | str,
        photo_path: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None
    ) -> bool:
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
                    if parse_mode:
                        data["parse_mode"] = parse_mode
                    resp = await client.post(url, data=data, files=files)
                    return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[TelegramGateway] Failed to send photo: {e}")
            return False

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        """Deletes a message from Telegram chat (used for privacy when sending passwords/PINs)"""
        if not self.token or not message_id:
            return False
        url = f"{self._base_url}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception:
            return False

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> bool:
        """Acknowledges an interactive Telegram inline callback query"""
        if not self.token or not callback_query_id:
            return False
        url = f"{self._base_url}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception:
            return False

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Downloads a file or voice note from Telegram servers"""
        if not self.token:
            return None
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                info_resp = await client.get(f"{self._base_url}/getFile?file_id={file_id}")
                if info_resp.status_code == 200:
                    f_path = info_resp.json().get("result", {}).get("file_path")
                    if f_path:
                        dl_resp = await client.get(f"{self._file_url}/{f_path}")
                        if dl_resp.status_code == 200:
                            return dl_resp.content
        except Exception as e:
            logger.warning(f"[TelegramGateway] File download error: {e}")
        return None

    async def transcribe_audio_bytes(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribes incoming voice note via Groq Whisper or Gemini"""
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            try:
                url = "https://api.groq.com/openai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {groq_key}"}
                files = {"file": ("voice_note.ogg", audio_bytes, "audio/ogg")}
                data = {"model": "whisper-large-v3", "language": "en"}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, headers=headers, files=files, data=data)
                    if resp.status_code == 200:
                        text = resp.json().get("text", "").strip()
                        if text:
                            return text
            except Exception as e_groq:
                logger.debug(f"[TelegramGateway] Groq voice transcription notice: {e_groq}")

        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_key:
            try:
                import base64
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": "Transcribe this audio command verbatim into plain text with no additional commentary:"},
                            {"inlineData": {"mimeType": "audio/ogg", "data": b64_audio}}
                        ]
                    }]
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        t = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if t:
                            return t
            except Exception as e_gem:
                logger.debug(f"[TelegramGateway] Gemini voice transcription notice: {e_gem}")

        return None

    async def handle_callback_query(self, cb: Dict[str, Any]):
        """Handles interactive inline keyboard trackpad clicks and mouse controls"""
        cb_id = cb.get("id")
        from_user = cb.get("from", {}).get("id")
        data = cb.get("data", "")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")

        if not self.is_authorized(from_user):
            await self.answer_callback_query(cb_id, text="Unauthorized")
            return

        await self.answer_callback_query(cb_id)

        try:
            from agents.computer.mouse_agent import mouse_agent
            if data.startswith("mouse_move:"):
                parts = data.split(":")
                dx = int(parts[1])
                dy = int(parts[2])
                cx, cy = mouse_agent.get_cursor_position()
                mouse_agent.move_cursor(cx + dx, cy + dy)

            elif data.startswith("mouse_click:"):
                btn = data.split(":")[1]
                mouse_agent.click(button=btn)

            elif data.startswith("mouse_scroll:"):
                direction = data.split(":")[1]
                mouse_agent.scroll(clicks=3, direction=direction)

            elif data == "key_enter":
                from agents.computer.keyboard_agent import keyboard_agent
                keyboard_agent.press_key("enter")

            elif data.startswith("mouse_snap"):
                from agents.computer.screen_agent import screen_agent
                snap = screen_agent.capture_screenshot()
                if snap.get("success") and snap.get("screenshot_path") and os.path.exists(snap["screenshot_path"]):
                    await self.send_photo(chat_id, snap["screenshot_path"], caption="🖥️ *Screen Snapshot (Trackpad)*", parse_mode="Markdown")
        except Exception as e:
            logger.debug(f"[TelegramGateway] Callback query handling error: {e}")

    async def handle_update(self, update: Dict[str, Any]):
        """Processes an incoming Telegram message update with full system control and simple words"""
        callback_query = update.get("callback_query")
        if callback_query:
            await self.handle_callback_query(callback_query)
            return

        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        text = message.get("text", "").strip()
        voice = message.get("voice") or message.get("audio")

        if not chat_id:
            return

        # Security check: User authorization
        if not self.is_authorized(user_id):
            logger.warning(f"[TelegramGateway] Unauthorized access attempt blocked from User ID: {user_id}")
            await self.send_message(chat_id, "⛔ Access Denied. You are not authorized to command Project J.A.R.V.I.S.")
            return

        # Handle Incoming Voice Note
        if voice and not text:
            file_id = voice.get("file_id")
            audio_bytes = await self.download_file(file_id)
            if audio_bytes:
                transcribed = await self.transcribe_audio_bytes(audio_bytes)
                if transcribed:
                    text = transcribed
                else:
                    await self.send_message(chat_id, "⚠️ Sorry, I couldn't hear that clearly. Could you please send it as text or try again?")
                    return
            else:
                await self.send_message(chat_id, "⚠️ Failed to download the audio recording.")
                return

        if not text:
            return

        lower = text.lower().strip()
        logger.info(f"[TelegramGateway] Routing command to Brain Runtime from {user_id}: '{text}'")

        # 1. TELEGRAM UI NAVIGATION & MENUS
        if lower in ["/start", "/menu", "menu", "main menu", "⬅️ main menu"]:
            self._writing_mode[str(user_id)] = False
            welcome_text = (
                "👋 *J.A.R.V.I.S. Command Center Online, sir.*\n\n"
                "I am listening. You can speak to me in plain English or use the one-tap controls below:\n\n"
                "• *Voice / Natural Speech:* Send a voice note or natural query (e.g. _'Open Opera and check battery'_)\n"
                "• *Vision:* Tap *📸 Screen Snapshot* or *👁️ What's on Screen?*\n"
                "• *Remote Trackpad:* Tap *🖱️ Mouse Trackpad* for real-time cursor control\n"
                "• *Remote Writing:* Tap *✍️ Writing Space* to type directly into active windows\n"
                "• *System Health:* Tap *💻 PC Status* or *🛡️ SRE Scan*"
            )
            await self.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
            return

        # 2. REMOTE WRITING SPACE & INPUT ERASER
        if lower in ["✍️ writing space", "/writing", "/writer", "writing space"]:
            self._writing_mode[str(user_id)] = True
            intro = (
                "✍️ *Remote Writing Space Activated!*\n\n"
                "You can now type anything into your active PC window directly from your phone.\n\n"
                "• Send any message to type it into your active window\n"
                "• Tap *🔙 Erase 1 Char* or send `/erase 1` to backspace\n"
                "• Tap *🗑️ Clear Field* or send `/clear` to clear current input field\n"
                "• Tap *⏎ Press Enter* or send `/enter` to submit / send\n"
                "• Tap *📋 Paste Clipboard* to paste copied text\n"
                "• Tap *⬅️ Main Menu* to return to standard controls"
            )
            await self.send_message(chat_id, intro, parse_mode="Markdown", reply_markup=WRITING_KEYBOARD)
            return

        if self._writing_mode.get(str(user_id)):
            if lower.startswith("/erase") or lower.startswith("erase ") or lower in ["🔙 erase 1 char", "🔙 erase 5 chars"]:
                from agents.computer.keyboard_agent import keyboard_agent
                count = 5 if lower in ["🔙 erase 5 chars", "/erase 5", "erase 5"] else 1
                if lower.startswith("/erase ") or lower.startswith("erase "):
                    arg = (text[7:] if lower.startswith("/erase ") else text[6:]).strip()
                    if arg.isdigit():
                        count = min(int(arg), 100)
                for _ in range(count):
                    keyboard_agent.press_key("backspace")
                    time.sleep(0.02)
                await self.send_message(chat_id, f"🔙 Erased {count} character{'s' if count > 1 else ''}.", reply_markup=WRITING_KEYBOARD)
                return

            if lower in ["/clear", "clear", "🗑️ clear field", "clear field"]:
                from agents.computer.keyboard_agent import keyboard_agent
                keyboard_agent.press_shortcut(["ctrl", "a"])
                time.sleep(0.05)
                keyboard_agent.press_key("backspace")

        # ======================================================================
        # MOUSE TRACKPAD & LIVE SCREEN STREAM
        # ======================================================================
        if lower in [
            "🖱️ mouse trackpad", "🎥 live video screen", "live video screen", "live screen",
            "/trackpad", "/mouse", "/stream", "/live", "/remote",
            "trackpad", "mouse", "remote", "live", "stream", "video", "live stream"
        ]:
            from services.gateway.remote_trackpad_server import get_local_ip, get_public_url, get_operator_token
            from services.security.cyber_lock import get_stored_pin
            local_ip = get_local_ip()
            public_url = get_public_url()
            token = get_operator_token()
            base_url = public_url if public_url.startswith("https://") else f"http://{local_ip}:8085"
            live_link = f"{base_url}/live"
            remote_link = f"{base_url}/remote"
            wifi_live = f"http://{local_ip}:8085/live"
            wifi_remote = f"http://{local_ip}:8085/remote"
            current_pin = get_stored_pin()

            trackpad_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🎥 Watch Live Video Feed", "url": live_link},
                        {"text": "📱 Open Touchpad & Remote", "url": remote_link}
                    ],
                    [
                        {"text": "↖️", "callback_data": "mouse_move:-30:-30"},
                        {"text": "⬆️ Up", "callback_data": "mouse_move:0:-35"},
                        {"text": "↗️", "callback_data": "mouse_move:30:-30"},
                    ],
                    [
                        {"text": "⬅️ Left", "callback_data": "mouse_move:-35:0"},
                        {"text": "🎯 Click", "callback_data": "mouse_click:left"},
                        {"text": "➡️ Right", "callback_data": "mouse_move:35:0"},
                    ],
                    [
                        {"text": "↙️", "callback_data": "mouse_move:-30:30"},
                        {"text": "⬇️ Down", "callback_data": "mouse_move:0:35"},
                        {"text": "↘️", "callback_data": "mouse_move:30:30"},
                    ],
                    [
                        {"text": "🖱️ Right Click", "callback_data": "mouse_click:right"},
                        {"text": "⏎ ENTER", "callback_data": "key_enter"},
                        {"text": "📸 Snapshot", "callback_data": "mouse_snap"}
                    ]
                ]
            }
            msg = (
                "🖥️ *J.A.R.V.I.S. Master Live Screen & Mobile Touchpad*\n\n"
                "👉 *1-Tap Instant Links on Your Phone:*\n\n"
                "🎥 *Direct Live Video Stream:*\n"
                f"🌐 {live_link}\n"
                f"_(Home Wi-Fi Live Link: `{wifi_live}`)_\n\n"
                "📱 *Interactive Touchpad & Remote Console:*\n"
                f"🌐 {remote_link}\n"
                f"_(Home Wi-Fi Touchpad Link: `{wifi_remote}`)_\n\n"
                "🛡️ *Unified Master PIN Gate Active:*\n"
                f"• Master PIN: `{current_pin}` (One single PIN for BOTH Web Trackpad & Cyber Lock)\n"
                f"• _To change Master PIN for both:_ `/setpin {current_pin} <new_pin>`\n"
                "• High-contrast cyan mouse pointer is visible on the live video stream!\n\n"
                "✨ *Features & Gestures:*\n"
                "• 🎥 **Real-time Video Feed**: Crystal-clear desktop video with cursor hotspot\n"
                "• 🎯 **Live Screen Tap-To-Click**: Tap anywhere on your phone screen to click on PC!\n"
                "• 🖱️ **Fluid Glide Mouse**: Ultra-responsive 1ms touch trackpad\n"
                "• 📜 **2-Finger Gliding Scroll**: Drag 2 fingers up/down to scroll web pages\n"
                "• 🗂️ **Browser Controls**: New Tab (`Ctrl+T`), Close Tab (`Ctrl+W`), Next/Prev Tab\n"
                "• ⏎ **Quick Actions**: Big ENTER Button, ESC, Backspace & Keyboard input"
            )
            await self.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=trackpad_keyboard)
            return

        # ======================================================================
        # ======================================================================
        # 3. DIRECT ROUTING TO BRAIN RUNTIME (Multi-Turn ReAct -> ToolRegistry -> VerificationEngine)
        # ======================================================================
        try:
            from services.brain.conversation_engine import conversation_engine
            turn_res = await conversation_engine.process_turn(text)
            reply = turn_res.get("response") or "Instruction executed, sir."

            # Check if any action produced a screenshot or image to return visually
            photo_sent = False
            for action in turn_res.get("actions_executed", []):
                res_data = action.get("result", {})
                if isinstance(res_data, dict):
                    snap_path = res_data.get("screenshot_path") or res_data.get("path")
                    if snap_path and os.path.exists(str(snap_path)) and str(snap_path).lower().endswith((".png", ".jpg", ".jpeg")):
                        caption = f"🗣️ *\"{text}\"*\n\n🤖 {reply}" if voice else f"🤖 {reply}"
                        await self.send_photo(chat_id, snap_path, caption=caption, parse_mode="Markdown")
                        photo_sent = True
                        break

            if not photo_sent:
                # Single message reply - no duplicate notifications
                msg_text = f"🗣️ *\"{text}\"*\n\n🤖 {reply}" if voice else f"🤖 {reply}"
                await self.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)

        except Exception as e:
            logger.error(f"[TelegramGateway] Brain execution error: {e}")
            await self.send_message(chat_id, f"⚠️ I encountered an error processing your instruction: {e}", reply_markup=MAIN_KEYBOARD)

    async def _register_bot_menu(self, client: httpx.AsyncClient):
        """Registers clean, easy-to-understand Telegram [/] Command Menu with Telegram API"""
        try:
            url = f"{self._base_url}/setMyCommands"
            commands = [
                {"command": "menu", "description": "📋 Open Main Command Center Menu"},
                {"command": "live", "description": "🎥 Watch live desktop video stream"},
                {"command": "trackpad", "description": "🖱️ Touchpad & live remote control"},
                {"command": "screen", "description": "📸 Desktop screenshot photo"},
                {"command": "whatscreen", "description": "👁️ Analyze what is on screen"},
                {"command": "writing", "description": "✍️ Remote typing into active window"},
                {"command": "type", "description": "⌨️ Type text onto computer"},
                {"command": "press", "description": "🔘 Press keyboard key (enter, esc, etc.)"},
                {"command": "shortcut", "description": "🔤 Shortcut keys (e.g. win d, ctrl t)"},
                {"command": "new_tab", "description": "➕ Open new browser tab"},
                {"command": "close_tab", "description": "❌ Close current browser tab"},
                {"command": "sudo", "description": "⚡ Master admin override execution"},
                {"command": "unlock", "description": "🔓 Remote unlock Windows workstation"},
                {"command": "lock", "description": "🔒 Lock computer safely (Win+L)"},
                {"command": "cyberlock", "description": "🛡️ Zero-blackout physical screen lock barrier"},
                {"command": "setpin", "description": "🛡️ Change Master Security PIN"},
                {"command": "start_jarvis", "description": "🚀 Launch 3D Floating Arc Reactor HUD"},
                {"command": "close_hud", "description": "🛑 Close 3D Floating Arc Reactor HUD"},
                {"command": "open", "description": "🚀 Open an app or website"},
                {"command": "close", "description": "🛑 Close an application"},
                {"command": "apps", "description": "📋 View open applications"},
                {"command": "status", "description": "💻 Simple PC health & vitals"},
                {"command": "battery", "description": "🔋 Check battery charge & status"},
                {"command": "vol", "description": "🔊 Volume: max, min, mute, 0-100"},
                {"command": "stealth", "description": "🌙 Turn monitors off for silent control"},
                {"command": "wake", "description": "☀️ Wake display monitors & desktop"},
                {"command": "clip", "description": "📋 Clipboard view & paste"},
                {"command": "say", "description": "🗣️ Speak words aloud through PC"},
                {"command": "sre", "description": "🛡️ Autonomous SRE scan & self-heal ports/locks"},
                {"command": "delegate", "description": "🌙 Overnight GhostWorker mission delegation"},
                {"command": "checkpoint", "description": "⏪ Create OS time-travel restore point"},
                {"command": "rewind", "description": "⏪ Rewind workstation state in <4s"},
                {"command": "teleport", "description": "🌐 Teleport session to Cloud or Phone"},
                {"command": "memory", "description": "🧠 View deep learning neural memory facts"},
                {"command": "forget", "description": "🗑️ Delete memory fact from neural graph"},
                {"command": "speed", "description": "⚡ Ecosystem latency benchmarks (<200ms)"},
                {"command": "evolve", "description": "🧬 Darwinian autonomous code evolution stats"},
                {"command": "files", "description": "📁 Browse project & download files"},
                {"command": "help", "description": "❓ Full help guide & command instructions"}
            ]
            resp = await client.post(url, json={"commands": commands})
            if resp.status_code == 200:
                logger.info("⚡ [Telegram Gateway] Native Telegram command menu synchronized.")
        except Exception as e:
            logger.debug(f"[TelegramGateway] setMyCommands notice: {e}")

    async def start(self):
        """Main polling background task"""
        if not self.is_configured:
            logger.info("⚡ [Telegram Gateway] Standing by (TELEGRAM_BOT_TOKEN not configured in .env).")
            return

        self._running = True
        logger.info(f"⚡ [Telegram Gateway] Online. Authorized users: {self.allowed_users or 'ALL'}")

        # Automatically launch live screen stream & touch trackpad server on LAN (port 8085)
        try:
            from services.gateway.remote_trackpad_server import start_trackpad_server
            start_trackpad_server(host="0.0.0.0", port=8085)
        except Exception as e:
            logger.warning(f"[TelegramGateway] Could not auto-start trackpad server: {e}")

        async with httpx.AsyncClient(timeout=40.0) as client:
            await self._register_bot_menu(client)
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

_SINGLE_INSTANCE_MUTEX = None

def ensure_single_instance() -> bool:
    """Ensures only one instance of the Telegram Gateway runs on the system to prevent duplicate message responses."""
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform == "win32":
        try:
            import ctypes
            mutex_name = "Global\\JarvisTelegramGatewayMutex"
            handle = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                logger.warning("⚠️ [TelegramGateway] Another instance of Telegram Gateway is already running! Exiting immediately to prevent duplicate messages.")
                return False
            _SINGLE_INSTANCE_MUTEX = handle
            return True
        except Exception as e:
            logger.debug(f"[TelegramGateway] Mutex notice: {e}")
    return True

telegram_gateway = JarvisTelegramGateway()

if __name__ == "__main__":
    if not ensure_single_instance():
        sys.exit(0)
    logger.info("==================================================")
    logger.info("   J.A.R.V.I.S. TELEGRAM MOBILE GATEWAY DAEMON")
    logger.info("   Starting active polling listener...")
    logger.info("==================================================")
    try:
        asyncio.run(telegram_gateway.start())
    except KeyboardInterrupt:
        telegram_gateway.stop()

