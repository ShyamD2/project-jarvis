"""
Project J.A.R.V.I.S. Telegram Gateway Windows Auto-Start Installer.
Configures Windows to automatically and silently launch the Telegram Gateway on system startup/login,
allowing 100% hands-free remote control from mobile without manually starting anything on the laptop.
"""
from __future__ import annotations
import os
import sys
import winreg

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PYTHON_EXE = sys.executable
GATEWAY_SCRIPT = os.path.join(PROJECT_ROOT, "services", "gateway", "telegram_bot.py")
VBS_PATH = os.path.join(PROJECT_ROOT, "services", "gateway", "start_silent_gateway.vbs")
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
STARTUP_VBS = os.path.join(STARTUP_DIR, "JarvisTelegramGateway.vbs")
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "JarvisTelegramGateway"

def create_vbs_script():
    """Generates the silent VBScript launcher with absolute paths."""
    content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{PROJECT_ROOT}"
WshShell.Run """{PYTHON_EXE}""" """{GATEWAY_SCRIPT}""", 0, False
'''
    with open(VBS_PATH, "w", encoding="ascii") as f:
        f.write(content)
    print(f"[OK] Created silent launcher: {VBS_PATH}")

def install():
    print("=" * 60)
    print("   INSTALLING J.A.R.V.I.S. AUTO-START (TELEGRAM GATEWAY)")
    print("=" * 60)
    
    create_vbs_script()
    
    # 1. Install to Windows Startup Folder
    if os.path.exists(STARTUP_DIR):
        with open(STARTUP_VBS, "w", encoding="ascii") as f:
            with open(VBS_PATH, "r", encoding="ascii") as src:
                f.write(src.read())
        print(f"[OK] Configured Windows Startup Folder: {STARTUP_VBS}")
    else:
        print(f"[WARN] Startup folder not found: {STARTUP_DIR}")

    # 2. Install to Windows Registry Run Key
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        cmd = f'wscript.exe "{VBS_PATH}"'
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(f"[OK] Registered HKCU Run key: {REG_NAME} -> {cmd}")
    except Exception as e:
        print(f"[WARN] Registry setup error: {e}")
        
    print("\n[SUCCESS] AUTO-START INSTALLED SUCCESSFULLY!")
    print("- When your laptop boots or logs in, Telegram Gateway starts 100% silently in the background.")
    print("- You can now tap 'Start J.A.R.V.I.S.' on Telegram from your phone at any time without manually starting anything on the laptop!\n")

def uninstall():
    print("Uninstalling J.A.R.V.I.S. Telegram Gateway auto-start...")
    if os.path.exists(STARTUP_VBS):
        try:
            os.remove(STARTUP_VBS)
            print(f"[OK] Removed from Startup Folder: {STARTUP_VBS}")
        except Exception as e:
            print(f"[WARN] Error removing startup file: {e}")
            
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, REG_NAME)
        winreg.CloseKey(key)
        print(f"[OK] Removed registry key: {REG_NAME}")
    except Exception as e:
        print(f"Notice: {e}")
        
    print("Auto-start uninstalled.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        uninstall()
    else:
        install()
