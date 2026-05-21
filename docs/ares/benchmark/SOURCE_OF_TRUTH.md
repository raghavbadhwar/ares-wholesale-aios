# Ares Benchmark Source of Truth

## Product identity

- Product name: **Ares / Hermes Vyapar**
- Segment: **Indian wholesalers and distributors**
- Product posture: **business partner that runs on software, not generic SaaS**
- Languages: **Hinglish primary + 7 regional languages**
- Interface order: **WhatsApp-first, mobile-second, web-dashboard third, voice as accessibility layer**
- Operating model: **approval-first, audit-heavy, owner-safe, accountant-compatible**

## Final polish definition

Ares reaches final polish only when it behaves like a trusted senior employee with perfect memory, zero ego, and strong compliance discipline. The owner should not need to change their workflow to fit the software; the agent should adapt itself to the owner, the accountant, and the sales/distribution realities of Indian wholesale.

## Non-negotiable design principles

- GST-native
- WhatsApp-first
- Hinglish-primary
- Tally-compatible
- MSME-calibrated
- Offline-resilient
- Zero-training UX
- Udhaar-aware

## Measurable polish KPIs

- GST invoice generation: **<3s**
- ITC match accuracy: **98%+**
- Languages supported: **8+**
- Manual e-way bill effort: **0**
- Udhaar leakage: **₹0 target**
- Agent availability: **24/7**
- Order error rate: **<2%**
- Tally sync trigger: **1-tap**

## Final polish user test

### Small wholesaler test
- Works fully in Hindi/Hinglish with no English dependency
- Orders, ledger queries, and complaints work via WhatsApp
- GST invoices auto-generate and auto-forward
- Payment reminders trigger on due dates automatically
- Runs on low-end Android + poor connectivity conditions

### Large distributor test
- Handles 120+ SKUs across 8 principals without spreadsheets
- GSTR-1 and ITC workflows operate on time every month
- Beat-route performance and underperforming retailers are visible
- Claim cycles are tracked and escalated
- Principal-wise margin/P&L is owner-readable

## Canonical feature inventory

> Note: the PDF footer says "47 Features," but the explicit module tables enumerate 48 named feature rows. This source-of-truth preserves the full enumerated list and treats the PDF footer as a likely counting mismatch.

### MOD-01 — GST & Compliance Engine (Critical)
- [P0] Smart GST Invoicing
- [P0] GSTR-1 Auto-Preparation
- [P0] ITC Reconciliation (2A/2B)
- [P0] E-Way Bill Automation
- [P1] Multi-GSTIN Management
- [P1] TDS / TCS Computation
- [P2] Composition Scheme Guard

### MOD-02 — Order Intelligence Engine (Core)
- [P0] WhatsApp Order Parsing
- [P0] Credit Limit Enforcement
- [P0] Beat Route Order Collation
- [P1] Scheme & Offer Auto-Apply
- [P1] Return & Damage Management

### MOD-03 — Udhaar & Collections Engine (Critical)
- [P0] Party-wise Ledger
- [P0] Aging Analysis & Alerts
- [P0] PDC Cheque Tracker
- [P0] UPI Payment Reconciliation
- [P1] Credit Scoring per Party
- [P1] Collections Dashboard

### MOD-04 — Inventory Intelligence (Core)
- [P0] Real-time Stock Ledger
- [P0] Batch & Expiry Tracking
- [P1] Auto-Reorder Intelligence
- [P1] Goods Receipt Note (GRN)
- [P2] Festive Demand Planning

### MOD-05 — Distribution Network Intelligence (Core)
- [P0] Beat Route Management
- [P0] Principal / Brand Management
- [P0] Claim & Scheme Reconciliation
- [P1] Salesman Performance Tracking
- [P1] New Party Onboarding

### MOD-06 — Financial Operations & Payments (Core)
- [P0] Daily Cash Flow Statement
- [P0] Supplier Payment Scheduling
- [P1] Bank Statement Reconciliation
- [P2] Working Capital Intelligence

### MOD-07 — Language & Communication Layer (Critical)
- [P0] Hinglish NLU Engine
- [P0] Regional Language Support
- [P0] WhatsApp Business Integration
- [P1] Automated Communication Workflows
- [P2] Voice Query Interface

### MOD-08 — Analytics & Decision Intelligence (Advanced)
- [P0] Principal-wise P&L
- [P1] SKU Performance Intelligence
- [P1] Retailer Segmentation
- [P1] Daily Owner Briefing
- [P2] Mandi Price Integration

### MOD-09 — Integration & Interoperability Layer (Advanced)
- [P0] Tally / Busy Sync
- [P0] GSTN API Integration
- [P0] UPI & Payment Gateway
- [P1] Logistics Integration
- [P2] Account Aggregator / AA
- [P2] ONDC Seller Node

## Build sequence

### Phase 1 — Non-negotiable core (Months 1–3)
- GST invoicing + e-invoice + e-way bill
- Party ledger + PDC tracker + WhatsApp collections
- Basic inventory + batch expiry
- WhatsApp order capture + credit limit enforcement
- Hinglish NLU for top 5 use cases
- Tally sync (one-way push)

### Phase 2 — Operational intelligence (Months 4–6)
- GSTR-1 auto-preparation + ITC reconciliation
- Beat route management + salesman tracking
- Principal-wise P&L + scheme reconciliation
- Auto-reorder + GRN + three-way match
- UPI reconciliation + supplier payment scheduling
- Regional language support

### Phase 3 — Polish and differentiation (Months 7–9)
- Credit scoring + account aggregator
- Festive demand planning + mandi price integration
- Daily owner briefing + retailer segmentation
- Voice interface
- ONDC seller node + logistics API
- Working capital intelligence + CCC tracking

## Absolute done-state gate

- Semi-literate salesman uses it daily without training
- Owner trusts agent summaries without calling accountant
- CA can close books from Tally without re-entry
- Zero GST penalty across 12 months of agent-managed operation
- Every rupee of udhaar is tracked to settlement
- 7 AM owner briefing reliably tells the owner what matters today
