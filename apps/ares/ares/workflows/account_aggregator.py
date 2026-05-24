"""Local Sahamati Account Aggregator consent placeholders."""

from __future__ import annotations

from uuid import uuid4


def initiate_aa_consent_request(*, customer_phone: str, customer_id: str) -> dict:
    return {
        "mode": "local_simulation",
        "customer_phone": customer_phone,
        "customer_id": customer_id,
        "consent_handle": f"aa_handle_{uuid4().hex[:12]}",
        "consent_status": "simulated_pending",
        "aa_network_called": False,
        "limitation": "Local AA simulation only; no Sahamati network call made.",
    }


def poll_aa_data_session(*, consent_handle: str) -> dict:
    return {
        "mode": "local_simulation",
        "consent_handle": consent_handle,
        "consent_status": "PENDING",
        "aa_network_called": False,
        "limitation": "Local AA simulation only; no FIU/FIP data session call made.",
    }
