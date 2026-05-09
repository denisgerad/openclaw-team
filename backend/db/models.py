"""
openclaw/backend/db/models.py
SQLAlchemy ORM models for all tables.
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer,
    String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    __allow_unmapped__ = True


# ── Enums ─────────────────────────────────────────────────────────────────────

class RiskLevel(str, PyEnum):
    CRITICAL = "Critical"
    MODERATE = "Moderate"
    MINOR    = "Minor"
    NONE     = "None"

class SprintStatus(str, PyEnum):
    ON_TIME = "On Time"
    DELAYED = "Delayed"
    AT_RISK = "At Risk"

class IssueStatus(str, PyEnum):
    OPEN        = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED    = "Resolved"

class UserRole(str, PyEnum):
    MANAGER   = "manager"
    DEVELOPER = "developer"

class EventType(str, PyEnum):
    STATUS_UPDATED       = "status_updated"
    MEMBER_CREATED       = "member_created"
    FILE_DOWNLOAD_COMPLETE = "file_download_complete"
    NOTE_TAGGED          = "note_tagged"


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:               Mapped[int]          = mapped_column(Integer, primary_key=True, index=True)
    name:             Mapped[str]          = mapped_column(String(120))
    email:            Mapped[str]          = mapped_column(String(200), unique=True, index=True)
    hashed_password:  Mapped[str]          = mapped_column(String(200))
    role:             Mapped[str]          = mapped_column(String(20), default=UserRole.DEVELOPER)
    team_role:        Mapped[str]          = mapped_column(String(80), default="Developer")  # e.g. "Frontend", "DevOps"
    is_active:        Mapped[bool]         = mapped_column(Boolean, default=True)
    oauth_token_enc:  Mapped[str | None]   = mapped_column(Text, nullable=True)   # AES-encrypted Google OAuth token
    created_at:       Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utcnow)

    statuses:  "list[StatusUpdate]" = relationship("StatusUpdate", back_populates="user", cascade="all, delete-orphan")
    notes:     "list[Note]"         = relationship("Note",         back_populates="user", cascade="all, delete-orphan")
    files:     "list[FileRecord]"   = relationship("FileRecord",   back_populates="user", cascade="all, delete-orphan")


# ── Status Updates ────────────────────────────────────────────────────────────

class StatusUpdate(Base):
    __tablename__ = "status_updates"

    id:                    Mapped[int]        = mapped_column(Integer, primary_key=True, index=True)
    user_id:               Mapped[int]        = mapped_column(ForeignKey("users.id"), index=True)

    risk_level:            Mapped[str]        = mapped_column(String(20), default=RiskLevel.NONE)
    risk_level_confirmed:  Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_detail:           Mapped[str]        = mapped_column(Text, default="")

    sprint_status:         Mapped[str]        = mapped_column(String(20), default=SprintStatus.ON_TIME)
    issue:                 Mapped[str]        = mapped_column(String(120), default="—")
    issue_status:          Mapped[str]        = mapped_column(String(20), default=IssueStatus.RESOLVED)
    comments:              Mapped[str]        = mapped_column(Text, default="")

    classified_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:            Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:            Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: "User" = relationship("User", back_populates="statuses")


# ── Notes ─────────────────────────────────────────────────────────────────────

class Note(Base):
    __tablename__ = "notes"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    user_id:    Mapped[int]      = mapped_column(ForeignKey("users.id"), index=True)
    title:      Mapped[str]      = mapped_column(String(200))
    content:    Mapped[str]      = mapped_column(Text, default="")
    tags:       Mapped[str]      = mapped_column(String(300), default="")   # comma-separated
    pinned:     Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: "User" = relationship("User", back_populates="notes")


# ── File Records ──────────────────────────────────────────────────────────────

class FileRecord(Base):
    __tablename__ = "file_records"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    user_id:         Mapped[int]      = mapped_column(ForeignKey("users.id"), index=True)
    filename:        Mapped[str]      = mapped_column(String(300))
    source_url:      Mapped[str]      = mapped_column(Text)
    local_path:      Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes:      Mapped[int]      = mapped_column(Integer, default=0)
    download_status: Mapped[str]      = mapped_column(String(20), default="pending")  # pending|downloading|complete|failed
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: "User" = relationship("User", back_populates="files")


# ── Event Log (consumed by WorkflowTriggersWorker) ───────────────────────────

class EventLog(Base):
    __tablename__ = "event_log"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    event_type:   Mapped[str]           = mapped_column(String(60), index=True)
    payload:      Mapped[str]           = mapped_column(Text, default="{}")   # JSON string
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Reminders Sent (dedup log) ────────────────────────────────────────────────

class ReminderSent(Base):
    __tablename__ = "reminders_sent"

    id:        Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:   Mapped[int]      = mapped_column(ForeignKey("users.id"), index=True)
    reason:    Mapped[str]      = mapped_column(String(60))
    sent_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Sprint ────────────────────────────────────────────────────────────────────

class Sprint(Base):
    __tablename__ = "sprints"

    id:        Mapped[int]      = mapped_column(Integer, primary_key=True)
    name:      Mapped[str]      = mapped_column(String(80))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date:   Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active:  Mapped[bool]    = mapped_column(Boolean, default=True)

    tasks: "list[SprintTask]" = relationship("SprintTask", back_populates="sprint", cascade="all, delete-orphan")


# ── Sprint Tasks ──────────────────────────────────────────────────────────────

class SprintTask(Base):
    __tablename__ = "sprint_tasks"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    sprint_id:   Mapped[int | None]    = mapped_column(ForeignKey("sprints.id"), nullable=True, index=True)
    user_id:     Mapped[int | None]    = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title:       Mapped[str]           = mapped_column(String(300))
    description: Mapped[str]           = mapped_column(Text, default="")
    status:      Mapped[str]           = mapped_column(String(30), default="todo")   # todo / in_progress / done / blocked
    priority:    Mapped[str]           = mapped_column(String(20), default="normal") # low / normal / high / critical
    due_date:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sprint: "Sprint"   = relationship("Sprint", back_populates="tasks")
    user:   "User | None" = relationship("User")


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    user_id:    Mapped[int | None]    = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action:     Mapped[str]           = mapped_column(String(100), index=True)
    table_name: Mapped[str]           = mapped_column(String(60))
    record_id:  Mapped[int | None]    = mapped_column(Integer, nullable=True)
    payload:    Mapped[str]           = mapped_column(Text, default="{}")
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utcnow)


# ── Document Management — imported so Base.metadata includes their tables ─────
from backend.db.document_models import Document, DocumentVersion  # noqa: E402, F401
from backend.search.index_model import DocumentEmbedding          # noqa: E402, F401
from backend.db.notification_models import Notification, NotificationRead  # noqa: E402, F401
