"""
J.A.R.V.I.S. Computer & OS Subsystem (Pillar 1).
Exports modular operating system automation agents.
"""

from .power_agent import power_agent, PowerAgent
from .audio_agent import audio_agent, AudioAgent
from .display_agent import display_agent, DisplayAgent
from .mouse_agent import mouse_agent, MouseAgent
from .keyboard_agent import keyboard_agent, KeyboardAgent
from .file_agent import file_agent, FileAgent
from .windows_agent import windows_agent, WindowsAgent
from .screen_agent import screen_agent, ScreenAgent
from .network_agent import network_agent, NetworkAgent

__all__ = [
    "power_agent", "PowerAgent",
    "audio_agent", "AudioAgent",
    "display_agent", "DisplayAgent",
    "mouse_agent", "MouseAgent",
    "keyboard_agent", "KeyboardAgent",
    "file_agent", "FileAgent",
    "windows_agent", "WindowsAgent",
    "screen_agent", "ScreenAgent",
    "network_agent", "NetworkAgent"
]
