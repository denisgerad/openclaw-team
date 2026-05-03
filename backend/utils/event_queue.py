"""
openclaw/backend/utils/event_queue.py

Lightweight in-process async event queue.
Workers push events here; the queue consumer dispatches
to the correct integration (Gmail, Calendar, etc.)
without workers having direct integration dependencies.

Usage (producer — from any worker):
    from backend.utils.event_queue import event_queue
    await event_queue.put({"type": "alert_email", "to": [...], ...})

Usage (consumer — started in app lifespan):
    from backend.utils.event_queue import start_consumer
    asyncio.create_task(start_consumer())
"""
import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("openclaw.event_queue")

# Global queue — one per process
event_queue: asyncio.Queue = asyncio.Queue(maxsize=500)


# ── Dispatch router ───────────────────────────────────────────────────────────

async def _dispatch(event: dict) -> None:
    """Route an event to the correct handler by event type."""
    etype = event.get("type")

    if etype in ("alert_email", "digest_email", "reminder_email"):
        await _handle_email(event)

    elif etype == "calendar_event":
        await _handle_calendar(event)

    else:
        logger.warning(f"[event_queue] Unknown event type: {etype}")


async def _handle_email(event: dict) -> None:
    """
    Send an email via the Gmail integration.
    Falls back to logging if Gmail is not configured.
    """
    try:
        from backend.integrations.gmail import send_email
        await send_email(
            to=event.get("to", []),
            subject=event.get("subject", "(no subject)"),
            body=event.get("body", ""),
        )
        logger.info(f"[event_queue] Email sent → {event.get('to')} | {event.get('subject')}")
    except Exception as exc:
        logger.error(f"[event_queue] Email failed: {exc}")
        # Log to stdout so nothing is silently dropped
        logger.info(
            f"[event_queue] EMAIL (unsent):\n"
            f"  TO:      {event.get('to')}\n"
            f"  SUBJECT: {event.get('subject')}\n"
            f"  BODY:    {event.get('body', '')[:200]}"
        )


async def _handle_calendar(event: dict) -> None:
    """Create a Google Calendar event via the calendar integration."""
    try:
        from backend.integrations.calendar import create_event
        await create_event(
            user_id=event.get("user_id"),
            title=event.get("title"),
            start=event.get("start"),
            end=event.get("end"),
            description=event.get("description", ""),
        )
        logger.info(f"[event_queue] Calendar event created: {event.get('title')}")
    except Exception as exc:
        logger.error(f"[event_queue] Calendar event failed: {exc}")


# ── Consumer loop ─────────────────────────────────────────────────────────────

async def start_consumer() -> None:
    """
    Long-running coroutine — started as an asyncio task in app lifespan.
    Drains the event queue continuously.
    """
    logger.info("[event_queue] Consumer started")
    while True:
        try:
            event: dict = await event_queue.get()
            await _dispatch(event)
            event_queue.task_done()
        except asyncio.CancelledError:
            logger.info("[event_queue] Consumer shutting down")
            break
        except Exception as exc:
            logger.error(f"[event_queue] Consumer error: {exc}")
