# Ares Wholesale AIOS Operator Runbook

This runbook is for the concierge deployment of Ares for Indian wholesalers.

The goal is simple: operator runs the morning loop, owner approves only sensitive/customer-facing actions, Ares keeps the audit trail and persistent memory.

## 1. Create a client

Preferred command:

```bash
ares setup \
  --client raj-demo \
  --business-name "Raj Demo Traders" \
  --owner-name "Raj"
```

Local state is stored under `~/.ares/clients/<client>/`:

- `profile.yaml` — client profile and connector flags
- `data/*.json` — persistent local business data
- `exports/` — dropped Tally/Busy/Vyapar CSVs
- `inbox/` — dropped forwarded message text files
- `reports/`, `approvals/`, `memory/`, `logs/` — operator-facing state and audit trail

## 2. Intake contract

### Exports folder

Drop CSV files into:

```text
~/.ares/clients/<client>/exports/
```

Supported filename cues:

- outstanding/receivables/invoice/payment → treated as receivables export
- stock/inventory → treated as stock export

Outstanding export required columns:

- customer: `customer_id` or `customer`
- amount: `amount`, `outstanding`, or `balance`

Stock export required columns:

- item: `sku_id`, `sku`, `product`, or `name`
- stock: `current_stock` or `stock`

### Inbox folder

Drop one `.txt` file per forwarded message into:

```text
~/.ares/clients/<client>/inbox/
```

Examples:

```text
Raj 5 box Surf kal bhejna
Gupta ji payment Friday ko karenge
```

## 3. Preflight validation

Before the morning loop, validate that the operator drops are usable:

```bash
ares validate-inputs --client raj-demo
```

What it checks:

- whether CSV files exist
- whether inbox text files exist
- whether export type can be inferred from filename
- whether required columns are present
- whether empty/invalid files would block ingestion

If output shows `Blocking issues: 0`, continue to the next step.

## 4. Morning operator loop

Run:

```bash
ares morning-run --client raj-demo
```

This command now does the real pilot loop:

1. ingest fresh dropped files once
2. update persistent local state
3. generate payment radar approvals
4. generate daily brief / stock / order summary
5. produce an owner-facing approval prompt

What the operator should read in the output:

- `Files ingested`
- `Overdue invoices`
- `Low-stock items`
- `Approvals created`
- `Owner message`

## 5. Owner approval loop

To preview the pending approvals again:

```bash
ares mobile-approvals --client raj-demo
```

Typical owner replies:

- `haan appr_xxx`
- `approve appr_xxx`
- `reject appr_xxx`
- `edit appr_xxx thoda soft tone me bhejo`
- `later appr_xxx`

Process reply:

```bash
ares mobile-reply --client raj-demo --reply "haan appr_xxx"
```

Important: Ares must not send customer/supplier-facing actions or mutate sensitive records without owner approval.

## 6. Approval rule

Owner approval is required before Ares performs or dispatches:

- customer-facing messages
- supplier-facing messages
- payment received / ledger / invoice status changes
- credit-limit or credit-extension changes
- purchase orders
- dispatch blocks
- recurring workflow activation
- sensitive business rules or memories

## 7. Scheduling

Print self-contained Hermes cron prompts:

```bash
ares print-cron-prompts --client raj-demo
```

Use those prompts with `cronjob(action="create")` or Hermes CLI scheduling. Cron prompts must remain self-contained and must not send customer messages or modify ledgers without approval.

## 8. Verification

Targeted Ares verification:

```bash
uv run --extra dev python -m pytest tests/ares/test_setup_bootstrap.py -q -o 'addopts='
uv run --extra dev python -m pytest tests/ares/test_validate_inputs.py -q -o 'addopts='
uv run --extra dev python -m pytest tests/ares/test_operator_morning_run.py -q -o 'addopts='
uv run --extra dev python -m pytest tests/ares/test_pilot_e2e.py -q -o 'addopts='
```

Full Ares verification:

```bash
uv run --extra dev python -m pytest tests/ares -q -o 'addopts='
```

Expected result for this implementation: all Ares tests pass.
