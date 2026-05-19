# Ares Security and Privacy

## Client Isolation

Each pilot client has a separate directory under `~/.ares/clients/<client_slug>/`. Never mix client exports, reports, approvals, logs, memories, or custom skills.

## Secrets

Do not store API keys or OAuth tokens in Ares profile files. Use Hermes or Google Workspace credential mechanisms. Profiles may contain IDs for Sheets and Drive folders, but not tokens.

## Data Minimization

Prefer structured records and short summaries over raw chat dumps. Do not persist one-off messages as memory. Store raw exports only when needed for audit or debugging.

## Approval Gates

Approval is required before customer/supplier messages, payment status changes, ledger changes, credit limit changes, purchase orders, recurring workflow activation, and sensitive business rules.

## Logs and Reports

Reports should contain business summaries and action lists. Avoid copying full raw messages into reports unless the owner specifically needs evidence for a decision.

## Revocation

For offboarding, revoke Google access, remove scheduled cron jobs, archive the client directory, and disable any gateway routes for the client.

