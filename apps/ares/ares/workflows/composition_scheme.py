"""Local GST composition-scheme guardrails."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import BusinessGSTRegistration, Customer, Invoice, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_COMPOSITION_GUARD_LIMITATION = (
    "Local composition-scheme guard only; no GSTN validation or accountant certification was performed."
)
STATE_CODE_BY_ALIAS = {
    "DL": "07",
    "GJ": "24",
    "KA": "29",
    "MH": "27",
    "TN": "33",
    "UP": "09",
    "WB": "19",
}


def _active_registrations(repository: BusinessRepository) -> dict[str, BusinessGSTRegistration]:
    return {
        registration.id: registration
        for registration in repository.get_business_gst_registrations()
        if registration.status.strip().lower() == "active"
    }


def _default_registration(registrations: dict[str, BusinessGSTRegistration]) -> BusinessGSTRegistration | None:
    for registration in registrations.values():
        if registration.is_default:
            return registration
    return next(iter(registrations.values()), None)


def _selected_registration(repository: BusinessRepository, invoice: Invoice) -> BusinessGSTRegistration | None:
    registrations = _active_registrations(repository)
    if invoice.business_gstin_id:
        return registrations.get(invoice.business_gstin_id)
    return _default_registration(registrations)


def _find_customer(repository: BusinessRepository, customer_id: str | None) -> Customer | None:
    if not customer_id:
        return None
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    return None


def _state_from_gstin(gstin: str | None) -> str | None:
    if not gstin:
        return None
    normalized = gstin.strip()
    return normalized[:2] if len(normalized) >= 2 else None


def _state_from_location(location: str | None) -> str | None:
    if not location:
        return None
    normalized = location.strip().upper()
    if len(normalized) == 2 and normalized.isdigit():
        return normalized
    return STATE_CODE_BY_ALIAS.get(normalized)


def _place_of_supply(repository: BusinessRepository, invoice: Invoice) -> str | None:
    customer = _find_customer(repository, invoice.customer_id)
    return invoice.place_of_supply or _state_from_gstin(customer.gstin if customer else None) or _state_from_location(customer.location if customer else None)


def _tax_collected(invoice: Invoice) -> bool:
    component_tax = float(invoice.cgst_amount) + float(invoice.sgst_amount) + float(invoice.igst_amount) + float(invoice.cess_amount)
    return float(invoice.tax_amount or 0) > 0 or float(invoice.gst_rate_percent or 0) > 0 or component_tax > 0


def _fy_turnover(repository: BusinessRepository, registration: BusinessGSTRegistration, fiscal_year_start: date, invoice: Invoice) -> float:
    current_end = invoice.date or fiscal_year_start
    return round(
        sum(
            float(item.taxable_value or 0)
            for item in repository.get_invoices()
            if item.date is not None
            and fiscal_year_start <= item.date <= current_end
            and (item.business_gstin_id or registration.id) == registration.id
            and item.status.strip().lower() not in {"cancelled", "void"}
        ),
        2,
    )


def review_composition_scheme_guard(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice: Invoice,
    fiscal_year_start: date,
    requested_by: str,
) -> dict[str, Any]:
    """Review a local invoice against composition-scheme guardrails."""
    registration = _selected_registration(repository, invoice)
    place_of_supply = _place_of_supply(repository, invoice)
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if registration is None:
        violations.append({"invoice_id": invoice.id, "code": "business_gstin_missing"})
    elif registration.composition_scheme:
        if _tax_collected(invoice):
            violations.append({"invoice_id": invoice.id, "code": "composition_tax_collection_not_allowed"})
        if place_of_supply and place_of_supply != registration.state_code:
            violations.append(
                {
                    "invoice_id": invoice.id,
                    "code": "composition_inter_state_supply_not_allowed",
                    "place_of_supply": place_of_supply,
                    "registration_state": registration.state_code,
                }
            )
        fy_turnover = _fy_turnover(repository, registration, fiscal_year_start, invoice)
        if fy_turnover > registration.composition_turnover_limit:
            violations.append(
                {
                    "invoice_id": invoice.id,
                    "code": "composition_turnover_limit_exceeded",
                    "fy_turnover": fy_turnover,
                    "turnover_limit": float(registration.composition_turnover_limit),
                }
            )
    else:
        warnings.append({"invoice_id": invoice.id, "code": "registration_not_under_composition_scheme"})

    audit = {
        "requested_by": requested_by,
        "external_gstn_validation_called": False,
        "accountant_certification_performed": False,
        "limitation": LOCAL_COMPOSITION_GUARD_LIMITATION,
    }
    summary = {"violations": len(violations), "warnings": len(warnings)}
    result = {
        "mode": "local_contract_mock",
        "status": "blocked_for_review" if violations else "clear",
        "invoice_id": invoice.id,
        "selected_registration_id": registration.id if registration else None,
        "allowed_document_type": "bill_of_supply" if registration and registration.composition_scheme else "tax_invoice",
        "summary": summary,
        "violations": violations,
        "warnings": warnings,
        "audit": audit,
    }
    if violations:
        batch_id = f"composition_{uuid4().hex[:12]}"
        approval = approvals.create_approval_request(
            client_id=client_id,
            action_type="review_composition_scheme_guard",
            proposed_action=f"Review composition-scheme guard violations for invoice {invoice.invoice_number}",
            data={
                "batch_id": batch_id,
                "invoice_id": invoice.id,
                "summary": summary,
                "violations": violations,
                "warnings": warnings,
                "mode": "local_contract_mock",
            },
            reason="Composition-scheme violations can create GST compliance risk; accountant review is required.",
            source="composition_scheme",
            confidence=0.9,
            risk_level=RiskLevel.high,
            dedupe_key=f"composition_scheme:{client_id}:{invoice.id}:{batch_id}",
        )
        result["batch_id"] = batch_id
        result["approval_id"] = approval.id
    return result
