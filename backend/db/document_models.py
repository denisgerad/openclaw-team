"""
openclaw/backend/db/document_models.py

Document Management System models — Step 1 extension.
These are ADDITIVE to v1 models. FileRecord stays unchanged.

Tables added:
  documents         — master document record (name, category, description, owner)
  document_versions — each upload is a version (file on disk, size, uploader, notes)

Design decisions:
  - A "document" is a logical entity (e.g. "System Requirements v1")
  - Each upload creates a new document_version row
  - Latest version is tracked via `is_latest` flag + version_number
  - Files stored on disk at: uploads/documents/{category}/{doc_id}/v{n}_{filename}
  - Metadata (owner, timestamps, size) stored in PostgreSQL
  - Private flag: private=True means only uploader can see it
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models import Base, utcnow


# ── Document categories ───────────────────────────────────────────────────────

DOCUMENT_CATEGORIES = [
    "Requirements",
    "Design",
    "Review",
    "Report",
    "Change Request",
    "Test Plan",
    "Architecture",
    "Meeting Notes",
    "Other",
]


# ── Document (logical entity) ─────────────────────────────────────────────────

class Document(Base):
    """
    Represents a logical document — not a file.
    A document can have multiple versions, each pointing to a file on disk.
    """
    __tablename__ = "documents"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    name:         Mapped[str]      = mapped_column(String(300), index=True)       # e.g. "System Requirements"
    category:     Mapped[str]      = mapped_column(String(60),  index=True)       # e.g. "Requirements"
    description:  Mapped[str]      = mapped_column(Text, default="")              # optional description
    is_private:   Mapped[bool]     = mapped_column(Boolean, default=False)        # True = owner-only
    owner_id:     Mapped[int]      = mapped_column(ForeignKey("users.id"), index=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    owner:    Mapped["User"]                  = relationship("User", foreign_keys=[owner_id])
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )


# ── Document Version (physical file) ─────────────────────────────────────────

class DocumentVersion(Base):
    """
    Each upload of a document creates a new version row.
    The actual file lives on disk; this row holds its metadata.
    """
    __tablename__ = "document_versions"

    id:             Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)
    document_id:    Mapped[int]         = mapped_column(ForeignKey("documents.id"), index=True)
    version_number: Mapped[int]         = mapped_column(Integer, default=1)        # auto-incremented per document
    filename:       Mapped[str]         = mapped_column(String(300))                # original filename
    local_path:     Mapped[str]         = mapped_column(Text)                       # absolute path on disk
    mime_type:      Mapped[str]         = mapped_column(String(120), default="application/octet-stream")
    size_bytes:     Mapped[int]         = mapped_column(Integer, default=0)
    change_note:    Mapped[str]         = mapped_column(Text, default="")           # "what changed in this version"
    is_latest:      Mapped[bool]        = mapped_column(Boolean, default=True)      # only one True per document
    uploaded_by:    Mapped[int]         = mapped_column(ForeignKey("users.id"), index=True)
    uploaded_at:    Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="versions")
    uploader: Mapped["User"]     = relationship("User", foreign_keys=[uploaded_by])
