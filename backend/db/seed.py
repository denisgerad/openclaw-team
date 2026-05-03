"""
openclaw/backend/db/seed.py

Creates initial data so the dashboard is populated on first run.
Run once after init_db():

    python -m backend.db.seed

Creates:
  - 1 manager account  (manager@openclaw.dev / manager123)
  - 5 developer accounts (dev1@openclaw.dev … / dev123)
  - 1 active sprint
  - 1 initial status update per member
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from backend.config import get_settings
from backend.db.session import init_db, AsyncSessionLocal
from backend.db.models import User, StatusUpdate, Sprint, SprintTask, EventLog
from backend.utils.auth import hash_password

MANAGER = {
    "name": "Alex Manager", "email": "manager@openclaw.dev",
    "password": "manager123", "role": "manager", "team_role": "Engineering Manager",
}

DEVELOPERS = [
    { "name":"Aria Chen",   "email":"aria@openclaw.dev",   "team_role":"Frontend",  "risk_level":"Moderate", "risk_detail":"Dependency risk — waiting on backend API contract",    "sprint_status":"At Risk",  "issue":"Build issues",         "issue_status":"In Progress", "comments":"Blocked on API schema. Flagged to backend team." },
    { "name":"Dev Patel",   "email":"dev@openclaw.dev",    "team_role":"Backend",   "risk_level":"Critical", "risk_detail":"Hardware not available — dev server down since Monday", "sprint_status":"Delayed",  "issue":"Bug fixes unresolved", "issue_status":"Open",        "comments":"Critical blocker. Escalated to infra." },
    { "name":"Sam Torres",  "email":"sam@openclaw.dev",    "team_role":"DevOps",    "risk_level":"None",     "risk_detail":"",                                                       "sprint_status":"On Time",  "issue":"—",                    "issue_status":"Resolved",    "comments":"CI/CD pipeline green. All good." },
    { "name":"Lena Kovač",  "email":"lena@openclaw.dev",   "team_role":"AI/ML",     "risk_level":"Minor",    "risk_detail":"Team member absence — Raj out until Friday",             "sprint_status":"On Time",  "issue":"—",                    "issue_status":"Resolved",    "comments":"On track. Covering for Raj on embeddings." },
    { "name":"Marcus Webb", "email":"marcus@openclaw.dev", "team_role":"QA",        "risk_level":"Moderate", "risk_detail":"Dependency risk — needs frontend stable build",           "sprint_status":"At Risk",  "issue":"Bug fixes unresolved", "issue_status":"In Progress", "comments":"Awaiting stable build. Test suite paused." },
]


async def seed():
    await init_db()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        # ── Skip if already seeded ────────────────────────────────────────────
        existing = (await session.execute(select(User))).first()
        if existing:
            print("Database already seeded — skipping.")
            return

        # ── Manager ───────────────────────────────────────────────────────────
        manager = User(
            name=MANAGER["name"],
            email=MANAGER["email"],
            hashed_password=hash_password(MANAGER["password"]),
            role=MANAGER["role"],
            team_role=MANAGER["team_role"],
            created_at=now,
        )
        session.add(manager)
        await session.flush()
        print(f"  ✓ Manager created: {manager.email}")

        # ── Sprint ────────────────────────────────────────────────────────────
        sprint = Sprint(
            name="Sprint 14",
            start_date=now - timedelta(days=7),
            end_date=now + timedelta(days=7),
            is_active=True,
        )
        session.add(sprint)
        await session.flush()  # get sprint.id

        # ── Sprint tasks ──────────────────────────────────────────────────────
        SPRINT_TASKS = [
            {"title": "Finalise API schema contract",   "status": "done",        "priority": "high",     "due_offset": 1},
            {"title": "Fix frontend build pipeline",    "status": "in_progress", "priority": "critical", "due_offset": 2},
            {"title": "Deploy CI/CD green run",         "status": "done",        "priority": "normal",   "due_offset": -1},
            {"title": "Embeddings baseline evaluation", "status": "in_progress", "priority": "normal",   "due_offset": 3},
            {"title": "Test suite unblocked — run E2E", "status": "blocked",     "priority": "high",     "due_offset": 4},
            {"title": "Infra server recovery",          "status": "in_progress", "priority": "critical", "due_offset": 0},
            {"title": "Sprint retro prep doc",          "status": "todo",        "priority": "low",      "due_offset": 6},
        ]
        for td in SPRINT_TASKS:
            session.add(SprintTask(
                sprint_id=sprint.id,
                user_id=None,
                title=td["title"],
                status=td["status"],
                priority=td["priority"],
                due_date=now + timedelta(days=td["due_offset"]),
                created_at=now,
                updated_at=now,
            ))

        # ── Developers ────────────────────────────────────────────────────────
        for d in DEVELOPERS:
            user = User(
                name=d["name"],
                email=d["email"],
                hashed_password=hash_password("dev123"),
                role="developer",
                team_role=d["team_role"],
                created_at=now,
            )
            session.add(user)
            await session.flush()

            status = StatusUpdate(
                user_id=user.id,
                risk_level=d["risk_level"],
                risk_detail=d["risk_detail"],
                sprint_status=d["sprint_status"],
                issue=d["issue"],
                issue_status=d["issue_status"],
                comments=d["comments"],
                created_at=now,
                updated_at=now,
            )
            session.add(status)

            # Write event log so workflow engine has something to process
            session.add(EventLog(
                event_type="status_updated",
                payload=json.dumps({
                    "user_id":       user.id,
                    "user_name":     user.name,
                    "team_role":     user.team_role,
                    "user_email":    user.email,
                    "risk_level":    d["risk_level"],
                    "risk_detail":   d["risk_detail"],
                    "sprint_status": d["sprint_status"],
                    "comments":      d["comments"],
                }),
                created_at=now,
            ))

            # Write member_created event
            session.add(EventLog(
                event_type="member_created",
                payload=json.dumps({
                    "user_id":    user.id,
                    "user_name":  user.name,
                    "user_email": user.email,
                }),
                created_at=now,
            ))

            print(f"  ✓ Developer created: {user.email}  [{d['team_role']}]  risk={d['risk_level']}")

        await session.commit()

    print("\nSeed complete.")
    print("\nLogin credentials:")
    print(f"  Manager:   manager@openclaw.dev  /  manager123")
    print(f"  Developer: aria@openclaw.dev     /  dev123  (and dev, sam, lena, marcus)")


if __name__ == "__main__":
    asyncio.run(seed())
