"""
document management tables

Revision ID: 0002
Down Revision: 0001
"""
from alembic import op
import sqlalchemy as sa

revision      = "0002"
down_revision = "0001"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id",          sa.Integer,  primary_key=True),
        sa.Column("name",        sa.String(300), nullable=False, index=True),
        sa.Column("category",    sa.String(60),  nullable=False, index=True),
        sa.Column("description", sa.Text,        nullable=False, server_default=""),
        sa.Column("is_private",  sa.Boolean,     nullable=False, server_default=sa.false()),
        sa.Column("owner_id",    sa.Integer,     sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "document_versions",
        sa.Column("id",             sa.Integer, primary_key=True),
        sa.Column("document_id",    sa.Integer, sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("filename",       sa.String(300), nullable=False),
        sa.Column("local_path",     sa.Text,        nullable=False),
        sa.Column("mime_type",      sa.String(120), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes",     sa.Integer,     nullable=False, server_default="0"),
        sa.Column("change_note",    sa.Text,        nullable=False, server_default=""),
        sa.Column("is_latest",      sa.Boolean,     nullable=False, server_default=sa.true()),
        sa.Column("uploaded_by",    sa.Integer,     sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("uploaded_at",    sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("document_versions")
    op.drop_table("documents")
