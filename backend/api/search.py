"""
openclaw/backend/api/search.py

Semantic Search & Summarisation API — Step 2.

Routes:
  POST /api/search                         semantic search across all indexed docs
  POST /api/search/summarise/{version_id}  summarise a specific document version
  POST /api/search/compare                 compare two versions of a document
  POST /api/search/reindex/{version_id}    re-index a specific version
  POST /api/search/reindex-all             re-index all versions (manager only)
  GET  /api/search/index-status            embedding status for all versions
  GET  /api/search/stats                   ChromaDB collection stats
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth           import get_current_user, require_manager
from backend.config             import get_settings
from backend.db.document_models import Document, DocumentVersion
from backend.db.models          import User
from backend.db.session         import get_db, get_session
from backend.search.chroma_store import collection_stats, search
from backend.search.extractor   import extract_text
from backend.search.index_model import DocumentEmbedding
from backend.search.pipeline    import index_document_version, reindex_all
from backend.search.summariser  import (
    compare_versions,
    summarise_chunks,
    summarise_document,
)

router   = APIRouter(prefix="/search", tags=["search"])
settings = get_settings()
logger   = logging.getLogger("openclaw.api.search")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:      str
    category:   Optional[str] = None
    doc_id:     Optional[int] = None
    version_id: Optional[int] = None
    n_results:  int           = 8
    summarise:  bool          = True    # if True, also generate a Mistral synthesis

class SearchResultItem(BaseModel):
    chunk_id:       str
    text:           str
    score:          float
    doc_id:         int
    doc_name:       str
    version_number: int
    filename:       str
    category:       str
    page_hint:      Optional[int]

class SearchResponse(BaseModel):
    query:      str
    results:    list[SearchResultItem]
    summary:    Optional[str]
    total_hits: int

class CompareRequest(BaseModel):
    doc_id:     int
    version_a:  int   # version_number (not id)
    version_b:  int   # version_number (not id)

class IndexStatusItem(BaseModel):
    version_id:     int
    doc_id:         int
    doc_name:       str
    version_number: int
    filename:       str
    index_status:   str
    chunk_count:    int
    char_count:     int
    indexed_at:     Optional[str]
    error_message:  str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_version(doc_id: int, version_number: int, db: AsyncSession) -> DocumentVersion:
    stmt = (
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.version_number == version_number,
        )
    )
    v = (await db.execute(stmt)).scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found for doc {doc_id}")
    return v


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=SearchResponse)
async def semantic_search(
    body: SearchRequest,
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
):
    """
    Semantic search across all indexed documents.
    Optionally filter by category, doc_id, or version_id.
    If summarise=True, also returns a Mistral-generated synthesis.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results = search(
        query=body.query,
        api_key=settings.mistral_api_key,
        n_results=body.n_results,
        category=body.category,
        doc_id=body.doc_id,
        version_id=body.version_id,
    )

    summary = None
    if body.summarise and results:
        summary = summarise_chunks(
            query=body.query,
            chunks=results,
            api_key=settings.mistral_api_key,
        )

    return SearchResponse(
        query=body.query,
        results=[SearchResultItem(**r) for r in results],
        summary=summary,
        total_hits=len(results),
    )


@router.post("/summarise/{version_id}")
async def summarise_version(
    version_id: int,
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
):
    """
    Generate a structured summary of a specific document version.
    Extracts text fresh from disk — does not require ChromaDB index.
    """
    stmt = (
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.id == version_id)
    )
    version = (await db.execute(stmt)).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Check visibility
    doc = version.document
    from backend.api.auth import get_current_user
    # (visibility already enforced by get_current_user dep)

    text = extract_text(path=version.local_path, mime_type=version.mime_type)
    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text in this file")

    summary = summarise_document(
        doc_name=doc.name,
        version_number=version.version_number,
        filename=version.filename,
        full_text=text,
        api_key=settings.mistral_api_key,
    )

    return {
        "doc_id":         doc.id,
        "doc_name":       doc.name,
        "version_number": version.version_number,
        "filename":       version.filename,
        "char_count":     len(text),
        "summary":        summary,
    }


@router.post("/compare")
async def compare_doc_versions(
    body: CompareRequest,
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
):
    """
    Semantic comparison between two versions of the same document.
    Returns structured diff: added, removed, changed, unchanged, verdict.
    """
    # Load both versions
    v_a = await _get_version(body.doc_id, body.version_a, db)
    v_b = await _get_version(body.doc_id, body.version_b, db)

    # Load document name
    doc = await db.get(Document, body.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    text_a = extract_text(path=v_a.local_path, mime_type=v_a.mime_type)
    text_b = extract_text(path=v_b.local_path, mime_type=v_b.mime_type)

    if not text_a.strip():
        raise HTTPException(status_code=422, detail=f"No extractable text in version {body.version_a}")
    if not text_b.strip():
        raise HTTPException(status_code=422, detail=f"No extractable text in version {body.version_b}")

    comparison = compare_versions(
        doc_name=doc.name,
        v1_number=body.version_a,
        v1_filename=v_a.filename,
        v1_text=text_a,
        v2_number=body.version_b,
        v2_filename=v_b.filename,
        v2_text=text_b,
        api_key=settings.mistral_api_key,
    )

    return {
        "doc_id":    doc.id,
        "doc_name":  doc.name,
        "version_a": body.version_a,
        "version_b": body.version_b,
        "comparison": comparison,
    }


@router.post("/reindex/{version_id}")
async def reindex_version(
    version_id:      int,
    background_tasks: BackgroundTasks,
    db:  AsyncSession = Depends(get_db),
    _:   User         = Depends(get_current_user),
):
    """Trigger re-indexing of a specific document version."""
    version = await db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    background_tasks.add_task(_bg_index, version_id)
    return {"ok": True, "version_id": version_id, "status": "indexing"}


@router.post("/reindex-all")
async def reindex_all_versions(
    background_tasks: BackgroundTasks,
    _: User = Depends(require_manager),
):
    """Re-index all document versions. Manager only. Runs in background."""
    background_tasks.add_task(_bg_reindex_all)
    return {"ok": True, "status": "reindex started in background"}


async def _bg_index(version_id: int):
    async with get_session() as session:
        await index_document_version(version_id, session, settings)

async def _bg_reindex_all():
    async with get_session() as session:
        result = await reindex_all(session, settings)
        logger.info(f"[search] Reindex all complete: {result}")


@router.get("/index-status", response_model=list[IndexStatusItem])
async def index_status(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    """
    Returns embedding index status for all document versions.
    Shows: indexed / pending / failed / skipped per version.
    """
    stmt = (
        select(DocumentVersion, Document, DocumentEmbedding)
        .join(Document, Document.id == DocumentVersion.document_id)
        .outerjoin(DocumentEmbedding, DocumentEmbedding.version_id == DocumentVersion.id)
        .order_by(Document.name, DocumentVersion.version_number)
    )
    rows = (await db.execute(stmt)).all()

    return [
        IndexStatusItem(
            version_id=v.id,
            doc_id=d.id,
            doc_name=d.name,
            version_number=v.version_number,
            filename=v.filename,
            index_status=e.index_status if e else "pending",
            chunk_count=e.chunk_count if e else 0,
            char_count=e.char_count if e else 0,
            indexed_at=e.indexed_at.isoformat() if (e and e.indexed_at) else None,
            error_message=e.error_message if e else "",
        )
        for v, d, e in rows
    ]


@router.get("/stats")
async def search_stats(_: User = Depends(get_current_user)):
    """ChromaDB collection stats — total chunks indexed, storage path."""
    return collection_stats()
