"""
document embeddings index tracking table

Revision ID: 0003
Down Revision: 0002
"""
from alembic import op
import sqlalchemy as sa

revision      = "0003"
down_revision = "0002"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "document_embeddings",
        sa.Column("id",            sa.Integer, primary_key=True),
        sa.Column("version_id",    sa.Integer, sa.ForeignKey("document_versions.id"), unique=True, nullable=False, index=True),
        sa.Column("doc_id",        sa.Integer, sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("chunk_count",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("char_count",    sa.Integer, nullable=False, server_default="0"),
        sa.Column("indexed_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_status",  sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text,       nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("document_embeddings")
