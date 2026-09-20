"""
Intelligent Mock / Local Reflex LLM Provider for J.A.R.V.I.S. Brain.
Provides rich, context-aware reasoning, real system status, and tool selection.
"""

import time
import re
from typing import List, Dict, Any, Optional, AsyncGenerator
import os
import sys
import datetime
import socket
import psutil
import urllib.parse
from services.brain.providers.base import BaseLLMProvider, LLMResponse, ToolCall

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc_agent"))

try:
    from system_monitor import system_monitor
except ImportError:
    from services.pc_agent.system_monitor import system_monitor


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "jarvis-reflex-brain"):
        self.model_name = model_name

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> LLMResponse:
        start_time = time.time()
        p = prompt.strip()
        p_lower = p.lower()
        # Clean wake prefix so commands work whether or not user starts with 'jarvis'
        p_cmd = re.sub(r"^(hey\s+)?jarvis[\s,]*", "", p_lower).strip()
        if not p_cmd:
            p_cmd = p_lower

        tool_calls: List[ToolCall] = []
        response_text = ""

        # 1. BROWSER TABS, WEB SITES & WEB SEARCH
        # Handles: "open new tab", "open new tab on opera", "open youtube", "search for X", "google X"
        if any(w in p_cmd for w in ["new tab", "open tab", "tab on", "browse", "website", "search for", "google ", "youtube", "github", "reddit", "chatgpt", "netflix", "twitter"]):
            browser = None
            if "opera" in p_cmd:
                browser = "opera"
            elif "chrome" in p_cmd:
                browser = "chrome"
            elif "edge" in p_cmd:
                browser = "edge"
            else:
                try:
                    from services.memory.feedback_learning import learner
                    browser = learner.memory.get("preferences", {}).get("browser", "opera")
                except Exception:
                    browser = "opera"

            url = "https://www.google.com"
            search_query = None

            if "youtube" in p_cmd:
                url = "https://www.youtube.com"
                response_text = f"Opening YouTube{' on ' + browser.capitalize() if browser else ''}, sir."
            elif "github" in p_cmd:
                url = "https://github.com"
                response_text = f"Opening GitHub{' on ' + browser.capitalize() if browser else ''}, sir."
            elif "reddit" in p_cmd:
                url = "https://reddit.com"
                response_text = f"Opening Reddit{' on ' + browser.capitalize() if browser else ''}, sir."
            elif "chatgpt" in p_cmd:
                url = "https://chatgpt.com"
                response_text = f"Opening ChatGPT{' on ' + browser.capitalize() if browser else ''}, sir."
            elif "netflix" in p_cmd:
                url = "https://netflix.com"
                response_text = f"Opening Netflix{' on ' + browser.capitalize() if browser else ''}, sir."
            elif "search for" in p_cmd or p_cmd.startswith("google ") or p_cmd.startswith("search "):
                q = re.sub(r"^(search for|google|search)\s+", "", p_cmd).strip()
                search_query = q
                response_text = f"Searching the web for '{q}'{' via ' + browser.capitalize() if browser else ''}, sir."
            else:
                b_name = browser.capitalize() if browser else "Opera"
                response_text = f"Opening a new tab on {b_name}, sir."

            tool_calls.append(
                ToolCall(
                    tool_name="browse_web",
                    arguments={"url": url, "browser": browser, "search_query": search_query}
                )
            )

        # 2. APPLICATION LAUNCHING
        # Handles: "open opera", "launch chrome", "open spotify", "open discord", "open calculator", etc.
        elif any(p_cmd.startswith(w) for w in ["open ", "launch ", "start ", "run "]) and not any(w in p_cmd for w in ["light", "lamp", "workspace"]):
            raw_target = re.sub(r"^(open|launch|start|run)\s+", "", p_cmd).strip()

            mode = "auto"
            if any(w in raw_target for w in ["on web", "on browser", "web version", "online"]):
                mode = "web"
            elif any(w in raw_target for w in ["on system", "on pc", "on desktop", "system app", "desktop app", "locally", "systems", "system's"]):
                mode = "system"

            clean_target = re.sub(r"\b(on\s+web|on\s+browser|on\s+system|on\s+pc|on\s+desktop|web\s+version|online|systems|system's|system|desktop|locally)\b", "", raw_target).strip()
            clean_target = re.sub(r"\s+", " ", clean_target).strip()
            if not clean_target:
                clean_target = raw_target

            # Map app names cleanly
            app_name = clean_target
            if "opera" in clean_target:
                app_name = "opera"
            elif clean_target in ["browser", "web"]:
                try:
                    from services.memory.feedback_learning import learner
                    app_name = learner.memory.get("preferences", {}).get("browser", "opera")
                except Exception:
                    app_name = "opera"
            elif "chrome" in clean_target:
                app_name = "chrome"
            elif "edge" in clean_target:
                app_name = "msedge"
            elif "spotify" in clean_target:
                app_name = "spotify"
            elif "discord" in clean_target:
                app_name = "discord"
            elif "telegram" in clean_target:
                app_name = "telegram"
            elif "whatsapp" in clean_target:
                app_name = "whatsapp"
            elif "snapchat" in clean_target:
                app_name = "snapchat"
            elif "steam" in clean_target:
                app_name = "steam"
            elif "calc" in clean_target:
                app_name = "calc"
            elif "note" in clean_target:
                app_name = "notepad"
            elif "code" in clean_target or "vs" in clean_target:
                app_name = "code"
            elif "terminal" in clean_target or "powershell" in clean_target or "cmd" in clean_target:
                app_name = "terminal"
            elif "explorer" in clean_target or "files" in clean_target or "folder" in clean_target:
                app_name = "explorer"
            elif "task" in clean_target or "process" in clean_target:
                app_name = "taskmgr"
            elif "paint" in clean_target:
                app_name = "mspaint"
            elif "setting" in clean_target:
                app_name = "settings"

            # Special rule: Snapchat defaults to web unless system is explicitly requested
            if app_name == "snapchat" and mode != "system":
                mode = "web"

            tool_calls.append(ToolCall(tool_name="launch_app", arguments={"app": app_name, "mode": mode}))
            if mode == "web":
                response_text = f"Opening {app_name.capitalize()} on the web, sir."
            elif mode == "system":
                response_text = f"Opening {app_name.capitalize()} on your system, sir."
            else:
                response_text = f"Opening {app_name.capitalize()}, sir."

        # 3. APPLICATION TERMINATION / CLOSE
        # Handles: "close notepad", "kill chrome", "close opera", "terminate calc"
        elif any(p_cmd.startswith(w) for w in ["close ", "kill ", "terminate ", "shut "]):
            target = re.sub(r"^(close|kill|terminate|shut)\s+(down\s+)?", "", p_cmd).strip()
            tool_calls.append(ToolCall(tool_name="close_app", arguments={"app_name": target}))
            response_text = f"Terminating {target.capitalize()} processes on your workstation, sir."

        # 4. TIME & DATE
        elif any(w in p_lower for w in ["what time", "current time", "what is the date", "what's the date", "what day", "today's date"]):
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d, %Y")
            tool_calls.append(ToolCall(tool_name="query_system_telemetry", arguments={"query_type": "time"}))
            response_text = f"The current time is {time_str}, and today is {date_str}, sir."

        # 5. BATTERY & POWER
        elif any(w in p_lower for w in ["battery", "power status", "charge level"]):
            batt = psutil.sensors_battery()
            tool_calls.append(ToolCall(tool_name="query_system_telemetry", arguments={"query_type": "battery"}))
            if batt:
                plugged = "connected to AC power" if batt.power_plugged else "discharging on battery"
                response_text = f"Battery status is currently at {round(batt.percent)}%, {plugged}, sir."
            else:
                response_text = "System is operating on direct desktop AC power, sir."

        # 6. STORAGE & DISK
        elif any(w in p_lower for w in ["disk", "storage", "hard drive", "space left"]):
            d = psutil.disk_usage('C:\\')
            free_gb = round(d.free / (1024**3), 1)
            total_gb = round(d.total / (1024**3), 1)
            tool_calls.append(ToolCall(tool_name="query_system_telemetry", arguments={"query_type": "disk"}))
            response_text = f"Primary C: drive has {free_gb} GB free out of {total_gb} GB ({d.percent}% utilized), sir."

        # 7. NETWORK & IP
        elif any(w in p_lower for w in ["ip address", "network", "my ip", "hostname"]):
            h = socket.gethostname()
            ip = socket.gethostbyname(h)
            tool_calls.append(ToolCall(tool_name="query_system_telemetry", arguments={"query_type": "network"}))
            response_text = f"Workstation '{h}' is online on local IP address {ip}, sir."

        # 8. SYSTEM STATUS & TELEMETRY
        # NOTE: bare "system" intentionally excluded — too greedy (matches "open X on system", "my system", etc.)
        elif any(w in p_lower for w in ["system status", "system report", "system diagnostic", "system vitals",
                                         "run diagnostic", "run diagnostics", "check vitals", "health check",
                                         "all systems", "full report", "status report"]):
            vitals = system_monitor.collect_telemetry()
            tool_calls.append(ToolCall(tool_name="system_status_report", arguments={}))
            response_text = (
                f"All systems are operating nominally, sir. "
                f"CPU utilization is at {vitals['cpu_percent']}%, memory consumption is at {vitals['memory_percent']}%, "
                f"active window is '{vitals['active_window']}'. "
                f"Physical IoT nodes and cloud event fabrics are synchronized and ready."
            )

        # 9. WORKSPACE PREPARATION
        elif any(w in p_lower for w in ["workspace", "dev setup", "developer setup", "prepare workspace"]):
            tool_calls.append(ToolCall(tool_name="prepare_workspace", arguments={"profile": "developer"}))
            response_text = "Preparing your development workspace right away, sir. Launching VS Code, Windows Terminal, and setting illumination."

        # 10. SCREEN LOCK
        elif any(w in p_lower for w in ["lock pc", "lock screen", "lock workstation", "lock computer"]):
            tool_calls.append(ToolCall(tool_name="lock_screen", arguments={}))
            response_text = "Locking your Windows workstation immediately, sir."

        # 11. VOLUME / AUDIO
        elif any(w in p_lower for w in ["volume", "mute", "unmute"]):
            level = 50
            if "up" in p_lower:
                level = 80
            elif "down" in p_lower:
                level = 30
            elif "mute" in p_lower:
                level = 0
            elif "100" in p_lower:
                level = 100
            elif re.search(r"\b(\d+)\b", p_lower):
                m = re.search(r"\b(\d+)\b", p_lower)
                level = int(m.group(1))
            tool_calls.append(ToolCall(tool_name="control_system_audio", arguments={"level": level}))
            response_text = f"Adjusting master audio volume to {level}%, sir."

        # 12. PHYSICAL IOT RELAY / LIGHTING
        elif any(w in p_lower for w in ["light", "lamp", "desk lamp"]):
            state = False if any(w in p_lower for w in ["off", "disable", "shutdown", "stop"]) else True
            target = "desk_lamp" if "desk" in p_lower or "lamp" in p_lower else "light_main"
            tool_calls.append(
                ToolCall(
                    tool_name="control_physical_device",
                    arguments={"device_id": "esp32_lab_01", "target": target, "state": state}
                )
            )
            response_text = f"Certainly, sir. Switching {'on' if state else 'off'} the {target.replace('_', ' ')}."

        # 13. CLOUD & INFRASTRUCTURE
        elif any(w in p_lower for w in ["cloud", "aws", "terraform", "infrastructure", "iac"]):
            response_text = "Cloud infrastructure is nominal, sir. Event bus 'jarvis-event-bus' and telemetry pipelines are verified. Terraform IaC modules are validated and in sync."

        # 14. EMERGENCY STAND DOWN
        elif any(w in p_lower for w in ["stand down", "abort", "freeze", "kill all"]):
            response_text = "Standing down immediately, sir. All active workflows are frozen."

        # 15. MATH / CALCULATIONS
        elif re.search(r"\b(calculate|what is|compute)\s+([\d\.\s\+\-\*\/\^\(\)]+)\b", p_lower):
            m = re.search(r"\b(calculate|what is|compute)\s+([\d\.\s\+\-\*\/\^\(\)]+)\b", p_lower)
            expr = m.group(2).strip()
            try:
                # Safe math evaluation
                clean_expr = expr.replace("^", "**")
                res = eval(clean_expr, {"__builtins__": None}, {})
                response_text = f"The calculated result of {expr} is {res}, sir."
            except Exception:
                response_text = f"I was unable to compute '{expr}', sir. Please check the mathematical syntax."

        # 16. CONVERSATIONAL & IDENTITY
        elif any(w in p_lower for w in ["who are you", "what are you", "your name"]):
            response_text = "I am J.A.R.V.I.S., Just A Rather Very Intelligent System. An autonomous cyber-physical operating system uniting your Windows computer, IoT hardware, and cloud fabric, sir."
        elif any(w in p_lower for w in ["who made you", "who created you"]):
            response_text = "I was engineered as your personal autonomous cyber-physical operating system, sir."
        elif any(w in p_lower for w in ["what can you do", "your capabilities", "help"]):
            response_text = "I can control your Windows workstation, open new tabs on Opera or Chrome, search the web, manage processes, adjust audio, report system vitals, query battery and storage, control physical IoT relays, and audit cloud infrastructure, sir."
        elif any(w in p_lower for w in ["joke", "make me laugh"]):
            response_text = "There are 10 types of people in this world, sir: those who understand binary, and those who do not."
        elif any(w in p_lower for w in ["hi", "hello", "hey", "hey jarvis", "jarvis", "good morning", "good evening"]):
            response_text = "Good day, sir. J.A.R.V.I.S. is online, standing by, and ready for your instruction."
        elif any(w in p_lower for w in ["thank", "thanks"]):
            response_text = "Always a pleasure to assist, sir."

        # 17. GENERAL INTELLIGENT FALLBACK
        else:
            response_text = f"Understood, sir. Processing '{prompt}'. All telemetry feeds and cyber-physical fabrics remain nominal."

        latency = (time.time() - start_time) * 1000
        return LLMResponse(
            content=response_text,
            tool_calls=tool_calls,
            model=self.model_name,
            finish_reason="tool_calls" if tool_calls else "stop",
            tokens_prompt=len(prompt.split()),
            tokens_completion=len(response_text.split()),
            latency_ms=round(latency, 2)
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        res = await self.generate(prompt)
        for word in res.content.split():
            yield word + " "
