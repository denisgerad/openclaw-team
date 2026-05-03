"""
openclaw/backend/api/status.py
CRUD for team status updates + event log writes.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.db.models import EventLog, StatusUpdate, User
from backend.db.session import get_db

router = APIRouter(prefix="/status", tags=["status"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class StatusIn(BaseModel):
    risk_level:    str = "None"
    risk_detail:   str = ""
    sprint_status: str = "On Time"
    issue:         str = "—"
    issue_status:  str = "Resolved"
    comments:      str = ""

class StatusOut(BaseModel):
    id:                    int
    user_id:               int
    user_name:             str
    user_team_role:        str
    risk_level:            str
    risk_level_confirmed:  str | None
    risk_detail:           str
    sprint_status:         str
    issue:                 str
    issue_status:          str
    comments:              str
    updated_at:            datetime

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _latest_per_user(session: AsyncSession) -> list[tuple[StatusUpdate, User]]:
    sub = (
        select(StatusUpdate.user_id, func.max(StatusUpdate.updated_at).label("latest"))
        .group_by(StatusUpdate.user_id)
        .subquery()
    )
    stmt = (
        select(StatusUpdate, User)
        .join(sub, (StatusUpdate.user_id == sub.c.user_id) & (StatusUpdate.updated_at == sub.c.latest))
        .join(User, User.id == StatusUpdate.user_id)
        .where(User.is_active == True)
        .order_by(StatusUpdate.updated_at.desc())
    )
    return (await session.execute(stmt)).all()


def _to_out(status: StatusUpdate, user: User) -> StatusOut:
    return StatusOut(
        id=status.id,
        user_id=user.id,
        user_name=user.name,
        user_team_role=user.team_role,
        risk_level=status.risk_level,
        risk_level_confirmed=status.risk_level_confirmed,
        risk_detail=status.risk_detail,
        sprint_status=status.sprint_status,
        issue=status.issue,
        issue_status=status.issue_status,
        comments=status.comments,
        updated_at=status.updated_at,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/team", response_model=list[StatusOut])
async def get_team_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Latest status for every active team member."""
    rows = await _latest_per_user(db)
    return [_to_out(s, u) for s, u in rows]


@router.get("/member/{user_id}", response_model=list[StatusOut])
async def get_member_history(
    user_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Full history for one member (latest first)."""
    stmt = (
        select(StatusUpdate, User)
        .join(User, User.id == StatusUpdate.user_id)
        .where(StatusUpdate.user_id == user_id)
        .order_by(StatusUpdate.updated_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [_to_out(s, u) for s, u in rows]


@router.post("/update", response_model=StatusOut, status_code=201)
async def update_status(
    body: StatusIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new status update row for the calling user.
    Also writes to event_log so WorkflowTriggersWorker can react.
    """
    now = datetime.now(timezone.utc)
    status = StatusUpdate(
        user_id=current_user.id,
        risk_level=body.risk_level,
        risk_detail=body.risk_detail,
        sprint_status=body.sprint_status,
        issue=body.issue,
        issue_status=body.issue_status,
        comments=body.comments,
        updated_at=now,
        created_at=now,
    )
    db.add(status)

    # Write to event log for workflow engine
    db.add(EventLog(
        event_type="status_updated",
        payload=json.dumps({
            "user_id":       current_user.id,
            "user_name":     current_user.name,
            "team_role":     current_user.team_role,
            "user_email":    current_user.email,
            "risk_level":    body.risk_level,
            "risk_detail":   body.risk_detail,
            "sprint_status": body.sprint_status,
            "comments":      body.comments,
        }),
    ))

    await db.commit()
    await db.refresh(status)
    return _to_out(status, current_user)
