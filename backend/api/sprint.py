"""
openclaw/backend/api/sprint.py
Sprint task CRUD endpoints.  Also exposes the active sprint metadata.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user, require_manager
from backend.db.models import AuditLog, Sprint, SprintTask, User
from backend.db.session import get_db

router = APIRouter(prefix="/sprint", tags=["sprint"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SprintOut(BaseModel):
    id:         int
    name:       str
    start_date: datetime
    end_date:   datetime
    is_active:  bool

    class Config:
        from_attributes = True


class TaskIn(BaseModel):
    title:       str
    description: str = ""
    status:      str = "todo"       # todo / in_progress / done / blocked
    priority:    str = "normal"     # low / normal / high / critical
    due_date:    datetime | None = None
    user_id:     int | None = None  # assign to another team member (manager only)


class TaskOut(BaseModel):
    id:          int
    sprint_id:   int | None
    user_id:     int | None
    user_name:   str | None
    title:       str
    description: str
    status:      str
    priority:    str
    due_date:    datetime | None
    created_at:  datetime
    updated_at:  datetime

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/active", response_model=SprintOut | None)
async def get_active_sprint(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the currently active sprint, or null if none."""
    sprint = (
        await db.execute(select(Sprint).where(Sprint.is_active == True).limit(1))
    ).scalar_one_or_none()
    return sprint


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all tasks for the active sprint.
    Managers see all tasks; developers see only their own.
    """
    sprint = (
        await db.execute(select(Sprint).where(Sprint.is_active == True).limit(1))
    ).scalar_one_or_none()

    if not sprint:
        return []

    stmt = select(SprintTask).where(SprintTask.sprint_id == sprint.id)
    if current_user.role != "manager":
        stmt = stmt.where(SprintTask.user_id == current_user.id)
    stmt = stmt.order_by(SprintTask.due_date.asc().nullslast(), SprintTask.created_at.asc())

    tasks = (await db.execute(stmt)).scalars().all()
    return [await _to_out(task, db) for task in tasks]


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a task in the active sprint."""
    sprint = (
        await db.execute(select(Sprint).where(Sprint.is_active == True).limit(1))
    ).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="No active sprint")

    # Developers can only create tasks for themselves
    assignee_id = body.user_id if current_user.role == "manager" else current_user.id

    task = SprintTask(
        sprint_id=sprint.id,
        user_id=assignee_id,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        due_date=body.due_date,
    )
    db.add(task)
    db.add(AuditLog(
        user_id=current_user.id,
        action="task_created",
        table_name="sprint_tasks",
        payload=json.dumps({"title": body.title, "sprint_id": sprint.id, "assignee": assignee_id}),
    ))
    await db.commit()
    await db.refresh(task)
    return await _to_out(task, db)


@router.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    body: TaskIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(SprintTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Developers may only update their own tasks
    if current_user.role != "manager" and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your task")

    task.title       = body.title
    task.description = body.description
    task.status      = body.status
    task.priority    = body.priority
    task.due_date    = body.due_date
    task.updated_at  = datetime.now(timezone.utc)

    if current_user.role == "manager":
        task.user_id = body.user_id if body.user_id is not None else task.user_id

    db.add(AuditLog(
        user_id=current_user.id,
        action="task_updated",
        table_name="sprint_tasks",
        record_id=task_id,
        payload=json.dumps({"title": body.title, "status": body.status}),
    ))
    await db.commit()
    await db.refresh(task)
    return await _to_out(task, db)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    task = await db.get(SprintTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _to_out(task: SprintTask, db: AsyncSession) -> TaskOut:
    user_name = None
    if task.user_id:
        user = await db.get(User, task.user_id)
        user_name = user.name if user else None
    return TaskOut(
        id=task.id,
        sprint_id=task.sprint_id,
        user_id=task.user_id,
        user_name=user_name,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
