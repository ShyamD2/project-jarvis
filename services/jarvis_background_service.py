"""
Master Silent Background Service for Project J.A.R.V.I.S.
Runs automatically on Windows startup:
- 🎙️ Acoustic Wake-Word Engine (openWakeWord ONNX CPU - 'Hey Jarvis' / 'Jarvis')
- 📱 Telegram Mobile Remote Gateway (if configured)
- ⚡ Event Mesh & Hands-Free Conversational Brain

Zero window clutter, <1% CPU footprint, runs silently via pythonw.exe or Windows Startup.
"""

from __future__ import annotations
import os
import sys
import time
import ctypes
import threading
import asyncio

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# When launched via pythonw.exe (no console window), redirect output to log file
log_dir = os.path.join(PROJECT_ROOT, "services", "gateway")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "jarvis_background.log")

if sys.stdout is None or sys.stderr is None:
    try:
        f = open(log_file, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = f
        if sys.stderr is None:
            sys.stderr = f
    except Exception:
        pass

import logging
file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s]: %(message)s", datefmt="%H:%M:%S"))
logging.getLogger().addHandler(file_handler)
logging.getLogger().setLevel(logging.INFO)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisBackgroundService")


def acquire_singleton_mutex(mutex_name: str = "Global\\JarvisMasterBackgroundServiceMutex") -> Optional[int]:
    """Ensures only a single instance of the background service runs at any time."""
    if sys.platform != "win32":
        return None
    try:
        ERROR_ALREADY_EXISTS = 183
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            logger.warning(f"[BackgroundService] Another instance is already active (Mutex '{mutex_name}' held). Exiting duplicate.")
            sys.exit(0)
        return handle
    except Exception as e:
        logger.warning(f"[BackgroundService] Mutex check warning: {e}")
        return None


def start_wake_word():
    """Starts continuous acoustic wake-word listener thread."""
    try:
        from services.sensory.wake_word_daemon import wake_word_daemon
        logger.info("🎙️ [BackgroundService] Starting Hands-Free Wake-Word Daemon ('Hey Jarvis')...")
        wake_word_daemon.start()
    except Exception as e:
        logger.error(f"[BackgroundService] Failed to start wake word daemon: {e}")


def start_telegram_gateway():
    """Starts Telegram Bot Gateway in a dedicated background event loop."""
    try:
        from services.gateway.telegram_bot import telegram_gateway
        if not telegram_gateway.is_configured:
            logger.info("📱 [BackgroundService] Telegram Bot Token not set; running wake-word only.")
            return

        def _telegram_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                logger.info("📱 [BackgroundService] Starting Telegram Gateway polling loop...")
                loop.run_until_complete(telegram_gateway.start())
            except Exception as e:
                logger.error(f"[BackgroundService] Telegram gateway error: {e}")
            finally:
                loop.close()

        t = threading.Thread(target=_telegram_worker, daemon=True, name="TelegramGatewayThread")
        t.start()
    except Exception as e:
        logger.error(f"[BackgroundService] Failed to start telegram gateway: {e}")


def main():
    mutex_handle = acquire_singleton_mutex()
    logger.info("==================================================================")
    logger.info("   PROJECT J.A.R.V.I.S. - MASTER SILENT BACKGROUND SERVICE ONLINE")
    logger.info("   Hands-Free Wake-Word ('Hey Jarvis') + Telegram Gateway Active")
    logger.info("==================================================================")

    # 1. Start Acoustic Wake-Word Engine
    start_wake_word()

    # 2. Start Telegram Gateway
    start_telegram_gateway()

    # 3. Keep main thread alive at low CPU (<0.1%)
    try:
        while True:
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        logger.info("⚡ [BackgroundService] Stopping background service...")
        try:
            from services.sensory.wake_word_daemon import wake_word_daemon
            wake_word_daemon.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
