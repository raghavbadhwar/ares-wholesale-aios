"""Local new-party onboarding review."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_PARTY_ONBOARDING_LIMITATION = (
    "Local new-party onboarding review only; no GSTN, DigiLocker, or credit-bureau integration was called."
)
REQUIRED_DOCUMENTS = ["gst_certificate", "address_proof", "owner_id"]


def _document_payload(party: dict[str, Any]) -> dict[str, bool]:
    raw = party.get("documents") or {}
    return {document: bool(raw.get(document)) for document in REQUIRED_DOCUMENTS}


def _validation_errors(repository: BusinessRepository, party: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    phone = str(party.get("phone") or "").strip()
    gstin = str(party.get("gstin") or "").strip()
    if not party.get("name"):
        errors.append({"code": "name_missing"})
    if not phone:
        errors.append({"code": "phone_missing"})
    if gstin and len(gstin) != 15:
        errors.append({"code": "gstin_format_invalid"})
    for customer in repository.get_customers():
        if gstin and customer.gstin and customer.gstin.strip().upper() == gstin.upper():
            errors.append({"code": "duplicate_gstin", "existing_customer_id": customer.id})
        if phone and customer.phone and customer.phone.strip() == phone:
            errors.append({"code": "duplicate_phone", "existing_customer_id": customer.id})
    documents = _document_payload(party)
    for document, present in documents.items():
        if not present:
            errors.append({"code": "missing_document", "document": document})
    return errors


def _draft_customer(proposed_customer_id: str, party: dict[str, Any]) -> Customer:
    return Customer(
        id=proposed_customer_id,
        name=str(party["name"]),
        phone=str(party.get("phone") or ""),
        gstin=party.get("gstin"),
        location=party.get("location"),
        credit_limit=float(party.get("credit_limit", 0) or 0),
        status="pending_onboarding",
    )


def _draft_payload(customer: Customer) -> dict[str, Any]:
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "gstin": customer.gstin,
        "location": customer.location,
        "credit_limit": float(customer.credit_limit or 0),
        "status": customer.status,
    }


def prepare_new_party_onboarding(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    proposed_customer_id: str,
    party: dict[str, Any],
    requested_by: str,
) -> dict[str, Any]:
    """Prepare a local new-party onboarding draft for owner approval."""
    documents = _document_payload(party)
    errors = _validation_errors(repository, party)
    draft = _draft_customer(proposed_customer_id, party) if not errors or party.get("name") else None
    summary = {
        "validation_errors": len(errors),
        "documents_present": sum(1 for present in documents.values() if present),
        "documents_missing": sum(1 for present in documents.values() if not present),
        "credit_limit": float(party.get("credit_limit", 0) or 0),
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": not errors,
        "external_gstn_validation_called": False,
        "digilocker_called": False,
        "credit_bureau_called": False,
        "limitation": LOCAL_PARTY_ONBOARDING_LIMITATION,
    }
    if errors:
        return {
            "mode": "local_contract_mock",
            "status": "needs_review",
            "summary": summary,
            "draft_customer": _draft_payload(draft) if draft else None,
            "validation_errors": errors,
            "audit": audit,
        }

    draft_payload = _draft_payload(draft)
    batch_id = f"party_onboard_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="onboard_new_party",
        proposed_action=f"Review new party onboarding for {draft.name}",
        data={
            "batch_id": batch_id,
            "draft_customer": draft_payload,
            "documents": documents,
            "summary": summary,
            "mode": "local_contract_mock",
        },
        reason="New party onboarding affects credit, sales, GST, and collections records; owner review is required first.",
        source="party_onboarding",
        confidence=0.82,
        risk_level=RiskLevel.medium,
        dedupe_key=f"party_onboarding:{client_id}:{proposed_customer_id}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "summary": summary,
        "draft_customer": draft_payload,
        "validation_errors": [],
        "audit": audit,
    }
