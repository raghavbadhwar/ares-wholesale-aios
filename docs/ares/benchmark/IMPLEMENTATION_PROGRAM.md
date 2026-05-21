# Ares Benchmark Implementation Program

> **For Hermes:** Execute this benchmark in small TDD slices. Do not claim benchmark parity from local tests alone. Every slice must end with tests + docs + explicit verification evidence.

## Goal

Move Ares from a pilot-ready concierge engine to the benchmark-aligned wholesale operating system defined in `SOURCE_OF_TRUTH.md`.

## Delivery posture

- Build in narrow, verifiable slices.
- Prioritize **P0 benchmark features** before P1/P2 polish.
- Preserve Ares's existing strengths:
  - approval-first execution
  - owner-safe summaries
  - deterministic client scaffolding
  - auditability
- Avoid fake completeness. If an integration is mocked or local-only, label it clearly.

## Program tracks

### Track 1 — Phase 1 benchmark core
1. GST invoice draft generation and validation
2. Credit limit enforcement on incoming orders
3. PDC tracker + collections memory
4. Batch/expiry-aware stock records
5. Tally export/sync contract
6. Hinglish top-5 workflow hardening

### Track 2 — Operational intelligence
1. GSTR-1 preparation surfaces
2. ITC/2B reconciliation contract
3. GRN and three-way match
4. Supplier payment scheduling
5. Principal-wise P&L
6. Regional language expansion

### Track 3 — Final polish
1. Voice and low-literacy surfaces
2. Working-capital intelligence
3. AA / ONDC / logistics APIs
4. Hosted product shell
5. SaaS control plane and billing

## Execution rule

Each benchmark slice should use this order:
1. Add failing tests
2. Run targeted RED test
3. Implement minimum code
4. Run targeted GREEN test
5. Run relevant broader suite
6. Update docs/source-of-truth tracking if behavior meaningfully changes

## Current active slice

### Slice A1 — Credit limit enforcement on incoming orders

**Why this first**
- It is a direct Phase 1 / P0 benchmark feature.
- It fits the current order-capture architecture.
- It strengthens owner safety immediately.
- It converts Ares from passive order capture toward real operating discipline.

**Definition of done**
- When a known customer's new order would push exposure above credit limit, Ares creates an approval-gated hold/extension request.
- When a known customer has hard-stop overdue exposure, Ares blocks dispatch via approval.
- Normal orders still capture cleanly without unnecessary approvals.
- Behavior is covered by tests.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_credit_enforcement.py`
- `capture_order(...)` now applies order-side credit guardrails in `apps/ares/ares/workflows/order_capture.py`
- Verified with:
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_credit_enforcement.py -q -o 'addopts='`
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

### Slice A2 — GST invoice draft generation and validation

**Objective:** Introduce a real compliance-facing invoice drafting surface that transforms an approved order into a GST-aware invoice draft with totals, tax breakdown, and validation errors when mandatory data is missing.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_gst_invoice.py`
- Added `apps/ares/ares/workflows/gst_invoice.py`
- Verified with:
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_gst_invoice.py -q -o 'addopts='`
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

### Next recommended slice

Slice A3 — PDC tracker + collections memory

**Objective:** Track post-dated cheque commitments and surface cheque-risk / promised-payment slippage inside the morning-run and payment radar flows.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_pdc_tracker.py`
- Added `apps/ares/ares/workflows/pdc_tracker.py`
- Added persistent `PostDatedCheque` support in the repository layer
- Integrated PDC reminders into `payment_radar`
- Extended memory loop with repeat-bounce pattern capture
- Verified with:
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_pdc_tracker.py -q -o 'addopts='`
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

### Next recommended slice

Slice A4 — Batch & expiry-aware stock records

**Objective:** Extend stock intelligence from simple quantity tracking into batch-level expiry visibility, so Ares can warn on near-expiry inventory and improve distributor-grade stock discipline.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_batch_expiry.py`
- Added `apps/ares/ares/workflows/stock_batches.py`
- Added persistent `InventoryBatch` support in the repository layer
- Extended `stock_radar` with `near_expiry_batches`, `expired_batches`, and `sku_expiry_summary`
- Verified with:
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_batch_expiry.py -q -o 'addopts='`
  - `uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

### Next recommended slice

Slice A5 — UPI/payment reconciliation primitives

**Objective:** Add structured bank/UPI receipt matching against open invoices so Ares can reduce manual collections reconciliation and move closer to the source-of-truth payments engine.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_payment_reconciliation.py`
- Added `apps/ares/ares/workflows/payment_reconciliation.py`
- Extended `Payment` records with candidate invoice IDs, unapplied balance, raw receipt source, and audit notes
- Added approval-gated ambiguous reconciliation via `review_payment_reconciliation`
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_payment_reconciliation.py -q -o 'addopts='`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

**Current limitation:** This is structured local receipt reconciliation only. It is not a live UPI gateway webhook, payment aggregator integration, or bank-statement import.

### Next recommended slice

Slice A6 — Tally / Busy sync contract

**Objective:** Define the deterministic export/sync contract for pushing Ares-led invoice, payment, stock, and approval-safe ledger changes toward Tally / Busy without pretending a live accounting integration exists yet.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_accounting_sync_contract.py`
- Added `apps/ares/ares/workflows/accounting_sync.py`
- Added approval-gated `export_accounting_sync` payload preparation for Tally/Busy-style parties, invoices, payments, stock items, and reconciliation metadata
- Added audit-only local import of accounting sync status receipts via `import_accounting_sync_status`
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_accounting_sync_contract.py -q -o 'addopts='`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`

**Current limitation:** This is a local contract/mock payload and audit surface only. It does not connect to Tally Prime, Busy Accounting, XML import/export runners, ODBC, desktop automation, or any live accounting API.

### Next recommended slice

Slice A7 — GSTR-1 preparation surfaces

**Objective:** Prepare local, approval-gated GSTR-1 draft structures for outward supplies without claiming a live GSTN filing integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_gstr1_preparation.py`
- Added `apps/ares/ares/workflows/gstr1.py`
- Extended invoice records with taxable value, GST rate, component tax fields, place of supply, reverse charge, invoice type, ecommerce GSTIN, and line-item/HSN support
- Added approval-gated `prepare_gstr1_return` draft preparation and `ares prepare-gstr1`
- Derives CGST/SGST or IGST from invoice `tax_amount` when explicit component tax fields are absent
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_gstr1_preparation.py -q -o 'addopts='`
    - Result: `4 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `73 passed`

**Current limitation:** This is a local filing-preparation contract only. It does not submit to GSTN, pull official portal state, generate JSON for upload, or certify that the draft is filing-ready without accountant review.

### Next recommended slice

Slice A8 — ITC / 2A / 2B reconciliation contract

**Objective:** Add a local supplier-purchase reconciliation surface for 2A/2B style input tax credit review, preserving approval-first accountant review before any statutory action.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_itc_reconciliation.py`
- Added `apps/ares/ares/workflows/itc_reconciliation.py`
- Added persistent `Supplier.gstin` and `PurchaseInvoice` support in the repository layer
- Added approval-gated `review_itc_reconciliation` contract for matching booked purchase invoices against structured local 2B-style entries
- Surfaces matched ITC, tax amount mismatches, booked invoices missing from 2B, and extra portal entries not present in books
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_itc_reconciliation.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `76 passed`

**Current limitation:** This is a local reconciliation contract only. It does not call GSTN, fetch real GSTR-2A/2B data, validate supplier filing state, or make statutory ITC claims without accountant review.

### Next recommended slice

Slice A9 — E-way bill automation contract

**Objective:** Add a local, approval-gated e-way bill preparation contract for invoice dispatches without claiming NIC/GSTN e-way bill API integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_eway_bill_contract.py`
- Added `apps/ares/ares/workflows/eway_bill.py`
- Added approval-gated `prepare_eway_bill` draft preparation for invoice dispatches above the e-way bill threshold
- Surfaces NIC-style payload fields for seller/buyer GSTIN, document details, pincode route, transport mode, vehicle number, and HSN line items
- Returns `not_required` without approval for invoices below the local threshold
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_eway_bill_contract.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `79 passed`

**Current limitation:** This is a local e-way bill preparation contract only. It does not call NIC/GSTN, generate an official EWB number, validate transporter credentials, or submit movement data.

### Next recommended slice

Slice A10 — Supplier payment scheduling

**Objective:** Add local payable scheduling for supplier invoices, due dates, early-payment-discount visibility, and approval-gated payment planning without live banking execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_supplier_payment_schedule.py`
- Added `apps/ares/ares/workflows/supplier_payments.py`
- Extended `PurchaseInvoice` with due date and early-payment-discount fields
- Added approval-gated `schedule_supplier_payments` planning for open supplier invoices
- Prioritizes overdue supplier invoices, due-next-7-day invoices, and early-payment-discount opportunities within available cash
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_supplier_payment_schedule.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `81 passed`

**Current limitation:** This is a local payment-planning contract only. It does not execute UPI, NEFT/RTGS, bank transfers, or payment gateway actions.

### Next recommended slice

Slice A11 — Beat route management

**Objective:** Add local beat-route and salesman visit planning surfaces for retailer coverage without claiming GPS, WhatsApp execution, or live field-force tracking.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_beat_route_management.py`
- Added `apps/ares/ares/workflows/beat_routes.py`
- Added persistent `BeatRoute`, `BeatRouteStop`, and `StaffMember` repository support
- Added approval-gated `plan_beat_route` local planning for salesman visits and retailer coverage
- Surfaces stop order, salesman assignment, open order IDs, outstanding exposure, overdue exposure, and coverage-risk flags
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_beat_route_management.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `84 passed`

**Current limitation:** This is a local beat-route planning contract only. It does not track GPS, send WhatsApp instructions, verify field visits, or provide live salesman performance telemetry.

### Next recommended slice

Slice A12 — Principal / brand management

**Objective:** Add local principal and brand records with margin/terms visibility, product linkage, and owner review surfaces without claiming live principal integrations.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_principal_brand_management.py`
- Added `apps/ares/ares/workflows/principal_brands.py`
- Added persistent `Principal` and `Brand` repository support
- Extended product records with `principal_id` and `brand_id`
- Added approval-gated `review_principal_brand_plan` for local principal/brand portfolio review
- Surfaces product linkage, low-stock products by principal, computed margin percent, payment terms, and missing principal/brand links
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_principal_brand_management.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `87 passed`

**Current limitation:** This is a local principal/brand management surface only. It does not sync live principal schemes, distributor portals, ERP masters, or field agreements.

### Next recommended slice

Slice A13 — Claim & scheme reconciliation

**Objective:** Add local scheme eligibility and principal claim reconciliation for sales invoices without claiming live principal portal settlement.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_claim_scheme_reconciliation.py`
- Added `apps/ares/ares/workflows/scheme_claims.py`
- Added persistent `TradeScheme` and `SchemeClaim` repository support
- Added approval-gated `review_scheme_claim_reconciliation` for local principal scheme claim review
- Reconciles eligible invoice line items against submitted scheme claims and surfaces missing claims and amount mismatches
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_claim_scheme_reconciliation.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `90 passed`

**Current limitation:** This is a local scheme claim reconciliation surface only. It does not call principal portals, submit claim files, verify settlements, or post accounting entries.

### Next recommended slice

Slice A14 — GRN and three-way match

**Objective:** Add local goods receipt and purchase-order/invoice/receipt matching for inventory discipline without claiming live warehouse, supplier, or accounting integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_grn_three_way_match.py`
- Added `apps/ares/ares/workflows/grn_matching.py`
- Added persistent `PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceiptNote`, and `GoodsReceiptNoteLine` repository support
- Extended `PurchaseInvoice` with purchase-order linkage and invoice line items
- Added approval-gated `review_grn_three_way_match` for local PO/invoice/receipt matching
- Surfaces matched lines, quantity mismatches, rate mismatches, and missing receipt lines
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_grn_three_way_match.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `93 passed`

**Current limitation:** This is a local GRN and three-way matching surface only. It does not update warehouse stock, submit supplier disputes, or post accounting entries without follow-on approved workflows.

### Next recommended slice

Slice A15 — Principal-wise P&L

**Objective:** Add local principal-wise revenue, cost, gross margin, scheme-claim, and stock-risk analytics without claiming full accounting close or live ERP integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_principal_pnl.py`
- Added `apps/ares/ares/workflows/principal_pnl.py`
- Extended the in-memory repository factory to seed inventory batches for analytics tests
- Produces principal-wise revenue, estimated COGS, gross margin, gross margin percent, approved scheme-claim contribution, net margin after claims, and low-stock SKU flags
- Flags unattributed invoice lines when SKU records are missing principal links
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_principal_pnl.py -q -o 'addopts='`
    - Result: `2 passed`

**Current limitation:** This is a local principal-wise P&L analytics surface only. It does not perform ERP close, bank reconciliation, accounting posting, or live principal settlement.

### Next recommended slice

Slice A16 — Regional language expansion

**Objective:** Add a local regional-language operations contract for the communication layer without claiming production WhatsApp Business, voice, or translation-provider integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_regional_language_support.py`
- Added `apps/ares/ares/workflows/regional_language.py`
- Updated forwarded message ingestion to attach local language-detection metadata
- Supports the benchmark's 8-language operating set: Hinglish, Tamil, Telugu, Kannada, Marathi, Gujarati, Bengali, Punjabi
- Provides local script/keyword language detection, selected-language document labels, trade vocabulary, sample owner-approved customer messages, and customer-language readiness matrix
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_regional_language_support.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `97 passed`

**Current limitation:** This is a local regional-language operations contract only. It does not call a translation provider, WhatsApp Business API, or voice stack.

### Next recommended slice

Slice A17 — WhatsApp Business execution contract

**Objective:** Add a contract-only WhatsApp Business execution surface for outbound approvals, delivery status, and message-drop auditability without claiming live Meta/WhatsApp production integration.

**Status:** Implemented as a contract-only mock and verified.

**Evidence:**
- Added `tests/ares/test_whatsapp_business_contract.py`
- Added `apps/ares/ares/workflows/whatsapp_business.py`
- Added approval-required action type `send_whatsapp_business_message`
- Extended approved action execution to dry-run WhatsApp Business outbound messages with channel/template/idempotency metadata
- Added local delivery-receipt/drop audit recording for WhatsApp Business events
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_whatsapp_business_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `99 passed`

**Current limitation:** This is a contract-only WhatsApp Business surface. It does not call Meta/WhatsApp production APIs, register templates, receive webhooks, or process voice notes.

### Next recommended slice

Slice A18 — Daily cash flow statement

**Objective:** Add a local daily cash-flow statement surface for incoming/outgoing cash visibility without claiming bank, payment-gateway, or accounting close integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_daily_cash_flow.py`
- Added `apps/ares/ares/workflows/cash_flow.py`
- Builds daily opening cash, actual same-day inflows, due/overdue receivables, scheduled PDC inflows, due/overdue supplier outflows, projected closing cash, and local risk counts
- Uses existing local `Payment`, `Invoice`, `PostDatedCheque`, and `PurchaseInvoice` repository data
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_daily_cash_flow.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `101 passed`

**Current limitation:** This is a local daily cash-flow statement only. It does not fetch bank balances, call payment gateways, post ledgers, or perform accounting close.

### Next recommended slice

Slice A19 — Retailer segmentation

**Objective:** Add local retailer segmentation for owner decisioning using sales, payments, credit, and activity signals without claiming predictive ML or live CRM enrichment.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_retailer_segmentation.py`
- Added `apps/ares/ares/workflows/retailer_segmentation.py`
- Segments local customers into credit-risk, priority-retailer, dormant/untraded, and regular-retailer groups using invoice, payment, overdue, credit-utilization, and activity recency signals
- Surfaces recommended owner actions and summary totals for revenue and overdue exposure
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_retailer_segmentation.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `103 passed`

**Current limitation:** This is a local retailer segmentation surface only. It does not call predictive ML, CRM enrichment, route telemetry, or external customer data providers.

### Next recommended slice

Slice A20 — SKU performance intelligence

**Objective:** Add local SKU performance analytics using sales, margin, stock, and batch/expiry signals without claiming demand forecasting or external market intelligence.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_sku_performance.py`
- Added `apps/ares/ares/workflows/sku_performance.py`
- Ranks SKUs by local invoice-line revenue and margin
- Adds units sold, estimated COGS, gross margin percent, current stock, reorder status, expiring-batch signals, recommended action, and unattributed invoice-line flags
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_sku_performance.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `105 passed`

**Current limitation:** This is a local SKU performance surface only. It does not call a demand-forecasting model, external market-intelligence source, or live replenishment integration.

### Next recommended slice

Slice A21 — Working capital intelligence

**Objective:** Add local working-capital analytics over receivables, payables, stock, PDCs, and cash-flow signals without claiming financing, account-aggregator, or bank integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_working_capital.py`
- Added `apps/ares/ares/workflows/working_capital.py`
- Builds a local working-capital snapshot across cash on hand, receivables, overdue receivables, payables, inventory value, scheduled PDC inflows, and net working capital
- Surfaces local risk flags for overdue receivable pressure, payable pressure, and low-stock replenishment need
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_working_capital.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `107 passed`

**Current limitation:** This is a local working-capital intelligence surface only. It does not call banks, account aggregators, lenders, financing APIs, or external credit sources.

### Next recommended slice

Slice A22 — Bank statement reconciliation

**Objective:** Add local bank-statement reconciliation for payment and supplier transaction matching without claiming live bank feed or account-aggregator integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_bank_statement_reconciliation.py`
- Added `apps/ares/ares/workflows/bank_reconciliation.py`
- Added approval-gated `review_bank_statement_reconciliation` for bank-line exceptions
- Matches local statement credits to payment receipts by reference or amount
- Matches local statement debits to supplier purchase invoices by payable amount plus narration/invoice/supplier cues
- Surfaces matched entries, ambiguous entries, unmatched entries, and review approvals without posting ledgers
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_bank_statement_reconciliation.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `109 passed`

**Current limitation:** This is a local bank-statement reconciliation contract only. It does not connect to live bank feeds, account aggregators, banking APIs, or perform ledger posting.

### Next recommended slice

Slice A23 — Multi-GSTIN management

**Objective:** Add local multi-GSTIN entity/branch selection for GST documents and compliance drafts without claiming live GSTN registration validation or filing integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_multi_gstin_management.py`
- Added `BusinessGSTRegistration` and invoice-level `business_gstin_id`
- Added persistent business GST registration support in in-memory and JSON repositories
- Added `apps/ares/ares/workflows/multi_gstin.py`
- Resolves invoice issuing GSTIN context, place of supply, and intra/inter-state tax mode
- Groups period invoices by active business GST registration for local return planning and flags inactive/missing GSTIN links
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_multi_gstin_management.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `111 passed`

**Current limitation:** This is local multi-GSTIN management only. It does not validate GST registrations against GSTN, file returns, or prove statutory correctness without accountant review.

### Next recommended slice

Slice A24 — TDS / TCS computation

**Objective:** Add local TDS/TCS computation surfaces for receivables/payables compliance review without claiming statutory filing, challan payment, or TRACES/GSTN integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_tds_tcs_computation.py`
- Added `apps/ares/ares/workflows/tds_tcs.py`
- Extended purchase invoices with optional TDS section, rate, and base amount markers
- Added approval-gated `review_tds_tcs_computation`
- Computes local TCS review rows for sales threshold crossing and local TDS rows for explicitly marked purchase invoices
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_tds_tcs_computation.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `113 passed`

**Current limitation:** This is a local TDS/TCS computation review only. It does not call income-tax portals, TRACES, challan payment rails, or statutory filing APIs.

### Next recommended slice

Slice A25 — Composition scheme guard

**Objective:** Add local composition-scheme eligibility and invoice guardrails without claiming GSTN validation or accountant-certified compliance.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_composition_scheme_guard.py`
- Added `apps/ares/ares/workflows/composition_scheme.py`
- Extended business GST registrations with composition-scheme flags and turnover limits
- Added approval-gated `review_composition_scheme_guard`
- Blocks composition-scheme review for GST tax collection, inter-state supply, and turnover-limit risk while allowing clean local bill-of-supply cases
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_composition_scheme_guard.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `115 passed`

**Current limitation:** This is a local composition-scheme guard only. It does not validate GSTN registration state, obtain accountant certification, or guarantee statutory eligibility.

### Next recommended slice

Slice A26 — Credit scoring per party

**Objective:** Add local party credit scoring from exposure, overdue, payment behavior, PDC, and order signals without claiming bureau, account-aggregator, or lender integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_party_credit_scoring.py`
- Added `apps/ares/ares/workflows/credit_scoring.py`
- Scores customer parties from local current exposure, overdue exposure, oldest overdue days, credit utilization, bounced PDC count, and reconciled payment behavior
- Produces low/medium/high risk bands, exposure summaries, and owner-safe recommended actions
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_party_credit_scoring.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `117 passed`

**Current limitation:** This is local party credit scoring only. It does not call credit bureaus, account aggregators, lenders, or external credit-score APIs.

### Next recommended slice

Slice A27 — Collections dashboard

**Objective:** Add local collections dashboard aggregation across overdue invoices, PDCs, payment reminders, credit scores, and promised-payment risk without claiming live CRM, WhatsApp automation, or bank integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_collections_dashboard.py`
- Added `apps/ares/ares/workflows/collections_dashboard.py`
- Aggregates overdue exposure, local credit-score bands, pending payment reminder approvals, bounced/due PDC action items, and customer-level collection priority
- Produces urgent/watch/routine queue rows with owner-safe recommended actions
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_collections_dashboard.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `119 passed`

**Current limitation:** This is a local collections dashboard only. It does not call live CRM systems, automate WhatsApp follow-ups, fetch bank feeds, or execute collection actions.

### Next recommended slice

Slice A28 — Scheme & offer auto-apply

**Objective:** Add local scheme/offer application suggestions for incoming orders and invoice drafts without claiming principal portal validation or automatic discount execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_scheme_offer_auto_apply.py`
- Added `apps/ares/ares/workflows/scheme_offers.py`
- Added approval-gated `apply_scheme_offer`
- Suggests the best active local principal/brand scheme for order lines using per-unit or percent benefit calculations
- Keeps application approval-first and does not mutate invoice/order pricing automatically
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_scheme_offer_auto_apply.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `121 passed`

**Current limitation:** This is a local scheme/offer suggestion surface only. It does not validate with principal portals, post discounts, or execute claim settlements automatically.

### Next recommended slice

Slice A29 — Return & damage management

**Objective:** Add local return/damage intake and approval-gated resolution planning without claiming logistics pickup, debit-note posting, or supplier portal integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_return_damage_management.py`
- Added `ReturnDamageCase` and `ReturnDamageCaseItem` persistence in in-memory and JSON repositories
- Added `apps/ares/ares/workflows/return_damage.py`
- Added approval-gated `review_return_damage_resolution`
- Creates local return/damage cases from invoice lines, estimates credit value, validates return quantity against original invoice quantity, and proposes resolution options
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_return_damage_management.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `123 passed`

**Current limitation:** This is local return/damage management only. It does not schedule logistics pickups, post debit/credit notes, update supplier portals, or settle supplier claims.

### Next recommended slice

Slice A30 — Auto-reorder intelligence

**Objective:** Add local replenishment recommendations from stock, reorder levels, supplier lead time, and sales velocity without claiming automatic purchase order placement or supplier integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_auto_reorder.py`
- Added `apps/ares/ares/workflows/auto_reorder.py`
- Builds local reorder recommendations from product stock, stock-record velocity, supplier lead time, coverage days, reorder level, and buying price
- Adds approval-gated `place_purchase_order` recommendations without placing purchase orders automatically
- Surfaces missing supplier links for reorder candidates
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_auto_reorder.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `125 passed`

**Current limitation:** This is local auto-reorder intelligence only. It does not call supplier portals, place purchase orders, or commit cash without owner approval.

### Next recommended slice

Slice A31 — Salesman performance tracking

**Objective:** Add local salesman performance scorecards from beat coverage, order capture, collections, and route activity without claiming GPS or field-force tracking integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_salesman_performance.py`
- Added `apps/ares/ares/workflows/salesman_performance.py`
- Extended the in-memory repository factory to seed regular orders for analytics tests
- Builds salesman scorecards from assigned beat-route stops, captured orders, route-customer collections, and overdue exposure
- Produces local performance score and strong/watch/needs-attention bands
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_salesman_performance.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `127 passed`

**Current limitation:** This is local salesman performance tracking only. It does not call GPS, live attendance, or field-force apps.

### Next recommended slice

Slice A32 — New party onboarding

**Objective:** Add local new-party onboarding review with duplicate, GSTIN, phone, credit-limit, and KYC/document checks without claiming DigiLocker, GSTN, or credit-bureau integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_new_party_onboarding.py`
- Added `apps/ares/ares/workflows/party_onboarding.py`
- Added approval-gated `onboard_new_party`
- Prepares pending customer drafts with duplicate GSTIN/phone checks, basic GSTIN format validation, document checklist, and credit-limit review
- Does not persist the customer until owner approval
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_new_party_onboarding.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `129 passed`

**Current limitation:** This is local new-party onboarding review only. It does not call GSTN, DigiLocker, credit bureaus, or KYC providers.

### Next recommended slice

Slice A33 — Automated communication workflows

**Objective:** Add local approval-gated communication workflow drafting for reminders, order confirmations, and collection nudges without claiming live WhatsApp automation or CRM campaign execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_automated_communication_workflows.py`
- Added `apps/ares/ares/workflows/communication_workflows.py`
- Drafts local overdue payment reminders and order confirmations as approval-gated `send_customer_message` actions
- Skips records without customer/phone data and never sends automatically
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_automated_communication_workflows.py -q -o 'addopts='`
    - Result: `3 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `132 passed`

**Current limitation:** This is a local automated communication drafting workflow only. It does not send WhatsApp messages, run CRM campaigns, or execute recurring campaigns without approval.

### Next recommended slice

Slice A34 — Daily owner briefing expansion

**Objective:** Expand the local daily owner briefing to include collections, working-capital, and owner-priority signals without claiming production 7 AM delivery, WhatsApp automation, or hosted scheduling.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_daily_owner_briefing_expansion.py`
- Extended `apps/ares/ares/workflows/daily_brief.py`
- Daily brief now includes local collections dashboard summary, working-capital snapshot, and richer top-action prioritization
- Added deterministic `today` and `opening_cash` inputs for testable owner brief generation
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_daily_owner_briefing_expansion.py -q -o 'addopts='`
    - Result: `1 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `133 passed`

**Current limitation:** This is a local daily owner briefing only. It does not use a production scheduler, hosted delivery, or WhatsApp automation.

### Next recommended slice

Slice A35 — Logistics integration contract

**Objective:** Add local logistics shipment preparation and delivery-status audit contracts without claiming live carrier API integration or dispatch execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_logistics_integration_contract.py`
- Added `LogisticsShipment` persistence in in-memory and JSON repositories
- Added `apps/ares/ares/workflows/logistics.py`
- Added approval-gated `prepare_logistics_dispatch`
- Prepares local shipment dispatch contracts and records delivery-status receipts as audit logs without carrier API calls
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_logistics_integration_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `135 passed`

**Current limitation:** This is a local logistics contract only. It does not call carrier APIs, book pickups, execute dispatch, or provide live tracking integration.

### Next recommended slice

Slice A36 — Voice query interface contract

**Objective:** Add local voice-query intent handling and transcript audit surfaces without claiming speech-to-text, IVR, or live voice integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_voice_query_interface.py`
- Added `apps/ares/ares/workflows/voice_query.py`
- Added transcript-only `handle_voice_query_transcript` routing through the existing Ares workflow router
- Runs supported owner workflows in read-only mode, including payment radar without creating customer-message approvals
- Persists local `voice_query_transcript` action logs with transcript, detected workflow, response text, and no-live-voice audit flags
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_voice_query_interface.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `137 passed`

**Current limitation:** This is a local transcript contract only. It does not call speech-to-text, IVR, telephony, voice-note processing, or live voice integrations.

### Next recommended slice

Slice A37 — Festive demand planning

**Objective:** Add local festival-calendar demand planning using historical sales, current stock, and reorder lead-time signals without claiming live forecasting, external market intelligence, or automated purchase ordering.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_festive_demand_planning.py`
- Added `apps/ares/ares/workflows/festive_demand.py`
- Added approval-gated `review_festive_stocking_plan`
- Builds six-week festive stocking recommendations from local prior-year invoice lines, current stock, sales velocity, supplier lead time, and local festival multipliers
- Keeps calendar and market signal handling local-only and does not place purchase orders
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_festive_demand_planning.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `139 passed`

**Current limitation:** This is local festive demand planning only. It does not call external festival calendars, market-intelligence feeds, forecasting models, supplier portals, or automatic purchase ordering.

### Next recommended slice

Slice A38 — Mandi price integration contract

**Objective:** Add a local mandi-price ingestion and recommendation contract for agri-commodity wholesalers without claiming live market-feed integration or automated price/order execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_mandi_price_integration_contract.py`
- Added `apps/ares/ares/workflows/mandi_prices.py`
- Added approval-gated `review_mandi_price_alert`
- Builds local mandi price movement alerts from uploaded/supplied price snapshots for relevant commodities and nearby APMCs
- Flags significant price movements at the configured threshold and prepares owner-review recommendations without live Agmarknet calls
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_mandi_price_integration_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `141 passed`

**Current limitation:** This is a local mandi price contract only. It does not call Agmarknet, external market feeds, purchase-order systems, or execute customer price changes.

### Next recommended slice

Slice A39 — GSTN API integration contract

**Objective:** Add local GSTN API request/response contract surfaces for GST return/e-invoice/e-way status exchange without claiming live GSTN, NIC, or statutory filing integration.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_gstn_api_integration_contract.py`
- Added `apps/ares/ares/workflows/gstn_api.py`
- Added approval-gated `submit_gstn_api_request`
- Builds queueable local GSTN/NIC request contracts for GSTR-1 upload, GSTR-2B pull, GSTIN validation, e-invoice IRN, and e-way status operations
- Persists `gstn_api_contract_prepared` action logs for both approval-required and validation-failed outcomes
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_gstn_api_integration_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `143 passed`

**Current limitation:** This is a local GSTN/NIC request contract only. It does not call GSTN sandbox/production APIs, use credentials, generate IRNs/e-way bills, pull real 2B data, or perform statutory filing.

### Next recommended slice

Slice A40 — UPI and payment gateway contract

**Objective:** Add local payment-link/webhook contract surfaces for Razorpay/Cashfree/PhonePe-style UPI flows without claiming live payment gateway integration, QR generation, autopay, or bank execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_payment_gateway_contract.py`
- Added `apps/ares/ares/workflows/payment_gateway.py`
- Added approval-gated `create_payment_gateway_link`
- Prepares local payment-link contracts with provider, invoice, amount, supported method, and webhook contract metadata
- Ingests local payment-gateway-shaped webhook events through the existing receipt reconciliation workflow
- Persists local action logs for payment-link and webhook contracts without claiming live gateway calls
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_payment_gateway_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `145 passed`

**Current limitation:** This is a local payment-gateway contract only. It does not call Razorpay, Cashfree, PhonePe, UPI autopay, QR generation, live webhooks, or bank/payment execution.

### Next recommended slice

Slice A41 — Account Aggregator contract

**Objective:** Add local Account Aggregator consent/financial-data contract surfaces for credit and working-capital intelligence without claiming RBI AA network integration or live bank data access.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_account_aggregator_contract.py`
- Added `apps/ares/ares/workflows/account_aggregator.py`
- Added approval-gated `request_account_aggregator_consent`
- Added approval-gated `review_account_aggregator_credit_signal`
- Prepares local AA consent contracts for customer financial-data review
- Converts local AA-shaped financial summaries into owner-review credit signals without changing credit limits
- Persists `account_aggregator_financial_data_contract` audit logs
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_account_aggregator_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `147 passed`

**Current limitation:** This is a local Account Aggregator contract only. It does not call the RBI AA network, submit consent, pull live bank data, integrate lenders, or change credit limits.

### Next recommended slice

Slice A42 — ONDC Seller Node contract

**Objective:** Add local ONDC catalogue/order contract surfaces for wholesale B2B discovery without claiming live ONDC network integration, catalogue sync, logistics, or order execution.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_ondc_seller_node_contract.py`
- Added `apps/ares/ares/workflows/ondc_seller.py`
- Added approval-gated `sync_ondc_catalogue`
- Prepares local ONDC catalogue-sync contracts from product records without committing stock
- Ingests ONDC-shaped order payloads into the same local order repository with duplicate detection by ONDC order ID
- Approval-gates dispatch queue movement and does not call ONDC, logistics APIs, or execute order commitments
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_ondc_seller_node_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `149 passed`

**Current limitation:** This is a local ONDC seller-node contract only. It does not call the ONDC network, sync catalogue externally, commit stock, call logistics APIs, or execute orders.

### Next recommended slice

Slice A43 — Product shell and operator surfaces

**Objective:** Add the first local app/operator shell across the implemented benchmark surfaces without claiming hosted SaaS infrastructure, production auth, billing, or live external integrations.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_operator_shell.py`
- Added `apps/ares/ares/face/operator_shell.py`
- Added `ares operator-shell --client <slug> [--json]`
- Builds a local command-center payload over current repository/profile data with metrics for pending approvals, pending orders, overdue invoices, low-stock SKUs, and action logs
- Groups implemented surfaces into command center, owner approvals, collections, inventory, compliance, and integration-contract sections
- Explicitly marks hosted SaaS, production auth, billing, and live external integrations as unavailable
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_operator_shell.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `151 passed`

**Current limitation:** This is a local operator shell only. It does not provide hosted SaaS infrastructure, production auth, billing, or live external integrations.

### Next recommended slice

Slice A44 — SaaS control plane and billing readiness contract

**Objective:** Add local tenant/plan/billing readiness surfaces so Ares can show what a hosted SaaS control plane must manage without claiming production auth, payment collection, subscription billing, or deployment.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_saas_control_plane_contract.py`
- Added `apps/ares/ares/workflows/saas_control_plane.py`
- Added approval-gated `review_saas_control_plane_contract`
- Prepares local tenant/plan readiness contracts from `ClientProfile` data, plan tier, seat limit, and local usage counts
- Flags seat-limit overruns without enforcing billing or collecting payment
- Persists `saas_control_plane_contract` audit logs with production auth, deployment, billing provider, subscription, and payment collection all marked false
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_saas_control_plane_contract.py -q -o 'addopts='`
    - Result: `2 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `153 passed`

**Current limitation:** This is a local SaaS control-plane readiness contract only. It does not provision hosted infrastructure, enable production auth, call billing providers, create subscriptions, or collect payments.

### Next recommended slice

Slice A45 — Benchmark completion audit and production blocker register

**Objective:** Add a current-state audit surface that maps implemented local/contract slices against source-of-truth done-state gates and identifies the remaining production blockers without claiming benchmark parity.

**Status:** Implemented locally and verified.

**Evidence:**
- Added `tests/ares/test_benchmark_completion_audit.py`
- Added `apps/ares/ares/workflows/benchmark_audit.py`
- Added `ares benchmark-audit --latest-local-test-result "<result>" --json`
- Maps the 48 enumerated source-of-truth feature rows to local/contract coverage
- Explicitly keeps `benchmark_parity` and `ship_ready` false
- Lists remaining production blockers for live WhatsApp, GSTN/NIC, Tally/Busy, payment gateways, bank/AA data, hosted SaaS auth/billing, low-end Android/connectivity verification, and 12-month compliance outcome evidence
- Can embed a sanitized local integration preflight summary via `--include-integration-preflight` in JSON and text output so audit evidence shows exact provider-sandbox blockers, benchmark feature rows, and production-blocker mapping without inspecting secrets or calling live APIs
- Maps final done-state gates to `not_proven`
- CLI exits nonzero while `ship_ready` is false so local coverage cannot be mistaken for production readiness
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_benchmark_completion_audit.py -q -o 'addopts='`
    - Result: `7 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `181 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '181 passed' --include-integration-preflight --provider razorpay`
    - Result: exited `1`, text output showed `Integration preflight: blocked`, Razorpay missing sandbox env names, benchmark feature rows, production-blocker mapping, no secret values inspected, no live API calls, and `ship_ready: False`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '181 passed' --include-integration-preflight --provider razorpay --json`
    - Result: exited `1`, with `benchmark_parity: false`, `ship_ready: false`, `integration_preflight.status: "blocked"`, Razorpay benchmark feature rows, production-blocker mapping, missing sandbox env names, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '181 passed' --include-integration-preflight --provider stripe --json`
    - Result: exited `1`, returned `unknown_integration_provider`, valid provider keys, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '162 passed' --json`
    - Result: exited `1`, with `benchmark_parity: false`, `ship_ready: false`, and local/contract coverage still not treated as production readiness

**Current limitation:** This is a local benchmark audit only. It does not prove production benchmark parity, live integration readiness, hosted SaaS readiness, or longitudinal business outcomes.

### Next recommended slice

Slice A46 — Production integration adapter hardening

**Objective:** Replace selected contract-only integration stubs with real sandbox adapters only where credentials and safe test environments are available; otherwise keep them blocked as explicit external-integration blockers.

**Status:** Local prerequisite preflight implemented and verified; provider-scoped rollout checks added. Live/sandbox adapter hardening remains blocked by missing external sandbox credentials and safe integration environments.

**Evidence:**
- Added `tests/ares/test_integration_preflight.py`
- Added `apps/ares/ares/workflows/integration_preflight.py`
- Added `ares integration-preflight --json`
- Preflight reports provider readiness from configured sandbox environment variable names only and requires explicit `--confirm-safe-sandbox <provider>` confirmation before marking any provider ready for sandbox adapter tests
- Preflight supports provider-scoped checks with repeatable `--provider <provider>` and `--list-providers` for focused sandbox rollout readiness
- Preflight supports `--readiness-packet` to generate provider-specific sandbox adapter handoff packets with setup checklist, operator commands, required external artifacts, and adapter hardening gate state
- Preflight supports `--env-template` to emit empty dotenv-style sandbox variable templates for selected providers without reading or printing values
- Preflight returns machine-readable JSON errors for unknown provider keys, unknown safe-sandbox confirmation keys, and valid-but-out-of-scope confirmation keys in `--json` mode, including the valid provider list and no-secret/no-network audit flags
- Provider reports now include `can_run_sandbox_adapter_tests`, concrete `blocked_reasons`, `next_required_actions`, allowed sandbox test scope, forbidden production/live action scope, benchmark feature rows, and production blockers addressed by the provider
- Preflight audit explicitly records that secret values are not inspected, live APIs are not called, and sandbox submissions are not performed
- Checked current process environment for integration credential variable names without printing secret values:
  - `env | cut -d= -f1 | rg '^(GSTN|NIC|RAZORPAY|CASHFREE|PHONEPE|TALLY|BUSY|WHATSAPP|META|ONDC|ACCOUNT_AGGREGATOR|AA_|AGMARKNET)'`
  - Result: no matching configured environment names
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_integration_preflight.py -q -o 'addopts='`
    - Result: `21 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `180 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --env-template --provider razorpay --json`
    - Result: exited `0`, scoped to `provider_scope: ["razorpay"]`, with empty Razorpay sandbox dotenv lines, `values_included: false`, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --env-template --provider razorpay`
    - Result: exited `0`, printed only empty dotenv assignments for Razorpay sandbox env names
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --readiness-packet --provider razorpay --json`
    - Result: exited `1`, scoped to `provider_scope: ["razorpay"]`, with `adapter_hardening_gate: "blocked_until_checklist_passes"`, setup checklist, operator commands, required external artifacts, benchmark feature rows, production-blocker mapping, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --provider razorpay --json`
    - Result: exited `1`, scoped to `provider_scope: ["razorpay"]`, with `blocked_provider_count: 1`, `can_run_sandbox_adapter_tests: false`, and no secret values inspected
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --list-providers --provider razorpay --json`
    - Result: exited `0`, scoped to `provider_scope: ["razorpay"]`, listed sandbox env names and confirmation flag, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --provider stripe --json`
    - Result: exited `1`, returned `unknown_integration_provider`, valid provider keys, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --provider razorpay --confirm-safe-sandbox stripe --json`
    - Result: exited `1`, returned `unknown_integration_provider` for the unknown confirmation key, valid provider keys, and no secret values inspected or live API calls performed
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli integration-preflight --provider razorpay --confirm-safe-sandbox cashfree --json`
    - Result: exited `1`, returned `invalid_integration_provider_scope` for the out-of-scope confirmation key, selected provider keys, and no secret values inspected or live API calls performed

**Current blocker evidence:**
- Current Ares app-layer integrations remain deliberately local/contract-only:
  - GSTN/NIC: `apps/ares/ares/workflows/gstn_api.py`
  - payment gateway: `apps/ares/ares/workflows/payment_gateway.py`
  - WhatsApp Business: `apps/ares/ares/workflows/whatsapp_business.py`
  - logistics: `apps/ares/ares/workflows/logistics.py`
  - Account Aggregator: `apps/ares/ares/workflows/account_aggregator.py`
  - ONDC: `apps/ares/ares/workflows/ondc_seller.py`

**Required unblockers:**
- Safe sandbox/test credentials and base URLs for the selected integration provider
- Non-production test tenant/account for GSTN/NIC, payment gateway, WhatsApp Business, Tally/Busy, logistics, AA, or ONDC, depending on which adapter is prioritized first
- Provider-specific contract docs and allowed test payloads
- Explicit confirmation that live submissions, messages, payments, or filings are safe to perform in the target sandbox

**Current limitation:** This is a local integration prerequisite preflight only. It does not inspect secret values, call live APIs, perform sandbox submissions, replace contract-only adapters with real provider clients, or prove production integration readiness.

### Next recommended slice

Slice A47 — Source-of-truth feature evidence traceability

**Objective:** Make the benchmark audit trace every enumerated source-of-truth feature row to the local implementation slice, workflow files, tests, current limitation, and production proof still required, without upgrading local coverage into a ship-ready claim.

**Status:** Implemented locally and verified.

**Evidence:**
- Extended `tests/ares/test_benchmark_completion_audit.py`
- Extended `apps/ares/ares/workflows/benchmark_audit.py`
- Extended `ares benchmark-audit` text output in `apps/ares/ares/cli.py`
- `feature_rows` now include module, priority, implementation slice, workflow files, test files, coverage type, current limitation, and required production evidence for all 48 source-of-truth rows
- `feature_evidence` now reports `source_of_truth_feature_rows_traced: true`, `feature_rows_with_evidence: 48`, `feature_rows_missing_evidence: []`, and `feature_rows_with_production_proof: 0`
- CLI text output now shows `Feature evidence traced: 48/48` and `Production-proof feature rows: 0/48`
- Verified with:
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_benchmark_completion_audit.py -q -o 'addopts='`
    - Result: `7 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='`
    - Result: `181 passed`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '181 passed' --include-integration-preflight --provider razorpay`
    - Result: exited `1`, with feature evidence traced `48/48`, production-proof feature rows `0/48`, blocked Razorpay integration preflight, no secret values inspected, no live API calls, and `ship_ready: False`
  - `UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m apps.ares.ares.cli benchmark-audit --latest-local-test-result '181 passed' --json`
    - Result: exited `1`, with every feature row carrying local evidence metadata and `production_proof.status: "not_proven"`

**Current limitation:** This is evidence traceability for local and contract coverage only. It does not prove live integrations, hosted SaaS behavior, low-end Android reliability, accountant-verified close, or 12-month compliance outcomes.

## Verification commands

Targeted:
```bash
UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares/test_benchmark_completion_audit.py -q -o 'addopts='
```

Broader:
```bash
UV_CACHE_DIR=/private/tmp/ares-uv-cache uv run --directory /Users/raghav/.ares/ares --extra dev python -m pytest tests/ares -q -o 'addopts='
```
