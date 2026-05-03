"""
openclaw/backend/integrations/calendar.py
Google Calendar integration — creates events per user OAuth token.
Logs to stdout in development; swap in Google API calls for production.
"""
import logging
from datetime import datetime

logger = logging.getLogger("openclaw.integrations.calendar")


async def create_event(
    user_id:     int,
    title:       str,
    start:       datetime | str,
    end:         datetime | str,
    description: str = "",
) -> None:
    logger.info(
        f"[Calendar] CREATE EVENT\n"
        f"  User: {user_id} | Title: {title}\n"
        f"  Start: {start} | End: {end}\n"
        f"  Description: {description}"
    )
    # Production:
    # creds   = Credentials.from_authorized_user_info(...)
    # service = build("calendar", "v3", credentials=creds)
    # service.events().insert(calendarId="primary", body={
    #     "summary": title,
    #     "description": description,
    #     "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
    #     "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
    # }).execute()
