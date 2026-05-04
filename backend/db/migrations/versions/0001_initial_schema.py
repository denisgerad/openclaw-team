"""initial schema

Revision ID: 0001
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",              sa.Integer,  primary_key=True),
        sa.Column("name",            sa.String(120), nullable=False),
        sa.Column("email",           sa.String(200), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("role",            sa.String(20),  nullable=False, server_default="developer"),
        sa.Column("team_role",       sa.String(80),  nullable=False, server_default="Developer"),
        sa.Column("is_active",       sa.Boolean,     nullable=False, server_default=sa.true()),
        sa.Column("oauth_token_enc", sa.Text,        nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sprints",
        sa.Column("id",         sa.Integer, primary_key=True),
        sa.Column("name",       sa.String(80), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active",  sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "status_updates",
        sa.Column("id",                   sa.Integer, primary_key=True),
        sa.Column("user_id",              sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("risk_level",           sa.String(20), nullable=False, server_default="None"),
        sa.Column("risk_level_confirmed", sa.String(20), nullable=True),
        sa.Column("risk_detail",          sa.Text,       nullable=False, server_default=""),
        sa.Column("sprint_status",        sa.String(20), nullable=False, server_default="On Time"),
        sa.Column("issue",                sa.String(120),nullable=False, server_default="—"),
        sa.Column("issue_status",         sa.String(20), nullable=False, server_default="Resolved"),
        sa.Column("comments",             sa.Text,       nullable=False, server_default=""),
        sa.Column("classified_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",           sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",           sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "notes",
        sa.Column("id",         sa.Integer, primary_key=True),
        sa.Column("user_id",    sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title",      sa.String(200), nullable=False),
        sa.Column("content",    sa.Text,        nullable=False, server_default=""),
        sa.Column("tags",       sa.String(300), nullable=False, server_default=""),
        sa.Column("pinned",     sa.Boolean,     nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "file_records",
        sa.Column("id",              sa.Integer, primary_key=True),
        sa.Column("user_id",         sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("filename",        sa.String(300), nullable=False),
        sa.Column("source_url",      sa.Text,        nullable=False),
        sa.Column("local_path",      sa.Text,        nullable=True),
        sa.Column("size_bytes",      sa.Integer,     nullable=False, server_default="0"),
        sa.Column("download_status", sa.String(20),  nullable=False, server_default="pending"),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at",    sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "event_log",
        sa.Column("id",           sa.Integer, primary_key=True),
        sa.Column("event_type",   sa.String(60), nullable=False, index=True),
        sa.Column("payload",      sa.Text,       nullable=False, server_default="{}"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "reminders_sent",
        sa.Column("id",      sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("reason",  sa.String(60), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in ["reminders_sent","event_log","file_records","notes","status_updates","sprints","users"]:
        op.drop_table(table)
