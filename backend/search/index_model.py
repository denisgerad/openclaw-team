"""
openclaw/backend/search/index_model.py

Tracks embedding index state per document version in PostgreSQL.
This is the link between the relational DB and ChromaDB.

Why needed:
  - Tells us if a version has been indexed, when, and how many chunks
  - Allows re-indexing (e.g. after changing chunking strategy)
  - Provides index status for the UI (indexed / pending / failed)
  - Source of truth if ChromaDB is wiped and needs rebuilding
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, utcnow


class DocumentEmbedding(Base):
    """One row per document version — tracks its ChromaDB index state."""
    __tablename__ = "document_embeddings"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True)
    version_id:     Mapped[int]      = mapped_column(ForeignKey("document_versions.id"), unique=True, index=True)
    doc_id:         Mapped[int]      = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_count:    Mapped[int]      = mapped_column(Integer, default=0)
    indexed_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_status:   Mapped[str]      = mapped_column(String(20), default="pending")  # pending|indexed|failed|skipped
    error_message:  Mapped[str]      = mapped_column(Text, default="")
    char_count:     Mapped[int]      = mapped_column(Integer, default=0)   # chars of extracted text
