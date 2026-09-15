"""
WebSocket Connection Manager for J.A.R.V.I.S. Core.
Enables real-time bi-directional streaming between JARVIS, HUD, and mobile interfaces.
"""

from typing import List, Dict, Any
from fastapi import WebSocket
import json


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected dashboards and HUD clients"""
        payload = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

    async def broadcast_audio_chunk(self, audio_b64: str, chunk_idx: int, is_final: bool, text_segment: str = ""):
        """Broadcasts progressive streaming audio chunk to connected HUD and web clients"""
        await self.broadcast({
            "channel": "audio_stream",
            "chunk_index": chunk_idx,
            "audio_b64": audio_b64,
            "is_final": is_final,
            "text": text_segment
        })


ws_manager = WebSocketManager()
