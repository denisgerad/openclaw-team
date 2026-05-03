"""
openclaw/backend/main.py
FastAPI application — lifespan, router mounting, CORS.

Run with:
    uvicorn backend.main:app --reload --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.session import init_db
from backend.engine.scheduler import OpenClawScheduler
from backend.utils.event_queue import start_consumer

# ── API routers
from backend.api.auth        import router as auth_router
from backend.api.status      import router as status_router
from backend.api.engine      import router as engine_router
from backend.api.notes_files import router as notes_files_router
from backend.api.sprint      import router as sprint_router
from backend.api.documents   import router as documents_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger   = logging.getLogger("openclaw")
settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{'='*60}")
    logger.info(f"  OpenClaw starting  [{settings.app_env.upper()}]")
    logger.info(f"{'='*60}")

    # 1. Create DB tables
    await init_db()
    logger.info("Database initialised ✓")

    # 2. Start event queue consumer
    consumer_task = asyncio.create_task(start_consumer())
    logger.info("Event queue consumer started ✓")

    # 3. Start engine scheduler
    scheduler = OpenClawScheduler(settings)
    await scheduler.startup()
    app.state.scheduler = scheduler

    yield   # ← application runs here

    # Graceful shutdown
    logger.info("OpenClaw shutting down…")
    consumer_task.cancel()
    await scheduler.shutdown()
    logger.info("Shutdown complete.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenClaw API",
    version="1.0.0",
    description="Team automation & intelligence platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://172.20.10.4:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api
app.include_router(auth_router,        prefix="/api")
app.include_router(status_router,      prefix="/api")
app.include_router(engine_router,      prefix="/api")
app.include_router(notes_files_router, prefix="/api")
app.include_router(sprint_router,      prefix="/api")
app.include_router(documents_router,   prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
