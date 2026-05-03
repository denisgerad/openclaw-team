"""
openclaw/backend/api/engine.py
Engine control routes + WebSocket for live dashboard updates.
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from backend.api.auth import require_manager

router = APIRouter(prefix="/engine", tags=["engine"])
logger = logging.getLogger("openclaw.api.engine")


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


ws_manager = ConnectionManager()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def engine_status(request: Request, _=Depends(require_manager)):
    """
    Full status for all workers.
    Shape per worker: name, status, last_run, last_error, run_count,
                      is_running, description, enabled, healthy, next_run,
                      trigger_on_startup
    """
    scheduler = request.app.state.scheduler
    return await scheduler.status()


@router.post("/trigger/{worker_name}")
async def trigger_worker(worker_name: str, request: Request, _=Depends(require_manager)):
    """Manually execute a specific worker immediately."""
    scheduler = request.app.state.scheduler
    try:
        result = await scheduler.trigger(worker_name)
        # Broadcast updated state to all connected dashboard clients
        await ws_manager.broadcast({"type": "worker_state", "worker": worker_name, "state": result})
        return {"ok": True, "worker": worker_name, "state": result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workers")
async def list_workers(request: Request, _=Depends(require_manager)):
    """List all registered workers with name, description, enabled, trigger_on_startup."""
    scheduler = request.app.state.scheduler
    status    = await scheduler.status()
    return [
        {
            "name":               name,
            "description":        data["description"],
            "enabled":            data["enabled"],
            "trigger_on_startup": data["trigger_on_startup"],
        }
        for name, data in status.items()
    ]


@router.websocket("/ws")
async def engine_ws(ws: WebSocket):
    """
    WebSocket for live engine state pushed to the dashboard.
    The client receives JSON messages of shape:
        { "type": "worker_state", "worker": "...", "state": {...} }
        { "type": "ping" }
    """
    await ws_manager.connect(ws)
    try:
        while True:
            await asyncio.sleep(10)
            await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
