# Atlas — Integration Adapter Notes

## Overview

Atlas communicates with external services through **14 integration adapters**, each
encapsulated in `atlas/integrations/<service>/adapter.py`. Adapters implement a common
interface for initialization, health checks, and service-specific operations.

## Adapter Inventory

| Adapter          | Directory                    | Auth Type       | Priority |
|------------------|------------------------------|-----------------|----------|
| Gmail            | `integrations/gmail/`        | OAuth2          | Phase 3  |
| Google Calendar  | `integrations/google_calendar/` | OAuth2       | Phase 3  |
| Google Drive     | `integrations/google_drive/` | OAuth2          | Phase 3  |
| Telegram         | `integrations/telegram/`     | Bot Token       | Phase 1  |
| Home Assistant   | `integrations/home_assistant/`| Long-lived Token| Phase 7  |
| Browser          | `integrations/browser/`      | Session/Cookies | Phase 6  |
| Card Portal      | `integrations/card_portal/`  | Credentials     | Phase 6  |
| Event Scraper    | `integrations/event_scraper/`| None (public)   | Phase 5  |
| Marketplace      | `integrations/marketplace/`  | API Key/OAuth   | Phase 6  |
| Speech           | `integrations/speech/`       | Local/API Key   | Phase 7  |
| Presence         | `integrations/presence/`     | Local network   | Phase 7  |
| Tesla            | `integrations/tesla/`        | OAuth2          | Phase 7  |
| Pricing Feed     | `integrations/pricing_feed/` | API Key/None    | Phase 5  |

> Note: The 14th adapter slot (if needed) is reserved for future integrations.

## Common Adapter Interface (Planned)

```python
class BaseAdapter:
    async def initialize(self) -> None: ...
    async def health_check(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

Each adapter extends this with service-specific methods.

## Authentication Patterns

- **OAuth2** (Gmail, Calendar, Drive, Tesla): Token refresh via secrets manager
- **Bot Token** (Telegram): Single long-lived token from .env
- **Long-lived Token** (Home Assistant): Stored in secrets manager
- **Credentials** (Card Portal): Encrypted username/password pairs
- **API Key** (Pricing Feed, Marketplace): Stored in secrets manager
- **Local** (Browser, Speech, Presence): No external auth needed

## TODO

- [ ] Define formal adapter protocol/ABC
- [ ] Document rate limiting strategy per adapter
- [ ] Add adapter health dashboard endpoint
- [ ] Document retry/backoff configuration per adapter
