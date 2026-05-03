"""
openclaw/backend/engine/workers/base_worker.py
Abstract base every OpenClaw worker must extend.
"""
import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class WorkerState:
    name:       str
    status:     str      = "idle"       # idle | running | error | disabled
    last_run:   Optional[datetime] = None
    last_error: Optional[str]      = None
    run_count:  int      = 0
    is_running: bool     = False

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "status":     self.status,
            "last_run":   self.last_run.isoformat() if self.last_run else None,
            "last_error": self.last_error,
            "run_count":  self.run_count,
            "is_running": self.is_running,
        }


class BaseWorker(ABC):
    """
    Subclass and implement:
        name        → str property
        description → str property
        run()       → async method returning a result dict

    Optionally override:
        on_startup()   called once when the scheduler starts
        on_shutdown()  called on graceful shutdown
        health_check() returns True if worker is operational
    """

    def __init__(self, db_session_factory, settings):
        self._db_factory = db_session_factory
        self._settings   = settings
        self.state       = WorkerState(name=self.name)
        self._log        = logging.getLogger(f"openclaw.engine.{self.name}")

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    # ── Lifecycle (optional overrides) ────────────────────────────────────────

    async def on_startup(self) -> None:
        self.log("info", "on_startup — no-op base")

    async def on_shutdown(self) -> None:
        self.log("info", "on_shutdown — no-op base")

    @abstractmethod
    async def run(self) -> dict:
        """Core logic. Return result dict. Raise to signal failure."""
        ...

    async def health_check(self) -> bool:
        return True

    # ── Framework wrapper (do not override) ───────────────────────────────────

    async def execute(self) -> WorkerState:
        if self.state.is_running:
            self.log("warning", "Skipping — previous execution still in progress")
            return self.state

        self.state.is_running = True
        self.state.status     = "running"
        started = datetime.now(timezone.utc)

        try:
            self.log("info", "Execution started")
            result  = await self.run()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            self.state.last_run   = datetime.now(timezone.utc)
            self.state.last_error = None
            self.state.run_count += 1
            self.state.status     = "idle"
            self.log("info", f"Completed in {elapsed:.2f}s — {result}")
        except Exception as exc:
            self.state.last_error = str(exc)
            self.state.status     = "error"
            self.log("error", f"Failed: {exc}\n{traceback.format_exc()}")
        finally:
            self.state.is_running = False

        return self.state

    # ── Helpers ───────────────────────────────────────────────────────────────

    def log(self, level: str, msg: str) -> None:
        getattr(self._log, level)(f"[{self.name}] {msg}")

    def db(self):
        return self._db_factory()

    @property
    def settings(self):
        return self._settings
