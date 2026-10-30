import asyncio
import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket

logger = logging.getLogger("astra.telemetry")

class TelemetryBroadcaster:
    def __init__(self):
        # Map channel name to set of active WebSockets
        self.channels: Dict[str, Set[WebSocket]] = {
            "all": set(),
            "touchdown_telemetry": set(),
            "rover_telemetry": set(),
            "decision_audit": set(),
            "experiment_progress": set(),
        }
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "all"):
        await websocket.accept()
        async with self._lock:
            if channel not in self.channels:
                self.channels[channel] = set()
            self.channels[channel].add(websocket)
            self.channels["all"].add(websocket)
        logger.info(f"WebSocket client connected to channel '{channel}'")

    async def disconnect(self, websocket: WebSocket, channel: str = "all"):
        async with self._lock:
            for ch in self.channels.values():
                ch.discard(websocket)
        logger.info(f"WebSocket client disconnected from channel '{channel}'")

    async def broadcast(self, channel: str, message: Dict[str, Any]):
        """Non-blocking broadcast to all clients listening on channel or 'all'."""
        if channel not in self.channels and channel != "all":
            return

        dead_sockets = set()
        targets = self.channels.get(channel, set()).copy()
        payload_text = json.dumps(message)

        for ws in targets:
            try:
                await ws.send_text(payload_text)
            except Exception:
                dead_sockets.add(ws)

        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    for ch in self.channels.values():
                        ch.discard(ws)

telemetry_broadcaster = TelemetryBroadcaster()
