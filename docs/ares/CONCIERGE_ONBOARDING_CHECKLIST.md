# Ares Concierge Onboarding Checklist

## Intake

- Business name, owner name, city, vertical, and primary language.
- Staff names, roles, and communication channels.
- Current operating systems: WhatsApp, Telegram, Tally, Busy, Vyapar, Marg, Google Sheets, Drive.
- Approval rules for payment, ledger, dispatch, supplier, and customer messages.
- Daily brief time and preferred report tone.

## Required Exports

- Customer list.
- Product/SKU list.
- Outstanding or receivable report.
- Stock report.
- Recent orders or WhatsApp/Telegram forwarded samples.
- Payment screenshots or bank CSV samples if available.

## Setup

- Create `~/.ares/clients/<client_slug>/profile.yaml`.
- Create isolated `memory`, `data`, `exports`, `reports`, `approvals`, `logs`, `workflows`, and `skills` folders.
- Create Google Drive folder structure.
- Create Google Sheet command center from `apps/ares/templates/google_sheets/wholesale_command_center.md`.
- Run payment radar, stock radar, and daily brief on fixtures first.

## Pilot Success Criteria

- Daily brief can be produced without manual compiling.
- Payment radar identifies overdue customers and drafts reminders for approval.
- Order tracker captures forwarded messages into pending orders or clarification requests.
- Stock radar flags low-stock items.
- Weekly report gives concrete priorities.
- At least five durable memories are proposed and approved during the pilot.

