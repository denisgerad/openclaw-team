"""
openclaw/backend/engine/scheduler.py
Central scheduler — registers all workers, exposes trigger + status API.
"""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.db.session import get_session
from backend.engine.workers.base_worker import BaseWorker
from backend.engine.workers.risk_classifier import RiskClassifierWorker
from backend.engine.workers.digest_generator import DigestGeneratorWorker
from backend.engine.workers.reminder_engine import ReminderEngineWorker
from backend.engine.workers.workflow_triggers import WorkflowTriggersWorker

logger = logging.getLogger("openclaw.scheduler")


class _Registration:
    def __init__(self, worker: BaseWorker, trigger, trigger_on_startup: bool, enabled: bool = True):
        self.worker             = worker
        self.trigger            = trigger
        self.trigger_on_startup = trigger_on_startup
        self.enabled            = enabled


class OpenClawScheduler:

    def __init__(self, settings):
        self._settings   = settings
        self._scheduler  = AsyncIOScheduler(timezone="UTC")
        self._registry: dict[str, _Registration] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def _build_registry(self) -> dict[str, _Registration]:
        s = self._settings
        return {
            "risk_classifier": _Registration(
                worker=RiskClassifierWorker(get_session, s),
                trigger=IntervalTrigger(minutes=5),
                trigger_on_startup=True,
            ),
            "digest_generator": _Registration(
                worker=DigestGeneratorWorker(get_session, s),
                trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
                trigger_on_startup=False,
            ),
            "reminder_engine": _Registration(
                worker=ReminderEngineWorker(get_session, s),
                trigger=IntervalTrigger(hours=1),
                trigger_on_startup=True,
            ),
            "workflow_triggers": _Registration(
                worker=WorkflowTriggersWorker(get_session, s),
                trigger=IntervalTrigger(minutes=2),
                trigger_on_startup=True,
            ),
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        self._registry = self._build_registry()
        logger.info(f"OpenClaw Engine — {len(self._registry)} workers registered")

        for name, reg in self._registry.items():
            if not reg.enabled:
                logger.info(f"  [DISABLED]   {name}")
                continue
            self._scheduler.add_job(
                func=reg.worker.execute,
                trigger=reg.trigger,
                id=name,
                name=name,
                replace_existing=True,
                misfire_grace_time=60,
                coalesce=True,
            )
            logger.info(f"  [SCHEDULED]  {name} — {reg.trigger}")

        self._scheduler.start()
        logger.info("APScheduler running")

        # Run startup hooks concurrently for opted-in workers
        startup_coros = [
            reg.worker.on_startup()
            for reg in self._registry.values()
            if reg.trigger_on_startup and reg.enabled
        ]
        if startup_coros:
            logger.info(f"Running {len(startup_coros)} startup worker(s)")
            results = await asyncio.gather(*startup_coros, return_exceptions=True)
            for name, result in zip(
                [n for n, r in self._registry.items() if r.trigger_on_startup and r.enabled],
                results
            ):
                if isinstance(result, Exception):
                    logger.error(f"  [STARTUP ERROR] {name}: {result}")

        logger.info("OpenClaw Engine ready ✓")

    async def shutdown(self) -> None:
        logger.info("OpenClaw Engine shutting down")
        self._scheduler.shutdown(wait=False)
        await asyncio.gather(
            *[reg.worker.on_shutdown() for reg in self._registry.values() if reg.enabled],
            return_exceptions=True,
        )

    # ── Public API (used by FastAPI routes) ───────────────────────────────────

    async def trigger(self, worker_name: str) -> dict:
        """Manually execute a worker. Returns its state dict."""
        reg = self._registry.get(worker_name)
        if not reg:
            raise ValueError(f"Unknown worker '{worker_name}'. Available: {list(self._registry)}")
        if not reg.enabled:
            raise ValueError(f"Worker '{worker_name}' is disabled")
        state = await reg.worker.execute()
        return state.to_dict()

    async def status(self) -> dict:
        """Full status for all workers — consumed by GET /api/engine/status."""
        out = {}
        for name, reg in self._registry.items():
            job    = self._scheduler.get_job(name)
            health = await reg.worker.health_check() if reg.enabled else False
            out[name] = {
                **reg.worker.state.to_dict(),
                "description":        reg.worker.description,
                "enabled":            reg.enabled,
                "healthy":            health,
                "trigger_on_startup": reg.trigger_on_startup,
                "next_run":           job.next_run_time.isoformat() if job and job.next_run_time else None,
            }
        return out
