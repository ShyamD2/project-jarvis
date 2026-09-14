"""
JARVIS Personality & Natural Response Generator for Project J.A.R.V.I.S.
Transforms raw technical tool outputs and telemetry data into composed, intelligent,
Paul Bettany-inspired British responses without robotic clichés.
"""

from __future__ import annotations
import random
import re
from typing import Dict, Any, Optional, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisResponseGenerator")


class ResponseGenerator:
    ACKNOWLEDGEMENTS = [
        "Right away, sir.",
        "Certainly, sir.",
        "On it, sir.",
        "Right on it.",
        "Working on that now, sir.",
        "At once, sir."
    ]

    COMPLETION_PHRASES = [
        "All taken care of, sir.",
        "Task completed, sir.",
        "Right here, sir.",
        "Done, sir."
    ]

    ROBOTIC_PHRASES = [
        r"\boperation completed successfully\b",
        r"\baction executed\b",
        r"\bsuccessfully executed tool\b",
        r"\breturned code 0\b",
        r"\bexecuted with status ok\b",
        r"\bcommand ran successfully\b",
        r"\btool execution completed\b"
    ]

    def generate_acknowledgement(self, query: str, tool_name: Optional[str] = None) -> str:
        """Generates a brief, refined conversational acknowledgement before or during execution."""
        q = query.lower()
        if "open" in q or "launch" in q:
            target = re.sub(r"^(?:open|launch)\s+", "", q).strip()
            return f"Opening {target.title()}, sir."
        elif "close" in q or "quit" in q:
            target = re.sub(r"^(?:close|quit)\s+", "", q).strip()
            return f"Closing {target.title()} now."
        elif "volume" in q or "audio" in q:
            return "Adjusting audio levels, sir."
        elif "cpu" in q or "ram" in q or "memory" in q or "disk" in q:
            return "Checking system telemetry now."
        elif "terraform" in q or "cloud" in q or "aws" in q:
            return "Querying cloud infrastructure, sir."
        elif "search" in q:
            return "Searching the web, sir."

        return random.choice(self.ACKNOWLEDGEMENTS)

    def format_telemetry_response(self, telemetry_data: Dict[str, Any]) -> str:
        """Formats CPU, RAM, and Disk metrics into conversational, fluent British speech."""
        parts = []
        if "cpu_usage" in telemetry_data or "cpu_percent" in telemetry_data:
            cpu = telemetry_data.get("cpu_usage") or telemetry_data.get("cpu_percent")
            parts.append(f"CPU utilization is currently at {cpu} percent")

        if "ram_usage" in telemetry_data or "ram_percent" in telemetry_data:
            ram = telemetry_data.get("ram_usage") or telemetry_data.get("ram_percent")
            used = telemetry_data.get("ram_used_gb")
            total = telemetry_data.get("ram_total_gb")
            if used and total:
                parts.append(f"RAM is sitting at {ram} percent, using {used:.1f} of {total:.1f} gigabytes")
            else:
                parts.append(f"RAM is at {ram} percent")

        if "disk_free_gb" in telemetry_data:
            free = telemetry_data.get("disk_free_gb")
            parts.append(f"with {free:.1f} gigabytes of free disk space remaining")

        if parts:
            return f"{', '.join(parts)}, sir."
        return "Telemetry retrieved, sir."

    def format_tool_result(self, tool_name: str, result_data: Dict[str, Any], raw_query: str) -> str:
        """
        Synthesizes a refined natural response from a tool's output dictionary,
        completely replacing robotic templates.
        """
        # Volume & Audio
        if tool_name == "control_system_audio":
            action = result_data.get("action", "")
            vol = result_data.get("volume")
            if action == "mute":
                return "Audio has been muted, sir."
            elif action == "unmute":
                return "Audio is unmuted, sir."
            elif vol is not None:
                return f"Volume set to {vol} percent, sir."
            elif "increase" in action:
                return "Volume increased, sir."
            elif "decrease" in action:
                return "Volume lowered, sir."
            return "Audio level adjusted, sir."

        # App Launching
        if tool_name == "launch_app":
            app = result_data.get("app_name") or result_data.get("name") or "Application"
            return f"{app.title()} is open and ready, sir."

        # App Closing
        if tool_name == "close_app":
            app = result_data.get("app_name") or "Application"
            return f"{app.title()} has been closed, sir."

        # System Telemetry
        if tool_name == "query_system_telemetry":
            return self.format_telemetry_response(result_data)

        # Web & Search
        if tool_name == "web_search":
            count = len(result_data.get("results", []))
            query_term = result_data.get("query", "your query")
            if count > 0:
                return f"I found {count} results for {query_term}, sir. The top result is ready."
            return f"I searched for {query_term}, but found no immediate matches, sir."

        # DevOps / Terraform
        if tool_name in ("terraform_plan", "terraform_apply", "docker_ops"):
            status = result_data.get("status", "complete")
            summary = result_data.get("summary") or result_data.get("message")
            if summary:
                return f"{summary}, sir."
            return f"Operation {status}, sir."

        # General fallbacks
        msg = result_data.get("message") or result_data.get("response")
        if msg:
            return self.polish_text(str(msg))

        return random.choice(self.COMPLETION_PHRASES)

    def format_error(self, error_msg: str, tool_name: Optional[str] = None) -> str:
        """Translates technical stack traces and errors into helpful conversational explanations."""
        lower_err = error_msg.lower()
        if "docker" in lower_err and ("connect" in lower_err or "not running" in lower_err):
            return "I was unable to connect to the Docker daemon, sir. It appears the service is stopped. Would you like me to start it?"
        if "permission" in lower_err or "denied" in lower_err or "forbidden" in lower_err:
            return "I don't have the requisite security permissions to perform that operation, sir."
        if "not found" in lower_err or "cannot find" in lower_err:
            return f"I couldn't locate the requested item, sir. Please verify the target."
        if "timeout" in lower_err:
            return "The request timed out before receiving a response, sir."

        return f"I encountered an issue executing that command, sir. {error_msg.splitlines()[0]}"

    def polish_text(self, text: str) -> str:
        """Removes any unintentional robotic boilerplate from output strings."""
        if not text:
            return "Task completed, sir."
        polished = text
        for pattern in self.ROBOTIC_PHRASES:
            polished = re.sub(pattern, "task complete", polished, flags=re.IGNORECASE)
        # Ensure it sounds like JARVIS
        if not polished.rstrip().endswith(("sir.", "sir!", "sir?")):
            if not any(polished.lower().endswith(end) for end in [".", "!", "?"]):
                polished += "."
        return polished


response_generator = ResponseGenerator()
