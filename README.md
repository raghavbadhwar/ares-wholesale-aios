<p align="center">
  <img src="assets/banner.png" alt="Ares Wholesale AIOS" width="100%">
</p>

# Ares Wholesale AIOS

<p align="center">
  <a href="docs/ares/QUICKSTART.md"><img src="https://img.shields.io/badge/Ares-Quickstart-B11226?style=for-the-badge" alt="Ares Quickstart"></a>
  <a href="docs/ares/OPERATOR_RUNBOOK.md"><img src="https://img.shields.io/badge/Operator-Runbook-B87A2C?style=for-the-badge" alt="Operator Runbook"></a>
  <a href="https://github.com/raghavbadhwar/ares-wholesale-aios"><img src="https://img.shields.io/badge/Company%20Brain-Indian%20Wholesalers-B11226?style=for-the-badge" alt="Company Brain for Indian Wholesalers"></a>
  <a href="https://github.com/NousResearch/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
</p>

Ares is a company brain for Indian wholesalers and distributors.

It runs on the Hermes Agent runtime, but this repository is presented and operated as Ares: a vertical AIOS that watches business signals, remembers customer/vendor patterns, drafts owner actions, and asks for approval before anything ledger-impacting happens.

Ares is built for real Indian wholesale operations: WhatsApp-first workflows, simple Indian-English owner approvals, Tally/Busy export ingestion, daily battle plans, payment radar, stock radar, order capture, and audit-safe action execution.

## What Ares does

- Daily Battle Plan: morning owner brief with money, stock, order, and follow-up priorities.
- Payment Radar: finds overdue invoices and drafts polite collection follow-ups.
- Order Capture: turns forwarded messages into structured order drafts.
- Stock Radar: highlights low-stock and movement issues from exports.
- Business Memory: learns practical operating patterns such as customer payment habits.
- Approval Center: keeps humans in control before messages/actions are executed.
- Mobile Owner Interface: supports simple Indian-English replies like `haan appr_xxx`, `reject appr_xxx`, `baadme appr_xxx`.
- Cron/Gateway Ready: works with Hermes cron and messaging gateway for scheduled/remote operation.

## One-command setup

From a machine with `git` and `uv` installed:

```bash
curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \
  --client demo-wholesaler \
  --business-name "Demo Wholesale" \
  --owner-name "Raghav"
```

Then run:

```bash
hermes ares autonomous-cycle --client demo-wholesaler
hermes ares mobile-approvals --client demo-wholesaler
hermes ares mobile-reply --client demo-wholesaler --reply "haan appr_xxx"
hermes ares print-cron-specs --client demo-wholesaler
```

## Ares command surface

Ares is registered as a native Hermes command group:

```bash
hermes ares setup
hermes ares autonomous-cycle
hermes ares mobile-approvals
hermes ares mobile-reply
hermes ares sync-drive-manifest
hermes ares print-cron-specs
hermes ares approval-center
hermes ares list-clients
hermes ares list-workflows
```

Gateway slash command:

```text
/ares <client> cycle
/ares <client> approvals
/ares <client> reply haan appr_xxx
/ares <client> reply approve appr_xxx
```

## Pilot operator flow

1. Onboard the wholesaler with `hermes ares setup`.
2. Drop Tally/Busy exports, stock exports, and forwarded WhatsApp/order text into the configured intake paths.
3. Run `hermes ares autonomous-cycle --client <client>` manually or via cron.
4. Send the owner the output from `hermes ares mobile-approvals --client <client>`.
5. Process owner replies with `hermes ares mobile-reply --client <client> --reply "haan appr_xxx"`.
6. Review action logs and memory updates before the next cycle.

## Repository map

```text
apps/ares/                         Ares application package
apps/ares/ares/cli.py              Ares CLI command implementation
apps/ares/ares/workflows/          Payment, order, stock, brief, approval workflows
apps/ares/ares/connectors/         File, Drive-manifest, message, GWS connector layer
apps/ares/ares/memory/             Business memory learning loop
apps/ares/ares/face/               Owner/mobile approval interface
apps/ares/ares/execution/          Approved action execution + audit logging
plugins/ares/                      Hermes plugin registration for Ares
scripts/setup_ares.sh              One-command Ares setup script
docs/ares/QUICKSTART.md            Setup and first-run guide
docs/ares/OPERATOR_RUNBOOK.md      Concierge/operator runbook
docs/ares/FIX_AND_POLISH_PLAN.md   Technical roadmap
docs/ares/SECURITY_AND_PRIVACY.md  Safety and privacy notes
```

## Important design rule

Ares is approval-first.

It can ingest, analyze, remember, draft, summarize, and prepare actions. But owner-sensitive actions — payment follow-ups, ledger-impacting updates, external messages, or operational decisions — should go through approval gates and action logs.

## Local development

```bash
git clone https://github.com/raghavbadhwar/ares-wholesale-aios.git ares
cd ares
uv run hermes ares --help
ARES_HOME=/tmp/ares-dev ./scripts/setup_ares.sh --current-repo \
  --client demo-wholesaler \
  --business-name "Demo Wholesale" \
  --owner-name "Raghav"
uv run --extra dev python -m pytest tests/ares tests/hermes_cli/test_plugin_cli_registration.py -q
```

## Docs

- [Ares Quickstart](docs/ares/QUICKSTART.md)
- [Operator Runbook](docs/ares/OPERATOR_RUNBOOK.md)
- [Ares Extension Strategy](docs/ares/ADR-001-ares-extension-strategy.md)
- [Security and Privacy](docs/ares/SECURITY_AND_PRIVACY.md)
- [Architecture Notes](docs/ares/architecture-notes.md)
- [Fix and Polish Plan](docs/ares/FIX_AND_POLISH_PLAN.md)

## Runtime attribution

Ares is built on top of the open-source Hermes Agent runtime by Nous Research. Hermes provides the CLI agent, model routing, tools, memory, skills, cron scheduler, plugin system, and gateway infrastructure. Ares adds the wholesaler-specific workflows, command surface, memory patterns, approval UX, and operator runbooks.

Upstream runtime:
https://github.com/NousResearch/hermes-agent

This Ares distribution:
https://github.com/raghavbadhwar/ares-wholesale-aios
