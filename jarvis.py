"""
================================================================================
           PROJECT J.A.R.V.I.S. - 1.0 MASTER AUTONOMOUS RUNTIME
================================================================================
Just A Rather Very Intelligent System
Cyber-Physical Autonomous Operating System uniting Physical, Computer & Cloud Worlds.
"""

from __future__ import annotations
import sys
import os
import argparse
import asyncio
import subprocess
import time
import webbrowser

# Set Project Root in path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/jarvis-core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/brain"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/permission-engine"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/planner"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/memory"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/sensory"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc-agent"))

from shared.sdk_python.jarvis_sdk.config import config
from shared.sdk_python.jarvis_sdk.logger import get_logger
from shared.sdk_python.jarvis_sdk.event_mesh import mesh
from shared.schemas.event_envelope import JarvisEvent
from shared.schemas.action_envelope import ActionEnvelope, ActionTier, TargetWorld
from services.brain.agent_runtime import runtime as brain_runtime
from services.planner.orchestrator import orchestrator
from services.memory.world_model import world_model
from services.sensory.voice_synthesizer import voice_synthesizer
from services.sensory.clap_detector import clap_detector
from services.sensory.voice_listener import voice_listener
from services.sensory.soundboard import soundboard
from agents.action_dispatcher import action_dispatcher

logger = get_logger("JARVIS-1.0")


def print_banner():
    banner = """
    \033[96m
    ███████╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗   ██╗██████╗ 
    ╚══███╔╝██╔══██╗██╔══██╗██║   ██║██║██╔════╝  ███║██╔═████╗
      ███╔╝ ███████║██████╔╝██║   ██║██║███████╗  ╚██║██║██╔██║
     ███╔╝  ██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║   ██║████╔╝██║
    ███████╗██║  ██║██║  ██║ ╚████╔╝ ██║███████║██╗██║╚██████╔╝
    ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝╚═╝╚═╝ ╚═════╝ 
    \033[0m
    >> \033[93mCYBER-PHYSICAL AUTONOMOUS OPERATING SYSTEM READY\033[0m <<
    --------------------------------------------------------
    * Physical World:   ESP32 Relays & Ambient Lux Sensors
    * Computer World:   Windows Process, App & Shell Control
    * Digital World:    AWS Cloud, Terraform IaC & LocalStack
    * Safety Matrix:    4-Tier Blast Radius + Stand Down Breaker
    * Cognitive Fabric: Real AI Multi-Provider + Continuous Learning
    * Hands-Free VOX:   Acoustic Wake-Word Daemon + Authentic Soundboard
    --------------------------------------------------------
    """
    print(banner)


async def execute_jarvis_command(query: str, play_voice: bool = True):
    """
    Executes a high-level instruction following the Master Architectural Loop:
    UNDERSTAND -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> RESPOND
    """
    print(f"\n\033[92m[Operator]:\033[0m {query}")
    logger.info(f"Ingesting instruction: '{query}'")

    matched_clip = soundboard.match_audio_clip(query)

    # 1. BRAIN AGENT RUNTIME EXECUTION
    result = await brain_runtime.execute_turn(query)

    response_text = result.get("response", "Action completed, sir.")
    intent = result.get("intent", "general")
    verified = result.get("verified", True)
    latency = result.get("latency_ms", 0.0)

    print(f"\033[96m[J.A.R.V.I.S.]:\033[0m {response_text}")
    print(f"\033[90m>> Intent: [{intent}] | Verified: [{verified}] | Latency: [{latency}ms]\033[0m")

    # 2. VOICE SYNTHESIS (TTS) OR AUTHENTIC SOUNDBOARD
    if play_voice:
        if matched_clip:
            soundboard.play_clip(matched_clip["clip_name"])
        else:
            await voice_synthesizer.speak(response_text, play_audio=True)

    return result


def start_server():
    """Starts FastAPI Core Server and launches the Futuristic HUD Dashboard"""
    import uvicorn
    print_banner()
    logger.info("Igniting J.A.R.V.I.S. Core Engine and Holographic HUD...")

    # Start Hands-Free Wake-Word Daemon
    try:
        from services.sensory.wake_word_daemon import wake_word_daemon
        wake_word_daemon.start()
    except Exception as e:
        logger.warning(f"Could not start WakeWordDaemon: {e}")

    url = f"http://{config.host}:{config.port}"
    print(f"\n⚡ Holographic HUD Dashboard available at: \033[94m{url}\033[0m\n")

    # Open browser automatically
    def open_hud():
        time.sleep(1.5)
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_hud, daemon=True).start()

    from main import app
    uvicorn.run(app, host=config.host, port=config.port)


def run_full_diagnostics():
    """Runs end-to-end test verification across all 35 phases"""
    print_banner()
    print("Initiating full system diagnostic across all 35 phases...")
    test_suites = [
        "shared/schemas/test_schemas.py",
        "services/jarvis-core/test_api.py",
        "services/brain/test_brain.py",
        "services/memory/test_memory.py",
        "services/planner/test_planner.py",
        "services/permission-engine/test_permission_engine.py",
        "agents/test_action_framework.py",
        "services/sensory/test_sensory.py",
        "services/pc-agent/test_pc_agent.py",
        "agents/cloud/test_cloud_suite.py",
        "services/iot-agent/test_iot.py",
        "services/observability/test_observability.py"
    ]

    passed = 0
    failed = 0
    for ts in test_suites:
        full_path = os.path.join(PROJECT_ROOT, ts)
        print(f"\n==================================================")
        print(f"Testing Suite: {ts}")
        print(f"==================================================")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, full_path], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if res.returncode == 0:
            print(f"\033[92m✔ PASS: {ts}\033[0m")
            passed += 1
        else:
            print(f"\033[91m✖ FAIL: {ts}\033[0m")
            print(res.stderr or res.stdout)
            failed += 1

    print("\n--------------------------------------------------")
    print(f"DIAGNOSTIC COMPLETE: \033[92m{passed} Passed\033[0m, \033[91m{failed} Failed\033[0m")
    print("--------------------------------------------------")


def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Master OS")
    parser.add_argument("command", choices=["start", "run", "test", "status", "stand-down"], help="Action to execute")
    parser.add_argument("--query", "-q", type=str, default="JARVIS, prepare my workspace", help="Instruction query for 'run'")
    args = parser.parse_args()

    if args.command == "start":
        start_server()
    elif args.command == "run":
        print_banner()
        asyncio.run(execute_jarvis_command(args.query))
    elif args.command == "test":
        run_full_diagnostics()
    elif args.command == "status":
        print_banner()
        snapshot = world_model.get_snapshot()
        import json
        print(json.dumps(snapshot, indent=2))
    elif args.command == "stand-down":
        config.emergency_stand_down = True
        print("\033[91m[CIRCUIT BREAKER]: EMERGENCY STAND DOWN ACTIVATED. All agent write tokens frozen.\033[0m")


if __name__ == "__main__":
    main()
