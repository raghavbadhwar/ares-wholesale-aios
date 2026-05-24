---
name: ares-agent
description: "Operate and extend Ares Wholesale AIOS in this repository."
version: 3.0.0
author: Ares Wholesale AIOS
license: MIT
platforms: [linux, macos, windows]
metadata:
  ares:
    tags: [ares, wholesale, workflows, approvals, audit, cli, dashboard, local-contracts]
    repo_contract: hermes-ares
---

# Ares Wholesale AIOS

Use this skill only for the Ares vertical product in this repository:

- local company-brain workflows for Indian wholesalers and distributors
- approval-first owner workflows
- WhatsApp/message intake, order capture, payment radar, stock radar, daily brief, and weekly war-room flows
- local/sandbox connector contracts for GST, payment gateway, Tally/Busy-style accounting sync, supplier payments, and evidence handoff
- Hermes command surfaces exposed as `hermes ares ...` and, after setup, the installed `ares ...` wrapper

This is not the upstream generic Nous Ares Agent framework. Do not import assumptions about generic agent setup, model pools, platform gateways, session search, autonomous code-agent delegation, or persistent memory unless this repository exposes and verifies those surfaces.

## Default Stance

Every query, task, and problem should be treated as a wholesaler AIOS problem first.

- Do not answer like a generic assistant when the user is operating Ares.
- Translate broad requests into wholesaler operating jobs: collections, order capture, dispatch, stock risk, supplier coordination, GST/compliance, approvals, and owner visibility.
- Favor action-oriented wholesaler outputs: what happened, what is blocked, what needs approval, what affects cash flow, and what should happen next.
- If a user asks something abstract, tie it back to the wholesaler workflow surface that should answer it.

## Non-Negotiable Runtime Rules

- LLMs may summarize, draft, classify, and propose.
- Code verifies deterministic facts.
- Policy and approval services decide whether a sensitive action can proceed.
- Human approval is required for high-risk money, ledger, customer/supplier messaging, dispatch, credit, filing, or external connector actions.
- Audit logs must record workflow runs, approvals, attempted actions, local/sandbox connector events, and evidence handoffs.
- External integrations remain local or sandbox-contract only unless live sandbox evidence is present in the repo and tests.

## Command Contract

User-facing Ares commands are:

```bash
hermes ares list-workflows
hermes ares run-workflow --client <client> --workflow daily-brief
hermes ares run-workflow --client <client> --workflow order-capture
hermes ares autonomous-cycle --client <client>
hermes ares mobile-approvals --client <client>
hermes ares owner-reply --client <client> --reply "haan appr_xxx"
hermes ares health-check --client <client>
hermes ares operator-shell --client <client>
hermes ares dashboard --client <client>
```

After `scripts/setup_ares.sh` installs the wrapper, the same commands may be run as `ares ...`. If the wrapper is missing or stale, run from the repo root with both homes set:

```bash
ARES_HOME=<ares-home> HERMES_HOME=<ares-home> uv run hermes ares <command> --client <client>
```

## Workflow Contract

Treat `apps/ares/ares/orchestrator/router.py` as the authoritative workflow registry. Do not advertise a workflow unless it appears in `WORKFLOW_ALIASES` and has executable router behavior.

Core local workflows:

- `daily-brief`
- `order-capture`
- `payment-radar`
- `stock-radar`
- `weekly-war-room`

Dashboard, command-center, chat context, and docs should derive from this contract or be tested against it.

## Tool Contract

Treat `agent/transports/ares_tools_mcp_server.py` as the Codex-runtime tool contract. Do not claim unavailable tools in server instructions. If `EXPOSED_TOOLS` names a tool, tests must prove it exists in the live registry returned by `get_tool_definitions()`.

Current tool messaging must not claim:

- subagent delegation
- persistent memory search
- cross-session search
- todo/kanban operations
- vision or image generation
- web search/extraction

unless the tool is registered and the MCP contract test is updated.

## Development Workflow

Before changing Ares behavior:

1. Inspect the actual repo files.
2. Keep edits scoped to the failing workflow, command, tool, or connector contract.
3. Prefer local/sandbox adapters and contract tests over live integrations.
4. Run the smallest relevant pytest target first.
5. Run broader `tests/ares` gates when shared models, repository contracts, CLI, or connector behavior changed.
6. Report exact commands and pass/fail results.

## Verification Shortcuts

```bash
UV_CACHE_DIR=/private/tmp/ares-uv-cache ARES_HOME=/tmp/ares-smoke HERMES_HOME=/tmp/ares-smoke uv run hermes ares list-workflows
UV_CACHE_DIR=/private/tmp/ares-uv-cache ARES_HOME=/tmp/ares-smoke HERMES_HOME=/tmp/ares-smoke uv run python -m pytest tests/ares/test_workflows_cli_plugin.py -q -o 'addopts='
UV_CACHE_DIR=/private/tmp/ares-uv-cache ARES_HOME=/tmp/ares-smoke HERMES_HOME=/tmp/ares-smoke uv run python -m pytest tests/agent/transports/test_ares_tools_mcp_server.py -q -o 'addopts='
```
