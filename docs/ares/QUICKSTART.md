# Ares Wholesale AIOS Quickstart

Ares is a company brain for Indian wholesalers and distributors.

It uses Hermes as the runtime layer for CLI, tools, memory, cron, model routing, and gateway messaging. Ares adds the India-specific wholesaler workflows: WhatsApp-style owner approvals, Tally/Busy export ingestion, payment follow-ups, stock radar, order capture, and business memory.

## One-command setup

From a fresh machine with `git` and `uv` installed:

```bash
curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \
  --client gupta-distributors \
  --business-name "Gupta Distributors" \
  --owner-name "Mr Gupta"
```

This will:

1. Clone or update the Ares repo from `main`.
2. Set `ARES_HOME` to `~/.ares` unless overridden.
3. Verify `hermes ares` is registered.
4. Create the wholesaler client profile.
5. Run the first autonomous-cycle smoke test.
6. Print gateway and cron next steps.

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

After setup, Ares works as a top-level Hermes command group:

```bash
hermes ares setup \
  --client gupta-distributors \
  --business-name "Gupta Distributors" \
  --owner-name "Mr Gupta"

hermes ares autonomous-cycle --client gupta-distributors
hermes ares mobile-approvals --client gupta-distributors
hermes ares mobile-reply --client gupta-distributors --reply "haan appr_xxx"
hermes ares print-cron-specs --client gupta-distributors
```

When running from the source checkout, use `uv run`:

```bash
uv run hermes ares autonomous-cycle --client gupta-distributors
```

## Gateway setup

Start with Telegram for the pilot. Move to WhatsApp Business API once the workflow is proven.

```bash
hermes gateway setup
hermes gateway run
```

Or as a background service:

```bash
hermes gateway install
hermes gateway start
hermes gateway status
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
hermes ares print-cron-specs --client gupta-distributors
```

Use those specs to create Hermes cron jobs for:

- 9 AM Daily Battle Plan
- 2 PM Payment Radar
- 6 PM Evening Follow-up Summary
- Weekly War Room report

## Data ingestion

Pilot mode supports deterministic file/manifest ingestion:

```bash
hermes ares sync-drive-manifest \
  --client gupta-distributors \
  --manifest /path/to/drive-manifest.json
```

The manifest can point to:

- Tally/Busy outstanding CSV exports
- stock CSV exports
- forwarded WhatsApp/order/message text files

## Indian wholesaler pilot flow

1. Operator drops Tally/Busy exports, stock exports, and forwarded order files into intake.
2. Ares runs the autonomous cycle.
3. Owner receives a mobile-friendly approval list.
4. Owner replies in simple Indian English: `haan`, `approve`, `reject`, `baadme`, or `edit`.
5. Ares executes only approved actions and writes audit logs.
6. Ares updates business memory, for example: “Customer usually pays after Friday reminder.”

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
