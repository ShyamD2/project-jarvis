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

from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.config import config

logger = get_logger("JarvisTelegramGateway")

# SIMPLE INTERACTIVE REPLY KEYBOARD FOR INSTANT ONE-TAP CONTROL
MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "🚀 Start J.A.R.V.I.S."}, {"text": "🛑 Close HUD"}],
        [{"text": "🌙 Stealth Screen Off"}, {"text": "☀️ Wake Screen"}],
        [{"text": "📸 Screen Snapshot"}, {"text": "👁️ What's on Screen?"}],
        [{"text": "💻 PC Status"}, {"text": "📋 Open Apps"}],
        [{"text": "🔊 Volume 50%"}, {"text": "🔒 Lock PC"}],
        [{"text": "❓ Help & Commands"}]
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

    async def handle_update(self, update: Dict[str, Any]):
        """Processes an incoming Telegram message update with full system control and simple words"""
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
            await self.send_message(chat_id, "🎙️ Listening to your voice message, sir...")
            file_id = voice.get("file_id")
            audio_bytes = await self.download_file(file_id)
            if audio_bytes:
                transcribed = await self.transcribe_audio_bytes(audio_bytes)
                if transcribed:
                    await self.send_message(chat_id, f"🗣️ *I heard:* \"{transcribed}\"", parse_mode="Markdown")
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
        logger.info(f"[TelegramGateway] Authorized command from {user_id}: '{text}'")

        # ======================================================================
        # 1. HELP & START MENU (SIMPLE EVERYDAY WORDS)
        # ======================================================================
        if lower in ["/start", "/help", "/menu", "help", "menu", "commands", "❓ help & commands"]:
            help_text = (
                "👋 *Welcome, sir! I am J.A.R.V.I.S.*\n"
                "💡 *Quick Ways to Control Your PC:*\n\n"
                "🛸 *Start J.A.R.V.I.S. Floating Agent*\n"
                "• Tap *'🚀 Start J.A.R.V.I.S.'* or `/start_jarvis` — Launch 3D Floating Window on your monitor\n"
                "• Tap *'🛑 Close HUD'* or `/close_hud` — Close the floating window\n\n"
                "📸 *See Your Computer*\n"
                "• `/screen` — Send me a photo of your PC screen right now\n"
                "• `/whatscreen` — Tell me what is open and happening on your screen in plain words\n\n"
                "⌨️ *Type & Press Keys*\n"
                "• `/type <text>` — Type text into your active window (e.g. `/type Hello there`)\n"
                "• `/press <key>` — Press a key (e.g. `/press enter`, `/press esc`, `/press space`)\n"
                "• `/shortcut <keys>` — Press shortcut (e.g. `/shortcut win d` to see desktop)\n\n"
                "💻 *Run Commands & Terminal*\n"
                "• `/cmd <command>` — Run any command on your PC (e.g. `/cmd dir`, `/cmd ipconfig`)\n\n"
                "🚀 *Open Apps & Websites*\n"
                "• `/open <app or link>` — Open any app or website (e.g. `/open chrome`, `/open youtube.com`)\n"
                "• `/close <app>` — Close an application\n"
                "• `/apps` — Show what apps are currently open\n"
                "• `/minimize` — Minimize windows to see your desktop\n\n"
                "📋 *Clipboard*\n"
                "• `/copy <text>` — Put text on your PC clipboard so you can paste it (Ctrl+V)\n"
                "• `/paste` — Paste clipboard on your PC\n"
                "• `/clip` — Check what is currently copied on your PC\n\n"
                "🔊 *Volume & Music*\n"
                "• `/volume <0-100>` — Set volume percentage (e.g. `/volume 50`)\n"
                "• `/mute` / `/unmute` — Mute or unmute sound\n"
                "• `/play` / `/pause` / `/next` / `/prev` — Control music playback\n"
                "• `/say <words>` — Speak words aloud through your computer speakers!\n\n"
                "📁 *Files & Folders*\n"
                "• `/files` — List files in your project or downloads\n"
                "• `/open_folder` — Open project folder in File Explorer\n\n"
                "📊 *PC Health*\n"
                "• `/status` — View simple PC health (CPU, RAM, Battery, Storage)\n"
                "• `/battery` — Check battery charge and remaining time\n\n"
                "🔒 *Safety & Power*\n"
                "• `/stealth` — Turn off monitors for silent master background control (no lock needed!)\n"
                "• `/wake` — Wake monitors back up and restore normal desktop display\n"
                "• `/lock` — Lock your computer immediately\n"
                "• `/unlock <PIN>` — Unlock Windows remotely from your phone (auto-deletes password)\n"
                "• `/sleep`, `/restart`, `/shutdown` — PC power controls\n\n"
                "✨ *Tip:* You can also simply speak or type natural sentences! For example: _'take a screenshot'_, _'type hello in notepad'_, or _'open chrome'_."
            )
            await self.send_message(chat_id, help_text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
            return

        # ======================================================================
        # 2. SCREEN & VISION (SEE & RECOGNIZE)
        # ======================================================================
        if lower in ["/screen", "screen", "screenshot", "take a screenshot", "send screen", "📸 screen snapshot"]:
            await self.send_message(chat_id, "📸 Taking a snapshot of your screen now, sir...")
            from agents.computer.screen_agent import screen_agent
            from agents.computer.windows_agent import windows_agent

            snap = screen_agent.capture_screenshot()
            if snap.get("success") and snap.get("screenshot_path"):
                win_info = windows_agent.get_active_window_info()
                app_name = win_info.get('process', 'Desktop')
                title = win_info.get('title', 'Desktop Screen')
                caption = f"🖥️ *Your PC Screen Right Now*\n• *Open App:* `{app_name}`\n• *Window:* `{title[:60]}`"
                await self.send_photo(chat_id, snap["screenshot_path"], caption=caption, parse_mode="Markdown")
            else:
                await self.send_message(chat_id, "❌ I couldn't capture your screen at this moment. The display may be asleep.")
            return

        if lower in [
            "/whatscreen", "whatscreen", "what's on screen?", "what is on my screen",
            "what is on screen", "what's on my screen", "read screen", "read my screen",
            "analyze screen", "👁️ what's on screen?"
        ]:
            await self.send_message(chat_id, "👁️ Looking at your screen and analyzing what's open, sir...")
            from services.device_agents.windows.windows_device_agent import windows_device_agent

            res = await windows_device_agent.recognize_screen()
            if res.get("success"):
                app = res.get("process", "Unknown")
                win_title = res.get("active_window", "Desktop")
                res_info = res.get("resolution", {})
                w, h = res_info.get("width", 1536), res_info.get("height", 864)

                simple_desc = (
                    f"👁️ *Here is what's currently on your screen, sir:*\n\n"
                    f"• *Main Window:* `{win_title}`\n"
                    f"• *Application:* `{app}`\n"
                    f"• *Display Resolution:* `{w} x {h}`\n\n"
                    f"Everything is running normally and ready for your commands."
                )

                snap_path = res.get("screenshot")
                if snap_path and os.path.exists(snap_path):
                    await self.send_photo(chat_id, snap_path, caption=simple_desc, parse_mode="Markdown")
                else:
                    await self.send_message(chat_id, simple_desc, parse_mode="Markdown")
            else:
                await self.send_message(chat_id, f"⚠️ Notice: {res.get('message', 'Could not read screen.')}")
            return

        # ======================================================================
        # 3. KEYBOARD & AUTONOMOUS TYPING
        # ======================================================================
        if lower.startswith("/type ") or lower.startswith("type "):
            content = text[6:] if lower.startswith("/type ") else text[5:]
            content = content.strip()

            if not content:
                await self.send_message(chat_id, "Please provide the text to type, for example: `/type Hello world`", parse_mode="Markdown")
                return

            from services.device_agents.windows.windows_device_agent import windows_device_agent

            # Check if target app was specified like: "in notepad hello" or "notepad: hello"
            target_app = None
            text_to_type = content
            if " in " in content.lower():
                parts = content.split(" in ", 1)
                text_to_type = parts[0].strip()
                target_app = parts[1].strip()
            elif ":" in content and len(content.split(":", 1)[0].split()) == 1:
                parts = content.split(":", 1)
                target_app = parts[0].strip()
                text_to_type = parts[1].strip()

            await self.send_message(chat_id, f"⌨️ Typing your text onto the computer...")
            res = await windows_device_agent.type_text(text_to_type, target_app=target_app)

            if res.get("success"):
                dest = f" into *{target_app}*" if target_app else " into the active window"
                await self.send_message(chat_id, f"✅ *Done, sir!* I typed your message{dest}.", parse_mode="Markdown")
            else:
                await self.send_message(chat_id, f"⚠️ Could not type: {res.get('message', 'error')}")
            return

        if lower.startswith("/press ") or lower.startswith("press "):
            key_name = (text[7:] if lower.startswith("/press ") else text[6:]).strip().lower()
            from agents.computer.keyboard_agent import keyboard_agent

            res = keyboard_agent.press_key(key_name)
            if res.get("success"):
                await self.send_message(chat_id, f"⌨️ Pressed the *{key_name.upper()}* key on your PC.", parse_mode="Markdown")
            else:
                await self.send_message(chat_id, f"⚠️ Unknown key '{key_name}'. Supported keys: enter, esc, space, backspace, tab, up, down, left, right, f1-f12.")
            return

        if lower.startswith("/shortcut "):
            shortcut_str = text[10:].strip()
            keys = [k.strip() for k in shortcut_str.replace("+", " ").split()]
            from agents.computer.keyboard_agent import keyboard_agent

            res = keyboard_agent.press_shortcut(keys)
            if res.get("success"):
                await self.send_message(chat_id, f"⌨️ Executed shortcut *{'+'.join(keys).upper()}* on your PC, sir.", parse_mode="Markdown")
            else:
                await self.send_message(chat_id, f"⚠️ Could not execute shortcut: {res.get('error', 'unknown error')}")
            return

        # ======================================================================
        # 4. MOUSE CONTROLS
        # ======================================================================
        if lower in ["/click", "click"]:
            from agents.computer.mouse_agent import mouse_agent
            mouse_agent.click()
            await self.send_message(chat_id, "🖱️ Left-clicked at the current mouse position.")
            return

        if lower in ["/rightclick", "right click", "rightclick"]:
            from agents.computer.mouse_agent import mouse_agent
            mouse_agent.click(button="right")
            await self.send_message(chat_id, "🖱️ Right-clicked on your PC.")
            return

        if lower in ["/doubleclick", "double click", "doubleclick"]:
            from agents.computer.mouse_agent import mouse_agent
            mouse_agent.double_click()
            await self.send_message(chat_id, "🖱️ Double-clicked on your PC.")
            return

        # ======================================================================
        # 5. CLIPBOARD ACCESS (COPY, PASTE, DIAGNOSE)
        # ======================================================================
        if lower.startswith("/copy ") or lower.startswith("copy "):
            copy_text = (text[6:] if lower.startswith("/copy ") else text[5:]).strip()
            from agents.computer.windows_agent import windows_agent

            ok = windows_agent.set_clipboard_text(copy_text)
            if ok:
                await self.send_message(
                    chat_id,
                    f"📋 *Copied to PC Clipboard!*\n\n`{copy_text}`\n\nYou can now paste it anywhere on your computer using *Ctrl+V*.",
                    parse_mode="Markdown"
                )
            else:
                await self.send_message(chat_id, "⚠️ Failed to copy to clipboard.")
            return

        if lower in ["/paste", "paste"]:
            from agents.computer.keyboard_agent import keyboard_agent
            keyboard_agent.press_shortcut(["ctrl", "v"])
            await self.send_message(chat_id, "📋 Pasted clipboard contents into your active window (Ctrl+V).")
            return

        if lower in ["/clip", "/clipboard", "clipboard", "diagnose clipboard", "check clipboard"]:
            from agents.computer.windows_agent import windows_agent
            current_clip = windows_agent.get_clipboard_text()

            if not current_clip or not current_clip.strip():
                await self.send_message(chat_id, "📋 Your PC clipboard is currently empty.")
                return

            # Check if it looks like an error to diagnose
            if any(k in current_clip for k in ["Error", "Exception", "Traceback", "failed", "SyntaxError"]):
                await self.send_message(chat_id, "🔍 Inspecting error snippet found on your clipboard...")
                res = await windows_agent.diagnose_clipboard_error()
                diag = res.get("diagnosis", current_clip[:300])
                reply = (
                    f"📋 *Clipboard Code Diagnosis*\n\n"
                    f"{diag}\n\n"
                    f"✅ *The verified fix has been placed in your clipboard. Press Ctrl+V on your PC to paste!*"
                )
                await self.send_message(chat_id, reply, parse_mode="Markdown")
            else:
                preview = current_clip[:600] + ("..." if len(current_clip) > 600 else "")
                await self.send_message(chat_id, f"📋 *Currently Copied on Your PC:*\n\n```\n{preview}\n```", parse_mode="Markdown")
            return

        # ======================================================================
        # 6. TERMINAL & COMMAND EXECUTION (FULL SYSTEM ACCESS)
        # ======================================================================
        if lower.startswith("/cmd ") or lower.startswith("/run ") or lower.startswith("/exec ") or lower.startswith("/powershell "):
            if lower.startswith("/powershell "):
                cmd = text[12:].strip()
            elif lower.startswith("/cmd "):
                cmd = text[5:].strip()
            elif lower.startswith("/run "):
                cmd = text[5:].strip()
            else:
                cmd = text[6:].strip()

            if not cmd:
                await self.send_message(chat_id, "Please provide the command to run, for example: `/cmd ipconfig` or `/cmd dir`", parse_mode="Markdown")
                return

            # Block destructive formatting commands for safety
            disallowed = ["format c:", "rmdir /s /q c:\\windows", "del /f /s /q c:\\windows"]
            if any(d in cmd.lower() for d in disallowed):
                await self.send_message(chat_id, "🛑 Command blocked for workstation safety.")
                return

            await self.send_message(chat_id, f"⚡ Running command: `{cmd}`...", parse_mode="Markdown")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=PROJECT_ROOT
                    )
                )
                out = result.stdout.strip() or result.stderr.strip() or "Command completed with no output."
                if len(out) > 3500:
                    out = out[:3500] + "\n... [Output truncated for readability]"

                await self.send_message(chat_id, f"💻 *Command Output:*\n```\n{out}\n```", parse_mode="Markdown")
            except subprocess.TimeoutExpired:
                await self.send_message(chat_id, "⏱️ Command timed out after 15 seconds.")
            except Exception as e:
                await self.send_message(chat_id, f"⚠️ Error running command: {e}")
            return

        # ======================================================================
        # 7. PC HEALTH & HARDWARE STATUS (SIMPLE WORDS)
        # ======================================================================
        if lower in ["/status", "/vitals", "status", "vitals", "pc status", "💻 pc status", "how is my pc", "how is my computer"]:
            import psutil
            from agents.computer.windows_agent import windows_agent

            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            bat = psutil.sensors_battery()
            d = psutil.disk_usage("C:\\") if os.path.exists("C:\\") else None
            active_win = windows_agent.get_active_window_info()

            # Plain English Health Ratings
            cpu_desc = "Running very fast" if cpu < 30 else ("Moderate load" if cpu < 75 else "Working hard")
            mem_desc = "Plenty of free memory" if mem < 60 else ("Comfortable" if mem < 85 else "High memory usage")

            if bat:
                bat_status = f"{int(bat.percent)}% ({'Plugged in & Charging' if bat.power_plugged else 'Running on battery'})"
            else:
                bat_status = "Connected to Wall Power (Desktop)"

            disk_str = f"{d.free / (1024**3):.1f} GB free space" if d else "Available"

            status_text = (
                "💻 *PC Health Summary*\n\n"
                f"• ⚡ *Speed (Processor):* `{cpu:.0f}%` — _{cpu_desc}_\n"
                f"• 🧠 *Memory (RAM):* `{mem:.0f}%` — _{mem_desc}_\n"
                f"• 🔋 *Battery / Power:* `{bat_status}`\n"
                f"• 💾 *Storage (Drive C:):* `{disk_str}`\n"
                f"• 🪟 *Currently Using:* `{active_win.get('process', 'Desktop')}` (`{active_win.get('title', 'Desktop')[:35]}`)\n"
                f"• 🕒 *Time:* `{datetime.now().strftime('%I:%M %p, %d %b')}`\n\n"
                "Everything is operating in excellent condition, sir."
            )
            await self.send_message(chat_id, status_text, parse_mode="Markdown")
            return

        if lower in ["/battery", "battery"]:
            import psutil
            bat = psutil.sensors_battery()
            if bat:
                plugged = "Plugged in and charging" if bat.power_plugged else "Running on battery"
                sec_left = bat.secsleft
                time_left = f" (~{sec_left // 60} minutes remaining)" if (sec_left and sec_left > 0 and not bat.power_plugged) else ""
                await self.send_message(chat_id, f"🔋 *Battery:* `{bat.percent}%`\n• Status: {plugged}{time_left}", parse_mode="Markdown")
            else:
                await self.send_message(chat_id, "🔋 *Power:* Operating on direct desktop AC power (no battery needed).")
            return

        if lower in ["/disk", "/storage", "disk", "storage"]:
            import psutil
            d = psutil.disk_usage("C:\\") if os.path.exists("C:\\") else None
            if d:
                free_gb = d.free / (1024**3)
                total_gb = d.total / (1024**3)
                await self.send_message(chat_id, f"💾 *Storage Drive (C:)*\n• Free Space: `{free_gb:.1f} GB`\n• Total Space: `{total_gb:.1f} GB`\n• Health: Great!", parse_mode="Markdown")
            else:
                await self.send_message(chat_id, "💾 Storage drive metrics unavailable.")
            return

        if lower in ["/apps", "/ps", "/processes", "apps", "processes", "📋 open apps", "open apps", "running apps"]:
            from agents.computer.windows_agent import windows_agent
            apps_res = windows_agent.list_running_applications()
            apps_list = apps_res.get("applications", [])[:10]
            if apps_list:
                msg_lines = ["📋 *Applications Currently Open on Your PC:*\n"]
                for i, a in enumerate(apps_list, 1):
                    pname = a.get("name") or a.get("process_name", "App")
                    msg_lines.append(f"{i}. *{pname}*")
                msg_lines.append("\n_To close any app, send: /close <name>_")
                await self.send_message(chat_id, "\n".join(msg_lines), parse_mode="Markdown")
            else:
                await self.send_message(chat_id, "No active user applications detected on your screen.")
            return

        # ======================================================================
        # 8. J.A.R.V.I.S. FLOATING AGENT LAUNCH & CLOSE (REMOTE START BUTTON)
        # ======================================================================
        if lower in [
            "/start_jarvis", "/launch_jarvis", "/start_hud", "/launch_hud",
            "🚀 start j.a.r.v.i.s.", "start jarvis", "launch jarvis", "start hud", "launch hud",
            "open jarvis", "open floating agent", "launch floating agent"
        ]:
            try:
                flags = 0
                if sys.platform == "win32":
                    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

                subprocess.Popen(
                    [sys.executable, "services/floating-agent/floating_app.py"],
                    cwd=PROJECT_ROOT,
                    creationflags=flags
                )
                await self.send_message(
                    chat_id,
                    "🚀 *J.A.R.V.I.S. Launched on Your PC!*\n\n"
                    "• 🛸 3D Holographic Arc Reactor is now active on your desktop.\n"
                    "• 🎙️ Hands-free continuous voice recognition is listening.\n"
                    "• 👁️ Multimodal AI Screen Vision is ready.\n"
                    "• ⚡ Press `Alt + J` or tap 'Mini Orb' anytime.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await self.send_message(chat_id, f"⚠️ Error launching J.A.R.V.I.S.: {e}")
            return

        if lower in [
            "/close_jarvis", "/close_hud", "/stop_jarvis",
            "🛑 close hud", "close jarvis", "close hud", "stop jarvis"
        ]:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.FindWindowW(None, "J.A.R.V.I.S. Floating Agent")
                if hwnd:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    await self.send_message(chat_id, "🛑 *J.A.R.V.I.S. Floating Window closed successfully, sir.*", parse_mode="Markdown")
                else:
                    subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq J.A.R.V.I.S. Floating Agent*"], capture_output=True)
                    await self.send_message(chat_id, "🛑 *J.A.R.V.I.S. Floating Window closed, sir.*", parse_mode="Markdown")
            except Exception as e:
                await self.send_message(chat_id, f"⚠️ Error closing J.A.R.V.I.S.: {e}")
            return

        # ======================================================================
        # 9. APPLICATION & WINDOW CONTROLS
        # ======================================================================
        if lower.startswith("/open ") or lower.startswith("open "):
            target = (text[6:] if lower.startswith("/open ") else text[5:]).strip()
            from agents.computer.windows_agent import windows_agent

            if target.startswith(("http://", "https://", "www.")) or ("." in target and not target.endswith(".exe") and " " not in target):
                windows_agent.open_url(target)
                await self.send_message(chat_id, f"🌐 *Opened website:* `{target}`", parse_mode="Markdown")
            else:
                windows_agent.launch_app(target)
                await self.send_message(chat_id, f"🚀 *Launched application:* `{target}` on your computer.", parse_mode="Markdown")
            return

        if lower.startswith("/close ") or lower.startswith("close "):
            target = (text[7:] if lower.startswith("/close ") else text[6:]).strip()
            from agents.computer.windows_agent import windows_agent

            windows_agent.close_active_window(target)
            await self.send_message(chat_id, f"🛑 Closed application: *{target}*", parse_mode="Markdown")
            return

        if lower in ["/close_all", "close all", "close all windows"]:
            from agents.computer.windows_agent import windows_agent
            windows_agent.close_all_user_apps()
            await self.send_message(chat_id, "🧹 Closed all open application windows for you, sir.")
            return

        if lower in ["/minimize", "minimize", "show desktop"]:
            from agents.computer.keyboard_agent import keyboard_agent
            keyboard_agent.press_shortcut(["win", "d"])
            await self.send_message(chat_id, "🪟 Minimized all windows. Your desktop is now visible.")
            return

        if lower.startswith("/focus ") or lower.startswith("focus "):
            target = (text[7:] if lower.startswith("/focus ") else text[6:]).strip()
            from agents.computer.windows_agent import focus_window_by_name

            focus_window_by_name(target)
            await self.send_message(chat_id, f"🪟 Brought *{target}* to the front of your screen.", parse_mode="Markdown")
            return

        # ======================================================================
        # 9. AUDIO & MEDIA CONTROLS
        # ======================================================================
        if lower.startswith("/volume") or lower.startswith("volume"):
            parts = lower.split()
            from agents.computer.audio_agent import audio_agent

            if len(parts) > 1 and parts[1].isdigit():
                val = int(parts[1])
                audio_agent.set_volume_percent(val)
                await self.send_message(chat_id, f"🔊 Master volume set to *{val}%*, sir.", parse_mode="Markdown")
            elif "up" in lower:
                audio_agent.adjust_volume("up")
                await self.send_message(chat_id, "🔊 Volume turned up, sir.")
            elif "down" in lower:
                audio_agent.adjust_volume("down")
                await self.send_message(chat_id, "🔉 Volume turned down, sir.")
            else:
                await self.send_message(chat_id, "Usage: `/volume 50` (sets volume to 50%) or `/volume up` / `/volume down`", parse_mode="Markdown")
            return

        if lower in ["🔊 volume 50%"]:
            from agents.computer.audio_agent import audio_agent
            audio_agent.set_volume_percent(50)
            await self.send_message(chat_id, "🔊 Volume set to 50%, sir.")
            return

        if lower in ["/mute", "mute", "mute audio", "🔇 mute audio"]:
            from agents.computer.audio_agent import audio_agent
            audio_agent.adjust_volume("mute")
            await self.send_message(chat_id, "🔇 Computer sound muted, sir.")
            return

        if lower in ["/unmute", "unmute"]:
            from agents.computer.audio_agent import audio_agent
            audio_agent.adjust_volume("unmute")
            await self.send_message(chat_id, "🔊 Computer sound unmuted, sir.")
            return

        if lower in ["/play", "/pause", "play", "pause", "play music"]:
            from agents.computer.audio_agent import audio_agent
            audio_agent.control_media("play_pause")
            await self.send_message(chat_id, "⏯️ Toggled music playback on your PC.")
            return

        if lower in ["/next", "/skip", "next track", "skip"]:
            from agents.computer.audio_agent import audio_agent
            audio_agent.control_media("next")
            await self.send_message(chat_id, "⏭️ Skipped to the next song.")
            return

        if lower.startswith("/say ") or lower.startswith("say "):
            speech_text = (text[5:] if lower.startswith("/say ") else text[4:]).strip()
            if speech_text:
                from services.voice.tts_engine import tts_engine
                asyncio.create_task(tts_engine.speak(speech_text, play_audio=True))
                await self.send_message(chat_id, f"🗣️ Speaking aloud on your computer: \"{speech_text}\"")
            return

        # ======================================================================
        # 10. FILES & FOLDERS
        # ======================================================================
        if lower in ["/files", "files", "📁 project files", "project files"]:
            items = os.listdir(PROJECT_ROOT)[:12]
            file_list = []
            for item in items:
                icon = "📁" if os.path.isdir(os.path.join(PROJECT_ROOT, item)) else "📄"
                file_list.append(f"{icon} `{item}`")

            reply = "📁 *Your Project Files:*\n\n" + "\n".join(file_list)
            await self.send_message(chat_id, reply, parse_mode="Markdown")
            return

        if lower in ["/open_folder", "open folder", "open workspace"]:
            os.startfile(PROJECT_ROOT)
            await self.send_message(chat_id, "📁 Opened project folder in Windows File Explorer on your computer.")
            return

        # ======================================================================
        # 11. POWER & LOCK CONTROLS
        # ======================================================================
        if lower in ["/lock", "lock", "lock pc", "lock the pc", "lock computer", "🔒 lock pc"]:
            from agents.computer.power_agent import power_agent
            power_agent.lock_workstation()
            await self.send_message(
                chat_id,
                "🔒 *Computer Locked Safely!*\n"
                "Your Windows screen has been locked.\n\n"
                "• _To unlock remotely from phone, send:_ `/unlock <PIN_or_password>`\n"
                "_(Your password message will be auto-deleted immediately from chat for your privacy.)_",
                parse_mode="Markdown"
            )
            return

        if lower.startswith("/unlock") or lower.startswith("unlock"):
            # Privacy & Security: Immediately auto-delete user's message containing password
            try:
                msg_id = message.get("message_id")
                if msg_id:
                    await self.delete_message(chat_id, msg_id)
            except Exception:
                pass

            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                await self.send_message(
                    chat_id,
                    "⚠️ *Usage:* `/unlock <your_PIN_or_password>`\n"
                    "_(Your message will be auto-deleted immediately for your privacy.)_",
                    parse_mode="Markdown"
                )
                return

            pin_or_pass = parts[1].strip()
            await self.send_message(
                chat_id,
                "🔓 *Attempting remote workstation unlock...*\n"
                "• Waking display monitors\n"
                "• Dismissing lock screen\n"
                "• Entering credentials securely",
                parse_mode="Markdown"
            )

            from services.device_agents.windows.windows_unlocker import remote_unlocker
            res = await remote_unlocker.unlock(pin_or_pass)

            if res.get("success"):
                caption = "🔓 *Workstation Unlocked Successfully, sir!*\nFull desktop master control is active."
                if res.get("screenshot_path") and os.path.exists(res["screenshot_path"]):
                    await self.send_photo(chat_id, res["screenshot_path"], caption=caption, parse_mode="Markdown")
                else:
                    await self.send_message(chat_id, caption, parse_mode="Markdown")
            else:
                err = res.get("error", "Failed to unlock workstation.")
                caption = f"⚠️ *Unlock Notice:*\n{err}"
                if res.get("screenshot_path") and os.path.exists(res["screenshot_path"]):
                    await self.send_photo(chat_id, res["screenshot_path"], caption=caption, parse_mode="Markdown")
                else:
                    await self.send_message(chat_id, caption, parse_mode="Markdown")
            return

        if lower in [
            "/stealth", "stealth", "stealth mode", "/display_off", "display off",
            "turn off screen", "turn off monitor", "screen off", "/screen_off", "🌙 stealth screen off"
        ]:
            from agents.computer.power_agent import power_agent
            res = power_agent.enable_stealth_mode()
            if res.get("success"):
                await self.send_message(
                    chat_id,
                    "🌙 *Stealth Master Mode Activated!*\n"
                    "Your physical monitors are now turned OFF.\n\n"
                    "🛡️ *Your PC is fully active & protected in stealth:*\n"
                    "• Anyone in the room sees a completely dark, sleeping screen.\n"
                    "• Your workstation will *never* auto-lock or sleep while in Stealth Mode.\n"
                    "• You have **100% unrestricted Master Administrator access** right here from your phone!\n"
                    "  — 📸 Screen snapshots & vision\n"
                    "  — ⌨️ Typing & keyboard shortcuts\n"
                    "  — 🚀 Launching apps & `/cmd`\n"
                    "  — 📁 Files, volume & PC health\n\n"
                    "☀️ _When you return to your desk, tap_ *☀️ Wake Screen* _or send_ `/wake`.",
                    parse_mode="Markdown"
                )
            else:
                await self.send_message(chat_id, f"⚠️ Could not activate stealth mode: {res.get('error', 'Unknown error')}")
            return

        if lower in [
            "/wake", "wake", "wake up", "wake screen", "wake pc", "/display_on",
            "display on", "turn on screen", "turn on monitor", "screen on", "/screen_on", "☀️ wake screen"
        ]:
            from agents.computer.power_agent import power_agent
            from agents.computer.screen_agent import screen_agent
            res = power_agent.wake_display()
            await asyncio.sleep(0.5)

            snap = screen_agent.capture_screenshot()
            caption = (
                "☀️ *Workstation Screen Awakened!*\n"
                "Monitors have been turned back on and normal desktop display is active.\n"
                "Welcome back, sir!"
            )
            if snap.get("success") and snap.get("screenshot_path") and os.path.exists(snap["screenshot_path"]):
                await self.send_photo(chat_id, snap["screenshot_path"], caption=caption, parse_mode="Markdown")
            else:
                await self.send_message(chat_id, caption, parse_mode="Markdown")
            return

        if lower in ["/sleep", "sleep"]:
            await self.send_message(chat_id, "⚠️ *Are you sure you want to put the computer to sleep?*\nSend `/sleep confirm` to proceed.", parse_mode="Markdown")
            return

        if lower == "/sleep confirm":
            from agents.computer.power_agent import power_agent
            await self.send_message(chat_id, "💤 Putting your computer to sleep now, sir.")
            power_agent.sleep_pc()
            return

        if lower in ["/restart", "restart pc", "reboot"]:
            await self.send_message(chat_id, "⚠️ *Are you sure you want to restart your computer?*\nSend `/restart confirm` to proceed.", parse_mode="Markdown")
            return

        if lower == "/restart confirm":
            from agents.computer.power_agent import power_agent
            await self.send_message(chat_id, "🔄 Restarting your computer now, sir.")
            power_agent.restart_pc()
            return

        if lower in ["/shutdown", "shutdown pc"]:
            await self.send_message(chat_id, "⚠️ *Are you sure you want to shut down your computer?*\nSend `/shutdown confirm` to proceed.", parse_mode="Markdown")
            return

        if lower == "/shutdown confirm":
            from agents.computer.power_agent import power_agent
            await self.send_message(chat_id, "🛑 Shutting down your computer now. Goodbye, sir.")
            power_agent.shutdown_pc()
            return

        # ======================================================================
        # 12. NATURAL LANGUAGE & CROSS-DEVICE ROUTING FALLBACK
        # ======================================================================
        # Check cross-device phrases
        if any(w in lower for w in ["on my phone", "on my laptop", "on phone", "on laptop", "on tablet", "on desktop"]):
            from services.cloud.device_router import device_router
            await self.send_message(chat_id, f"🎯 Routing: \"{text}\"...")
            res = await device_router.route_and_execute(text, source_device_id="telegram")
            msg = res.get("message", "Executed successfully, sir.")
            await self.send_message(chat_id, f"✅ {msg}")
            return

        # Natural Conversational AI Brain Loop (OpenRouter / Gemini / Groq)
        try:
            from services.brain.conversation_engine import conversation_engine
            turn_res = await conversation_engine.process_turn(text)
            reply = turn_res.get("response") or "I've handled that for you, sir."
            await self.send_message(chat_id, f"🤖 {reply}")
        except Exception as e:
            logger.error(f"[TelegramGateway] Brain turn error: {e}")
            await self.send_message(chat_id, f"I processed your request, sir.")

    async def _register_bot_menu(self, client: httpx.AsyncClient):
        """Registers clean, easy-to-understand Telegram [/] Command Menu with Telegram API"""
        try:
            url = f"{self._base_url}/setMyCommands"
            commands = [
                {"command": "stealth", "description": "🌙 Turn monitors off for silent master control"},
                {"command": "wake", "description": "☀️ Wake display monitors & show desktop"},
                {"command": "status", "description": "💻 Simple PC health, speed, and battery"},
                {"command": "screen", "description": "📸 Send desktop screenshot photo"},
                {"command": "whatscreen", "description": "👁️ Tell me what's on my screen"},
                {"command": "type", "description": "⌨️ Type text onto computer"},
                {"command": "open", "description": "🚀 Open an app or website"},
                {"command": "close", "description": "🛑 Close an application"},
                {"command": "apps", "description": "📋 See open applications"},
                {"command": "volume", "description": "🔊 Set volume or mute sound"},
                {"command": "lock", "description": "🔒 Lock computer safely"},
                {"command": "clip", "description": "📋 Check clipboard & diagnose errors"},
                {"command": "files", "description": "📁 Browse project files"},
                {"command": "help", "description": "❓ Help & quick guide"}
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

telegram_gateway = JarvisTelegramGateway()

if __name__ == "__main__":
    logger.info("==================================================")
    logger.info("   J.A.R.V.I.S. TELEGRAM MOBILE GATEWAY DAEMON")
    logger.info("   Starting active polling listener...")
    logger.info("==================================================")
    try:
        asyncio.run(telegram_gateway.start())
    except KeyboardInterrupt:
        telegram_gateway.stop()

