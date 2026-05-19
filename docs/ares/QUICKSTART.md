# Ares Wholesale AIOS Quickstart

Ares is a vertical Hermes distribution/plugin for Indian wholesalers and distributors.
It uses Hermes for the runtime, gateway, cron, model routing, tools, and memory; Ares adds the wholesaler workflows.

## One-command setup

From a fresh machine with `git` and `uv` installed:

```bash
curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/hermes-agent/codex/ares-wholesale-aios/scripts/setup_ares.sh | bash -s -- \
  --client gupta-distributors \
  --business-name "Gupta Distributors" \
  --owner-name "Mr Gupta"
```

This will:

1. Clone/update the Hermes branch that contains Ares.
2. Set `ARES_HOME` to `~/.ares` unless overridden.
3. Verify `hermes ares` is registered.
4. Create the client profile.
5. Run a first autonomous-cycle smoke test.
6. Print the gateway and cron next steps.

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

## Native Hermes commands

After setup, Ares works as a top-level Hermes command:

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

Start with Telegram first; move to WhatsApp Business API later.

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

- 9 AM daily battle plan
- 2 PM payment radar
- 6 PM evening follow-up summary
- weekly war-room report

## Data ingestion

Early pilot mode supports deterministic file/manifest ingestion:

```bash
hermes ares sync-drive-manifest \
  --client gupta-distributors \
  --manifest /path/to/drive-manifest.json
```

The manifest can point to:

- Tally/Busy outstanding CSV exports
- stock CSV exports
- forwarded order/message text files

## Pilot flow

1. Client/operator drops Tally/Busy exports and forwarded order files.
2. Ares runs an autonomous cycle.
3. Owner receives mobile-friendly approvals.
4. Owner replies with `haan`, `approve`, `reject`, `baadme`, or `edit`.
5. Ares executes only approved actions and writes audit logs.

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
