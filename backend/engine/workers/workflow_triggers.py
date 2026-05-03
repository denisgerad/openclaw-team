"""
openclaw/backend/engine/workers/workflow_triggers.py

Event-Condition-Action (ECA) rule engine.
Reads unprocessed rows from event_log, evaluates rules, fires actions.

To add a new workflow:
  1. Add a WorkflowRule to _register_rules()
  2. Implement the matching _action_<action_name>() method
  No other changes needed.

Schedule : every 2 minutes
Startup  : YES — processes events missed while offline
Trigger  : POST /api/engine/trigger/workflow_triggers
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, update

from backend.db.models import EventLog
from backend.utils.event_queue import event_queue
from .base_worker import BaseWorker


@dataclass
class WorkflowRule:
    id:          str
    event_type:  str
    description: str
    action:      str
    priority:    int = 10
    enabled:     bool = True
    condition:   Callable[[dict], bool] = field(default=lambda e: True)


class WorkflowTriggersWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "workflow_triggers"

    @property
    def description(self) -> str:
        return "ECA rule engine — fires configured workflows on DB events (Critical, Delayed sprint, files, notes)"

    def __init__(self, db_session_factory, settings):
        super().__init__(db_session_factory, settings)
        self._rules = sorted(self._register_rules(), key=lambda r: r.priority)

    # ── Rule registry ─────────────────────────────────────────────────────────

    def _register_rules(self) -> list[WorkflowRule]:
        return [
            WorkflowRule(
                id="R1_critical_escalation",
                event_type="status_updated",
                description="Critical risk → escalation email to manager",
                priority=1,
                action="escalate_to_manager",
                condition=lambda e: e.get("risk_level") == "Critical",
            ),
            WorkflowRule(
                id="R2_sprint_delayed",
                event_type="status_updated",
                description="Sprint flipped to Delayed → manager notification",
                priority=2,
                action="notify_sprint_delayed",
                condition=lambda e: e.get("sprint_status") == "Delayed",
            ),
            WorkflowRule(
                id="R3_file_complete",
                event_type="file_download_complete",
                description="File download complete → notify user",
                priority=5,
                action="notify_file_complete",
            ),
            WorkflowRule(
                id="R4_urgent_note",
                event_type="note_tagged",
                description="Note tagged #urgent → alert manager",
                priority=3,
                action="urgent_note_alert",
                condition=lambda e: "#urgent" in (e.get("tags") or ""),
            ),
            WorkflowRule(
                id="R5_member_onboard",
                event_type="member_created",
                description="New member added → welcome email",
                priority=4,
                action="onboard_new_member",
            ),
        ]

    # ── Core ──────────────────────────────────────────────────────────────────

    async def on_startup(self) -> None:
        self.log("info", f"Startup sweep — {len(self._rules)} rules registered")
        await self.execute()

    async def run(self) -> dict:
        fired = skipped = 0

        async with self.db() as session:
            events = await self._fetch_unprocessed(session)
            self.log("info", f"Processing {len(events)} event(s)")

            for event in events:
                matched = False
                for rule in self._rules:
                    if not rule.enabled:
                        continue
                    if rule.event_type != event.get("event_type"):
                        continue
                    try:
                        if rule.condition(event):
                            self.log("info", f"Rule {rule.id} matched event id={event.get('id')}")
                            await self._dispatch(rule.action, event)
                            fired += 1
                            matched = True
                            break   # first matching rule wins per event
                    except Exception as exc:
                        self.log("error", f"Rule {rule.id} condition error: {exc}")

                if not matched:
                    skipped += 1

                await self._mark_processed(session, event["id"])

            await session.commit()

        return {"events": len(events), "fired": fired, "skipped": skipped}

    # ── Action dispatcher ─────────────────────────────────────────────────────

    async def _dispatch(self, action: str, event: dict) -> None:
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            self.log("warning", f"No handler for action '{action}'")
            return
        await handler(event)

    # ── Action implementations ────────────────────────────────────────────────

    async def _action_escalate_to_manager(self, event: dict) -> None:
        await event_queue.put({
            "type":    "alert_email",
            "to":      self.settings.digest_recipient_list,
            "subject": f"[OpenClaw] 🔴 CRITICAL — {event.get('user_name', 'Unknown')}",
            "body": (
                f"Critical risk escalation.\n\n"
                f"Member : {event.get('user_name')} ({event.get('team_role')})\n"
                f"Detail : {event.get('risk_detail', '—')}\n"
                f"Comment: {event.get('comments', '—')}\n\n"
                "Review immediately in the OpenClaw dashboard."
            ),
        })

    async def _action_notify_sprint_delayed(self, event: dict) -> None:
        await event_queue.put({
            "type":    "alert_email",
            "to":      self.settings.digest_recipient_list,
            "subject": f"[OpenClaw] ⚠️ Sprint Delayed — {event.get('user_name', 'Unknown')}",
            "body": (
                f"Sprint status changed to Delayed.\n\n"
                f"Member : {event.get('user_name')} ({event.get('team_role')})\n"
                f"Comment: {event.get('comments', '—')}\n"
            ),
        })

    async def _action_notify_file_complete(self, event: dict) -> None:
        await event_queue.put({
            "type":    "reminder_email",
            "to":      [event.get("user_email", "")],
            "subject": f"[OpenClaw] Download complete: {event.get('filename', 'file')}",
            "body":    f"Your file '{event.get('filename')}' has finished downloading.",
        })

    async def _action_urgent_note_alert(self, event: dict) -> None:
        await event_queue.put({
            "type":    "alert_email",
            "to":      self.settings.digest_recipient_list,
            "subject": f"[OpenClaw] 📌 Urgent note from {event.get('user_name', 'Unknown')}",
            "body":    f"Title: {event.get('title')}\n\nTags: {event.get('tags')}",
        })

    async def _action_onboard_new_member(self, event: dict) -> None:
        await event_queue.put({
            "type":    "reminder_email",
            "to":      [event.get("user_email", "")],
            "subject": "[OpenClaw] Welcome to the team dashboard",
            "body": (
                f"Hi {event.get('user_name')},\n\n"
                "You've been added to OpenClaw. Please log in and update your sprint status.\n\n"
                "— OpenClaw Engine"
            ),
        })

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _fetch_unprocessed(self, session) -> list[dict]:
        stmt = select(EventLog).where(EventLog.processed_at.is_(None)).limit(100)
        rows = (await session.execute(stmt)).scalars().all()
        result = []
        for row in rows:
            try:
                payload = json.loads(row.payload)
            except Exception:
                payload = {}
            result.append({"id": row.id, "event_type": row.event_type, **payload})
        return result

    async def _mark_processed(self, session, event_id: int) -> None:
        await session.execute(
            update(EventLog)
            .where(EventLog.id == event_id)
            .values(processed_at=datetime.now(timezone.utc))
        )

    async def health_check(self) -> bool:
        enabled = [r for r in self._rules if r.enabled]
        return len(enabled) > 0
