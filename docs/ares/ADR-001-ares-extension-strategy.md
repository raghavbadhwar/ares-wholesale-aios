# ADR-001: Ares Extension Strategy

## Status

Accepted.

## Decision

Implement Ares as a Hermes extension layer, not a hard fork of Hermes core.

The product code lives in `apps/ares/ares`, and Hermes integration lives in `plugins/ares`. The plugin registers an operator CLI command and namespaced skills. Core edits are limited to packaging metadata so the Ares package and assets are included.

## Rationale

- Ships the first concierge MVP quickly.
- Avoids invasive changes to `run_agent.py`, `cli.py`, `model_tools.py`, and gateway internals.
- Preserves Hermes update compatibility.
- Keeps client isolation explicit under `~/.ares/clients/<client_slug>/`.
- Allows later migration into deeper gateway, cron, MCP, or Google Workspace integrations only after pilot data proves the wedge.

## Consequences

- `hermes ares ...` depends on the bundled `ares` plugin being enabled.
- Ares workflows can also run directly with `python -m apps.ares.ares.cli`.
- Live Google/WhatsApp integrations remain connector adapters, not required for unit tests.

