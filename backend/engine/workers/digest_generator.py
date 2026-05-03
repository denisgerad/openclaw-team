"""
openclaw/backend/engine/workers/digest_generator.py

Builds a structured daily team digest, generates a plain-English
narrative via Mistral, and queues it for email dispatch.

Schedule : daily at 08:00
Startup  : NO — schedule-only; use manual trigger before standups
Trigger  : POST /api/engine/trigger/digest_generator
"""
from datetime import datetime, timezone

from sqlalchemy import select, func

from backend.db.models import StatusUpdate, User
from backend.utils.event_queue import event_queue
from .base_worker import BaseWorker

RISK_ORDER = {"Critical": 0, "Moderate": 1, "Minor": 2, "None": 3}


class DigestGeneratorWorker(BaseWorker):

    @property
    def name(self) -> str:
        return "digest_generator"

    @property
    def description(self) -> str:
        return "Daily team summary with Mistral narrative; dispatched via email at 08:00 or on manual trigger"

    async def on_startup(self) -> None:
        self.log("info", "Startup skipped — schedule-only worker (use /trigger for on-demand)")

    # ── Core ──────────────────────────────────────────────────────────────────

    async def run(self) -> dict:
        async with self.db() as session:
            members = await self._fetch_latest_statuses(session)

        if not members:
            self.log("warning", "No member statuses found — skipping digest")
            return {"members": 0, "emails_queued": 0}

        grouped   = self._group_by_risk(members)
        data      = self._build_data(grouped)
        narrative = await self._generate_narrative(data)
        body      = self._render_body(data, narrative)

        recipients = self.settings.digest_recipient_list
        if recipients:
            await event_queue.put({
                "type":    "digest_email",
                "to":      recipients,
                "subject": f"[OpenClaw] Daily Digest — {data['date']}",
                "body":    body,
            })
            queued = len(recipients)
        else:
            self.log("warning", "DIGEST_RECIPIENTS not configured — digest generated but not sent")
            queued = 0

        self.log("info", f"Digest built for {len(members)} member(s), queued for {queued} recipient(s)")
        return {"members": len(members), "emails_queued": queued}

    # ── DB fetch ──────────────────────────────────────────────────────────────

    async def _fetch_latest_statuses(self, session) -> list[dict]:
        """Latest status update per user, joined with user info."""
        # Subquery: max updated_at per user
        sub = (
            select(StatusUpdate.user_id, func.max(StatusUpdate.updated_at).label("latest"))
            .group_by(StatusUpdate.user_id)
            .subquery()
        )
        stmt = (
            select(StatusUpdate, User)
            .join(sub, (StatusUpdate.user_id == sub.c.user_id) & (StatusUpdate.updated_at == sub.c.latest))
            .join(User, User.id == StatusUpdate.user_id)
            .where(User.is_active == True)
        )
        rows = (await session.execute(stmt)).all()
        return [
            {
                "name":          u.name,
                "role":          u.team_role,
                "email":         u.email,
                "risk_level":    s.risk_level_confirmed or s.risk_level,
                "sprint_status": s.sprint_status,
                "issue":         s.issue,
                "issue_status":  s.issue_status,
                "comments":      s.comments,
                "updated_at":    s.updated_at,
            }
            for s, u in rows
        ]

    # ── Build / group ─────────────────────────────────────────────────────────

    def _group_by_risk(self, members: list[dict]) -> dict:
        groups: dict[str, list] = {"Critical": [], "Moderate": [], "Minor": [], "None": []}
        for m in members:
            groups.setdefault(m["risk_level"], []).append(m)
        return groups

    def _build_data(self, grouped: dict) -> dict:
        all_members = [m for g in grouped.values() for m in g]
        return {
            "date":           datetime.now(timezone.utc).strftime("%A %d %B %Y"),
            "grouped":        grouped,
            "total":          len(all_members),
            "critical_count": len(grouped.get("Critical", [])),
            "delayed_count":  sum(1 for m in all_members if m["sprint_status"] == "Delayed"),
            "on_track":       sum(1 for m in all_members if m["sprint_status"] == "On Time"),
            "at_risk":        sum(1 for m in all_members if m["sprint_status"] == "At Risk"),
            "open_issues":    sum(1 for m in all_members if m["issue_status"] == "Open"),
        }

    # ── Mistral narrative ─────────────────────────────────────────────────────

    async def _generate_narrative(self, data: dict) -> str:
        if not self.settings.mistral_api_key:
            return self._fallback_narrative(data)

        try:
            from mistralai import Mistral
            client = Mistral(api_key=self.settings.mistral_api_key)

            critical_names = [m["name"] for m in data["grouped"].get("Critical", [])]
            delayed_names  = [m["name"] for m in (data["grouped"].get("Critical", []) + data["grouped"].get("Moderate", [])) if m["sprint_status"] == "Delayed"]

            prompt = (
                f"Team sprint status for {data['date']}:\n"
                f"- Total members: {data['total']}\n"
                f"- Critical risk: {data['critical_count']} ({', '.join(critical_names) or 'none'})\n"
                f"- Sprint delayed: {data['delayed_count']} ({', '.join(delayed_names) or 'none'})\n"
                f"- At risk: {data['at_risk']}, On track: {data['on_track']}\n"
                f"- Open issues: {data['open_issues']}\n\n"
                "Write a concise 3-4 sentence engineering manager standup summary. "
                "Be direct. Highlight blockers and risks first. No fluff or greetings."
            )
            resp = client.chat.complete(
                model=self.settings.mistral_model,
                messages=[
                    {"role": "system", "content": "You are an engineering manager writing a brief daily team digest for stakeholders."},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=200,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()

        except Exception as exc:
            self.log("warning", f"Mistral narrative failed — using fallback: {exc}")
            return self._fallback_narrative(data)

    def _fallback_narrative(self, data: dict) -> str:
        return (
            f"Daily digest for {data['date']}. "
            f"{data['critical_count']} critical risk(s), "
            f"{data['delayed_count']} delayed sprint task(s), "
            f"{data['on_track']} member(s) on track. "
            f"{data['open_issues']} open issue(s) require attention."
        )

    # ── Email renderer ────────────────────────────────────────────────────────

    def _render_body(self, data: dict, narrative: str) -> str:
        lines = [
            f"OpenClaw Daily Digest — {data['date']}",
            "=" * 64,
            "",
            narrative,
            "",
            f"  Critical : {data['critical_count']}   Delayed : {data['delayed_count']}",
            f"  At Risk  : {data['at_risk']}          On Track: {data['on_track']}",
            f"  Open Issues: {data['open_issues']}",
            "",
            "─" * 64,
            "TEAM BREAKDOWN",
            "─" * 64,
        ]
        for level in ("Critical", "Moderate", "Minor", "None"):
            members = data["grouped"].get(level, [])
            if not members:
                continue
            lines.append(f"\n[ {level.upper()} ]")
            for m in members:
                lines.append(f"  {m['name']:<20} ({m['role']:<12}) Sprint: {m['sprint_status']:<10} Issue: {m['issue_status']}")
                if m["comments"]:
                    lines.append(f"    → {m['comments']}")
        lines += ["", "─" * 64, "OpenClaw Engine · Auto-generated · Do not reply"]
        return "\n".join(lines)

    async def health_check(self) -> bool:
        return True
