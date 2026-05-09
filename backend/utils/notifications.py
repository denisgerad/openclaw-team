"""
openclaw/backend/utils/notifications.py

Central notification service.
All other parts of the system call these functions to create notifications.
Never import this from DB models — only from API routes and workers.

Usage:
    from backend.utils.notifications import notify

    await notify.document_uploaded(doc_name="Req v2", category="Requirements",
                                   actor_id=3, actor_name="Aria Chen",
                                   doc_id=7, session=db)

    await notify.risk_critical(member_name="Dev Patel", risk_detail="Server down",
                               actor_id=2, actor_name="Dev Patel", session=db)
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.notification_models import (
    SCOPE_TEAM, SCOPE_USER, Notification, NotificationRead
)

logger = logging.getLogger("openclaw.notifications")


# ── Internal helper ───────────────────────────────────────────────────────────

async def _create(
    session:    AsyncSession,
    notif_type: str,
    title:      str,
    body:       str        = "",
    link_page:  str        = "",
    link_id:    int | None = None,
    actor_id:   int | None = None,
    actor_name: str        = "",
    scope:      str        = SCOPE_TEAM,
    target_user_id: int | None = None,
) -> Notification:
    """Create and persist a notification. Returns the new row."""
    n = Notification(
        notif_type=notif_type,
        title=title,
        body=body,
        link_page=link_page,
        link_id=link_id,
        actor_id=actor_id,
        actor_name=actor_name,
        scope=scope,
        target_user_id=target_user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(n)
    await session.flush()   # get n.id without full commit
    logger.info(f"[notify] {notif_type} → scope={scope} actor={actor_name!r} title={title!r}")
    return n


# ── Public notification creators ──────────────────────────────────────────────

class _NotifyService:
    """
    Namespace for all notification factory methods.
    Import and use as: from backend.utils.notifications import notify
    """

    async def document_uploaded(
        self,
        doc_name:   str,
        category:   str,
        version:    int,
        actor_id:   int,
        actor_name: str,
        doc_id:     int,
        session:    AsyncSession,
    ) -> Notification:
        return await _create(
            session=session,
            notif_type="document_uploaded",
            title=f"📄 {actor_name} uploaded a document",
            body=f"{doc_name} (v{version}) · {category}",
            link_page="documents",
            link_id=doc_id,
            actor_id=actor_id,
            actor_name=actor_name,
            scope=SCOPE_TEAM,
        )

    async def risk_critical(
        self,
        member_name: str,
        risk_detail: str,
        actor_id:    int,
        actor_name:  str,
        session:     AsyncSession,
    ) -> Notification:
        detail = risk_detail[:80] + "…" if len(risk_detail) > 80 else risk_detail
        return await _create(
            session=session,
            notif_type="risk_critical",
            title=f"🔴 Critical risk — {member_name}",
            body=detail or "Risk escalated to Critical level",
            link_page="dashboard",
            actor_id=actor_id,
            actor_name=actor_name,
            scope=SCOPE_TEAM,
        )

    async def risk_escalated(
        self,
        member_name: str,
        from_level:  str,
        to_level:    str,
        actor_id:    int,
        actor_name:  str,
        session:     AsyncSession,
    ) -> Notification:
        return await _create(
            session=session,
            notif_type="risk_escalated",
            title=f"🟠 Risk escalated — {member_name}",
            body=f"Level changed from {from_level} to {to_level} by AI classifier",
            link_page="dashboard",
            actor_id=actor_id,
            actor_name=actor_name,
            scope=SCOPE_TEAM,
        )

    async def sprint_delayed(
        self,
        member_name: str,
        comments:    str,
        actor_id:    int,
        actor_name:  str,
        session:     AsyncSession,
    ) -> Notification:
        snippet = comments[:80] + "…" if len(comments) > 80 else comments
        return await _create(
            session=session,
            notif_type="sprint_delayed",
            title=f"⚠️ Sprint delayed — {member_name}",
            body=snippet or "Sprint status changed to Delayed",
            link_page="dashboard",
            actor_id=actor_id,
            actor_name=actor_name,
            scope=SCOPE_TEAM,
        )

    async def complexity_complete(
        self,
        doc_name:       str,
        overall_rating: str,
        version:        int,
        actor_id:       int,
        actor_name:     str,
        doc_id:         int,
        session:        AsyncSession,
    ) -> Notification:
        """Targeted at the uploader only — not broadcast to team."""
        icons = {"Simple": "🟢", "Moderate": "🟡", "Complex": "🟠", "Critical": "🔴"}
        icon  = icons.get(overall_rating, "◎")
        return await _create(
            session=session,
            notif_type="complexity_complete",
            title=f"◎ Complexity analysis complete",
            body=f"{doc_name} v{version} — {icon} {overall_rating} overall",
            link_page="complexity",
            link_id=doc_id,
            actor_id=actor_id,
            actor_name=actor_name,
            scope=SCOPE_USER,
            target_user_id=actor_id,
        )

    async def member_joined(
        self,
        new_member_name: str,
        team_role:       str,
        new_member_id:   int,
        session:         AsyncSession,
    ) -> Notification:
        return await _create(
            session=session,
            notif_type="member_joined",
            title=f"👤 New team member — {new_member_name}",
            body=f"Role: {team_role}",
            link_page="summary",
            link_id=new_member_id,
            actor_name="System",
            scope=SCOPE_TEAM,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
notify = _NotifyService()


# ── Query helpers (used by the API) ──────────────────────────────────────────

async def get_notifications_for_user(
    user_id:  int,
    session:  AsyncSession,
    limit:    int = 30,
    unread_only: bool = False,
) -> list[dict]:
    """
    Return notifications visible to this user, most recent first.
    Expands team-scope notifications and merges user-scope ones.
    Attaches is_read flag based on NotificationRead join table.
    """
    from sqlalchemy import or_, desc

    # Fetch all notifications this user can see
    stmt = (
        select(Notification)
        .where(
            or_(
                Notification.scope == SCOPE_TEAM,
                Notification.target_user_id == user_id,
            )
        )
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    if not rows:
        return []

    # Fetch read records for this user
    notif_ids = [n.id for n in rows]
    read_stmt = select(NotificationRead.notification_id).where(
        NotificationRead.user_id == user_id,
        NotificationRead.notification_id.in_(notif_ids),
    )
    read_ids = set((await session.execute(read_stmt)).scalars().all())

    result = []
    for n in rows:
        is_read = n.id in read_ids
        if unread_only and is_read:
            continue
        result.append({
            "id":          n.id,
            "notif_type":  n.notif_type,
            "title":       n.title,
            "body":        n.body,
            "link_page":   n.link_page,
            "link_id":     n.link_id,
            "actor_name":  n.actor_name,
            "scope":       n.scope,
            "is_read":     is_read,
            "created_at":  n.created_at.isoformat(),
        })

    return result


async def get_unread_count(user_id: int, session: AsyncSession) -> int:
    """Fast unread count — used for the bell badge."""
    from sqlalchemy import or_, func

    # Count team + user-targeted notifications
    total_stmt = (
        select(func.count(Notification.id))
        .where(
            or_(
                Notification.scope == SCOPE_TEAM,
                Notification.target_user_id == user_id,
            )
        )
    )
    total = (await session.execute(total_stmt)).scalar_one()

    # Count read ones
    read_stmt = (
        select(func.count(NotificationRead.id))
        .where(NotificationRead.user_id == user_id)
    )
    read = (await session.execute(read_stmt)).scalar_one()

    return max(0, total - read)


async def mark_read(
    user_id:  int,
    notif_id: int | None,   # None = mark all
    session:  AsyncSession,
) -> int:
    """
    Mark one or all notifications as read for this user.
    Returns count of newly-marked records.
    """
    from sqlalchemy import or_

    # Find unread notifications for this user
    stmt = (
        select(Notification.id)
        .where(
            or_(
                Notification.scope == SCOPE_TEAM,
                Notification.target_user_id == user_id,
            )
        )
    )
    if notif_id is not None:
        stmt = stmt.where(Notification.id == notif_id)

    all_ids = (await session.execute(stmt)).scalars().all()

    # Check which ones already have a read record
    existing_stmt = select(NotificationRead.notification_id).where(
        NotificationRead.user_id == user_id,
        NotificationRead.notification_id.in_(all_ids),
    )
    already_read = set((await session.execute(existing_stmt)).scalars().all())

    # Insert read records for unread ones
    new_reads = [
        NotificationRead(
            notification_id=nid,
            user_id=user_id,
            read_at=datetime.now(timezone.utc),
        )
        for nid in all_ids if nid not in already_read
    ]
    for r in new_reads:
        session.add(r)

    await session.flush()
    return len(new_reads)
