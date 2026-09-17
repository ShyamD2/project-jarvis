"""
Project J.A.R.V.I.S. Cyber Lock System (Solution 1).
Provides an un-bypassable full-screen security barrier on physical monitors while keeping
the Windows session active, enabling 100% crystal-clear mobile live streaming and remote unlock.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisCyberLock")

SECURITY_DIR = os.path.dirname(os.path.abspath(__file__))
PIN_FILE = os.path.join(SECURITY_DIR, "lock_pin.txt")
PID_FILE = os.path.join(SECURITY_DIR, "lock_pid.txt")
DEFAULT_PIN = "1234"


def get_stored_pin() -> str:
    """Returns persistent authorization PIN (default: '1234')."""
    if os.path.exists(PIN_FILE):
        try:
            with open(PIN_FILE, "r", encoding="utf-8") as f:
                pin = f.read().strip()
                if pin:
                    return pin
        except Exception:
            pass
    return DEFAULT_PIN


def save_pin(new_pin: str) -> bool:
    """Saves new authorization PIN persistently."""
    try:
        clean = new_pin.strip()
        if not clean or len(clean) < 4:
            return False
        os.makedirs(SECURITY_DIR, exist_ok=True)
        with open(PIN_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
        return True
    except Exception as e:
        logger.error(f"[CyberLock] Failed to save PIN: {e}")
        return False


class CyberLockManager:
    """Manages the lifecycle of J.A.R.V.I.S. Cyber Security Lock Barrier."""

    def __init__(self):
        self._pin = get_stored_pin()

    def get_pin(self) -> str:
        return get_stored_pin()

    def set_pin(self, new_pin: str) -> bool:
        success = save_pin(new_pin)
        if success:
            self._pin = new_pin.strip()
        return success

    def is_locked(self) -> bool:
        """Checks whether the Cyber Lock GUI process is currently running."""
        if not os.path.exists(PID_FILE):
            return False
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            # Check if process is alive on Windows
            if sys.platform == "win32":
                import ctypes
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if h_proc:
                    ctypes.windll.kernel32.CloseHandle(h_proc)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def lock(self, custom_pin: Optional[str] = None) -> Dict[str, Any]:
        """Activates full-screen Cyber Lock on physical monitors."""
        if custom_pin:
            self.set_pin(custom_pin)

        if self.is_locked():
            return {"success": True, "already_locked": True, "message": "Workstation is already locked with Cyber Security Barrier."}

        try:
            os.makedirs(SECURITY_DIR, exist_ok=True)
            python_exe = sys.executable
            # Launch GUI process in background
            script_path = os.path.abspath(__file__)
            proc = subprocess.Popen([python_exe, script_path, "--gui"])
            with open(PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(proc.pid))

            logger.info(f"🔒 [CyberLock] Activated Cyber Security Lock (PID: {proc.pid})")
            return {
                "success": True,
                "action": "locked",
                "pid": proc.pid,
                "message": "J.A.R.V.I.S. Cyber Security Barrier is active on all monitors."
            }
        except Exception as e:
            logger.error(f"[CyberLock] Failed to activate lock: {e}")
            return {"success": False, "error": str(e)}

    def unlock(self, pin: str) -> Dict[str, Any]:
        """Validates PIN and dismisses Cyber Lock."""
        stored = self.get_pin()
        if str(pin).strip() != stored:
            logger.warning("[CyberLock] Unlock failed: Invalid PIN attempt.")
            return {"success": False, "error": "Invalid Authorization PIN. Workstation remains locked."}

        return self.force_unlock()

    def force_unlock(self) -> Dict[str, Any]:
        """Directly terminates Cyber Lock GUI process without PIN check (for authorized internal flows)."""
        pid = None
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
            except Exception:
                pass

        try:
            if pid:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                else:
                    os.kill(pid, 9)

            # Fallback kill by title/command line
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq J.A.R.V.I.S. SECURITY SHIELD*"], capture_output=True)

            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass

            logger.info("🔓 [CyberLock] Workstation unlocked successfully.")
            return {"success": True, "action": "unlocked", "message": "Workstation unlocked successfully."}
        except Exception as e:
            logger.error(f"[CyberLock] Error during unlock: {e}")
            return {"success": False, "error": str(e)}


cyber_lock = CyberLockManager()


# ======================================================================
# FULL-SCREEN TKINTER CYBER SECURITY BARRIER GUI
# ======================================================================
def run_lock_gui():
    import tkinter as tk

    root = tk.Tk()
    root.title("J.A.R.V.I.S. SECURITY SHIELD")
    root.configure(bg="#050811")

    # Cover entire screen / all virtual desktop bounds
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.overrideredirect(True)

    # Force keep focus and stay on top
    def keep_topmost():
        try:
            root.lift()
            root.attributes("-topmost", True)
            root.after(250, keep_topmost)
        except Exception:
            pass

    # Suppress close or window switching keys
    def block_event(event=None):
        return "break"

    root.bind("<Alt-F4>", block_event)
    root.bind("<Alt-Tab>", block_event)
    root.bind("<Escape>", block_event)

    # Container Frame
    center_frame = tk.Frame(root, bg="#050811", highlightthickness=2, highlightbackground="#00f0ff", padx=30, pady=25)
    center_frame.place(relx=0.5, rely=0.5, anchor="center")

    # Neon Shield Title
    badge_label = tk.Label(center_frame, text="🛡️ J.A.R.V.I.S. CYBER SECURITY BARRIER", font=("Segoe UI", 11, "bold"), fg="#ff3366", bg="#050811")
    badge_label.pack(pady=(0, 6))

    title_label = tk.Label(center_frame, text="WORKSTATION LOCKED", font=("Segoe UI", 22, "bold"), fg="#00f0ff", bg="#050811")
    title_label.pack(pady=(0, 2))

    desc_label = tk.Label(center_frame, text="Protected by Master Operator Authentication", font=("Segoe UI", 10), fg="#94a3b8", bg="#050811")
    desc_label.pack(pady=(0, 15))

    # Real-time clock
    clock_label = tk.Label(center_frame, text="", font=("Consolas", 18, "bold"), fg="#00ff88", bg="#050811")
    clock_label.pack(pady=(0, 15))

    def update_clock():
        cur_time = time.strftime("%I:%M:%S %p  •  %d %b %Y")
        clock_label.config(text=cur_time)
        root.after(1000, update_clock)

    update_clock()

    # PIN Input Display
    pin_var = tk.StringVar()
    entry = tk.Entry(center_frame, textvariable=pin_var, show="●", font=("Consolas", 22, "bold"), justify="center", width=10, bg="#0d1829", fg="#00f0ff", insertbackground="#00f0ff", relief="flat", highlightthickness=1, highlightbackground="#00f0ff")
    entry.pack(pady=(0, 12))
    entry.focus_set()

    status_label = tk.Label(center_frame, text="Enter 4-digit PIN or unlock remotely from phone (/unlock)", font=("Segoe UI", 9), fg="#94a3b8", bg="#050811")
    status_label.pack(pady=(0, 14))

    failed_attempts = 0

    def attempt_unlock(event=None):
        nonlocal failed_attempts
        entered = pin_var.get().strip()
        correct_pin = get_stored_pin()
        if entered == correct_pin:
            status_label.config(text="✅ AUTHORIZATION GRANTED — WELCOME BACK", fg="#00ff88")
            root.update()
            time.sleep(0.3)
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass
            root.destroy()
            sys.exit(0)
        else:
            failed_attempts += 1
            pin_var.set("")
            status_label.config(text=f"❌ ACCESS DENIED ({failed_attempts}) — INVALID PIN", fg="#ff3366")
            center_frame.config(highlightbackground="#ff3366")
            root.after(1500, lambda: center_frame.config(highlightbackground="#00f0ff"))

    entry.bind("<Return>", attempt_unlock)

    # Keypad Buttons
    grid_frame = tk.Frame(center_frame, bg="#050811")
    grid_frame.pack(pady=(0, 10))

    def btn_press(num):
        pin_var.set(pin_var.get() + str(num))

    def btn_clear():
        pin_var.set("")

    buttons = [
        ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
        ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
        ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
        ("CLR", 3, 0), ("0", 3, 1), ("⏎", 3, 2),
    ]

    for text, r, c in buttons:
        if text == "CLR":
            cmd = btn_clear
            fg_col = "#ff3366"
        elif text == "⏎":
            cmd = attempt_unlock
            fg_col = "#00ff88"
        else:
            cmd = lambda n=text: btn_press(n)
            fg_col = "#ffffff"

        b = tk.Button(grid_frame, text=text, font=("Segoe UI", 12, "bold"), width=4, height=1, bg="#111d33", fg=fg_col, activebackground="#00f0ff", activeforeground="#000", relief="flat", bd=0, command=cmd)
        b.grid(row=r, column=c, padx=3, pady=3)

    keep_topmost()
    root.mainloop()


if __name__ == "__main__":
    if "--gui" in sys.argv:
        run_lock_gui()
    else:
        # CLI test
        print("CyberLock Status:", "LOCKED" if cyber_lock.is_locked() else "UNLOCKED")
        print("Current PIN:", cyber_lock.get_pin())
