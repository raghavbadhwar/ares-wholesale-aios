# Ares Wholesale AIOS

Ares is a Hermes-based vertical layer for concierge MVP pilots with Indian wholesalers, distributors, and stockists. It keeps the first build narrow: Sheets/Drive/export ingestion, payment radar, order capture, stock radar, daily briefs, weekly reports, durable business memory, and approval gates.

The package lives under `apps/ares/ares` and integrates with Hermes through the `plugins/ares` adapter. Client runtime state is isolated under `~/.ares/clients/<client_slug>/`.

## MVP Scope

- Google Sheets-ready repository abstraction, with in-memory fixtures for tests.
- Google Drive and forwarded-message event normalization.
- CSV export parsing for outstanding and stock reports.
- Approval-first sensitive actions.
- Payment radar, stock radar, order capture, daily brief, weekly war room, and approval center workflows.
- Mobile-friendly text/Markdown reporting.

## Local Run

```bash
python -m apps.ares.ares.cli create-sample-client --client demo-wholesale --business-name "Demo Wholesale" --owner-name "Owner"
python -m apps.ares.ares.cli run-workflow --client demo-wholesale --workflow daily-brief
```

When the bundled plugin is enabled, the same action is available as:

```bash
hermes ares run-workflow --client demo-wholesale --workflow daily-brief
```

