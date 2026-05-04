"""
openclaw/backend/engine/workers/reminder_engine.py

Detects stale updates, sprint deadline proximity, and absence gaps.
Sends targeted per-user reminders via the event queue.

Schedule : every hour
Startup  : YES — catches stale updates after restart
Trigger  : POST /api/engine/trigger/reminder_engine
"""
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from sqlalchemy import select, func, and_

from backend.db.models import StatusUpdate, User, Sprint, ReminderSent
from backend.utils.event_queue import event_queue
from .base_worker import BaseWorker

STALE_HOURS      = 24
SPRINT_WARN_DAYS = 2
ABSENCE_GAP_HOURS = 4
DEDUP_HOURS      = 12   # don't re-send same reminder type within 12h


@dataclass
class Reminder:
    user_id:    int
    user_name:  str
    user_email: str
    reason:     str   # stale_update | sprint_warning | absence_gap
    detail:     str


class ReminderEngineWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "reminder_engine"

    @property
    def description(self) -> str:
        return "Detects stale updates and sprint deadline proximity; dispatches targeted reminders"

    async def on_startup(self) -> None:
        self.log("info", "Startup reminder sweep")
        await self.execute()

    # ── Core ──────────────────────────────────────────────────────────────────

    async def run(self) -> dict:
        sent = candidates = 0

        async with self.db() as session:
            members     = await self._fetch_member_states(session)
            sprint_end  = await self._fetch_sprint_end(session)

            reminders: list[Reminder] = []
            for m in members:
                reminders.extend(self._evaluate(m, sprint_end))

            candidates = len(reminders)
            for r in reminders:
                if await self._already_sent(session, r):
                    continue
                await self._dispatch(r)
                await self._record(session, r)
                sent += 1

            await session.commit()

        self.log("info", f"Sent {sent}/{candidates} reminder(s)")
        return {"candidates": candidates, "sent": sent}

    # ── Evaluation rules ──────────────────────────────────────────────────────

    def _evaluate(self, m: dict, sprint_end: datetime | None) -> list[Reminder]:
        events = []
        now    = datetime.now(timezone.utc)
        updated_at = m.get("updated_at")
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        # Rule 1: Stale update
        if updated_at:
            age_h = (now - updated_at).total_seconds() / 3600
            if age_h > STALE_HOURS:
                events.append(Reminder(
                    user_id=m["user_id"], user_name=m["name"], user_email=m["email"],
                    reason="stale_update",
                    detail=f"Your OpenClaw status hasn't been updated in {age_h:.0f} hours. Please update.",
                ))

        # Rule 2: Sprint deadline warning
        if sprint_end and m.get("sprint_status") != "On Time":
            days_left = (sprint_end - now).total_seconds() / 86400
            if 0 < days_left <= SPRINT_WARN_DAYS:
                events.append(Reminder(
                    user_id=m["user_id"], user_name=m["name"], user_email=m["email"],
                    reason="sprint_warning",
                    detail=f"Sprint ends in {days_left:.1f} day(s) and your status is '{m['sprint_status']}'. Please review your tasks.",
                ))

        # Rule 3: Absence gap
        detail = (m.get("risk_detail") or "").lower()
        if "absence" in detail and updated_at:
            age_h = (now - updated_at).total_seconds() / 3600
            if age_h > ABSENCE_GAP_HOURS:
                events.append(Reminder(
                    user_id=m["user_id"], user_name=m["name"], user_email=m["email"],
                    reason="absence_gap",
                    detail="Your risk flags a team absence. Please confirm current coverage status.",
                ))

        return events

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _fetch_member_states(self, session) -> list[dict]:
        sub = (
            select(StatusUpdate.user_id, func.max(StatusUpdate.updated_at).label("latest"))
            .group_by(StatusUpdate.user_id)
            .subquery()
        )
        stmt = (
            select(StatusUpdate, User)
            .join(sub, and_(StatusUpdate.user_id == sub.c.user_id, StatusUpdate.updated_at == sub.c.latest))
            .join(User, User.id == StatusUpdate.user_id)
            .where(User.is_active == True)
        )
        rows = (await session.execute(stmt)).all()
        return [
            {
                "user_id":      u.id,
                "name":         u.name,
                "email":        u.email,
                "risk_detail":  s.risk_detail,
                "sprint_status":s.sprint_status,
                "updated_at":   s.updated_at,
            }
            for s, u in rows
        ]

    async def _fetch_sprint_end(self, session) -> datetime | None:
        stmt = select(Sprint.end_date).where(Sprint.is_active == True).limit(1)
        row  = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None and row.tzinfo is None:
            row = row.replace(tzinfo=timezone.utc)
        return row

    async def _already_sent(self, session, r: Reminder) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)
        stmt   = select(ReminderSent).where(
            ReminderSent.user_id == r.user_id,
            ReminderSent.reason  == r.reason,
            ReminderSent.sent_at >= cutoff,
        )
        row = (await session.execute(stmt)).first()
        return row is not None

    async def _record(self, session, r: Reminder) -> None:
        session.add(ReminderSent(user_id=r.user_id, reason=r.reason))

    async def _dispatch(self, r: Reminder) -> None:
        self.log("info", f"Reminder → {r.user_name} [{r.reason}]")
        await event_queue.put({
            "type":    "reminder_email",
            "to":      [r.user_email],
            "subject": f"[OpenClaw] Reminder: {r.reason.replace('_', ' ').title()}",
            "body":    f"Hi {r.user_name},\n\n{r.detail}\n\n— OpenClaw Engine",
        })
