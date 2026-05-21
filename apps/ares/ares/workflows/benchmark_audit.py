"""Local benchmark completion audit for Ares."""

from __future__ import annotations

from typing import Any

BENCHMARK_AUDIT_LIMITATION = (
    "Local benchmark audit only; passing local tests and contract slices do not prove production benchmark parity."
)

FEATURE_ROWS = [
    "Smart GST Invoicing",
    "GSTR-1 Auto-Preparation",
    "ITC Reconciliation (2A/2B)",
    "E-Way Bill Automation",
    "Multi-GSTIN Management",
    "TDS / TCS Computation",
    "Composition Scheme Guard",
    "WhatsApp Order Parsing",
    "Credit Limit Enforcement",
    "Beat Route Order Collation",
    "Scheme & Offer Auto-Apply",
    "Return & Damage Management",
    "Party-wise Ledger",
    "Aging Analysis & Alerts",
    "PDC Cheque Tracker",
    "UPI Payment Reconciliation",
    "Credit Scoring per Party",
    "Collections Dashboard",
    "Real-time Stock Ledger",
    "Batch & Expiry Tracking",
    "Auto-Reorder Intelligence",
    "Goods Receipt Note (GRN)",
    "Festive Demand Planning",
    "Beat Route Management",
    "Principal / Brand Management",
    "Claim & Scheme Reconciliation",
    "Salesman Performance Tracking",
    "New Party Onboarding",
    "Daily Cash Flow Statement",
    "Supplier Payment Scheduling",
    "Bank Statement Reconciliation",
    "Working Capital Intelligence",
    "Hinglish NLU Engine",
    "Regional Language Support",
    "WhatsApp Business Integration",
    "Automated Communication Workflows",
    "Voice Query Interface",
    "Principal-wise P&L",
    "SKU Performance Intelligence",
    "Retailer Segmentation",
    "Daily Owner Briefing",
    "Mandi Price Integration",
    "Tally / Busy Sync",
    "GSTN API Integration",
    "UPI & Payment Gateway",
    "Logistics Integration",
    "Account Aggregator / AA",
    "ONDC Seller Node",
]

PRODUCTION_BLOCKERS = [
    "live_whatsapp_business_api",
    "live_gstn_nic_integration",
    "live_tally_busy_bidirectional_sync",
    "live_payment_gateway_webhooks",
    "live_bank_account_aggregator_data",
    "hosted_saas_auth_billing",
    "low_end_android_and_poor_connectivity_verification",
    "12_month_compliance_outcome_evidence",
]

DONE_STATE_GATES = [
    "small_wholesaler_no_training",
    "large_distributor_monthly_compliance",
    "ca_closes_books_without_reentry",
    "zero_gst_penalty_12_months",
    "every_rupee_udhaar_settled",
    "reliable_7am_owner_briefing",
]


def build_benchmark_completion_audit(*, latest_local_test_result: str) -> dict[str, Any]:
    """Return a current-state audit that separates local coverage from production proof."""
    return {
        "mode": "local_audit",
        "feature_rows_total": len(FEATURE_ROWS),
        "local_or_contract_rows_covered": len(FEATURE_ROWS),
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "feature_rows": [{"name": name, "status": "local_or_contract_covered"} for name in FEATURE_ROWS],
        "production_blockers": list(PRODUCTION_BLOCKERS),
        "done_state_gates": [{"gate": gate, "status": "not_proven"} for gate in DONE_STATE_GATES],
        "audit": {
            "local_tests_are_sufficient_for_ship_ready_claim": False,
            "external_integrations_verified": False,
            "hosted_saas_verified": False,
            "longitudinal_business_outcomes_verified": False,
            "limitation": BENCHMARK_AUDIT_LIMITATION,
        },
    }
