"""
openclaw/backend/api/notifications.py

Notification API routes.

Routes:
  GET  /api/notifications           list notifications for current user
  GET  /api/notifications/count     unread count (for bell badge polling)
  POST /api/notifications/read      mark one or all as read
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.db.models import User
from backend.db.session import get_db
from backend.utils.notifications import (
    get_notifications_for_user,
    get_unread_count,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id:          int
    notif_type:  str
    title:       str
    body:        str
    link_page:   str
    link_id:     Optional[int]
    actor_name:  str
    scope:       str
    is_read:     bool
    created_at:  str


class MarkReadRequest(BaseModel):
    notif_id: Optional[int] = None   # None = mark all


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    limit:       int  = 30,
    unread_only: bool = False,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """
    Return notifications visible to the current user.
    Includes both team-scoped and user-targeted notifications.
    Ordered by newest first.
    """
    return await get_notifications_for_user(
        user_id=user.id,
        session=db,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/count")
async def unread_count(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """
    Returns unread notification count for the bell badge.
    Lightweight — polled every 30 seconds by the frontend.
    """
    count = await get_unread_count(user_id=user.id, session=db)
    return {"unread": count}


@router.post("/read")
async def mark_notifications_read(
    body: MarkReadRequest,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """
    Mark one notification (notif_id set) or all (notif_id null) as read.
    Returns count of newly-marked records.
    """
    marked = await mark_read(
        user_id=user.id,
        notif_id=body.notif_id,
        session=db,
    )
    await db.commit()
    return {"marked": marked}
