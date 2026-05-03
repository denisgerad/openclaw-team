"""
openclaw/backend/integrations/gmail.py

Sends emails via Gmail API (OAuth2 per-user) or falls back to
SMTP/logging in development.

In production:
  1. Configure GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env
  2. Users complete OAuth2 consent via /api/auth/oauth/google
  3. Their encrypted token is stored in users.oauth_token_enc
  4. send_email() decrypts the token and uses the Gmail API

For now this module logs emails to stdout so the rest of the
system works without Google credentials.
"""
import logging

logger = logging.getLogger("openclaw.integrations.gmail")


async def send_email(to: list[str], subject: str, body: str, user_id: int | None = None) -> None:
    """
    Send an email to one or more recipients.

    Args:
        to:       list of recipient email addresses
        subject:  email subject line
        body:     plain-text email body
        user_id:  if provided, use that user's OAuth token for sending
                  (otherwise uses the service/manager account)
    """
    if not to:
        logger.warning("[gmail] send_email called with empty recipient list — skipped")
        return

    # ── Development: log to stdout ────────────────────────────────────────────
    logger.info(
        f"\n{'─'*60}\n"
        f"[Gmail] TO:      {', '.join(to)}\n"
        f"[Gmail] SUBJECT: {subject}\n"
        f"[Gmail] BODY:\n{body}\n"
        f"{'─'*60}"
    )

    # ── Production: uncomment and configure ───────────────────────────────────
    # from google.oauth2.credentials import Credentials
    # from googleapiclient.discovery import build
    # import base64
    # from email.mime.text import MIMEText
    # from backend.utils.auth import decrypt_token
    # from backend.db.session import get_session
    # from backend.db.models import User
    #
    # async with get_session() as session:
    #     user = await session.get(User, user_id) if user_id else None
    #     token_json = decrypt_token(user.oauth_token_enc) if user and user.oauth_token_enc else None
    #
    # if not token_json:
    #     logger.warning("[gmail] No OAuth token available — email not sent")
    #     return
    #
    # creds = Credentials.from_authorized_user_info(json.loads(token_json))
    # service = build("gmail", "v1", credentials=creds)
    #
    # message = MIMEText(body)
    # message["to"]      = ", ".join(to)
    # message["subject"] = subject
    # raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    # service.users().messages().send(userId="me", body={"raw": raw}).execute()
