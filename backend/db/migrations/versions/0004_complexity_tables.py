"""
complexity analysis tables

Revision ID: 0004
Down Revision: 0003
"""
from alembic import op
import sqlalchemy as sa

revision      = "0004"
down_revision = "0003"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "complexity_results",
        sa.Column("id",             sa.Integer, primary_key=True),
        sa.Column("version_id",     sa.Integer, sa.ForeignKey("document_versions.id"), nullable=False, index=True),
        sa.Column("doc_id",         sa.Integer, sa.ForeignKey("documents.id"),         nullable=False, index=True),
        sa.Column("doc_name",       sa.String(300), nullable=False),
        sa.Column("version_number", sa.Integer,     nullable=False),
        sa.Column("filename",       sa.String(300), nullable=False),
        sa.Column("doc_category",   sa.String(60),  nullable=False),
        sa.Column("overall_rating", sa.String(20),  nullable=False, server_default="Pending"),
        sa.Column("overall_score",  sa.Float,       nullable=False, server_default="0"),
        sa.Column("section_count",  sa.Integer,     nullable=False, server_default="0"),
        sa.Column("factor_summary", sa.Text,        nullable=False, server_default="{}"),
        sa.Column("analyse_status", sa.String(20),  nullable=False, server_default="pending"),
        sa.Column("error_message",  sa.Text,        nullable=False, server_default=""),
        sa.Column("analysed_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "complexity_sections",
        sa.Column("id",            sa.Integer, primary_key=True),
        sa.Column("result_id",     sa.Integer, sa.ForeignKey("complexity_results.id"), nullable=False, index=True),
        sa.Column("section_id",    sa.String(30),  nullable=False),
        sa.Column("title",         sa.String(300), nullable=False),
        sa.Column("section_order", sa.Integer,     nullable=False, server_default="0"),
        sa.Column("rating",        sa.String(20),  nullable=False),
        sa.Column("score",         sa.Integer,     nullable=False, server_default="0"),
        sa.Column("confidence",    sa.Float,       nullable=False, server_default="0"),
        sa.Column("summary",       sa.Text,        nullable=False, server_default=""),
        sa.Column("raw_text",      sa.Text,        nullable=False, server_default=""),
    )

    op.create_table(
        "complexity_factors",
        sa.Column("id",         sa.Integer, primary_key=True),
        sa.Column("section_id", sa.Integer, sa.ForeignKey("complexity_sections.id"), nullable=False, index=True),
        sa.Column("factor",     sa.String(200), nullable=False),
        sa.Column("category",   sa.String(80),  nullable=False),
        sa.Column("weight",     sa.Integer,     nullable=False, server_default="1"),
        sa.Column("evidence",   sa.Text,        nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("complexity_factors")
    op.drop_table("complexity_sections")
    op.drop_table("complexity_results")
