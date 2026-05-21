# Current Build vs Benchmark Gap Analysis

## Executive read

The current Ares build is **pilot-ready for an approval-first concierge workflow**, but it is **not yet benchmark-equivalent** to the final Hermes Vyapar spec.

It currently behaves like:
- a local operator loop
- a workflow engine for ingestion, radar generation, and approvals
- a good foundation for a managed pilot

It does **not yet** behave like:
- a full compliance-native wholesale operating system
- a multilingual WhatsApp business copilot with production integrations
- a polished self-serve SaaS product

## What exists now and maps well

### 1. Approval-first operator control loop
Evidence:
- `apps/ares/ares/cli.py`
- `apps/ares/ares/autonomy/runner.py`
- `apps/ares/ares/face/mobile_approval.py`
- `apps/ares/ares/execution/actions.py`

Current state:
- `setup`, `validate-inputs`, `morning-run`, `mobile-approvals`, and `mobile-reply` exist.
- Morning-run composes ingestion + payment radar + daily brief + approval prompt.
- Execution remains approval-gated and auditable.

Benchmark alignment:
- Strong alignment with the owner-loop philosophy.
- Still much narrower than the benchmark's business-partner scope.

### 2. Local persistence and deterministic client scaffolding
Evidence:
- `apps/ares/ares/paths.py`
- `apps/ares/ares/profiles.py`
- `apps/ares/ares/data/json_repository.py`

Current state:
- per-client local folders under `~/.ares/clients/<client>/`
- JSON-backed records for invoices, orders, stock, approvals, memories, workflow runs, action logs

Benchmark alignment:
- Good for pilot operations and audit trail foundations.
- Not enough for hosted multi-tenant SaaS or enterprise-grade resiliency.

### 3. Basic order, stock, and collections intelligence
Evidence:
- `apps/ares/ares/workflows/order_capture.py`
- `apps/ares/ares/workflows/payment_radar.py`
- `apps/ares/ares/workflows/stock_radar.py`
- `apps/ares/ares/workflows/daily_brief.py`
- `apps/ares/ares/connectors/export_parser.py`

Current state:
- regex-based message order extraction
- outstanding invoice parsing from CSV
- stock report parsing from CSV
- low-stock and overdue payment surfacing
- brief generation for the owner

Benchmark alignment:
- Partial alignment with WhatsApp order parsing, ledger visibility, low-stock alerts, and daily briefing.
- Depth, accuracy, and integration levels are far below benchmark targets.

## Major benchmark gaps

### A. Compliance engine is mostly missing
Benchmark modules affected:
- MOD-01
- parts of MOD-09

Missing or not yet implemented in product code:
- GST invoice generation
- NIC IRN / QR e-invoice flow
- GSTR-1 draft generation
- ITC 2A/2B reconciliation
- e-way bill automation
- multi-GSTIN logic
- TDS/TCS computation
- composition-scheme guardrails
- GSTN production integration

Grounding:
- The current codebase has CSV parsing for exports, but no implemented compliance engine surface.
- Search coverage in `apps/ares/ares` shows no real GSTN/NIC integration workflow implementation.

### B. Real communication layer is missing
Benchmark modules affected:
- MOD-07

Current state:
- mobile approval formatting exists
- current message execution defaults to dry-run sender in `execution/actions.py`
- no implemented WhatsApp Business API connector in the Ares app layer
- no voice/IVR stack in `apps/ares`

Gap:
- no real invoice dispatch over WhatsApp
- no DLT workflow
- no voice-note processing pipeline
- no regional language operational layer beyond profile metadata / Hinglish-oriented text handling

### C. Inventory depth is limited
Benchmark modules affected:
- MOD-04

Current state:
- stock ledger is shallow
- reorder logic is basic threshold math

Missing:
- batch/expiry/FIFO enforcement
- GRN and three-way match
- warehouse depth
- supplier-side debit-note flow
- festive demand planning

### D. Distribution/principal intelligence is mostly absent
Benchmark modules affected:
- MOD-05

Missing:
- beat route management
- principal-specific margin and terms engine
- claims and scheme reconciliation stack
- salesman scorecards
- retailer onboarding with verification/KYC/DigiLocker

### E. Financial ops depth is mostly absent
Benchmark modules affected:
- MOD-06

Current state:
- some payment extraction and reminder drafting

Missing:
- daily cashflow statement
- supplier payable scheduling
- bank statement parsing across Indian formats
- working capital / CCC intelligence

### F. Analytics layer is underbuilt
Benchmark modules affected:
- MOD-08

Current state:
- a basic daily brief exists

Missing:
- principal-wise P&L
- SKU performance analytics
- retailer segmentation
- mandi price integration
- owner-grade financial drill-down

### G. Integration layer is mostly placeholder-level
Benchmark modules affected:
- MOD-09

Current state:
- Drive manifest sync exists
- a thin Google Sheets adapter shape exists

Missing:
- real Tally/Busy sync
- real GSTN integration
- UPI/payment gateway webhooks
- logistics APIs
- AA framework
- ONDC node support

### H. Product shell / SaaS polish is missing
Outside the benchmark modules but necessary for sellable SaaS:
- no self-serve web product shell in `apps/ares`
- no auth/signup/billing surface in `apps/ares`
- no hosted control plane, plan limits, or deployment layer in product scope

## Readiness verdict

### What Ares is right now
- pilot-capable concierge engine
- operator workflow backend
- approval-safe company-brain foundation

### What Ares is not yet
- benchmark-equal Hermes Vyapar
- polished self-serve SaaS
- production integration-complete wholesale AIOS

## Recommended next build order

1. MOD-01 compliance engine
2. MOD-03 collections and ledger depth
3. MOD-07 real WhatsApp layer
4. MOD-04 inventory depth + GRN/batch/expiry
5. MOD-05 principal/beat/claim intelligence
6. MOD-08 owner analytics
7. MOD-09 external integrations
8. web/mobile/dashboard shell
9. hosted SaaS infrastructure and billing
