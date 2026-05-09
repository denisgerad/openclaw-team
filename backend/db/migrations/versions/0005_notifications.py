"""
notifications and notification_reads tables

Revision ID: 0005
Down Revision: 0004
"""
from alembic import op
import sqlalchemy as sa

revision      = "0005"
down_revision = "0004"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id",             sa.Integer, primary_key=True, index=True),
        sa.Column("notif_type",     sa.String(40),  nullable=False, index=True),
        sa.Column("title",          sa.String(200), nullable=False),
        sa.Column("body",           sa.Text,        nullable=False, server_default=""),
        sa.Column("link_page",      sa.String(40),  nullable=False, server_default=""),
        sa.Column("link_id",        sa.Integer,     nullable=True),
        sa.Column("actor_id",       sa.Integer,     sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("actor_name",     sa.String(120), nullable=False, server_default=""),
        sa.Column("scope",          sa.String(10),  nullable=False, server_default="team"),
        sa.Column("target_user_id", sa.Integer,     sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "notification_reads",
        sa.Column("id",              sa.Integer, primary_key=True),
        sa.Column("notification_id", sa.Integer, sa.ForeignKey("notifications.id"), nullable=False, index=True),
        sa.Column("user_id",         sa.Integer, sa.ForeignKey("users.id"),         nullable=False, index=True),
        sa.Column("read_at",         sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_reads")
    op.drop_table("notifications")
