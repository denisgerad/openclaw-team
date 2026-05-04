"""
openclaw/backend/search/pipeline.py

Orchestrates the full indexing pipeline for a document version:
  1. Extract text from file on disk
  2. Chunk text into overlapping segments
  3. Embed chunks via Mistral
  4. Store in ChromaDB
  5. Update document_embeddings row in PostgreSQL

Called from:
  - documents.py upload route (as a BackgroundTask after file is saved)
  - The re-index API endpoint
  - The search API when a version is marked pending

Usage:
    from backend.search.pipeline import index_document_version
    await index_document_version(version_id=42, db_session=session, settings=settings)
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.document_models import Document, DocumentVersion
from backend.search.chroma_store import delete_version, index_version
from backend.search.chunker      import chunk_text
from backend.search.extractor    import extract_text
from backend.search.index_model  import DocumentEmbedding

logger = logging.getLogger("openclaw.search.pipeline")


async def index_document_version(
    version_id: int,
    session:    AsyncSession,
    settings,
) -> DocumentEmbedding:
    """
    Full pipeline: extract → chunk → embed → store.
    Creates or updates the DocumentEmbedding row.
    Never raises — errors are recorded in the embedding row.
    """
    from sqlalchemy.orm import selectinload

    # ── Load version + document ───────────────────────────────────────────────
    stmt = (
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.id == version_id)
    )
    version = (await session.execute(stmt)).scalar_one_or_none()
    if not version:
        logger.error(f"[pipeline] Version {version_id} not found")
        return None

    doc = version.document

    # ── Get or create embedding row ───────────────────────────────────────────
    emb_stmt = select(DocumentEmbedding).where(DocumentEmbedding.version_id == version_id)
    emb = (await session.execute(emb_stmt)).scalar_one_or_none()
    if not emb:
        emb = DocumentEmbedding(version_id=version_id, doc_id=doc.id)
        session.add(emb)

    emb.index_status = "pending"
    await session.commit()

    try:
        logger.info(f"[pipeline] Indexing version_id={version_id} doc='{doc.name}' file='{version.filename}'")

        # ── Step 1: Extract text ──────────────────────────────────────────────
        text = extract_text(path=version.local_path, mime_type=version.mime_type)
        if not text.strip():
            logger.warning(f"[pipeline] No text extracted from {version.filename} — marking skipped")
            emb.index_status  = "skipped"
            emb.error_message = "No extractable text (binary or image-only file)"
            emb.indexed_at    = datetime.now(timezone.utc)
            await session.commit()
            return emb

        emb.char_count = len(text)

        # ── Step 2: Chunk ─────────────────────────────────────────────────────
        chunks = chunk_text(text)
        logger.info(f"[pipeline] {len(chunks)} chunk(s) from {len(text)} chars")

        # ── Step 3 + 4: Embed + store in ChromaDB ────────────────────────────
        count = index_version(
            version_id=version_id,
            doc_id=doc.id,
            version_number=version.version_number,
            doc_name=doc.name,
            category=doc.category,
            filename=version.filename,
            chunks=chunks,
            api_key=settings.mistral_api_key,
        )

        # ── Step 5: Update embedding row ──────────────────────────────────────
        emb.chunk_count   = count
        emb.index_status  = "indexed"
        emb.error_message = ""
        emb.indexed_at    = datetime.now(timezone.utc)
        await session.commit()

        logger.info(f"[pipeline] ✓ version_id={version_id} indexed {count} chunk(s)")

    except Exception as exc:
        logger.error(f"[pipeline] Failed version_id={version_id}: {exc}")
        emb.index_status  = "failed"
        emb.error_message = str(exc)[:500]
        emb.indexed_at    = datetime.now(timezone.utc)
        await session.commit()

    return emb


async def reindex_all(session: AsyncSession, settings) -> dict:
    """
    Re-index all document versions that are pending, failed, or explicitly requested.
    Called from the search admin endpoint or on startup if needed.
    """
    stmt     = select(DocumentVersion)
    versions = (await session.execute(stmt)).scalars().all()
    results  = {"total": len(versions), "indexed": 0, "skipped": 0, "failed": 0}

    for v in versions:
        emb = await index_document_version(v.id, session, settings)
        if emb:
            if emb.index_status == "indexed": results["indexed"] += 1
            elif emb.index_status == "skipped": results["skipped"] += 1
            elif emb.index_status == "failed": results["failed"] += 1

    return results
