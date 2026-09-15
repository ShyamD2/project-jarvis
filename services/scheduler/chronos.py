"""
Chronos Autonomous Scheduler & Persistent Reminder Engine for Project J.A.R.V.I.S.
Provides persistent timers, reminders, and recurring routine schedules that survive reboots.
Dispatches proactive vocal neural TTS, Telegram alerts, and Windows toast notifications.
"""

from __future__ import annotations
import os
import sys
import time
import json
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisChronosScheduler")

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TASKS_FILE = os.path.join(DATA_DIR, "chronos_tasks.json")


class ChronosScheduler:
    def __init__(self, tasks_file: str = TASKS_FILE):
        self.tasks_file = tasks_file
        self.tasks: List[Dict[str, Any]] = []
        self._running = False
        self._load_tasks()

    def _load_tasks(self):
        """Loads persistent schedules from disk"""
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
                logger.info(f"⏰ [Chronos] Loaded {len(self.tasks)} persistent tasks from disk.")
            except Exception as e:
                logger.warning(f"[Chronos] Failed to load tasks from {self.tasks_file}: {e}")
                self.tasks = []
        else:
            self.tasks = []

    def _save_tasks(self):
        """Saves active schedules to disk"""
        try:
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2)
        except Exception as e:
            logger.error(f"[Chronos] Failed to persist tasks to {self.tasks_file}: {e}")

    def _show_windows_toast(self, title: str, message: str):
        """Displays native Windows toast notification"""
        try:
            safe_title = str(title).replace("'", "''")
            safe_message = str(message).replace("'", "''")
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) > $null
            $textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_message}')) > $null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Project J.A.R.V.I.S.").Show($toast)
            """
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"[Chronos] Windows toast notification notice: {e}")

    def add_timer(self, seconds: int, message: str, action: Optional[str] = None) -> Dict[str, Any]:
        """Creates a one-off persistent timer"""
        now = time.time()
        trigger_time = now + max(1, seconds)
        task_id = f"timer_{int(now * 1000) % 1000000}"

        task = {
            "id": task_id,
            "type": "timer",
            "message": message,
            "duration_seconds": seconds,
            "trigger_time": trigger_time,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_time_str": datetime.fromtimestamp(trigger_time).strftime("%I:%M:%S %p"),
            "action": action
        }
        self.tasks.append(task)
        self._save_tasks()
        logger.info(f"⏰ [Chronos] Added timer '{message}' for {seconds}s (fires at {task['target_time_str']})")
        return {
            "success": True,
            "task_id": task_id,
            "message": message,
            "fires_in_seconds": seconds,
            "target_time": task["target_time_str"]
        }

    def add_recurring(self, interval_seconds: int, message: str, action: Optional[str] = None) -> Dict[str, Any]:
        """Creates a recurring routine timer (e.g. hourly water reminder, daily briefing)"""
        now = time.time()
        trigger_time = now + max(5, interval_seconds)
        task_id = f"routine_{int(now * 1000) % 1000000}"

        task = {
            "id": task_id,
            "type": "recurring",
            "message": message,
            "interval_seconds": interval_seconds,
            "trigger_time": trigger_time,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_time_str": datetime.fromtimestamp(trigger_time).strftime("%I:%M:%S %p"),
            "action": action
        }
        self.tasks.append(task)
        self._save_tasks()
        logger.info(f"⏰ [Chronos] Added recurring routine '{message}' every {interval_seconds}s")
        return {
            "success": True,
            "task_id": task_id,
            "message": message,
            "interval_seconds": interval_seconds,
            "next_fire": task["target_time_str"]
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancels an active timer or routine"""
        initial_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        if len(self.tasks) < initial_count:
            self._save_tasks()
            logger.info(f"⏰ [Chronos] Canceled task: {task_id}")
            return True
        return False

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """Lists active timers and routines with remaining seconds"""
        now = time.time()
        results = []
        for t in self.tasks:
            rem = max(0, int(t.get("trigger_time", 0) - now))
            results.append({
                "id": t.get("id"),
                "type": t.get("type"),
                "message": t.get("message"),
                "remaining_seconds": rem,
                "target_time": t.get("target_time_str"),
                "action": t.get("action")
            })
        return results

    async def _dispatch_task(self, task: Dict[str, Any]):
        """Dispatches vocal audio, Telegram notification, and Windows toast"""
        msg = task.get("message", "Timer completed.")
        logger.info(f"🔔 [Chronos Triggered] {task.get('id')}: {msg}")

        # 1. Native Windows Toast
        self._show_windows_toast("J.A.R.V.I.S. Reminder", msg)

        # 2. Spoken Voice Output via TTS
        try:
            from services.sensory.voice_synthesizer import voice_synthesizer
            await voice_synthesizer.speak(f"Pardon the interruption, sir. Chronos reminder: {msg}", play_audio=True)
        except Exception as e:
            logger.debug(f"[Chronos] Voice notification skip: {e}")

        # 3. Telegram Notification Push
        try:
            from services.gateway.telegram_bot import telegram_gateway
            if telegram_gateway.is_configured:
                await telegram_gateway.broadcast_to_authorized(
                    f"⏰ <b>Chronos Reminder</b>\n\n{msg}\n\n<i>Scheduled Alert</i>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.debug(f"[Chronos] Telegram notification skip: {e}")

        # 4. Optional Workflow Action Execution
        action = task.get("action")
        if action:
            try:
                if action.startswith("workflow:"):
                    wf_name = action.split(":", 1)[1]
                    from agents.intelligence.planner import planner
                    logger.info(f"⚡ [Chronos] Executing scheduled workflow: {wf_name}")
                    planner.execute_workflow(wf_name)
            except Exception as e:
                logger.error(f"[Chronos] Failed to execute action '{action}': {e}")

    async def start(self):
        """Continuous background tick loop checking for scheduled tasks"""
        self._running = True
        logger.info("⏰ [Chronos] Autonomous Scheduler daemon online and ticking.")

        while self._running:
            try:
                now = time.time()
                ready_tasks = []
                remaining_tasks = []

                for t in self.tasks:
                    if now >= t.get("trigger_time", 0):
                        ready_tasks.append(t)
                    else:
                        remaining_tasks.append(t)

                for t in ready_tasks:
                    await self._dispatch_task(t)
                    # If recurring, calculate next schedule
                    if t.get("type") == "recurring":
                        interval = t.get("interval_seconds", 3600)
                        t["trigger_time"] = now + interval
                        t["target_time_str"] = datetime.fromtimestamp(t["trigger_time"]).strftime("%I:%M:%S %p")
                        remaining_tasks.append(t)

                if len(ready_tasks) > 0:
                    self.tasks = remaining_tasks
                    self._save_tasks()

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Chronos] Scheduler tick loop error: {e}")
                await asyncio.sleep(2.0)

    def stop(self):
        self._running = False
        logger.info("⏰ [Chronos] Scheduler daemon halted.")


chronos = ChronosScheduler()
