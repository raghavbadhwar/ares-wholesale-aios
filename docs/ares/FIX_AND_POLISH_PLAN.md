# Ares Wholesale AIOS Fixing and Polishing Plan

> For Codex: implement this plan task-by-task. Keep Ares as a Hermes plugin/app layer, not a broad Hermes core fork. Use TDD for every code change. Run the exact verification commands after each task.

Goal: Turn the current Ares scaffold into a reliable concierge-MVP layer inside Hermes for Indian wholesalers.

Architecture: Ares should remain under `apps/ares` with a Hermes plugin adapter under `plugins/ares`. Workflows should depend on repository/connector abstractions, not hard-coded in-memory state. Sensitive business actions must always go through approval gates. Data ingestion should degrade gracefully: Google Sheets/Drive if configured, CSV/manual fallback if not.

Tech Stack: Python, Hermes plugin system, Pydantic models, pytest, PyYAML, Google Workspace/GWS or injected Google clients, local client state under `~/.ares/clients/<client_slug>/`.

---

## Current State Summary

Observed path: `/Volumes/RAGHAV2/hermes`

Current Ares areas:

- `apps/ares/ares/cli.py`
- `apps/ares/ares/data/models.py`
- `apps/ares/ares/data/repository.py`
- `apps/ares/ares/approvals/service.py`
- `apps/ares/ares/orchestrator/router.py`
- `apps/ares/ares/workflows/*.py`
- `apps/ares/ares/connectors/*.py`
- `apps/ares/ares/agents/memory_agent.py`
- `apps/ares/ares/skills/wholesale_india/*.md`
- `plugins/ares/__init__.py`
- `tests/ares/*.py`

Verification already run externally:

```bash
PYTHONPATH=/Volumes/RAGHAV2/hermes uv run --no-project --with pytest --with pydantic --with pyyaml python -m pytest /Volumes/RAGHAV2/hermes/tests/ares -q -o 'addopts='
```

Observed result:

```text
21 passed
```

But normal project build failed because `pyproject.toml` has invalid `tool.setuptools.package-data` dotted keys.

---

## Critical Fix Order

1. Fix packaging/build config.
2. Add persistent client repository/state.
3. Remove duplicated approval creation from daily brief/payment radar.
4. Strengthen approval action taxonomy.
5. Implement real Google Sheets read/write adapter or GWS-backed adapter.
6. Implement Drive/file ingestion routing.
7. Integrate MemoryAgent into workflows.
8. Improve order extraction fallback and approval flow.
9. Polish CLI/plugin UX.
10. Add end-to-end pilot readiness tests and docs.

---

# Phase 1: Build and Packaging Fixes

## Task 1: Fix `pyproject.toml` package-data keys

Objective: Make normal `uv run`, editable install, and package discovery work again.

Files:

- Modify: `pyproject.toml`

Problem:

Current unquoted dotted keys are interpreted as nested TOML tables:

```toml
apps.ares = ["config/**/*.yaml", "ares/skills/**/*.md", "templates/**/*.md", "demo/**/*"]
plugins.ares = ["plugin.yaml"]
```

Change to quoted package names:

```toml
"apps.ares" = ["config/**/*.yaml", "ares/skills/**/*.md", "templates/**/*.md", "demo/**/*"]
"plugins.ares" = ["plugin.yaml"]
```

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares -q -o 'addopts='
```

Expected:

- project builds successfully
- Ares tests run
- output ends with all tests passing

Commit:

```bash
git add pyproject.toml
git commit -m "fix(ares): correct package data configuration"
```

---

## Task 2: Add packaging regression test or build check

Objective: Prevent this packaging bug from coming back.

Files:

- Create/Modify: `tests/ares/test_packaging.py`

Test idea:

```python
from pathlib import Path
import tomllib


def test_ares_package_data_uses_quoted_package_names():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    package_data = data["tool"]["setuptools"]["package-data"]

    assert "apps.ares" in package_data
    assert "plugins.ares" in package_data
    assert "apps" not in package_data
    assert "plugins" not in package_data
```

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_packaging.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add tests/ares/test_packaging.py
git commit -m "test(ares): guard package data config"
```

---

# Phase 2: Persistent Client State

## Task 3: Introduce a JSON-backed client repository

Objective: Stop using only `InMemoryRepository` for real CLI runs. Persist client data under `~/.ares/clients/<client_slug>/data/`.

Files:

- Create: `apps/ares/ares/data/json_repository.py`
- Test: `tests/ares/test_json_repository.py`

Design:

Use simple JSON files first. Do not introduce Postgres yet.

Suggested files per client:

```text
~/.ares/clients/<client_slug>/data/customers.json
~/.ares/clients/<client_slug>/data/products.json
~/.ares/clients/<client_slug>/data/orders.json
~/.ares/clients/<client_slug>/data/invoices.json
~/.ares/clients/<client_slug>/data/payments.json
~/.ares/clients/<client_slug>/data/stock_records.json
~/.ares/clients/<client_slug>/data/approvals.json
~/.ares/clients/<client_slug>/data/memories.json
~/.ares/clients/<client_slug>/data/workflow_runs.json
```

Implementation notes:

- Class name: `JsonClientRepository`
- Subclass or implement `BusinessRepository`
- Load all JSON at init
- Write after every mutating method
- Use Pydantic `model_dump(mode="json")`
- Use atomic write: write temp file, then rename
- Keep format simple: list of objects per file

Test cases:

1. `upsert_invoice()` persists to disk.
2. New repository instance reloads invoice.
3. `create_approval()` persists pending approval.
4. `save_memory()` persists memory.
5. Corrupt/missing files degrade gracefully with empty list or clear error.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_json_repository.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/data/json_repository.py tests/ares/test_json_repository.py
git commit -m "feat(ares): add persistent JSON client repository"
```

---

## Task 4: Make CLI use persistent repository by default

Objective: `ares run-workflow` should use the client's stored data, not a fresh empty in-memory repo.

Files:

- Modify: `apps/ares/ares/cli.py`
- Modify: `tests/ares/test_workflows_cli_plugin.py` or create `tests/ares/test_cli_persistence.py`

Current issue:

```python
repo = InMemoryRepository()
```

Change:

- Load profile.
- Create `JsonClientRepository(client_root(profile.client_slug) / "data")`.
- Import CSV rows into persistent repo when CSV flags are passed.
- Then run workflow.

Important behavior:

- If user passes `--outstanding-csv`, persist parsed invoices.
- If user passes `--stock-csv`, persist parsed stock.
- Next run without CSV should still see previous data.

Tests:

1. Create sample client in temp ARES_HOME.
2. Run payment radar with outstanding CSV.
3. Run daily brief without CSV.
4. Assert outstanding data is still present.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_cli_persistence.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/cli.py tests/ares/test_cli_persistence.py
git commit -m "feat(ares): persist CLI workflow data per client"
```

---

# Phase 3: Approval Semantics and Duplicate Prevention

## Task 5: Split payment radar analysis from side effects

Objective: Daily brief should not create duplicate approval requests every time it runs.

Files:

- Modify: `apps/ares/ares/workflows/payment_radar.py`
- Modify: `apps/ares/ares/workflows/daily_brief.py`
- Test: `tests/ares/test_payment_radar_side_effects.py`

New API shape:

```python
def analyze_payment_radar(repository, *, today=None) -> dict:
    """Pure analysis. No approvals created."""


def create_payment_reminder_approvals(repository, approvals, *, client_id, priorities) -> list[ApprovalRequest]:
    """Creates approval requests idempotently."""


def run_payment_radar(repository, approvals, *, client_id, today=None, create_approvals=True) -> dict:
    """Workflow wrapper."""
```

Daily brief should call:

```python
payment = run_payment_radar(..., create_approvals=False)
```

Standalone `payment-radar` workflow may call with `create_approvals=True`.

Tests:

1. `analyze_payment_radar()` creates zero approvals.
2. `run_daily_brief()` creates zero new payment approvals.
3. `run_payment_radar(create_approvals=True)` creates approvals.
4. Re-running `run_payment_radar(create_approvals=True)` does not duplicate approvals for same invoice/action.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_payment_radar_side_effects.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/workflows/payment_radar.py apps/ares/ares/workflows/daily_brief.py tests/ares/test_payment_radar_side_effects.py
git commit -m "fix(ares): make payment radar approvals idempotent"
```

---

## Task 6: Add approval deduplication to repository/service

Objective: Prevent duplicate approval spam across all workflows.

Files:

- Modify: `apps/ares/ares/data/models.py`
- Modify: `apps/ares/ares/data/repository.py`
- Modify: `apps/ares/ares/approvals/service.py`
- Modify: `apps/ares/ares/data/json_repository.py`
- Test: `tests/ares/test_approvals_memory.py`

Add field to `ApprovalRequest`:

```python
dedupe_key: str | None = None
```

Approval service behavior:

- If a pending approval exists for same `client_id`, `type`, and `dedupe_key`, return existing approval.
- If no `dedupe_key`, preserve current behavior.

Suggested dedupe keys:

- Payment reminder: `payment_reminder:<invoice_id>`
- Payment match: `payment_match:<reference_or_amount_customer>`
- Unclear order: `unclear_order:<order_id>`
- Stock reorder: `stock_reorder:<sku_id>`

Tests:

1. Creating same dedupe approval twice returns one pending approval.
2. Rejected/approved approval should not block a new future approval unless business rule says so.
3. JSON repository persists dedupe key.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_approvals_memory.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/data/models.py apps/ares/ares/data/repository.py apps/ares/ares/approvals/service.py apps/ares/ares/data/json_repository.py tests/ares/test_approvals_memory.py
git commit -m "feat(ares): dedupe pending approvals"
```

---

## Task 7: Normalize approval action names

Objective: Use clear approval action taxonomy matching the Ares product model.

Files:

- Modify: `apps/ares/ares/approvals/service.py`
- Modify: `apps/ares/ares/workflows/order_capture.py`
- Modify: `apps/ares/config/verticals/wholesale_india.yaml`
- Tests: relevant approval/order tests

Add/standardize required action names:

```python
"confirm_unclear_order"
"add_order_to_dispatch_queue"
"update_order_status"
"send_customer_message"
"send_supplier_message"
"mark_payment_received"
"update_invoice_status"
"modify_ledger"
"block_dispatch"
"approve_credit_extension"
"change_credit_limit"
"place_purchase_order"
"activate_recurring_workflow"
"save_sensitive_business_rule"
"save_sensitive_memory"
```

Replace current unclear order action:

```python
"update_final_order_status"
```

With:

```python
"confirm_unclear_order"
```

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/approvals/service.py apps/ares/ares/workflows/order_capture.py apps/ares/config/verticals/wholesale_india.yaml tests/ares
git commit -m "refactor(ares): normalize approval action types"
```

---

# Phase 4: Google Sheets and Drive Connectors

## Task 8: Define a real Sheets client implementation boundary

Objective: Convert the current `SheetsClient` protocol into a usable adapter with at least one concrete backend.

Files:

- Modify: `apps/ares/ares/connectors/google_sheets.py`
- Create: `apps/ares/ares/connectors/gws_sheets_client.py` or similar
- Test: `tests/ares/test_google_sheets_repository.py`

Recommended MVP backend:

Use the installed `gws` CLI if available, because this Mac already has it at `/opt/homebrew/bin/gws`.

Design:

```python
class GwsSheetsClient:
    def read_rows(self, spreadsheet_id: str, tab: str) -> list[dict]: ...
    def append_row(self, spreadsheet_id: str, tab: str, row: dict) -> None: ...
```

Important:

- Keep this adapter thin.
- Unit tests should mock subprocess or use a fake client.
- Do not require live Google credentials in unit tests.
- If GWS is unavailable, raise a clear connector error with manual fallback instructions.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_google_sheets_repository.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/connectors/google_sheets.py apps/ares/ares/connectors/gws_sheets_client.py tests/ares/test_google_sheets_repository.py
git commit -m "feat(ares): add GWS-backed Sheets client adapter"
```

---

## Task 9: Add repository selection based on client profile

Objective: If client has Google Sheet configured, use Sheets repository; otherwise use JSON repository.

Files:

- Create: `apps/ares/ares/data/factory.py`
- Modify: `apps/ares/ares/cli.py`
- Test: `tests/ares/test_repository_factory.py`

Factory behavior:

```python
def create_repository_for_profile(profile: ClientProfile) -> BusinessRepository:
    if profile.google.command_center_sheet_id and profile.connector_status.google_sheets == "configured":
        return GoogleSheetsRepository(...)
    return JsonClientRepository(...)
```

For now:

- Real CLI can default to JSON.
- Sheets repo can be used only when explicitly configured.
- Avoid hidden live network calls in tests.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_repository_factory.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/data/factory.py apps/ares/ares/cli.py tests/ares/test_repository_factory.py
git commit -m "feat(ares): select repository from client profile"
```

---

## Task 10: Implement Drive file ingestion routing

Objective: Watch Drive/export folders, classify new files, and route them to the correct parser/workflow.

Files:

- Modify: `apps/ares/ares/connectors/google_drive.py`
- Modify/Create: `apps/ares/ares/connectors/file_ingest.py`
- Modify/Create: `apps/ares/ares/workflows/ingest_files.py`
- Test: `tests/ares/test_drive_file_ingestion.py`

Classification rules:

- Filename contains `outstanding`, `receivable`, `ledger`, `party` → outstanding parser
- Filename contains `stock`, `inventory`, `godown` → stock parser
- MIME/PDF/image → create event for invoice/payment OCR queue, but do not claim parsed if OCR not implemented yet
- Unsupported file → create clear warning/event

MVP behavior:

- Support CSV immediately.
- For XLSX, either add parser or return clear error: “Convert XLSX to CSV for MVP.”
- Do not silently ignore files.

Tests:

1. New outstanding CSV produces invoices.
2. New stock CSV produces stock records.
3. Unsupported file produces a skipped/needs_manual_review result.
4. Seen file IDs are not processed twice.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_drive_file_ingestion.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/connectors/google_drive.py apps/ares/ares/connectors/file_ingest.py apps/ares/ares/workflows/ingest_files.py tests/ares/test_drive_file_ingestion.py
git commit -m "feat(ares): route Drive files into Ares workflows"
```

---

# Phase 5: Memory Agent Integration

## Task 11: Add memory proposal workflow

Objective: Make the Memory Agent a real part of Ares, not a disconnected helper.

Files:

- Modify: `apps/ares/ares/agents/memory_agent.py`
- Create: `apps/ares/ares/workflows/memory_review.py`
- Modify: `apps/ares/ares/orchestrator/router.py`
- Test: `tests/ares/test_memory_workflow.py`

Workflow:

```text
business events/history -> memory candidates -> policy evaluation -> approval if sensitive -> save durable memory
```

Rules:

- Durable patterns only.
- Do not save one-time transaction facts.
- Sensitive memories require approval.
- Memories should be subject-scoped: customer, supplier, product, staff, owner, business_rule.

Add route aliases:

```python
"memory-review": ("memory", "yaad", "remember", "pattern")
```

Tests:

1. 4 late payments produce one candidate memory.
2. 1 late payment produces no memory.
3. Sensitive memory creates approval, not direct save.
4. Non-sensitive repeated issue can save directly or create review item depending policy.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_memory_workflow.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/agents/memory_agent.py apps/ares/ares/workflows/memory_review.py apps/ares/ares/orchestrator/router.py tests/ares/test_memory_workflow.py
git commit -m "feat(ares): integrate memory review workflow"
```

---

## Task 12: Feed memories into payment/order/stock workflows

Objective: Workflows should use durable business context.

Files:

- Modify: `apps/ares/ares/workflows/payment_radar.py`
- Modify: `apps/ares/ares/workflows/order_capture.py`
- Modify: `apps/ares/ares/workflows/stock_radar.py`
- Test: `tests/ares/test_memory_context_usage.py`

Examples:

Payment radar:

- If customer memory says “usually pays 7-10 days late”, adjust tone/risk.
- If memory says “owner wants soft tone for this customer”, draft softer message.

Order capture:

- If raw message says “same maal”, use customer reorder memory only as suggestion and require approval.

Stock radar:

- If product memory says seasonal spike near festival, mark higher reorder urgency.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_memory_context_usage.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/workflows/payment_radar.py apps/ares/ares/workflows/order_capture.py apps/ares/ares/workflows/stock_radar.py tests/ares/test_memory_context_usage.py
git commit -m "feat(ares): use business memory in core workflows"
```

---

# Phase 6: Order Capture Polish

## Task 13: Improve order extraction result model

Objective: Represent uncertainty cleanly instead of forcing partial orders into final state.

Files:

- Modify: `apps/ares/ares/workflows/order_capture.py`
- Possibly modify: `apps/ares/ares/data/models.py`
- Test: `tests/ares/test_order_capture_extraction.py`

Add extraction metadata:

```python
class OrderExtractionResult(BaseModel):
    order: Order
    missing_fields: list[str]
    warnings: list[str]
    needs_approval: bool
```

Detection logic:

- no items → missing `items`
- no customer hint → missing `customer`
- vague text like `same`, `last`, `purana`, `same maal` → warning and needs approval
- multiple items should be parsed where possible

Tests:

1. Clear message captures order without approval.
2. “same maal bhej dena” requires approval.
3. Message with two items extracts two items.
4. Hindi/Hinglish common units are handled.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_order_capture_extraction.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/workflows/order_capture.py apps/ares/ares/data/models.py tests/ares/test_order_capture_extraction.py
git commit -m "feat(ares): improve order extraction uncertainty handling"
```

---

## Task 14: Add LLM-assisted extraction boundary, but keep deterministic tests

Objective: Prepare for real messy WhatsApp messages without making tests flaky.

Files:

- Create: `apps/ares/ares/extraction/order_extractor.py`
- Modify: `apps/ares/ares/workflows/order_capture.py`
- Test: `tests/ares/test_order_extractor.py`

Design:

```python
class OrderExtractor(Protocol):
    def extract(self, event: IngestedEvent) -> OrderExtractionResult: ...

class RegexOrderExtractor:
    ...

class LLMOrderExtractor:
    ...  # optional/future; injected, not default in unit tests
```

Rules:

- Deterministic regex extractor remains default for tests.
- LLM extractor must return structured JSON/Pydantic model.
- Low confidence always goes to approval.
- Never auto-dispatch based on LLM extraction.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_order_extractor.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/extraction/order_extractor.py apps/ares/ares/workflows/order_capture.py tests/ares/test_order_extractor.py
git commit -m "refactor(ares): add injectable order extraction boundary"
```

---

# Phase 7: CLI and Plugin UX Polish

## Task 15: Add onboarding command for real clients

Objective: Replace `create-sample-client` with a proper concierge setup command while keeping sample command for demos.

Files:

- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/profiles.py`
- Test: `tests/ares/test_cli_onboarding.py`

New command:

```bash
hermes ares onboard-client \
  --client raj-distributors \
  --business-name "Raj Distributors" \
  --owner-name "Raj" \
  --language english_hinglish \
  --timezone Asia/Kolkata
```

Should create:

```text
~/.ares/clients/<client_slug>/profile.yaml
~/.ares/clients/<client_slug>/data/
~/.ares/clients/<client_slug>/exports/
~/.ares/clients/<client_slug>/reports/
~/.ares/clients/<client_slug>/approvals/
~/.ares/clients/<client_slug>/memory/
```

Keep:

```bash
create-sample-client
```

As alias or demo-only command.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_cli_onboarding.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/cli.py apps/ares/ares/profiles.py tests/ares/test_cli_onboarding.py
git commit -m "feat(ares): add client onboarding CLI"
```

---

## Task 16: Improve `run-workflow` UX and error messages

Objective: Make CLI useful for pilots and Codex operation.

Files:

- Modify: `apps/ares/ares/cli.py`
- Modify: `apps/ares/ares/orchestrator/router.py`
- Test: `tests/ares/test_cli_errors.py`

Add:

```bash
hermes ares list-clients
hermes ares show-client --client demo
hermes ares list-workflows
hermes ares approval-center --client demo
```

Better errors:

- Missing profile: show exact onboarding command.
- Missing CSV: show exact file path issue.
- Unknown workflow: show valid workflows.
- Missing connector: show manual fallback.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_cli_errors.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/cli.py apps/ares/ares/orchestrator/router.py tests/ares/test_cli_errors.py
git commit -m "feat(ares): polish CLI workflow UX"
```

---

# Phase 8: Workflow Scheduling and Hermes Integration

## Task 17: Add schedule generation for Hermes cron jobs

Objective: Convert Ares client profiles into self-contained Hermes cron job prompts.

Files:

- Create: `apps/ares/ares/scheduling.py`
- Modify: `apps/ares/ares/cli.py`
- Test: `tests/ares/test_scheduling.py`

Command:

```bash
hermes ares print-cron-prompts --client demo-wholesale
```

Output should include self-contained prompts for:

- daily brief at 9 AM
- payment radar daily
- stock radar daily
- weekly war room Friday evening

Important:

Cron prompts must be self-contained because Hermes cron jobs run in fresh sessions.

Prompt should include:

- client slug
- workflow name
- expected command
- approval-first reminder
- no recursive cron scheduling

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_scheduling.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/scheduling.py apps/ares/ares/cli.py tests/ares/test_scheduling.py
git commit -m "feat(ares): generate Hermes cron prompts"
```

---

## Task 18: Add gateway/Telegram delivery formatting boundary

Objective: Prepare Ares outputs for Telegram/WhatsApp-style delivery without hard-coding platform APIs.

Files:

- Create: `apps/ares/ares/reports/mobile_formatter.py`
- Modify: `apps/ares/ares/reports/renderer.py`
- Test: `tests/ares/test_mobile_formatting.py`

Rules:

- Short sections
- No giant Markdown tables
- INR formatting
- Hinglish-friendly language
- Approval count clearly visible
- Message length safe for chat platforms

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_mobile_formatting.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add apps/ares/ares/reports/mobile_formatter.py apps/ares/ares/reports/renderer.py tests/ares/test_mobile_formatting.py
git commit -m "feat(ares): add mobile-first report formatting"
```

---

# Phase 9: Documentation and Operator Runbook Polish

## Task 19: Update operator runbook with real commands

Objective: Make the pilot setup executable by a human/operator.

Files:

- Modify: `docs/ares/OPERATOR_RUNBOOK.md`
- Modify: `docs/ares/CONCIERGE_ONBOARDING_CHECKLIST.md`
- Modify: `apps/ares/README.md`

Include:

1. How to onboard a client.
2. How to import outstanding CSV.
3. How to import stock CSV.
4. How to run daily brief.
5. How to view approvals.
6. How to recover from missing connectors.
7. How to check logs/data directory.
8. What actions require owner approval.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
python3 - <<'PY'
from pathlib import Path
for path in [
    'docs/ares/OPERATOR_RUNBOOK.md',
    'docs/ares/CONCIERGE_ONBOARDING_CHECKLIST.md',
    'apps/ares/README.md',
]:
    text = Path(path).read_text()
    assert 'hermes ares' in text or 'python -m apps.ares.ares.cli' in text
print('docs contain runnable Ares commands')
PY
```

Commit:

```bash
git add docs/ares/OPERATOR_RUNBOOK.md docs/ares/CONCIERGE_ONBOARDING_CHECKLIST.md apps/ares/README.md
git commit -m "docs(ares): update concierge pilot runbook"
```

---

## Task 20: Add MVP acceptance checklist

Objective: Define what “pilot ready” means.

Files:

- Create: `docs/ares/PILOT_ACCEPTANCE_CHECKLIST.md`

Checklist:

- [ ] `uv run python -m pytest tests/ares -q -o 'addopts='` passes.
- [ ] `hermes ares onboard-client` creates client profile and directories.
- [ ] Outstanding CSV import persists invoices.
- [ ] Stock CSV import persists stock records.
- [ ] `daily-brief` reads persisted data.
- [ ] `payment-radar` creates non-duplicate approvals.
- [ ] `approval-center` displays pending approvals.
- [ ] Memory review proposes durable memories only.
- [ ] Missing Google connector gives manual fallback.
- [ ] No customer-facing action is sent without approval.
- [ ] No money/ledger action is finalized without approval.
- [ ] Runbook has exact commands.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
test -f docs/ares/PILOT_ACCEPTANCE_CHECKLIST.md
```

Commit:

```bash
git add docs/ares/PILOT_ACCEPTANCE_CHECKLIST.md
git commit -m "docs(ares): add pilot acceptance checklist"
```

---

# Phase 10: End-to-End Pilot Test

## Task 21: Add end-to-end local pilot test

Objective: Prove the local concierge MVP works without live Google credentials.

Files:

- Create: `tests/ares/test_local_pilot_e2e.py`

Test flow:

1. Set `ARES_HOME` to temp directory.
2. Run/onboard client profile.
3. Create outstanding CSV.
4. Create stock CSV.
5. Run CLI/import workflow with CSVs.
6. Run `daily-brief` without CSVs.
7. Assert report includes payment and stock info.
8. Run `payment-radar` twice.
9. Assert approvals are not duplicated.
10. Run `approval-center`.
11. Assert pending approvals display.

Verification:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares/test_local_pilot_e2e.py -q -o 'addopts='
uv run python -m pytest tests/ares -q -o 'addopts='
```

Commit:

```bash
git add tests/ares/test_local_pilot_e2e.py
git commit -m "test(ares): add local pilot end-to-end flow"
```

---

## Task 22: Run full relevant verification

Objective: Confirm Ares changes are clean and do not break Hermes packaging.

Commands:

```bash
cd /Volumes/RAGHAV2/hermes
uv run python -m pytest tests/ares -q -o 'addopts='
uv run python -m compileall -q apps/ares plugins/ares tests/ares
uv run python - <<'PY'
from apps.ares.ares.profiles import ClientProfile
from plugins.ares import register
print(ClientProfile(client_slug='demo', business_name='Demo', owner_name='Owner').client_slug)
print(register)
PY
```

Expected:

- pytest passes
- compileall exits 0
- import smoke test exits 0

Commit if only verification-related docs changed:

```bash
git status --short
```

No code commit needed if no changes.

---

# Final Pilot-Ready Definition

Ares is pilot-ready only when all of these are true:

1. Normal project build works with `uv run`.
2. Ares test suite passes without `--no-project` hacks.
3. Client profile and state persist under `~/.ares/clients/<client_slug>/`.
4. Daily brief does not create duplicate approvals.
5. Payment radar is idempotent.
6. Approval action taxonomy is clear and complete.
7. Google Sheets/Drive connector failures degrade gracefully.
8. MemoryAgent is integrated into at least one real workflow.
9. CLI can onboard, import data, run workflows, and show approvals.
10. Operator runbook has exact working commands.
11. No customer/money/ledger action can execute without approval.

---

# Suggested Implementation Sequence for Codex

Use this sequence exactly:

1. Task 1: Packaging fix
2. Task 2: Packaging regression test
3. Task 3: JSON repository
4. Task 4: CLI persistence
5. Task 5: Split payment radar side effects
6. Task 6: Approval dedupe
7. Task 7: Approval taxonomy
8. Task 21: Local pilot E2E test early, expected to fail until later tasks are complete
9. Task 15-16: CLI UX polish
10. Task 11-12: Memory integration
11. Task 13-14: Order capture polish
12. Task 8-10: Sheets/Drive connectors
13. Task 17-18: Scheduling and mobile formatting
14. Task 19-20: Docs/checklist
15. Task 22: Full verification

This order gets the project buildable first, then makes local pilot behavior real, then adds connector polish.

---

# Non-Negotiable Guardrails

1. Do not send customer-facing messages automatically.
2. Do not mark payments received automatically.
3. Do not change ledger/invoice status without approval.
4. Do not save sensitive memory without approval.
5. Do not store temporary transaction facts as memory.
6. Do not make Hermes core changes unless plugin architecture cannot support the need.
7. Do not require live Google credentials for unit tests.
8. Do not allow duplicate approval spam.
9. Do not claim pilot readiness without running verification.
10. Keep MVP narrow: payments, orders, stock, daily brief, memory, approvals.
