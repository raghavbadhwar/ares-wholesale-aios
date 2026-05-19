# Ares Wholesale AIOS Operator Runbook

This runbook is for the concierge/MVP deployment of Ares for Indian wholesalers.

## 1. Create a client

```bash
ares onboard-client \
  --client raj-demo \
  --business-name "Raj Demo Traders" \
  --owner-name "Raj"
```

Local state is stored under `~/.ares/clients/<client>/`:

- `profile.yaml` — client profile and connector flags
- `data/*.json` — persistent local business data
- `exports/` — dropped Tally/Busy/Vyapar CSVs
- `approvals/`, `reports/`, `memory/` — operator-facing folders

## 2. Import data without manual entry

Preferred MVP routes:

1. Forward WhatsApp/Telegram order/payment text into Ares ingestion.
2. Drop Tally/Busy/Vyapar CSV exports and pass them to workflow commands.
3. Configure Google Sheets/Drive later using the client profile.

Examples:

```bash
ares run-workflow --client raj-demo --workflow payment-radar --outstanding-csv exports/tally_outstanding.csv
ares run-workflow --client raj-demo --workflow stock-radar --stock-csv exports/stock_export.csv
```

Ares persists imported CSV records in local JSON, so the next workflow run can use the same data without re-importing.

## 3. Daily operating loop

```bash
ares chat --client raj-demo
ares run-workflow --client raj-demo --workflow daily-brief
ares run-workflow --client raj-demo --workflow payment-radar
ares approval-center --client raj-demo
```

Daily brief is read-only. Payment radar creates approval drafts for reminders but does not send messages.

## 4. Approval rule

Owner approval is required before Ares performs or dispatches:

- customer-facing messages
- supplier-facing messages
- payment received / ledger / invoice status changes
- credit-limit or credit-extension changes
- purchase orders
- dispatch blocks
- recurring workflow activation
- sensitive business rules or memories

## 5. Scheduling

Print self-contained Hermes cron prompts:

```bash
ares print-cron-prompts --client raj-demo
```

Use those prompts with `cronjob(action="create")` or Hermes CLI scheduling. Cron prompts must remain self-contained and must not send customer messages or modify ledgers without approval.

## 6. Verification

From the Hermes repo:

```bash
uv run --extra dev python -m pytest tests/ares -q -o 'addopts='
```

Expected result for this implementation: all Ares tests pass.
