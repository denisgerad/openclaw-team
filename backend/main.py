"""
openclaw/backend/main.py
FastAPI application — lifespan, router mounting, CORS, upload limits.

Run with:
    uvicorn backend.main:app --reload --port 8000

For remote developer access (LAN):
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from backend.api.search      import router as search_router
from backend.api.complexity     import router as complexity_router
from backend.api.notifications import router as notifications_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger   = logging.getLogger("openclaw")
settings = get_settings()


# ── Upload size enforcement middleware ────────────────────────────────────────

class UploadSizeLimitMiddleware:
    """
    Reject requests whose Content-Length exceeds MAX_UPLOAD_MB before
    the body is read into memory. Returns HTTP 413 with a clear message.
    """
    def __init__(self, app, max_bytes: int):
        self.app       = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            cl = headers.get(b"content-length")
            if cl and int(cl) > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"File too large. Maximum allowed size is "
                            f"{self.max_bytes // (1024*1024)} MB. "
                            f"Received {int(cl) // (1024*1024)} MB."
                        )
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"  OpenClaw starting  [{settings.app_env.upper()}]")
    logger.info(f"  Server URL : {settings.server_url}")
    logger.info(f"  Max upload : {settings.max_upload_mb} MB")
    logger.info(f"  CORS origins: {settings.allowed_origins_list}")
    logger.info("=" * 60)

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

    # 4. Index any unindexed document versions (Step 2 — runs in background)
    from backend.search.startup_indexer import index_pending_on_startup
    asyncio.create_task(index_pending_on_startup(settings))
    logger.info("Startup document indexer queued ✓")

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

# Upload size limit — applied before any route handler reads the body
app.add_middleware(UploadSizeLimitMiddleware, max_bytes=settings.max_upload_bytes)

# CORS — driven by ALLOWED_ORIGINS in .env so any LAN machine can be added
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
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
app.include_router(search_router,      prefix="/api")
app.include_router(complexity_router,    prefix="/api")
app.include_router(notifications_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "OpenClaw API — use /api/* routes or access the frontend at port 3000"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/api/server-info")
async def server_info():
    """
    Returns public server configuration.
    Used by the CLI to validate connection and display upload limits.
    No authentication required.
    """
    return {
        "app":           settings.app_name,
        "version":       "1.0.0",
        "env":           settings.app_env,
        "max_upload_mb": settings.max_upload_mb,
        "server_url":    settings.server_url,
        "categories": [
            "Requirements", "Design", "Review", "Report",
            "Change Request", "Test Plan", "Architecture",
            "Meeting Notes", "Other",
        ],
    }
