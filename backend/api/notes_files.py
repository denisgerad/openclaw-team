"""
openclaw/backend/api/notes_files.py
Notes CRUD and file download manager routes.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.db.models import EventLog, FileRecord, Note, User
from backend.db.session import get_db

router = APIRouter(tags=["notes_files"])

DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteIn(BaseModel):
    title:   str
    content: str = ""
    tags:    str = ""
    pinned:  bool = False

class NoteOut(BaseModel):
    id:         int
    title:      str
    content:    str
    tags:       str
    pinned:     bool
    updated_at: datetime
    class Config:
        from_attributes = True


@router.get("/notes", response_model=list[NoteOut])
async def list_notes(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Note).where(Note.user_id == user.id).order_by(Note.pinned.desc(), Note.updated_at.desc())
    notes = (await db.execute(stmt)).scalars().all()
    return notes


@router.post("/notes", response_model=NoteOut, status_code=201)
async def create_note(body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    note = Note(user_id=user.id, **body.model_dump())
    db.add(note)

    # Write event if tagged #urgent
    if "#urgent" in body.tags:
        db.add(EventLog(
            event_type="note_tagged",
            payload=json.dumps({"user_id": user.id, "user_name": user.name, "user_email": user.email, "title": body.title, "tags": body.tags}),
        ))

    await db.commit()
    await db.refresh(note)
    return note


@router.put("/notes/{note_id}", response_model=NoteOut)
async def update_note(note_id: int, body: NoteIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    note = await db.get(Note, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(status_code=404, detail="Note not found")
    for k, v in body.model_dump().items():
        setattr(note, k, v)
    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    note = await db.get(Note, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()


# ── File Download Manager ─────────────────────────────────────────────────────

class FileIn(BaseModel):
    source_url: str
    filename:   str = ""

class FileOut(BaseModel):
    id:              int
    filename:        str
    source_url:      str
    size_bytes:      int
    download_status: str
    created_at:      datetime
    completed_at:    datetime | None
    class Config:
        from_attributes = True


@router.get("/files", response_model=list[FileOut])
async def list_files(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(FileRecord).where(FileRecord.user_id == user.id).order_by(FileRecord.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/files/download", response_model=FileOut, status_code=202)
async def queue_download(
    body: FileIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filename = body.filename or body.source_url.split("/")[-1] or "download"
    record   = FileRecord(
        user_id=user.id,
        filename=filename,
        source_url=body.source_url,
        download_status="pending",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    background_tasks.add_task(_do_download, record.id, body.source_url, filename, user)
    return record


async def _do_download(record_id: int, url: str, filename: str, user: User):
    """Background download task — streams file to disk, updates DB."""
    from backend.db.session import get_session
    dest = DOWNLOAD_DIR / f"{user.id}_{filename}"

    async with get_session() as session:
        record = await session.get(FileRecord, record_id)
        record.download_status = "downloading"
        record.local_path = str(dest)
        await session.commit()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            total = 0
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        total += len(chunk)

        async with get_session() as session:
            record = await session.get(FileRecord, record_id)
            record.download_status = "complete"
            record.size_bytes      = total
            record.completed_at    = datetime.now(timezone.utc)
            session.add(EventLog(
                event_type="file_download_complete",
                payload=json.dumps({"user_id": user.id, "user_name": user.name, "user_email": user.email, "filename": filename}),
            ))
            await session.commit()

    except Exception as exc:
        async with get_session() as session:
            record = await session.get(FileRecord, record_id)
            record.download_status = "failed"
            await session.commit()
