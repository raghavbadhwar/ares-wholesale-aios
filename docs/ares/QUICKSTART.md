# Ares Wholesale AIOS Quickstart

Ares is a company brain for Indian wholesalers and distributors.

It uses Hermes as the runtime layer for CLI, tools, memory, cron, model routing, and gateway messaging. Ares adds the India-specific wholesaler workflows: WhatsApp-style owner approvals, Tally/Busy export ingestion, payment follow-ups, stock radar, order capture, and business memory.

## One-command setup

From a fresh machine with `git` installed. The installer will use `uv`, and can install `uv` automatically if it is missing:

```bash
curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \
  --client gupta-distributors \
  --business-name "Gupta Distributors" \
  --owner-name "Mr Gupta"
```

This will:

1. Clone or update the Ares repo from `main`.
2. Set `ARES_HOME` to `~/.ares` unless overridden.
3. Verify the local Ares command is available.
4. Create the wholesaler client profile.
5. Create pilot intake folders and README placeholders.
6. Print the exact next commands for validation, morning-run, and approvals.

## Local developer setup

From an existing checkout:

```bash
cd /Volumes/RAGHAV2/hermes
export ARES_HOME=/Users/raghav/.ares
./scripts/setup_ares.sh --current-repo \
  --client demo-wholesaler \
  --business-name "Demo Wholesale" \
  --owner-name "Raghav"
```

## Native Ares commands

After setup, use the installed `ares` wrapper from any terminal:

```bash
ares setup \
  --client gupta-distributors \
  --business-name "Gupta Distributors" \
  --owner-name "Mr Gupta"

# preflight dropped files
ares validate-inputs --client gupta-distributors

# main operator loop
ares morning-run --client gupta-distributors

# owner approval surface
ares mobile-approvals --client gupta-distributors
ares mobile-reply --client gupta-distributors --reply "haan appr_xxx"

# optional direct ops
ares chat --client gupta-distributors
ares autonomous-cycle --client gupta-distributors
ares print-cron-specs --client gupta-distributors
```

When running from the source checkout, use `uv run`:

```bash
ARES_HOME=/Users/raghav/.ares uv run hermes ares validate-inputs --client gupta-distributors
ARES_HOME=/Users/raghav/.ares uv run hermes ares morning-run --client gupta-distributors
```

## Pilot folder layout

Each client lives under `~/.ares/clients/<client>/`.

Important subfolders:

- `profile.yaml` — client profile and connector flags
- `data/` — persistent JSON business state
- `exports/` — CSV drop for Tally/Busy/Vyapar exports
- `inbox/` — forwarded customer/order/payment text files (`.txt`)
- `reports/` — saved operator-facing outputs
- `approvals/`, `memory/`, `logs/`, `workflows/`, `skills/` — audit and operating state

Setup now also creates placeholder READMEs in `exports/`, `inbox/`, and `reports/` so an operator can understand what belongs where.

## Data ingestion contract

### Export filenames

Use obvious filenames so Ares can infer type:

- outstanding / receivables: `tally_outstanding.csv`, `receivables.csv`, `invoice_overdue.csv`
- stock / inventory: `stock_export.csv`, `inventory.csv`

### Outstanding CSV required columns

Ares accepts aliases for these fields:

- customer: `customer_id` or `customer`
- amount: `amount`, `outstanding`, or `balance`

Optional:

- invoice: `invoice_number`, `invoice`, or `id`
- due date: `due_date`
- status: `status`

### Stock CSV required columns

Ares accepts aliases for these fields:

- sku/item: `sku_id`, `sku`, `product`, or `name`
- current stock: `current_stock` or `stock`

Optional:

- reorder level: `reorder_level` or `min_stock`
- unit: `unit`
- supplier: `supplier_id`

### Inbox messages

Drop one forwarded message per `.txt` file into `inbox/`.

Examples:

```text
Raj 5 box Surf kal bhejna
Gupta ji payment Friday ko karenge
```

## Real pilot operating loop

Use this loop every morning for a concierge pilot:

1. Drop fresh CSV exports into `exports/`.
2. Drop forwarded order/payment/customer text messages into `inbox/`.
3. Run:

```bash
ares validate-inputs --client gupta-distributors
ares morning-run --client gupta-distributors
```

4. Read the operator summary.
5. Send the owner-facing approvals prompt over Telegram/WhatsApp.
6. Owner replies with simple commands such as:
   - `haan appr_xxx`
   - `approve appr_xxx`
   - `reject appr_xxx`
   - `edit appr_xxx thoda soft tone me bhejo`
   - `later appr_xxx`
7. Run the reply back through Ares:

```bash
ares mobile-reply --client gupta-distributors --reply "haan appr_xxx"
```

## Gateway setup

Start with Telegram for the pilot. Move to WhatsApp Business API once the workflow is proven.

```bash
ares-hermes gateway setup
ares-hermes gateway run
```

Or as a background service:

```bash
ares-hermes gateway install
ares-hermes gateway start
ares-hermes gateway status
```

Ares also registers a gateway/CLI slash command:

```text
/ares gupta-distributors cycle
/ares gupta-distributors approvals
/ares gupta-distributors reply haan appr_xxx
/ares gupta-distributors reply approve appr_xxx
```

## Cron setup

Generate default schedule specs:

```bash
ares print-cron-specs --client gupta-distributors
```

Use those specs to create Hermes cron jobs for:

- 9 AM Daily Battle Plan
- 2 PM Payment Radar
- 6 PM Evening Follow-up Summary
- Weekly War Room report

## Drive-manifest ingestion

Pilot mode also supports deterministic file/manifest ingestion:

```bash
ares sync-drive-manifest \
  --client gupta-distributors \
  --manifest /path/to/drive-manifest.json
```

The manifest can point to:

- Tally/Busy outstanding CSV exports
- stock CSV exports
- forwarded WhatsApp/order/message text files

## Useful paths

Default data root:

```text
~/.ares
```

Per-client profile:

```text
~/.ares/clients/<client>/profile.yaml
```

Operator runbook:

```text
docs/ares/OPERATOR_RUNBOOK.md
```
