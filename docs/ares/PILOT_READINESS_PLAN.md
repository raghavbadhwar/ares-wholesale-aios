# Ares Pilot Readiness Implementation Plan

> **For Hermes:** Use `software-development/writing-plans` and `software-development/subagent-driven-development` if executing this later task-by-task.

**Goal:** Move Ares from a working local MVP to a pilot-ready concierge product for one real Indian wholesaler.

**Architecture:** Keep Ares as a Hermes app/plugin layer. Do **not** broaden scope into full ERP or multi-tenant SaaS. The shortest path is: make onboarding deterministic, make local ingestion reliable, make owner approval delivery runnable every day, and prove the whole loop with one end-to-end pilot fixture.

**Tech Stack:** Python, Hermes plugin system, pytest, Pydantic, local JSON persistence under `~/.ares/clients/<slug>/`, CSV-based exports, optional GWS/Drive adapters.

---

## Current verified baseline

Already confirmed working:
- CLI wrapper: `/Users/raghav/.ares/bin/ares`
- Commands exist: `setup`, `onboard-client`, `run-workflow`, `autonomous-cycle`, `mobile-approvals`, `mobile-reply`, `sync-drive-manifest`, `print-cron-specs`
- Core workflows exist: `daily-brief`, `payment-radar`, `stock-radar`, `approval-center`, `weekly-war-room`, `autonomous-cycle`
- Hermes integration exists via `plugins/ares/__init__.py`
- Local persistence exists via `apps/ares/ares/data/json_repository.py` and `apps/ares/ares/data/factory.py`
- Local deterministic ingestion exists via `apps/ares/ares/connectors/auto_ingest.py`
- CSV parsers exist via `apps/ares/ares/connectors/export_parser.py`
- Demo profile exists but has no real connectors/data
- Verified tests: `41 passed`

So the remaining gap is **not** “build Ares.” It is **operationalize Ares for a pilot**.

---

## What to skip

Do **not** spend the next cycle on:
- full WhatsApp Business API productization
- hosted SaaS control plane
- Postgres/database migration
- ERP-grade accounting sync
- generic multi-vertical abstractions
- autonomous customer/supplier sending without approval

These are later-stage problems.

---

## Success definition for this plan

Ares is pilot-ready when all 5 are true:
1. A new client can be created with one command and a complete local folder scaffold.
2. A human operator can drop CSV/TXT files into the client folders and get useful outputs without hand-editing internals.
3. The owner can receive a daily brief and approval prompt in a mobile-friendly format.
4. Approving/rejecting a draft action updates state durably and predictably.
5. One end-to-end acceptance test proves the whole concierge loop works from raw exports to owner-facing output.

---

# Phase 1: Make onboarding and setup impossible to mess up

### Task 1: Turn `ares setup` into the canonical pilot bootstrap

**Objective:** One command should create a client that is actually ready for pilot ops, not just a bare profile.

**Files:**
- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/profiles.py`
- Modify: `apps/ares/ares/paths.py`
- Modify: `docs/ares/QUICKSTART.md`
- Test: `tests/ares/test_workflows_cli_plugin.py`

**Required behavior:**
- `ares setup --client ... --business-name ... --owner-name ...` should:
  - create profile
  - create all expected folders under `~/.ares/clients/<slug>/`
  - create empty placeholder files or README notes inside `exports/`, `inbox/`, and `reports/`
  - print the exact next 3 commands the operator should run
  - print the exact folder paths where exports/messages must be dropped
- Keep `onboard-client` as the lower-level primitive, but document `setup` as the primary path.

**Verification:**
```bash
/Users/raghav/.ares/bin/ares setup --client test-pilot --business-name "Test Wholesale" --owner-name "Raghav" --sample
/Users/raghav/.ares/bin/ares show-client --client test-pilot
```
Expected:
- profile created
- folders exist
- output shows next actions clearly

---

### Task 2: Add a setup regression test for scaffold completeness

**Objective:** Prevent future breakage where setup creates a profile but forgets pilot folders/files.

**Files:**
- Create: `tests/ares/test_setup_bootstrap.py`

**Test cases:**
- `setup` creates client root
- `setup` creates `data/`, `exports/`, `inbox/`, `reports/`, `approvals/`, `logs/`, `workflows/`, `skills/`
- `setup` emits operator guidance text with exact paths

**Verification:**
```bash
cd /Users/raghav/.ares/ares
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_setup_bootstrap.py -q -o 'addopts='
```

---

# Phase 2: Make ingestion useful for a real pilot, not just fixtures

### Task 3: Standardize import contracts for outstanding and stock exports

**Objective:** Ares should tell the operator exactly what CSV formats are accepted and fail clearly when columns are missing.

**Files:**
- Modify: `apps/ares/ares/connectors/export_parser.py`
- Modify: `apps/ares/ares/connectors/auto_ingest.py`
- Create: `docs/ares/EXPORT_CONTRACTS.md`
- Test: `tests/ares/test_persistence_approvals_ingestion.py`

**Required behavior:**
- Define accepted columns for:
  - outstanding/receivables CSV
  - stock CSV
- On bad CSV shape, return actionable error messages such as:
  - missing required columns
  - unsupported file type
  - zero valid rows parsed
- `auto_ingest.py` should include these parser errors in the operator-facing summary, not hide them.

**Verification:**
```bash
cd /Users/raghav/.ares/ares
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_persistence_approvals_ingestion.py -q -o 'addopts='
```

---

### Task 4: Add a command that validates a client’s dropped files before running workflows

**Objective:** Give the operator a fast preflight check before the morning run.

**Files:**
- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/connectors/auto_ingest.py`
- Create: `tests/ares/test_validate_inputs.py`

**New command:**
- `ares validate-inputs --client <slug>`

**Required behavior:**
- scan `exports/*.csv` and `inbox/*.txt`
- report counts
- report parseable/unparseable files
- exit non-zero only on true blocking issues

**Verification:**
```bash
/Users/raghav/.ares/bin/ares validate-inputs --client demo-wholesaler
```
Expected:
- useful summary even when folders are empty

---

# Phase 3: Make the owner loop truly runnable every day

### Task 5: Add a deterministic “operator morning run” command

**Objective:** One command should encapsulate the actual concierge daily workflow.

**Files:**
- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/autonomy/runner.py`
- Modify: `apps/ares/ares/face/mobile_approval.py`
- Create: `tests/ares/test_operator_morning_run.py`

**New command:**
- `ares morning-run --client <slug>`

**Required behavior:**
- perform auto-ingest
- run payment radar
- run stock radar
- build daily brief
- render pending approvals in a mobile-friendly block
- output one final operator summary with:
  - files ingested
  - overdue/risky customers found
  - low-stock items found
  - approvals created
  - next action for the human operator

This is better than forcing the operator to manually chain 3–5 commands.

**Verification:**
```bash
/Users/raghav/.ares/bin/ares morning-run --client demo-wholesaler
```
Expected:
- one concise actionable output block

---

### Task 6: Make owner-facing output deliverable, not just printable

**Objective:** Ares already renders mobile-friendly approval text; now make the delivery path explicit and reliable for pilot use.

**Files:**
- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/face/mobile_approval.py`
- Modify: `docs/ares/OPERATOR_RUNBOOK.md`
- Test: `tests/ares/test_mobile_drive_upgrade.py`

**Required behavior:**
- clearly separate:
  - `render` path: produce message text
  - `deliver` path: emit text suitable for Hermes Telegram delivery or manual copy-paste
- add one canonical documented pilot path:
  - Hermes cron/job generates output
  - delivery target is owner on Telegram
- do **not** build WhatsApp automation yet; document manual-forward or Telegram-first path.

**Verification:**
```bash
/Users/raghav/.ares/bin/ares mobile-approvals --client demo-wholesaler
/Users/raghav/.ares/bin/ares print-cron-specs --client demo-wholesaler
```
Expected:
- clean owner-facing prompt
- cron specs usable without manual editing

---

# Phase 4: Prove end-to-end pilot readiness in tests

### Task 7: Add one acceptance test for the full concierge loop

**Objective:** Encode the real product promise in one end-to-end test.

**Files:**
- Create: `tests/ares/test_pilot_readiness_e2e.py`
- Reuse/inspect: `tests/ares/test_autonomous_operator.py`
- Reuse/inspect: `tests/ares/test_persistence_approvals_ingestion.py`

**Scenario:**
1. create temp client profile
2. drop one outstanding CSV
3. drop one stock CSV
4. drop one inbox text order message
5. run `morning-run`
6. assert:
   - invoices persisted
   - stock persisted
   - at least one approval created for customer reminder or unclear order
   - daily brief contains real signals
   - mobile approval prompt contains actionable items

**Verification:**
```bash
cd /Users/raghav/.ares/ares
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_pilot_readiness_e2e.py -q -o 'addopts='
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='
```

---

# Phase 5: Tighten operator docs so a non-dev can actually run it

### Task 8: Rewrite the quickstart around the pilot flow, not code structure

**Objective:** Docs should match the operator journey.

**Files:**
- Modify: `docs/ares/QUICKSTART.md`
- Modify: `docs/ares/OPERATOR_RUNBOOK.md`
- Modify: `docs/ares/CONCIERGE_ONBOARDING_CHECKLIST.md`

**Required structure:**
1. Create client
2. Drop exports
3. Validate inputs
4. Run morning cycle
5. Review approvals
6. Send owner message
7. Process owner reply
8. Schedule the cycle

**Verification:**
- A new operator should be able to follow docs with zero code reading.

---

## Suggested implementation order

If doing the shortest useful sequence, do it in this order:
1. Task 1 — canonical setup bootstrap
2. Task 2 — setup regression test
3. Task 3 — import contracts and clear parser errors
4. Task 4 — `validate-inputs`
5. Task 5 — `morning-run`
6. Task 7 — end-to-end pilot readiness test
7. Task 6 — delivery-path cleanup
8. Task 8 — docs rewrite

That order gets you to a usable pilot fastest.

---

## Commands to use as the release gate

Run all of these before calling Ares pilot-ready:

```bash
cd /Users/raghav/.ares/ares
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='
/Users/raghav/.ares/bin/ares setup --client smoke-pilot --business-name "Smoke Wholesale" --owner-name "Raghav" --sample
/Users/raghav/.ares/bin/ares validate-inputs --client smoke-pilot
/Users/raghav/.ares/bin/ares morning-run --client smoke-pilot
/Users/raghav/.ares/bin/ares mobile-approvals --client smoke-pilot
/Users/raghav/.ares/bin/ares print-cron-specs --client smoke-pilot
```

Expected release-gate outcome:
- tests green
- setup works from zero
- empty-state validation is clear
- morning-run output is actionable
- owner approval prompt is readable
- cron specs are directly usable

---

## Definition of done

Ares is “pilot-ready” when:
- a non-dev operator can onboard one client in under 20 minutes
- CSV drops consistently produce useful payment/stock signals
- owner can receive and respond to approvals from mobile-friendly text
- state persists across runs
- the whole flow is protected by automated tests

---

## After this plan, but not before

Only once the above is complete should you consider:
- Google Sheets as the default backend instead of optional adapter
- Drive sync as the primary intake path instead of local folders
- WhatsApp API delivery
- multi-client hosted ops dashboard
- vertical-specific modules beyond the first wholesaler wedge
