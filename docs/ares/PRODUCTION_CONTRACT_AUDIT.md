# Ares Production Contract Audit

This audit is a separate architecture-and-contract review for
`/Users/raghav/.ares/ares`. It does not continue the benchmark slice chain, and
it does not claim benchmark parity.

## Scope

Reviewed against the current repo state, with benchmark context from:

- `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
- `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`
- `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`

Primary code surfaces reviewed:

- `apps/ares/ares/data/models.py`
- `apps/ares/ares/data/repository.py`
- `apps/ares/ares/data/json_repository.py`
- `apps/ares/ares/approvals/service.py`
- `apps/ares/ares/execution/actions.py`
- `apps/ares/ares/workflows/payment_reconciliation.py`
- `apps/ares/ares/workflows/payment_gateway.py`
- `apps/ares/ares/workflows/accounting_sync.py`
- `apps/ares/ares/workflows/gst_invoice.py`
- `apps/ares/ares/workflows/gstr1.py`
- `apps/ares/ares/workflows/gstn_api.py`
- `apps/ares/ares/workflows/itc_reconciliation.py`
- `apps/ares/ares/workflows/eway_bill.py`
- `apps/ares/ares/workflows/whatsapp_business.py`
- `apps/ares/ares/workflows/production_integration_readiness.py`
- `apps/ares/ares/hardening.py`
- `apps/ares/ares/paths.py`
- `apps/ares/ares/profiles.py`

## Severity-ranked findings

### P1 - Live statutory invoice lifecycle is still under-modeled

Current invoice and GST models are strong enough for local draft preparation,
but they are not sufficient for live NIC/GSTN-style lifecycle handling.

Evidence:

- `Invoice` in `apps/ares/ares/data/models.py` supports taxable value, tax
  components, place of supply, reverse charge, invoice type, and line items.
- `gstn_api.py` already names operations such as `einvoice_irn_generation` and
  `eway_bill_status`.
- No first-class invoice fields exist for IRN, acknowledgement number/date,
  signed QR payload/hash, e-way bill number/status, cancellation metadata, or
  filing/portal sync state.

Why this matters:

- Live GSTN/NIC work needs durable identifiers on the invoice record itself.
- Without them, reconciliation falls back to log/result payloads instead of a
  stable business object.
- Sandbox or live retry handling becomes fragile because the statutory identity
  is not modeled where downstream workflows can trust it.

Exact change needed:

- Extend `Invoice` with explicit statutory lifecycle fields, at minimum:
  `irn`, `irn_generated_at`, `ack_number`, `ack_date`, `signed_qr_payload`,
  `eway_bill_number`, `eway_bill_generated_at`, `eway_bill_status`,
  `cancelled_at`, `cancel_reason`, `portal_sync_status`, and
  `portal_reference`.

### P1 - External payment events still have a persistence and redaction gap

The payment boundary is safer than before, but payment receipts still persist
full event payloads into local storage.

Evidence:

- `Payment.raw_source` in `apps/ares/ares/data/models.py` stores arbitrary
  receipt payloads.
- `payment_gateway.py` writes `gateway_event: dict(webhook_event)` into the
  receipt passed to `ingest_payment_receipt(...)`.
- `payment_reconciliation.py` stores `raw_source=dict(receipt)`.
- `json_repository.py` appends `model_dump(mode="json")` audit payloads via
  `append_client_audit_event(...)`.

Why this matters:

- Today’s fixtures are redacted, but a real gateway adapter could easily
  persist headers, raw webhook bodies, payer metadata, or future secret-bearing
  fields into client JSON and audit streams.
- That becomes a production liability before any sandbox-live deepening.

Exact change needed:

- Introduce a redacted event envelope for payments and webhooks.
- Persist raw provider bodies only in an explicitly redacted form, or avoid
  storing them entirely in `Payment.raw_source`.
- Add a dedicated normalization boundary in the future
  `payment_gateway_sandbox.py` adapter before repository writes occur.

### P1 - Action audit correlation was too weak for replay and incident tracing

Action logs previously captured only `approval_id`, `action_type`, `status`,
and a result blob.

Evidence:

- `ActionExecutionLog` originally lacked correlation or idempotency fields.
- Workflow logs in `payment_gateway.py`, `gstn_api.py`, `accounting_sync.py`,
  and `whatsapp_business.py` emitted operational results without a first-class
  cross-object trace key.

Safe fix applied in this audit:

- Added `correlation_id` and `idempotency_key` to
  `ActionExecutionLog` in `apps/ares/ares/data/models.py`.
- Wired the fields into:
  - `apps/ares/ares/execution/actions.py`
  - `apps/ares/ares/workflows/payment_gateway.py`
  - `apps/ares/ares/workflows/gstn_api.py`
  - `apps/ares/ares/workflows/accounting_sync.py`
  - `apps/ares/ares/workflows/whatsapp_business.py`

Remaining gap:

- Correlation is still not uniformly propagated across all workflow log writers,
  workflow runs, payment allocations, and ledger entries.

Exact change needed:

- Standardize on one contract identity per external/business event and thread it
  through approval, action log, payment, allocation, ledger entry, and workflow
  run records.

### P1 - Replay safety is still inconsistent outside the audited integration slice

The current audit hardened several critical integration contracts, but the repo
still contains random replay keys in other workflow families.

Evidence from current search:

- `apps/ares/ares/workflows/bank_reconciliation.py`
- `apps/ares/ares/workflows/mandi_prices.py`
- `apps/ares/ares/workflows/composition_scheme.py`
- `apps/ares/ares/workflows/party_onboarding.py`
- `apps/ares/ares/workflows/ondc_seller.py`
- `apps/ares/ares/workflows/grn_matching.py`
- `apps/ares/ares/workflows/scheme_offers.py`
- `apps/ares/ares/workflows/scheme_claims.py`
- `apps/ares/ares/workflows/festive_demand.py`
- `apps/ares/ares/workflows/saas_control_plane.py`
- `apps/ares/ares/workflows/supplier_payments.py`
- `apps/ares/ares/workflows/return_damage.py`
- `apps/ares/ares/workflows/auto_reorder.py`
- `apps/ares/ares/workflows/tds_tcs.py`
- `apps/ares/ares/workflows/beat_routes.py`
- `apps/ares/ares/workflows/principal_brands.py`

Why this matters:

- A crash, retry, replayed webhook, or operator rerun can create duplicate
  approvals or divergent contract identities for the same business event.
- That is manageable in local benchmark coverage but destabilizing in sandbox
  or live operation.

Exact change needed:

- Continue the deterministic-key pattern from `contract_keys.py` across every
  approval-gated or externally replayable workflow.

### P2 - Ledger and reconciliation models are still customer-collection centric

The payment and ledger surfaces are materially better than a simple receipt
matcher, but they are not yet full accounting event models.

Evidence:

- `Payment`, `PaymentAllocation`, and `LedgerEntry` in
  `apps/ares/ares/data/models.py` support reconciliation, allocations, and
  ledger postings.
- `bank_reconciliation.py` exists as a local contract, but there is no
  first-class bank statement line model in the shared data layer.
- No dedicated settlement/bank-clearing/payout object exists to connect gateway
  settlement, bank statement evidence, and supplier or payout-side workflows.

Why this matters:

- Real operation needs more than customer receipt matching.
- Gateway settlement, bank statement proof, reversals, chargebacks, and payout
  allocation should not live only in ad hoc workflow payloads.

Exact change needed:

- Add first-class models for bank statement lines and settlement batches, then
  link them to `Payment`, `PaymentAllocation`, and `LedgerEntry`.
- Model reversal and chargeback flows explicitly instead of relying on free-form
  status strings.

### P2 - Client isolation is good for local pilots, not for hosted multi-tenant operation

Current client scoping is deterministic and practical, but it is filesystem
  isolation, not hard multi-tenant isolation.

Evidence:

- `paths.py` and `profiles.py` normalize and scaffold per-client roots.
- `json_repository.py` and `hardening.py` write per-client JSON and JSONL audit
  trails under `~/.ares/clients/<client>/...`.

Why this matters:

- This is appropriate for local bench and managed pilot use.
- It is not enough proof for hosted deployment, concurrent tenant isolation, or
  stronger access-control assumptions.

Exact change needed:

- Keep the current local model for benchmark work.
- If hosted multi-tenant operation is planned, introduce a database-backed
  tenant boundary and request-scoped authorization model instead of extending
  filesystem JSON further.

## Safe fixes applied in this audit

These changes are intentionally narrow and production-safety-oriented:

1. Added deterministic contract key helpers in
   `apps/ares/ares/workflows/contract_keys.py`.
2. Converted key integration workflows away from random contract identities:
   - `whatsapp_business.py`
   - `payment_gateway.py`
   - `accounting_sync.py`
   - `gstn_api.py`
   - `gstr1.py`
   - `itc_reconciliation.py`
   - `eway_bill.py`
3. Blocked invoice mutation from unverified external payment events in
   `payment_reconciliation.py`.
4. Added first-class `correlation_id` and `idempotency_key` to action logs and
   wired them into the highest-risk integration surfaces.

## Recommended fix order before deeper sandbox/live work

1. Finish data-safe external edge handling:
   - payment webhook redaction boundary
   - WhatsApp webhook verification adapter
2. Finish replay-safe identity rollout across the remaining random-key workflows
3. Extend invoice/statutory models for IRN, acknowledgement, e-way, and portal
   sync state
4. Add bank statement line and settlement models before real payment gateway or
   accounting sync deepening
5. Keep hosted multi-tenant concerns explicitly out of the current local JSON
   pilot architecture unless the storage boundary changes
