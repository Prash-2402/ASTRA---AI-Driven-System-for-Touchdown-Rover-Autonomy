from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.events.bus import CHANNELS, bus

router = APIRouter()


@router.websocket("/ws/{channel}")
async def ws_channel(ws: WebSocket, channel: str):
    if channel not in CHANNELS:
        await ws.close(code=4404)
        return
    await ws.accept()
    q = bus.subscribe(channel)
    try:
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
        pass
    finally:
        bus.unsubscribe(channel, q)
