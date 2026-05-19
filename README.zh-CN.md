<p align="center">
  <img src="assets/banner.png" alt="Ares Wholesale AIOS" width="100%">
</p>

# Ares Wholesale AIOS

Ares is a company brain for Indian wholesalers and distributors.

This file is intentionally kept in English so the repository has one clear, India-focused product message. For the full landing page, read [README.md](README.md).

## Quick setup

```bash
curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \
  --client demo-wholesaler \
  --business-name "Demo Wholesale" \
  --owner-name "Raghav"
```

## Daily Ares commands

```bash
hermes ares autonomous-cycle --client demo-wholesaler
hermes ares mobile-approvals --client demo-wholesaler
hermes ares mobile-reply --client demo-wholesaler --reply "haan appr_xxx"
hermes ares print-cron-specs --client demo-wholesaler
```

## What Ares is built for

- Indian wholesale and distribution businesses
- WhatsApp-first operations
- simple Indian-English owner approvals
- Tally/Busy export ingestion
- Daily Battle Plan, Payment Radar, Stock Radar, and Order Capture
- Human-in-the-loop approval before external messages or ledger-impacting actions

## Docs

- [Ares Quickstart](docs/ares/QUICKSTART.md)
- [Operator Runbook](docs/ares/OPERATOR_RUNBOOK.md)
- [Security and Privacy](docs/ares/SECURITY_AND_PRIVACY.md)
- [Architecture Notes](docs/ares/architecture-notes.md)

Ares uses Hermes Agent as the runtime layer. Hermes provides the CLI, tools, gateway, memory, skills, cron, and model routing. Ares provides the Indian wholesaler workflows and operating system layer.
