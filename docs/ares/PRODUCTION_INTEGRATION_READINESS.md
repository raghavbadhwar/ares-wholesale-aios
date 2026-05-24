# Ares Production Integration Readiness

This document is a separate production-integration spike artifact for
`/Users/raghav/.ares/ares`. It does not claim benchmark parity and it does not
change the active benchmark chain.

## Scope

The report below maps the real production-integration path for:

- WhatsApp Business sandbox / Meta Cloud API
- GSTN or GSP sandbox integration
- Tally / Busy sync bridge
- UPI / payment gateway webhook integration

Each integration is labeled with:

- `current_code_status`: current repo posture (`local` or `contract_only`)
- `production_readiness_status`: current live path gate (`sandbox_ready` or `live_blocked`)

## Current readiness snapshot

| Integration | current_code_status | production_readiness_status | Existing repo surface | Missing adapter path |
| --- | --- | --- | --- | --- |
| WhatsApp Business sandbox / Meta Cloud API | `contract_only` | `live_blocked` | `apps/ares/ares/workflows/whatsapp_business.py`, `apps/ares/ares/connectors/message_ingest.py`, `apps/ares/ares/execution/actions.py` | `apps/ares/ares/connectors/whatsapp_sandbox.py` |
| UPI / payment gateway webhook integration | `local` | `live_blocked` | `apps/ares/ares/workflows/payment_gateway.py`, `apps/ares/ares/workflows/payment_reconciliation.py`, `apps/ares/ares/workflows/payment_match.py` | `apps/ares/ares/connectors/payment_gateway_sandbox.py` |
| Tally / Busy sync bridge | `local` | `live_blocked` | `apps/ares/ares/workflows/accounting_sync.py` | `apps/ares/ares/connectors/tally_sync_adapter.py` |
| GSTN or GSP sandbox integration | `local` | `live_blocked` | `apps/ares/ares/workflows/gstn_api.py`, `apps/ares/ares/workflows/gst_invoice.py`, `apps/ares/ares/workflows/gstr1.py`, `apps/ares/ares/workflows/itc_reconciliation.py`, `apps/ares/ares/workflows/eway_bill.py` | `apps/ares/ares/connectors/gstn_sandbox.py`, `apps/ares/ares/connectors/gsp_sandbox.py` |

## Repo-grounded findings

### 1. WhatsApp Business sandbox / Meta Cloud API

- Current repo surface is approval-safe and contract-only:
  - `apps/ares/ares/workflows/whatsapp_business.py`
  - `apps/ares/ares/connectors/message_ingest.py`
  - `apps/ares/ares/execution/actions.py`
- Current repo env contract covers:
  - `META_WABA_SANDBOX_PHONE_NUMBER_ID`
  - `META_WABA_SANDBOX_ACCESS_TOKEN`
  - `META_WABA_SANDBOX_VERIFY_TOKEN`
- Additional env contract still needed for a real webhook path:
  - `META_WABA_SANDBOX_APP_SECRET`
  - `META_WABA_SANDBOX_BUSINESS_ACCOUNT_ID`
- Approval boundary:
  - keep `send_whatsapp_business_message` owner-approved before any outbound send
  - require webhook signature verification before trusting inbound status or message events
- Live blockers:
  - no Meta webhook/client adapter exists
  - no template registration evidence exists in repo
  - no sandbox-tenant proof exists in repo

### 2. UPI / payment gateway webhook integration

- Current repo surface is local and webhook-shaped:
  - `apps/ares/ares/workflows/payment_gateway.py`
  - `apps/ares/ares/workflows/payment_reconciliation.py`
  - `apps/ares/ares/workflows/payment_match.py`
- Current repo env contract already covers three providers:
  - Razorpay: `RAZORPAY_SANDBOX_KEY_ID`, `RAZORPAY_SANDBOX_KEY_SECRET`, `RAZORPAY_SANDBOX_WEBHOOK_SECRET`
  - Cashfree: `CASHFREE_SANDBOX_CLIENT_ID`, `CASHFREE_SANDBOX_CLIENT_SECRET`, `CASHFREE_SANDBOX_WEBHOOK_SECRET`
  - PhonePe: `PHONEPE_SANDBOX_MERCHANT_ID`, `PHONEPE_SANDBOX_SALT_KEY`, `PHONEPE_SANDBOX_SALT_INDEX`
- Approval boundary:
  - keep `create_payment_gateway_link` owner-approved
  - keep ambiguous matching behind reconciliation review
  - verify webhook signatures before ingestion
- Live blockers:
  - no provider webhook adapter exists
  - no chosen primary provider is encoded in repo
  - no sandbox webhook capture fixture exists

### 3. Tally / Busy sync bridge

- Current repo surface is local export/import-contract only:
  - `apps/ares/ares/workflows/accounting_sync.py`
- Current repo env contract only covers:
  - `TALLY_SANDBOX_BASE_URL`
  - `BUSY_SANDBOX_BASE_URL`
- Missing env contract still needed:
  - bridge-mode details for XML vs ODBC
  - company-selection / desktop-target contract for Tally or Busy
- Approval boundary:
  - keep `export_accounting_sync` accountant- or owner-approved
  - keep receipt import audit-only until one-way export proof is stable
- Live blockers:
  - no bridge adapter exists
  - no operator-approved sync transcript exists in repo
  - no CA-reviewed close proof exists in repo

### 4. GSTN or GSP sandbox integration

- Current repo surface is local compliance-contract only:
  - `apps/ares/ares/workflows/gstn_api.py`
  - `apps/ares/ares/workflows/gst_invoice.py`
  - `apps/ares/ares/workflows/gstr1.py`
  - `apps/ares/ares/workflows/itc_reconciliation.py`
  - `apps/ares/ares/workflows/eway_bill.py`
- Current repo env contract covers GSTN/NIC only:
  - `GSTN_SANDBOX_BASE_URL`
  - `GSTN_SANDBOX_CLIENT_ID`
  - `GSTN_SANDBOX_CLIENT_SECRET`
  - `NIC_SANDBOX_BASE_URL`
  - `NIC_SANDBOX_CLIENT_ID`
  - `NIC_SANDBOX_CLIENT_SECRET`
- Missing env/module contract still needed:
  - named GSP provider selection
  - provider-specific GSP sandbox env names
  - connector module for whichever path is chosen first
- Approval boundary:
  - keep `submit_gstn_api_request` accountant-approved
  - keep invoice, GSTR-1, ITC, and e-way flows on manual fallback for any sandbox failure
  - do not allow credentials or taxpayer data into logs or prompts unredacted
- Live blockers:
  - no GSTN/NIC connector exists
  - no GSP connector exists
  - no redacted sandbox filing transcript exists in repo

## Recommended implementation order

1. WhatsApp Business sandbox / Meta Cloud API
   - Ares is WhatsApp-first and still depends on forwarded text plus dry-run dispatch.
2. UPI / payment gateway webhook integration
   - This is the narrowest non-destructive live edge and reuses existing reconciliation logic.
3. Tally / Busy sync bridge
   - Accounting sync should follow stabilized message and payment events, starting one-way.
4. GSTN or GSP sandbox integration
   - This has the highest compliance blast radius and should follow accounting-truth hardening plus provider selection.

## Recommended next implementation step

Implement the WhatsApp sandbox edge first:

- add `apps/ares/ares/connectors/whatsapp_sandbox.py`
- support Meta webhook verification, template-send payload shaping, and delivery-status normalization
- keep outbound sends behind existing owner approvals
- leave benchmark docs untouched until real sandbox evidence exists
