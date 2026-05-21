# Ares Benchmark Alignment Plan

## Goal

Bring the current Ares pilot build into alignment with the **Hermes Vyapar final polish benchmark** captured in the uploaded PDF.

## Current reality

The current build is strongest in:
- local client scaffolding
- CSV inbox/export ingestion
- payment radar
- stock radar
- daily brief / morning-run
- approval-first mobile loop
- JSON-backed local persistence

The current build is not yet benchmark-complete in:
- GST/e-invoice/e-way bill/GSTR/ITC compliance
- Tally/Busy/GSTN/payment gateway/logistics integrations
- multi-language operational depth
- analytics, principal management, beat ops, claims, GRN, cashflow intelligence
- real WhatsApp Business and voice interfaces
- web/mobile product shell and hosted SaaS infrastructure

## Phased execution plan

### Phase A — Source-of-truth alignment
- Use `SOURCE_OF_TRUTH.md` as canonical product contract
- Keep `EXTRACTED_SPEC.md` as raw benchmark archive
- Maintain feature parity tracking against all **48 features**

### Phase B — Benchmark parity by module
1. MOD-01 compliance engine
2. MOD-03 ledger/collections depth
3. MOD-04 inventory depth
4. MOD-05 distribution/principal intelligence
5. MOD-07 language/WhatsApp layer
6. MOD-08 analytics and owner intelligence
7. MOD-09 external integrations

### Phase C — Product shell
- owner dashboard
- operator console
- auth + tenant isolation
- onboarding surfaces
- hosted deployment and secrets
- monitoring and backups

### Phase D — Pilot-to-product hardening
- live integration sandboxes
- synthetic + real data validation
- performance and failure-mode testing
- compliance review
- commercial packaging and onboarding

## Delivery rule

Do not claim benchmark completion from passing unit tests alone. Completion requires:
- workflow verification
- integration verification
- owner-experience verification
- auditability verification
- low-end device / low-connectivity resilience verification
