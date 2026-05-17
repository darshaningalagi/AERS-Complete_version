"""
AERS WebSocket Manager
Broadcasts live case events to all connected browser clients.
"""
import json
import asyncio
from typing import Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        try:
            await ws.accept()
            self.active.add(ws)
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: dict):
        """Send a JSON message to every connected client."""
        if not self.active:
            return
        try:
            text = json.dumps(message)
        except Exception:
            text = json.dumps({"type": "error", "data": {"message": "Failed to serialize message"}})

        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)

    def count(self) -> int:
        return len(self.active)


# Singleton
manager = ConnectionManager()
