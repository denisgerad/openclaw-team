"""
openclaw/backend/search/startup_indexer.py

Called from app lifespan on startup.
Finds any document versions not yet indexed (no DocumentEmbedding row,
or status=pending/failed) and queues them for indexing.

This ensures that:
  1. Documents uploaded before Step 2 was added get indexed automatically
  2. Any versions that failed indexing are retried on restart
  3. No manual /reindex-all call needed after first deployment of Step 2
"""
import asyncio
import logging

from sqlalchemy import select, outerjoin

from backend.db.document_models import DocumentVersion
from backend.db.session         import get_session
from backend.search.index_model import DocumentEmbedding
from backend.search.pipeline    import index_document_version

logger = logging.getLogger("openclaw.search.startup")


async def index_pending_on_startup(settings) -> None:
    """
    Run at app startup — index all versions that are not yet indexed.
    Runs concurrently with a semaphore to avoid overwhelming Mistral API.
    """
    async with get_session() as session:
        # Find versions with no embedding row OR status != indexed
        stmt = (
            select(DocumentVersion)
            .outerjoin(DocumentEmbedding, DocumentEmbedding.version_id == DocumentVersion.id)
            .where(
                (DocumentEmbedding.id.is_(None)) |
                (DocumentEmbedding.index_status.in_(["pending", "failed"]))
            )
        )
        versions = (await session.execute(stmt)).scalars().all()

    if not versions:
        logger.info("[startup_indexer] All versions already indexed — nothing to do")
        return

    logger.info(f"[startup_indexer] Found {len(versions)} version(s) to index on startup")

    # Semaphore: max 2 concurrent Mistral embed calls at startup
    sem = asyncio.Semaphore(2)

    async def index_one(version_id: int):
        async with sem:
            async with get_session() as session:
                await index_document_version(version_id, session, settings)

    tasks = [index_one(v.id) for v in versions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if not isinstance(r, Exception))
    errors  = sum(1 for r in results if isinstance(r, Exception))
    logger.info(f"[startup_indexer] Startup indexing complete — {success} indexed, {errors} error(s)")
