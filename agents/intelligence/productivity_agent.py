"""
J.A.R.V.I.S. Productivity Agent (Intelligence Pillar).
Consolidates Domains 11 & 12: Reminders, Timers, Toast Notifications, Notes, and Tasks.
"""

import os
import json
import time
import threading
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisProductivityAgent")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")


class ProductivityAgent:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._reminders: List[Dict[str, Any]] = []

    def _show_windows_toast(self, title: str, message: str):
        """Displays native Windows 10/11 toast notification"""
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
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script])
        except Exception as e:
            logger.warning(f"Toast notification failed: {e}")

    def create_reminder(self, message: str, delay_seconds: int = 60) -> Dict[str, Any]:
        """Schedules a persistent reminder timer via Chronos Autonomous Scheduler"""
        try:
            from services.scheduler.chronos import chronos
            res = chronos.add_timer(seconds=delay_seconds, message=message)
            return {
                "success": True,
                "reminder_id": res["task_id"],
                "message": message,
                "delay_seconds": delay_seconds,
                "scheduled_time": res["target_time"]
            }
        except Exception as e:
            logger.warning(f"[ProductivityAgent] Falling back to local thread reminder: {e}")

        rem_id = f"rem_{len(self._reminders) + 1}"
        rem = {
            "id": rem_id,
            "message": message,
            "delay_seconds": delay_seconds,
            "target_time": time.time() + delay_seconds,
            "created_at": datetime.now().strftime("%I:%M %p")
        }
        self._reminders.append(rem)
        logger.info(f"[ProductivityAgent] Reminder set: '{message}' in {delay_seconds}s")

        def _reminder_worker():
            time.sleep(delay_seconds)
            logger.info(f"🔔 [REMINDER TRIGGERED] {message}")
            self._show_windows_toast("J.A.R.V.I.S. Reminder", message)

        t = threading.Thread(target=_reminder_worker, daemon=True, name=f"Reminder_{rem_id}")
        t.start()

        return {
            "success": True,
            "reminder_id": rem_id,
            "message": message,
            "delay_seconds": delay_seconds,
            "scheduled_time": datetime.fromtimestamp(rem["target_time"]).strftime("%I:%M %p")
        }

    def save_note(self, title: str, content: str) -> Dict[str, Any]:
        """Saves a quick note to persistent storage"""
        notes = self._load_json(NOTES_FILE, default=[])
        note = {
            "id": f"note_{len(notes) + 1}",
            "title": title,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p")
        }
        notes.append(note)
        self._save_json(NOTES_FILE, notes)
        logger.info(f"[ProductivityAgent] Saved note '{title}'")
        return {"success": True, "note": note}

    def read_notes(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        """Reads saved notes, optionally filtering by keyword"""
        notes = self._load_json(NOTES_FILE, default=[])
        if keyword:
            k = keyword.lower()
            filtered = [n for n in notes if k in n.get("title", "").lower() or k in n.get("content", "").lower()]
            return {"success": True, "count": len(filtered), "notes": filtered}
        return {"success": True, "count": len(notes), "notes": notes[-10:]}

    def add_task(self, task_text: str) -> Dict[str, Any]:
        """Adds a task to the checklist"""
        tasks = self._load_json(TASKS_FILE, default=[])
        task = {
            "id": len(tasks) + 1,
            "task": task_text,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %I:%M %p")
        }
        tasks.append(task)
        self._save_json(TASKS_FILE, tasks)
        logger.info(f"[ProductivityAgent] Added task: '{task_text}'")
        return {"success": True, "task": task}

    def list_tasks(self, include_completed: bool = False) -> Dict[str, Any]:
        """Lists active tasks"""
        tasks = self._load_json(TASKS_FILE, default=[])
        if not include_completed:
            tasks = [t for t in tasks if not t.get("completed", False)]
        return {"success": True, "count": len(tasks), "tasks": tasks}

    def complete_task(self, task_id: int) -> Dict[str, Any]:
        """Marks a task as completed"""
        tasks = self._load_json(TASKS_FILE, default=[])
        found = False
        for t in tasks:
            if t.get("id") == task_id:
                t["completed"] = True
                t["completed_at"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                found = True
                break
        if found:
            self._save_json(TASKS_FILE, tasks)
            return {"success": True, "task_id": task_id, "status": "completed"}
        return {"success": False, "error": f"Task id {task_id} not found"}

    def _load_json(self, path: str, default: Any) -> Any:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: str, data: Any):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save JSON to {path}: {e}")


productivity_agent = ProductivityAgent()
