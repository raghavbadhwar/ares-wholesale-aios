# Codex Handoff — Ares Benchmark Build

## Mission
Take Ares from its current **pilot-ready concierge engine** state to the benchmark-aligned **source-of-truth wholesale operating system** described in:

- `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
- `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`

Do **not** claim final benchmark parity yet. Ares has improved materially, but it is still missing major P0/P1 capabilities.

---

## Current repo state

- Repo root: `/Users/raghav/.ares/ares`
- Branch: `feat/pilot-readiness`
- Working tree: **dirty** with benchmark-alignment work in progress
- Current benchmark status:
  - A1 complete: credit enforcement
  - A2 complete: GST invoice draft generation
  - A3 complete: PDC tracker + collections memory
  - A4 complete: batch + expiry inventory
  - A5 next: UPI/payment reconciliation primitives

---

## Fresh verification snapshot
Run on this machine before handoff creation:

```bash
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='
```

Result:
- `63 passed in 0.94s`

Interpretation:
- Current in-progress benchmark work is locally green at the full `tests/ares` level.
- This does **not** mean the product is benchmark-complete or ship-ready against the full source of truth.

---

## Files already created for the benchmark program
Under `docs/ares/benchmark/`:

- `AGENT.md`
- `PLAN.md`
- `SOURCE_OF_TRUTH.md`
- `FEATURE_MATRIX.md`
- `CURRENT_BUILD_GAP_ANALYSIS.md`
- `REPORT.md`
- `ARES_BENCHMARK_REPORT.pdf`
- `IMPLEMENTATION_PROGRAM.md`
- `CODEX_HANDOFF.md` ← this file
- plus extracted benchmark artifacts

These documents are the canonical guidance for continuing the build.

---

## Code changes already in progress

### Modified files
- `apps/ares/ares/agents/memory_agent.py`
- `apps/ares/ares/data/json_repository.py`
- `apps/ares/ares/data/models.py`
- `apps/ares/ares/data/repository.py`
- `apps/ares/ares/memory/loop.py`
- `apps/ares/ares/memory/policies.py`
- `apps/ares/ares/workflows/order_capture.py`
- `apps/ares/ares/workflows/payment_radar.py`
- `apps/ares/ares/workflows/stock_radar.py`

### New workflow files
- `apps/ares/ares/workflows/gst_invoice.py`
- `apps/ares/ares/workflows/pdc_tracker.py`
- `apps/ares/ares/workflows/stock_batches.py`

### New tests
- `tests/ares/test_credit_enforcement.py`
- `tests/ares/test_gst_invoice.py`
- `tests/ares/test_pdc_tracker.py`
- `tests/ares/test_batch_expiry.py`

---

## What has been implemented so far

### Slice A1 — Credit limit enforcement
Implemented in `apps/ares/ares/workflows/order_capture.py`

Behavior added:
- hard-stop overdue customers trigger dispatch-block approvals
- over-limit projected exposure triggers credit-extension approvals
- normal orders still flow through cleanly

Tests:
- `tests/ares/test_credit_enforcement.py`

### Slice A2 — GST invoice draft generation
Implemented in `apps/ares/ares/workflows/gst_invoice.py`

Behavior added:
- GST-aware draft invoice generation from order data
- GSTIN validation
- intra-state CGST/SGST split
- inter-state IGST
- taxable value, tax amount, grand total

Tests:
- `tests/ares/test_gst_invoice.py`

### Slice A3 — PDC tracker + collections memory
Implemented in:
- `apps/ares/ares/workflows/pdc_tracker.py`
- `apps/ares/ares/workflows/payment_radar.py`
- `apps/ares/ares/agents/memory_agent.py`
- `apps/ares/ares/memory/loop.py`
- repository/model layers

Behavior added:
- post-dated cheque registration
- deposit reminder approvals
- bounced-cheque follow-up approvals
- durable memory for repeated cheque bounce patterns

Tests:
- `tests/ares/test_pdc_tracker.py`

### Slice A4 — Batch & expiry inventory
Implemented in:
- `apps/ares/ares/workflows/stock_batches.py`
- `apps/ares/ares/workflows/stock_radar.py`
- repository/model layers

Behavior added:
- `InventoryBatch` persistence
- batch-aware stock registration
- near-expiry surfacing
- expired-batch surfacing
- SKU-level expiry summary

Tests:
- `tests/ares/test_batch_expiry.py`

---

## The next exact slice to build

# Slice A5 — UPI/payment reconciliation primitives

### Objective
Add structured bank/UPI receipt matching against open invoices so Ares can reduce manual collections reconciliation and move closer to the source-of-truth payments engine.

### Why this next
Because `SOURCE_OF_TRUTH.md` includes:
- `UPI Payment Reconciliation` as **MOD-03 / P0**
- `UPI & Payment Gateway` as **MOD-09 / P0**

This is one of the highest-leverage missing payment capabilities after PDC tracking.

### Expected minimum scope for A5
Codex should implement the smallest correct benchmark-aligned primitive, not an inflated fake integration.

Suggested minimum:
1. Define a receipt/UPI settlement model if needed
2. Add a reconciliation workflow that:
   - ingests a structured receipt/payment event
   - finds candidate open invoices by party + amount
   - supports exact-match happy path first
   - records reconciliation status/confidence
3. Update payment/customer state safely
4. Create approval/escalation path for ambiguous matches
5. Add tests first, then implement

### Good first tests for A5
Write RED tests for cases like:
- exact payment amount matches one overdue invoice
- one payment matches multiple candidate invoices and requires approval
- payment exceeds invoice and leaves unapplied balance
- unknown customer receipt stays unreconciled but visible

---

## Build discipline for Codex
Use strict TDD for every slice:

1. Write failing tests first
2. Run targeted RED test
3. Implement minimum code
4. Run targeted GREEN test
5. Run broader suite
6. Update `IMPLEMENTATION_PROGRAM.md`
7. Only then move to next slice

Do **not** skip RED/GREEN verification.

---

## High-priority remaining benchmark gaps after A5
Even after A5, Ares will still be missing large source-of-truth areas such as:

- GSTR-1 auto-preparation
- ITC / 2A / 2B reconciliation
- e-way bill automation
- Tally / Busy deeper sync contract
- beat route management
- principal / brand management
- claim & scheme reconciliation
- supplier payment scheduling
- WhatsApp Business execution layer
- regional language expansion
- principal-wise P&L
- hosted control plane / auth / billing / SaaS shell

So do not stop at A5.

---

## Suggested command sequence for Codex
From repo root:

```bash
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_batch_expiry.py -q -o 'addopts='
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='
```

Then begin A5 with new failing tests, likely something like:

```bash
uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_upi_reconciliation.py -q -o 'addopts='
```

---

## Non-negotiable constraints
- Preserve approval-first execution.
- Preserve owner-safe summaries.
- Preserve deterministic local/client scaffolding.
- Preserve auditability.
- If an external integration is mocked/local-only, label it clearly.
- Do not market or describe Ares as fully ship-ready against the benchmark yet.
- Benchmark source of truth outranks current implementation assumptions.

---

## Honest current verdict
Ares is now a stronger benchmark-aligned pilot engine, but it is **not yet** at the full source-of-truth level.

If Codex picks this up, the correct next move is:

# Build Slice A5 with TDD, verify it, update the benchmark program, then continue slice-by-slice until the P0 benchmark core is genuinely covered.
