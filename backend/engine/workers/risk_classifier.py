"""
openclaw/backend/engine/workers/risk_classifier.py

Reads status rows not yet classified (or edited since last classification),
calls Mistral to validate the risk level, writes back the confirmed level,
and queues Critical alerts.

Schedule : every 5 minutes
Startup  : YES — catches any rows missed while server was offline
Trigger  : POST /api/engine/trigger/risk_classifier
"""
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_

from backend.db.models import StatusUpdate, User
from backend.utils.event_queue import event_queue
from .base_worker import BaseWorker

VALID_LEVELS = {"Critical", "Moderate", "Minor", "None"}


class RiskClassifierWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "risk_classifier"

    @property
    def description(self) -> str:
        return "Validates developer-supplied risk levels via Mistral; queues Critical alerts"

    async def on_startup(self) -> None:
        self.log("info", "Startup pass — classifying rows missed while offline")
        await self.execute()

    # ── Core ──────────────────────────────────────────────────────────────────

    async def run(self) -> dict:
        processed = alerts = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        async with self.db() as session:
            # Rows with no classification OR re-edited since last classification
            stmt = (
                select(StatusUpdate, User)
                .join(User, User.id == StatusUpdate.user_id)
                .where(
                    or_(
                        StatusUpdate.classified_at.is_(None),
                        StatusUpdate.updated_at > StatusUpdate.classified_at,
                    ),
                    StatusUpdate.updated_at >= cutoff,
                )
            )
            rows = (await session.execute(stmt)).all()
            self.log("info", f"Found {len(rows)} row(s) to classify")

            for status, user in rows:
                confirmed = await self._classify(status)

                prev = status.risk_level_confirmed
                status.risk_level_confirmed = confirmed
                status.classified_at        = datetime.now(timezone.utc)
                session.add(status)
                processed += 1

                if confirmed == "Critical":
                    await self._queue_alert(user, status)
                    alerts += 1

                if prev != confirmed:
                    self.log("info", f"Level adjusted {prev!r} → {confirmed!r} for {user.name}")

            await session.commit()

        return {"processed": processed, "alerts_queued": alerts}

    # ── Web search enrichment ──────────────────────────────────────────────────

    async def _enrich_with_search(self, status: StatusUpdate) -> str:
        """Return a web-context snippet to append to the Mistral prompt."""
        query = (status.risk_detail or "").strip()
        if len(query) < 15:
            return ""
        try:
            from backend.integrations.web_search import search
            results = await search(query, max_results=2)
            if not results:
                return ""
            snippets = "\n".join(
                f"- {r['snippet']}" for r in results if r.get("snippet")
            )
            return f"\n\nWeb context for \"{query[:80]}\":\n{snippets}"
        except Exception as exc:
            self.log("debug", f"Web search enrichment skipped: {exc}")
            return ""

    # ── Mistral classification ─────────────────────────────────────────────────

    async def _classify(self, status: StatusUpdate) -> str:
        if not self.settings.mistral_api_key:
            return status.risk_level  # no key — trust developer input

        try:
            from mistralai import Mistral
            client = Mistral(api_key=self.settings.mistral_api_key)

            web_context = await self._enrich_with_search(status)

            prompt = (
                f"Reported risk level: \"{status.risk_level}\"\n"
                f"Risk detail: \"{status.risk_detail}\"\n"
                f"Comments: \"{status.comments}\""
                f"{web_context}\n\n"
                "Based on the detail, comments, and any web context above, "
                "what is the most accurate risk level?\n"
                "Reply with exactly one word: Critical, Moderate, Minor, or None."
            )
            resp = client.chat.complete(
                model=self.settings.mistral_model,
                messages=[
                    {"role": "system", "content": "You are a software project risk classifier. Be conservative — only escalate to Critical when there is a concrete blocking issue."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=5,
                temperature=0.0,
            )
            level = resp.choices[0].message.content.strip().rstrip(".")
            return level if level in VALID_LEVELS else status.risk_level

        except Exception as exc:
            self.log("warning", f"Mistral call failed — using reported level: {exc}")
            return status.risk_level

    async def _queue_alert(self, user: User, status: StatusUpdate) -> None:
        await event_queue.put({
            "type":    "alert_email",
            "to":      [self.settings.digest_recipients] if self.settings.digest_recipients else [],
            "subject": f"[OpenClaw] 🔴 CRITICAL — {user.name}",
            "body": (
                f"Critical risk flagged for {user.name} ({user.team_role}).\n\n"
                f"Risk detail: {status.risk_detail or '—'}\n"
                f"Comments:    {status.comments or '—'}\n"
                f"Sprint:      {status.sprint_status}\n\n"
                "Please review immediately in the OpenClaw dashboard."
            ),
        })

    async def health_check(self) -> bool:
        return True  # works with or without Mistral key
