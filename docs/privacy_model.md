# Atlas — Privacy Model

## Core Principle

Atlas is a **local-first** system. All data storage, processing, and decision-making
happens on the user's local machine. External services are contacted only when a workflow
explicitly requires it (e.g., sending an email, checking a calendar).

## Data Classification

| Level      | Description                          | Examples                              | Storage         |
|------------|--------------------------------------|---------------------------------------|-----------------|
| **Public** | Non-sensitive, freely shareable      | Weather data, public event listings   | Postgres        |
| **Internal** | Personal but non-critical          | Task lists, workflow states           | Postgres        |
| **Confidential** | Sensitive personal data         | Financial data, medical credentials   | Postgres (encrypted cols) |
| **Secret** | Credentials and tokens               | API keys, OAuth tokens, passwords     | Secrets manager |

## Privacy Controls

### Data at Rest
- PostgreSQL runs locally (Docker) with no external network exposure
- Confidential fields use column-level encryption (planned)
- Secrets stored via the secrets manager (OS keyring or encrypted file)
- No telemetry or analytics data collection

### Data in Transit
- External API calls use TLS exclusively
- Telegram bot API uses HTTPS webhook or long-polling
- Local service communication (Redis, Postgres) stays on localhost

### Data Sharing Rules
- **No data leaves the machine** unless a workflow action explicitly sends it
- Workflows at `approve` trust level require human confirmation before any external action
- Audit log records every external data transmission
- User can review and revoke any pending external action

### Browser Automation Privacy
- Playwright sessions are ephemeral (no persistent browser profiles by default)
- Card portal credentials are never logged or included in audit trail payloads
- Screenshots are stored locally and auto-purged after processing

## Trust Level Enforcement

The policy engine enforces privacy controls based on workflow trust levels:

- **auto**: Can read external data and perform pre-approved low-risk actions
- **suggest**: Can read external data but must present actions for user review
- **approve**: Must obtain explicit approval before any action, including data reads for sensitive sources

## TODO

- [ ] Define column-level encryption strategy
- [ ] Implement data retention policies (auto-purge old audit logs)
- [ ] Add data export capability (GDPR-style, even for personal use)
- [ ] Document per-workflow data flow diagrams
