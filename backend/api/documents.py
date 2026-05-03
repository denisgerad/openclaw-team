"""
openclaw/backend/api/documents.py

Document Management System — Step 1.
Extends v1 file manager with:
  - Direct browser upload (multipart)
  - Categories (Requirements, Design, Review, etc.)
  - Auto-versioning (same doc name + category → new version)
  - Ownership tracking (uploaded_by, owner)
  - Private flag
  - Protected download (auth required)
  - Version history per document

Routes:
  GET    /api/docs                          list all visible documents (latest version each)
  GET    /api/docs/categories               list available categories
  GET    /api/docs/{doc_id}                 get document + full version history
  GET    /api/docs/{doc_id}/versions/{v}    download a specific version
  POST   /api/docs/upload                   upload new doc or new version of existing
  PATCH  /api/docs/{doc_id}                 update name / description / category / privacy
  DELETE /api/docs/{doc_id}                 delete document + all versions (owner only)
  DELETE /api/docs/{doc_id}/versions/{v}    delete a specific version (owner only)
"""
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.db.document_models import DOCUMENT_CATEGORIES, Document, DocumentVersion
from backend.db.models import User
from backend.db.session import get_db

router = APIRouter(prefix="/docs", tags=["documents"])

# All uploaded documents stored here
DOCS_DIR = Path("./uploads/documents")
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class VersionOut(BaseModel):
    id:             int
    version_number: int
    filename:       str
    size_bytes:     int
    mime_type:      str
    change_note:    str
    is_latest:      bool
    uploaded_by_name: str
    uploaded_at:    datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id:           int
    name:         str
    category:     str
    description:  str
    is_private:   bool
    owner_name:   str
    owner_id:     int
    latest_version: int
    filename:     str
    size_bytes:   int
    uploaded_at:  datetime
    created_at:   datetime
    updated_at:   datetime
    versions:     list[VersionOut] = []

    class Config:
        from_attributes = True


class DocumentPatch(BaseModel):
    name:        str | None = None
    category:    str | None = None
    description: str | None = None
    is_private:  bool | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc_dir(doc_id: int) -> Path:
    """Filesystem folder for all versions of a document."""
    d = DOCS_DIR / str(doc_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _version_path(doc_id: int, version_number: int, filename: str) -> Path:
    return _doc_dir(doc_id) / f"v{version_number}_{filename}"


def _build_doc_out(doc: Document) -> DocumentOut:
    versions_list = list(doc.versions)
    latest = next((v for v in reversed(versions_list) if v.is_latest), None) or (versions_list[-1] if versions_list else None)
    return DocumentOut(
        id=doc.id,
        name=doc.name,
        category=doc.category,
        description=doc.description,
        is_private=doc.is_private,
        owner_name=doc.owner.name if doc.owner else "—",
        owner_id=doc.owner_id,
        latest_version=latest.version_number if latest else 0,
        filename=latest.filename if latest else "—",
        size_bytes=latest.size_bytes if latest else 0,
        uploaded_at=latest.uploaded_at if latest else doc.created_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        versions=[
            VersionOut(
                id=v.id,
                version_number=v.version_number,
                filename=v.filename,
                size_bytes=v.size_bytes,
                mime_type=v.mime_type,
                change_note=v.change_note,
                is_latest=v.is_latest,
                uploaded_by_name=v.uploader.name if v.uploader else "—",
                uploaded_at=v.uploaded_at,
            )
            for v in versions_list
        ],
    )


async def _load_doc(doc_id: int, db: AsyncSession, user: User) -> Document:
    """Load a document with versions + relationships, checking visibility."""
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Document)
        .options(
            selectinload(Document.versions).selectinload(DocumentVersion.uploader),
            selectinload(Document.owner),
        )
        .where(Document.id == doc_id)
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.is_private and doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="This document is private")
    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories():
    """Return available document categories."""
    return {"categories": DOCUMENT_CATEGORIES}


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    List all documents visible to the current user (latest version each).
    Private documents are only shown to their owner.
    Optionally filter by category.
    """
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Document)
        .options(
            selectinload(Document.versions).selectinload(DocumentVersion.uploader),
            selectinload(Document.owner),
        )
        .where(
            (Document.is_private == False) | (Document.owner_id == user.id)
        )
        .order_by(Document.updated_at.desc())
    )
    if category:
        stmt = stmt.where(Document.category == category)

    docs = (await db.execute(stmt)).scalars().all()
    return [_build_doc_out(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single document with full version history."""
    doc = await _load_doc(doc_id, db, user)
    return _build_doc_out(doc)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file:        UploadFile = File(...),
    name:        str        = Form(...),
    category:    str        = Form(...),
    description: str        = Form(""),
    change_note: str        = Form("Initial upload"),
    is_private:  bool       = Form(False),
    doc_id:      int | None = Form(None),   # if set, upload as new version of existing doc
    db:          AsyncSession = Depends(get_db),
    user:        User         = Depends(get_current_user),
):
    """
    Upload a document.

    - If doc_id is None    → creates a new Document + version 1
    - If doc_id is provided → adds a new version to the existing document

    File is saved to:  uploads/documents/{doc_id}/v{n}_{original_filename}
    """
    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Choose from: {DOCUMENT_CATEGORIES}")

    now = datetime.now(timezone.utc)

    # ── New document ──────────────────────────────────────────────────────────
    if doc_id is None:
        doc = Document(
            name=name,
            category=category,
            description=description,
            is_private=is_private,
            owner_id=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
        await db.flush()   # get doc.id before saving file
        next_version = 1

    # ── New version of existing document ─────────────────────────────────────
    else:
        from sqlalchemy.orm import selectinload
        stmt = select(Document).options(selectinload(Document.versions)).where(Document.id == doc_id)
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.is_private and doc.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Cannot version a private document you don't own")

        # Unset is_latest on all existing versions
        await db.execute(
            update(DocumentVersion)
            .where(DocumentVersion.document_id == doc_id)
            .values(is_latest=False)
        )
        next_version = max((v.version_number for v in doc.versions), default=0) + 1

        # Update document metadata
        doc.updated_at = now
        if description:
            doc.description = description

    # ── Save file to disk ─────────────────────────────────────────────────────
    safe_filename = Path(file.filename or "upload").name   # strip any path components
    dest_path = _version_path(doc.id, next_version, safe_filename)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    mime = file.content_type or mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"

    # ── Create version row ────────────────────────────────────────────────────
    version = DocumentVersion(
        document_id=doc.id,
        version_number=next_version,
        filename=safe_filename,
        local_path=str(dest_path),
        mime_type=mime,
        size_bytes=len(content),
        change_note=change_note,
        is_latest=True,
        uploaded_by=user.id,
        uploaded_at=now,
    )
    db.add(version)
    await db.commit()

    # Reload with relationships for response
    return _build_doc_out(await _load_doc(doc.id, db, user))


@router.get("/{doc_id}/versions/{version_number}/download")
async def download_version(
    doc_id:         int,
    version_number: int,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """Download a specific version of a document."""
    doc = await _load_doc(doc_id, db, user)
    version = next((v for v in doc.versions if v.version_number == version_number), None)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")

    path = Path(version.local_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(path),
        filename=version.filename,
        media_type=version.mime_type,
    )


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: int,
    body:   DocumentPatch,
    db:     AsyncSession = Depends(get_db),
    user:   User         = Depends(get_current_user),
):
    """Update document metadata. Owner or manager only."""
    doc = await _load_doc(doc_id, db, user)
    if doc.owner_id != user.id and user.role != "manager":
        raise HTTPException(status_code=403, detail="Only the document owner or a manager can edit metadata")

    if body.name        is not None: doc.name        = body.name
    if body.category    is not None:
        if body.category not in DOCUMENT_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category")
        doc.category = body.category
    if body.description is not None: doc.description = body.description
    if body.is_private  is not None: doc.is_private  = body.is_private
    doc.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return _build_doc_out(await _load_doc(doc_id, db, user))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    db:     AsyncSession = Depends(get_db),
    user:   User         = Depends(get_current_user),
):
    """Delete a document and all its versions. Owner or manager only."""
    from sqlalchemy.orm import selectinload
    stmt = select(Document).options(selectinload(Document.versions)).where(Document.id == doc_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.owner_id != user.id and user.role != "manager":
        raise HTTPException(status_code=403, detail="Only the document owner or a manager can delete")

    # Remove files from disk
    doc_folder = _doc_dir(doc_id)
    if doc_folder.exists():
        shutil.rmtree(doc_folder)

    await db.delete(doc)
    await db.commit()


@router.delete("/{doc_id}/versions/{version_number}", status_code=204)
async def delete_version(
    doc_id:         int,
    version_number: int,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """
    Delete a specific version. Owner or manager only.
    Cannot delete the only remaining version — delete the document instead.
    """
    from sqlalchemy.orm import selectinload
    stmt = select(Document).options(selectinload(Document.versions)).where(Document.id == doc_id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.owner_id != user.id and user.role != "manager":
        raise HTTPException(status_code=403, detail="Only the document owner or a manager can delete versions")

    version = next((v for v in doc.versions if v.version_number == version_number), None)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")
    if len(doc.versions) == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only version. Delete the document instead.")

    # Remove file from disk
    path = Path(version.local_path)
    if path.exists():
        os.remove(path)

    # If deleting the latest, promote the previous version
    was_latest = version.is_latest
    await db.delete(version)
    await db.flush()

    if was_latest:
        remaining = sorted([v for v in doc.versions if v.id != version.id], key=lambda v: v.version_number)
        if remaining:
            remaining[-1].is_latest = True

    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
