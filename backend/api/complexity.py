"""
openclaw/backend/api/complexity.py

Complexity Analysis API.

Routes:
  POST /api/complexity/analyse/{version_id}   trigger analysis (background)
  GET  /api/complexity/result/{version_id}    get full result with sections + factors
  GET  /api/complexity/list                   list all analysed documents (summary)
  GET  /api/complexity/stats                  factor frequency across all documents
  DELETE /api/complexity/{version_id}         delete result (re-run triggers fresh)
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth              import get_current_user
from backend.config                import get_settings
from backend.db.document_models    import Document, DocumentVersion
from backend.db.models             import User
from backend.db.session            import get_db, get_session
from backend.search.complexity_analyser import (
    RATING_COLORS,
    DocumentComplexityResult,
    analyse_document,
)
from backend.search.complexity_models import (
    ComplexityFactor,
    ComplexityResult,
    ComplexitySection,
)

router   = APIRouter(prefix="/complexity", tags=["complexity"])
settings = get_settings()
logger   = logging.getLogger("openclaw.api.complexity")


# ── Schemas ───────────────────────────────────────────────────────────────────

class FactorOut(BaseModel):
    id:       int
    factor:   str
    category: str
    weight:   int
    evidence: str
    class Config: from_attributes = True


class SectionOut(BaseModel):
    id:            int
    section_id:    str
    title:         str
    section_order: int
    rating:        str
    rating_color:  str
    score:         int
    confidence:    float
    summary:       str
    raw_text:      str
    factors:       list[FactorOut] = []
    class Config: from_attributes = True


class ResultOut(BaseModel):
    id:             int
    version_id:     int
    doc_id:         int
    doc_name:       str
    version_number: int
    filename:       str
    doc_category:   str
    overall_rating: str
    overall_color:  str
    overall_score:  float
    section_count:  int
    factor_summary: dict
    analyse_status: str
    analysed_at:    str | None
    sections:       list[SectionOut] = []
    class Config: from_attributes = True


class SummaryOut(BaseModel):
    version_id:     int
    doc_id:         int
    doc_name:       str
    version_number: int
    filename:       str
    doc_category:   str
    overall_rating: str
    overall_color:  str
    overall_score:  float
    section_count:  int
    analyse_status: str
    analysed_at:    str | None
    class Config: from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _result_to_out(r: ComplexityResult) -> ResultOut:
    try:
        factor_summary = json.loads(r.factor_summary) if r.factor_summary else {}
    except Exception:
        factor_summary = {}

    sections = []
    for s in r.sections:
        sections.append(SectionOut(
            id=s.id,
            section_id=s.section_id,
            title=s.title,
            section_order=s.section_order,
            rating=s.rating,
            rating_color=RATING_COLORS.get(s.rating, "#4a5a6a"),
            score=s.score,
            confidence=s.confidence,
            summary=s.summary,
            raw_text=s.raw_text,
            factors=[
                FactorOut(id=f.id, factor=f.factor, category=f.category,
                          weight=f.weight, evidence=f.evidence)
                for f in s.factors
            ],
        ))

    return ResultOut(
        id=r.id,
        version_id=r.version_id,
        doc_id=r.doc_id,
        doc_name=r.doc_name,
        version_number=r.version_number,
        filename=r.filename,
        doc_category=r.doc_category,
        overall_rating=r.overall_rating,
        overall_color=RATING_COLORS.get(r.overall_rating, "#4a5a6a"),
        overall_score=r.overall_score,
        section_count=r.section_count,
        factor_summary=factor_summary,
        analyse_status=r.analyse_status,
        analysed_at=r.analysed_at.isoformat() if r.analysed_at else None,
        sections=sections,
    )


async def _load_result(version_id: int, db: AsyncSession) -> ComplexityResult | None:
    stmt = (
        select(ComplexityResult)
        .options(
            selectinload(ComplexityResult.sections)
            .selectinload(ComplexitySection.factors)
        )
        .where(ComplexityResult.version_id == version_id)
        .order_by(ComplexityResult.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().first()


# ── Background task ───────────────────────────────────────────────────────────

async def _run_analysis(version_id: int) -> None:
    """Full pipeline: extract → analyse → persist."""
    async with get_session() as session:
        # Load version + document
        stmt = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.document))
            .where(DocumentVersion.id == version_id)
        )
        version = (await session.execute(stmt)).scalar_one_or_none()
        if not version:
            logger.error(f"[complexity] Version {version_id} not found")
            return

        doc = version.document

        # Delete old result if any — cascade deletes sections + factors
        existing = await _load_result(version_id, session)
        if existing:
            await session.execute(
                delete(ComplexityResult).where(ComplexityResult.version_id == version_id)
            )
            await session.commit()

        result_row = ComplexityResult(
            version_id=version_id,
            doc_id=doc.id,
            doc_name=doc.name,
            version_number=version.version_number,
            filename=version.filename,
            doc_category=doc.category,
            overall_rating="Pending",
            overall_score=0.0,
            section_count=0,
            analyse_status="pending",
        )
        session.add(result_row)
        await session.commit()
        await session.refresh(result_row)

    try:
        # Run analysis (may take 30-120s for large docs)
        doc_result: DocumentComplexityResult = await analyse_document(
            doc_id=doc.id,
            version_id=version_id,
            doc_name=doc.name,
            version_number=version.version_number,
            filename=version.filename,
            category=doc.category,
            file_path=version.local_path,
            mime_type=version.mime_type,
            api_key=settings.mistral_api_key,
        )

        # Persist results
        async with get_session() as session:
            r = await session.get(ComplexityResult, result_row.id)

            r.overall_rating = doc_result.overall_rating
            r.overall_score  = doc_result.overall_score
            r.section_count  = doc_result.section_count
            r.factor_summary = json.dumps(doc_result.factor_summary)
            r.analyse_status = "complete"
            r.analysed_at    = doc_result.analysed_at

            for order, sec in enumerate(doc_result.sections):
                sec_row = ComplexitySection(
                    result_id=r.id,
                    section_id=sec.section_id,
                    title=sec.title,
                    section_order=order,
                    rating=sec.rating,
                    score=sec.score,
                    confidence=sec.confidence,
                    summary=sec.summary,
                    raw_text=sec.raw_text[:5000],   # cap stored text
                )
                session.add(sec_row)
                await session.flush()

                for f in sec.factors:
                    session.add(ComplexityFactor(
                        section_id=sec_row.id,
                        factor=f.factor,
                        category=f.category,
                        weight=f.weight,
                        evidence=f.evidence,
                    ))

            await session.commit()
            logger.info(f"[complexity] ✓ version_id={version_id} — {doc_result.section_count} sections, rating={doc_result.overall_rating}")

            # Notify the uploader that analysis is complete
            try:
                from backend.utils.notifications import notify as _notify
                uploader_stmt = select(DocumentVersion).where(DocumentVersion.id == version_id)
                _ver = (await session.execute(uploader_stmt)).scalar_one_or_none()
                if _ver:
                    await _notify.complexity_complete(
                        doc_name=doc_result.doc_name,
                        overall_rating=doc_result.overall_rating,
                        version=doc_result.version_number,
                        actor_id=_ver.uploaded_by,
                        actor_name=doc_result.doc_name,
                        doc_id=doc_result.doc_id,
                        session=session,
                    )
                    await session.commit()
            except Exception as _ne:
                logger.warning(f"[complexity] Notification error (non-fatal): {_ne}")

    except Exception as exc:
        logger.error(f"[complexity] Analysis failed version_id={version_id}: {exc}")
        async with get_session() as session:
            r = await session.get(ComplexityResult, result_row.id)
            if r:
                r.analyse_status = "failed"
                r.error_message  = str(exc)[:500]
                await session.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/analyse/{version_id}", status_code=202)
async def trigger_analysis(
    version_id:       int,
    background_tasks: BackgroundTasks,
    db:  AsyncSession = Depends(get_db),
    _:   User         = Depends(get_current_user),
):
    """
    Trigger complexity analysis for a document version.
    Runs in the background. Poll GET /complexity/result/{version_id} for status.
    """
    version = await db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    # Prevent concurrent runs — check for an in-progress analysis
    existing = await _load_result(version_id, db)
    if existing and existing.analyse_status == "pending":
        return {"ok": False, "version_id": version_id, "status": "already running"}

    background_tasks.add_task(_run_analysis, version_id)
    return {"ok": True, "version_id": version_id, "status": "analysis started"}


@router.get("/result/{version_id}", response_model=ResultOut)
async def get_result(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    """Get full complexity result including all sections and factors."""
    result = await _load_result(version_id, db)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No complexity analysis found for this version. Run POST /complexity/analyse/{version_id} first."
        )
    return _result_to_out(result)


@router.get("/list", response_model=list[SummaryOut])
async def list_results(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    """List all document complexity analyses (summary, no sections/factors)."""
    stmt = (
        select(ComplexityResult)
        .order_by(ComplexityResult.analysed_at.desc())
    )
    results = (await db.execute(stmt)).scalars().all()
    return [
        SummaryOut(
            version_id=r.version_id,
            doc_id=r.doc_id,
            doc_name=r.doc_name,
            version_number=r.version_number,
            filename=r.filename,
            doc_category=r.doc_category,
            overall_rating=r.overall_rating,
            overall_color=RATING_COLORS.get(r.overall_rating, "#4a5a6a"),
            overall_score=r.overall_score,
            section_count=r.section_count,
            analyse_status=r.analyse_status,
            analysed_at=r.analysed_at.isoformat() if r.analysed_at else None,
        )
        for r in results
    ]


@router.get("/stats")
async def complexity_stats(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    """Aggregate factor frequency and rating distribution across all documents."""
    stmt    = select(ComplexityResult).where(ComplexityResult.analyse_status == "complete")
    results = (await db.execute(stmt)).scalars().all()

    rating_dist:   dict[str, int] = {}
    factor_totals: dict[str, int] = {}

    for r in results:
        rating_dist[r.overall_rating] = rating_dist.get(r.overall_rating, 0) + 1
        try:
            fs = json.loads(r.factor_summary) if r.factor_summary else {}
            for cat, count in fs.items():
                factor_totals[cat] = factor_totals.get(cat, 0) + count
        except Exception:
            pass

    return {
        "total_documents": len(results),
        "rating_distribution": rating_dist,
        "factor_frequency":    dict(sorted(factor_totals.items(), key=lambda x: -x[1])),
    }


@router.delete("/{version_id}", status_code=204)
async def delete_result(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
):
    """Delete complexity analysis result. Re-run /analyse to get a fresh result."""
    await db.execute(
        delete(ComplexityResult).where(ComplexityResult.version_id == version_id)
    )
    await db.commit()
