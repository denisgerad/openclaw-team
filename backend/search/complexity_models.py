"""
openclaw/backend/search/complexity_models.py

Database models for complexity analysis results.

Tables:
  complexity_results  — one row per document version analysis run
  complexity_sections — one row per section within a document
  complexity_factors  — one row per factor within a section

Design:
  - Re-analysis replaces previous results (delete + insert)
  - Sections link back to version via complexity_result_id
  - Factors link to sections via complexity_section_id
  - raw_text stored on section so UI can show drill-down without re-extracting
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, List

from backend.db.models import Base, utcnow


class ComplexityResult(Base):
    """Document-level complexity analysis — one per version analysis run."""
    __tablename__ = "complexity_results"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True)
    version_id:     Mapped[int]      = mapped_column(ForeignKey("document_versions.id"), index=True)
    doc_id:         Mapped[int]      = mapped_column(ForeignKey("documents.id"), index=True)
    doc_name:       Mapped[str]      = mapped_column(String(300))
    version_number: Mapped[int]      = mapped_column(Integer)
    filename:       Mapped[str]      = mapped_column(String(300))
    doc_category:   Mapped[str]      = mapped_column(String(60))   # Requirements | Design | etc.
    overall_rating: Mapped[str]      = mapped_column(String(20))   # Simple|Moderate|Complex|Critical
    overall_score:  Mapped[float]    = mapped_column(Float, default=0.0)
    section_count:  Mapped[int]      = mapped_column(Integer, default=0)
    factor_summary: Mapped[str]      = mapped_column(Text, default="{}")   # JSON: {category: count}
    analyse_status: Mapped[str]      = mapped_column(String(20), default="pending")  # pending|complete|failed
    error_message:  Mapped[str]      = mapped_column(Text, default="")
    analysed_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sections: Mapped[List["ComplexitySection"]] = relationship(
        "ComplexitySection", back_populates="result",
        cascade="all, delete-orphan",
        order_by="ComplexitySection.section_order",
    )


class ComplexitySection(Base):
    """Section-level result — one per requirement/design entry."""
    __tablename__ = "complexity_sections"

    id:           Mapped[int]   = mapped_column(Integer, primary_key=True)
    result_id:    Mapped[int]   = mapped_column(ForeignKey("complexity_results.id"), index=True)
    section_id:   Mapped[str]   = mapped_column(String(30))    # e.g. "REQ-007"
    title:        Mapped[str]   = mapped_column(String(300))
    section_order:Mapped[int]   = mapped_column(Integer, default=0)
    rating:       Mapped[str]   = mapped_column(String(20))    # Simple|Moderate|Complex|Critical
    score:        Mapped[int]   = mapped_column(Integer, default=0)
    confidence:   Mapped[float] = mapped_column(Float, default=0.0)
    summary:      Mapped[str]   = mapped_column(Text, default="")
    raw_text:     Mapped[str]   = mapped_column(Text, default="")   # section body for drill-down

    result:  Mapped["ComplexityResult"]          = relationship("ComplexityResult", back_populates="sections")
    factors: Mapped[List["ComplexityFactor"]]    = relationship(
        "ComplexityFactor", back_populates="section",
        cascade="all, delete-orphan",
    )


class ComplexityFactor(Base):
    """Individual complexity factor within a section."""
    __tablename__ = "complexity_factors"

    id:          Mapped[int]   = mapped_column(Integer, primary_key=True)
    section_id:  Mapped[int]   = mapped_column(ForeignKey("complexity_sections.id"), index=True)
    factor:      Mapped[str]   = mapped_column(String(200))    # factor name
    category:    Mapped[str]   = mapped_column(String(80))     # factor category
    weight:      Mapped[int]   = mapped_column(Integer, default=1)  # 1|2|3
    evidence:    Mapped[str]   = mapped_column(Text, default="")    # supporting quote

    section: Mapped["ComplexitySection"] = relationship("ComplexitySection", back_populates="factors")
