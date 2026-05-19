# Ares Agent Authority Passport

This resource adapts the Agent Authority Passport blueprint for Ares Wholesale AIOS.
It is intentionally documentation/configuration only: no credentials, tokens, API keys, or private endpoints belong here.

## Core principle
Ares agents are identified by role, authority, data scope, and approval boundary. They may draft and recommend actions, but owner approval is mandatory for customer-facing, money, ledger, credit, supplier-order, recurring-workflow, or sensitive-memory changes.

## Agent passports

### Router Agent
- Authority: route plain-language owner intent to workflows.
- Allowed: read client profile, call workflow agents, render summaries.
- Requires approval: none directly; delegated workflow actions still enforce approval.

### Finance Agent
- Authority: analyze outstanding invoices, payment screenshots/text, credit risk.
- Allowed: draft reminders, propose payment matches, compute collection priorities.
- Requires approval: send_customer_message, mark_payment_received, update_invoice_status, modify_ledger, change_credit_limit.

### Inventory Agent
- Authority: analyze stock CSVs/Sheets and propose reorder actions.
- Allowed: flag low stock, draft reorder suggestions.
- Requires approval: place_purchase_order, block_dispatch.

### Sales/Customer Agent
- Authority: parse WhatsApp/Telegram/email orders and customer requests.
- Allowed: create pending orders, draft confirmations.
- Requires approval: confirm_unclear_order, add_order_to_dispatch_queue, update_order_status, send_customer_message.

### Memory Agent
- Authority: propose durable memories from repeated behavior.
- Allowed: save non-sensitive operational patterns with confidence/evidence.
- Requires approval: save_sensitive_memory, save_sensitive_business_rule.

### Ops/Dispatch Agent
- Authority: summarize open dispatches and staff tasks.
- Allowed: create internal task suggestions.
- Requires approval: customer-visible status updates, delivery commitments, dispatch blocks.

## Permission scopes
- read_profile
- read_business_data
- write_local_state
- draft_customer_message
- draft_supplier_message
- propose_ledger_update
- propose_credit_change
- propose_purchase_order
- propose_memory
- schedule_owner_report

## Audit requirements
Each approval request must include:
- client_id
- action type
- proposed action
- source workflow/agent
- reason
- confidence
- risk level
- dedupe key when repeatable

## Ares MVP mapping
The code-level guardrail lives in ApprovalService.DEFAULT_APPROVAL_REQUIRED_ACTIONS.
The repository stores ApprovalRequest records with status and decision metadata.
Cron prompts must be self-contained and must explicitly say not to send customer messages or modify ledgers without approval.
