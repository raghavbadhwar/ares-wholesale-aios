"""Local multi-GSTIN management for compliance drafts."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from apps.ares.ares.data.models import BusinessGSTRegistration, Customer, Invoice
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_MULTI_GSTIN_LIMITATION = "Local multi-GSTIN management only; no GSTN registration validation or filing API was called."
EXCLUDED_STATUSES = {"cancelled", "void"}
STATE_CODE_BY_ALIAS = {
    "DL": "07",
    "GJ": "24",
    "KA": "29",
    "MH": "27",
    "TN": "33",
    "UP": "09",
    "WB": "19",
}


def _registration_payload(registration: BusinessGSTRegistration) -> dict[str, Any]:
    return {
        "id": registration.id,
        "gstin": registration.gstin,
        "legal_name": registration.legal_name,
        "state_code": registration.state_code,
        "state_name": registration.state_name,
    }


def _active_registrations(repository: BusinessRepository) -> dict[str, BusinessGSTRegistration]:
    return {
        registration.id: registration
        for registration in repository.get_business_gst_registrations()
        if registration.status.strip().lower() == "active"
    }


def _all_registrations(repository: BusinessRepository) -> dict[str, BusinessGSTRegistration]:
    return {registration.id: registration for registration in repository.get_business_gst_registrations()}


def _default_registration(registrations: dict[str, BusinessGSTRegistration]) -> BusinessGSTRegistration | None:
    for registration in registrations.values():
        if registration.is_default:
            return registration
    return next(iter(registrations.values()), None)


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


def _select_registration(
    *,
    repository: BusinessRepository,
    invoice: Invoice,
) -> tuple[BusinessGSTRegistration | None, list[dict[str, str]]]:
    active = _active_registrations(repository)
    all_registrations = _all_registrations(repository)
    errors: list[dict[str, str]] = []
    if invoice.business_gstin_id:
        registration = all_registrations.get(invoice.business_gstin_id)
        if registration is None:
            errors.append({"invoice_id": invoice.id, "code": "business_gstin_missing"})
            return None, errors
        if registration.status.strip().lower() != "active":
            errors.append({"invoice_id": invoice.id, "code": "business_gstin_inactive"})
            return None, errors
        return registration, errors

    default = _default_registration(active)
    if default is None:
        errors.append({"invoice_id": invoice.id, "code": "default_business_gstin_missing"})
    return default, errors


def resolve_invoice_gstin_context(*, repository: BusinessRepository, invoice: Invoice) -> dict[str, Any]:
    """Resolve the local GST registration that should issue an invoice."""
    registration, errors = _select_registration(repository=repository, invoice=invoice)
    place_of_supply = _place_of_supply(repository, invoice)
    seller_state = registration.state_code if registration else None
    tax_mode = "inter_state" if seller_state and place_of_supply and seller_state != place_of_supply else "intra_state"
    return {
        "mode": "local_contract_mock",
        "invoice_id": invoice.id,
        "selected_registration": _registration_payload(registration) if registration else None,
        "place_of_supply": place_of_supply,
        "tax_mode": tax_mode,
        "validation_errors": errors,
        "audit": {
            "external_gstn_registration_validation_called": False,
            "filing_performed": False,
            "limitation": LOCAL_MULTI_GSTIN_LIMITATION,
        },
    }


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def build_multi_gstin_return_plan(*, repository: BusinessRepository, period: str) -> dict[str, Any]:
    """Group local invoices by issuing GST registration for period-wise compliance work."""
    start, end = _period_bounds(period)
    active = _active_registrations(repository)
    buckets: dict[str, dict[str, Any]] = {}
    validation_errors: list[dict[str, str]] = []

    for invoice in repository.get_invoices():
        if invoice.status.strip().lower() in EXCLUDED_STATUSES:
            continue
        if invoice.date is None or invoice.date < start or invoice.date > end:
            continue
        registration, errors = _select_registration(repository=repository, invoice=invoice)
        if errors:
            validation_errors.extend(errors)
            continue
        if registration is None:
            continue
        bucket = buckets.setdefault(
            registration.id,
            {
                "business_gstin_id": registration.id,
                "gstin": registration.gstin,
                "state_code": registration.state_code,
                "invoice_ids": [],
                "invoice_count": 0,
                "taxable_value": 0.0,
                "tax_amount": 0.0,
            },
        )
        bucket["invoice_ids"].append(invoice.id)
        bucket["invoice_count"] += 1
        bucket["taxable_value"] = round(float(bucket["taxable_value"]) + float(invoice.taxable_value or 0), 2)
        bucket["tax_amount"] = round(float(bucket["tax_amount"]) + float(invoice.tax_amount or 0), 2)

    registrations = list(buckets.values())
    return {
        "mode": "local_contract_mock",
        "period": period,
        "summary": {
            "active_registrations": len(active),
            "invoice_count": sum(int(row["invoice_count"]) for row in registrations),
            "taxable_value": round(sum(float(row["taxable_value"]) for row in registrations), 2),
            "tax_amount": round(sum(float(row["tax_amount"]) for row in registrations), 2),
            "validation_errors": len(validation_errors),
        },
        "registrations": registrations,
        "validation_errors": validation_errors,
        "audit": {
            "external_gstn_registration_validation_called": False,
            "filing_performed": False,
            "limitation": LOCAL_MULTI_GSTIN_LIMITATION,
        },
    }
