"""
openclaw/backend/db/notification_models.py

Notification system — one row per notification per user.

Design:
  - Notifications are created server-side when team events occur
  - Each notification targets either one user (user_id set) or
    ALL active users (user_id = NULL, scope = "team")
  - The API fan-out query expands team-scope rows into per-user reads
  - read_at = NULL means unread; set to timestamp on mark-read
  - Soft delete: deleted_at lets users dismiss without DB delete

Notification types and when they fire:
  document_uploaded   → a team member uploads a document (scope: team)
  risk_critical       → a member's risk is confirmed Critical (scope: team)
  risk_escalated      → AI escalates a risk level (scope: team)
  sprint_delayed      → a member flips sprint to Delayed (scope: team)
  complexity_complete → complexity analysis finished (scope: uploader)
  member_joined       → new team member registered (scope: team)
  digest_sent         → daily digest was sent (scope: managers only)
  mention             → future: @mention in comments (scope: mentioned user)
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models import Base, utcnow


# ── Notification types ────────────────────────────────────────────────────────

NOTIFICATION_TYPES = {
    "document_uploaded":   "📄",
    "risk_critical":       "🔴",
    "risk_escalated":      "🟠",
    "sprint_delayed":      "⚠️",
    "complexity_complete": "◎",
    "member_joined":       "👤",
    "digest_sent":         "📧",
    "mention":             "💬",
}

# Scope constants
SCOPE_TEAM = "team"        # broadcast to all active users
SCOPE_USER = "user"        # targeted at one specific user


class Notification(Base):
    """
    A notification event. Scope determines who sees it:
      scope="team"  → all active users see this notification
      scope="user"  → only target_user_id sees it
    """
    __tablename__ = "notifications"

    id:             Mapped[int]         = mapped_column(Integer, primary_key=True, index=True)

    # What happened
    notif_type:     Mapped[str]         = mapped_column(String(40), index=True)   # e.g. "document_uploaded"
    title:          Mapped[str]         = mapped_column(String(200))               # short headline
    body:           Mapped[str]         = mapped_column(Text, default="")          # detail text
    link_page:      Mapped[str]         = mapped_column(String(40), default="")    # frontend page to nav to
    link_id:        Mapped[int | None]  = mapped_column(Integer, nullable=True)    # doc_id, user_id, etc.

    # Who triggered it
    actor_id:       Mapped[int | None]  = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_name:     Mapped[str]         = mapped_column(String(120), default="")   # denormalised for speed

    # Who sees it
    scope:          Mapped[str]         = mapped_column(String(10), default=SCOPE_TEAM)  # team | user
    target_user_id: Mapped[int | None]  = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    # Timestamps
    created_at:     Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Per-user read state — stored in NotificationRead join table
    # (avoids duplicating a notification row per user for team-scope events)


class NotificationRead(Base):
    """
    Tracks which users have read which notifications.
    One row per (user_id, notification_id) pair.
    Created when a user marks a notification as read.
    """
    __tablename__ = "notification_reads"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int]      = mapped_column(ForeignKey("notifications.id"), index=True)
    user_id:         Mapped[int]      = mapped_column(ForeignKey("users.id"), index=True)
    read_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
