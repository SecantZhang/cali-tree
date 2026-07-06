"""WS /api/runs/{run_id}/ws — stream node_status/log_line/run_complete events.

Sends a resync message with the current status first (in case the run already
finished, or the client reconnects mid-run), then streams events as they happen.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..run_registry import REGISTRY

router = APIRouter(tags=["runs"])


@router.websocket("/api/runs/{run_id}/ws")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    handle = REGISTRY.get(run_id)
    if handle is None:
        await websocket.send_json({"type": "error", "detail": f"No run '{run_id}'"})
        await websocket.close()
        return

    await websocket.send_json({"type": "resync", "status": handle.status})
    if handle.status != "running":
        await websocket.close()
        return

    loop = asyncio.get_event_loop()
    try:
        while True:
            event = await loop.run_in_executor(None, handle.events.get)
            await websocket.send_json(event)
            if event.get("type") == "run_complete":
                break
    except WebSocketDisconnect:
        return
    await websocket.close()
