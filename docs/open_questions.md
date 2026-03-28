# Atlas Open Questions

Last updated: 2026-03-26

## True Hard Dependencies (Only)

1. Telegram credentials
- Needed for real notification delivery (beyond log channel).
- Required values:
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID

2. Gmail/Google OAuth credentials
- Needed to move communication workflows from manual input to live data.
- Required values:
  - GOOGLE_CLIENT_ID
  - GOOGLE_CLIENT_SECRET
  - GOOGLE_REDIRECT_URI

3. Home Assistant credentials
- Needed for home/presence automation workflows.
- Required values:
  - HOME_ASSISTANT_URL
  - HOME_ASSISTANT_TOKEN

4. Tesla tokens
- Needed only for travel/vehicle workflows.
- Required values:
  - TESLA_ACCESS_TOKEN
  - TESLA_REFRESH_TOKEN

## Architecture Choices With Safe Defaults (No Immediate User Input Needed)

- Keep FastAPI + SQLAlchemy + Redis + arq stack.
- Keep single-user local-first posture.
- Keep trust-level model with manual/approval controls.

## Non-Blocking Future Decision

- Data retention policy for long-term audit and memory data.
  - Default proposed: 365 days retention for detailed records, monthly rollups retained longer.
