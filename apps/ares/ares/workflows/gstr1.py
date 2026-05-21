"""Local GSTR-1 return preparation surface."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, InvoiceLineItem, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_GSTR1_LIMITATION = "Local GSTR-1 preparation payload only; no GSTN filing or API call was performed."
B2CL_THRESHOLD = 250000.0
EXCLUDED_STATUSES = {"cancelled", "void"}
STATE_CODE_BY_ALIAS = {
    "AP": "37",
    "AR": "12",
    "AS": "18",
    "BR": "10",
    "CG": "22",
    "DL": "07",
    "GA": "30",
    "GJ": "24",
    "HR": "06",
    "HP": "02",
    "JH": "20",
    "KA": "29",
    "KL": "32",
    "MP": "23",
    "MH": "27",
    "OD": "21",
    "PB": "03",
    "RJ": "08",
    "TN": "33",
    "TS": "36",
    "UK": "05",
    "UP": "09",
    "WB": "19",
}


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


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


def _place_of_supply(customer: Customer | None, invoice: Invoice) -> str | None:
    return invoice.place_of_supply or _state_from_gstin(customer.gstin if customer else None) or _state_from_location(customer.location if customer else None)


def _invoice_validation_errors(invoice: Invoice, customer: Customer | None, place_of_supply: str | None) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if invoice.date is None:
        errors.append({"invoice_id": invoice.id, "code": "invoice_date_missing"})
    if invoice.customer_id and customer is None:
        errors.append({"invoice_id": invoice.id, "code": "customer_missing"})
    if place_of_supply is None:
        errors.append({"invoice_id": invoice.id, "code": "place_of_supply_missing"})
    if invoice.taxable_value is None:
        errors.append({"invoice_id": invoice.id, "code": "taxable_value_missing"})
    if invoice.gst_rate_percent is None:
        errors.append({"invoice_id": invoice.id, "code": "gst_rate_missing"})
    return errors


def _component_tax(invoice: Invoice, place_of_supply: str, seller_state: str | None) -> dict[str, float]:
    components = {
        "integrated_tax": float(invoice.igst_amount),
        "central_tax": float(invoice.cgst_amount),
        "state_tax": float(invoice.sgst_amount),
        "cess_amount": float(invoice.cess_amount),
    }
    if sum(components.values()) > 0 or invoice.tax_amount is None:
        return components

    tax_amount = round(float(invoice.tax_amount), 2)
    if seller_state and place_of_supply != seller_state:
        components["integrated_tax"] = tax_amount
        return components

    components["central_tax"] = round(tax_amount / 2, 2)
    components["state_tax"] = round(tax_amount - components["central_tax"], 2)
    return components


def _b2b_row(invoice: Invoice, customer: Customer, place_of_supply: str, seller_state: str | None) -> dict[str, Any]:
    taxes = _component_tax(invoice, place_of_supply, seller_state)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.date.isoformat() if invoice.date else None,
        "recipient_id": customer.id,
        "recipient_name": customer.name,
        "recipient_gstin": customer.gstin,
        "place_of_supply": place_of_supply,
        "rate_percent": float(invoice.gst_rate_percent or 0),
        "taxable_value": float(invoice.taxable_value or 0),
        "invoice_value": float(invoice.amount),
        **taxes,
    }


def _b2cl_row(invoice: Invoice, place_of_supply: str, seller_state: str | None) -> dict[str, Any]:
    taxes = _component_tax(invoice, place_of_supply, seller_state)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.date.isoformat() if invoice.date else None,
        "place_of_supply": place_of_supply,
        "rate_percent": float(invoice.gst_rate_percent or 0),
        "taxable_value": float(invoice.taxable_value or 0),
        "invoice_value": float(invoice.amount),
        **taxes,
    }


def _empty_b2cs_bucket(place_of_supply: str, rate_percent: float) -> dict[str, float | str]:
    return {
        "place_of_supply": place_of_supply,
        "rate_percent": rate_percent,
        "taxable_value": 0.0,
        "integrated_tax": 0.0,
        "central_tax": 0.0,
        "state_tax": 0.0,
        "cess_amount": 0.0,
    }


def _invoice_level_line_item(invoice: Invoice, taxes: dict[str, float]) -> InvoiceLineItem:
    return InvoiceLineItem(
        description="Invoice-level summary",
        hsn_code="unclassified",
        quantity=0,
        unit="unit",
        taxable_value=invoice.taxable_value or 0,
        gst_rate_percent=invoice.gst_rate_percent,
        igst_amount=taxes["integrated_tax"],
        cgst_amount=taxes["central_tax"],
        sgst_amount=taxes["state_tax"],
        cess_amount=taxes["cess_amount"],
    )


def _add_hsn_rows(hsn_buckets: dict[tuple[str, float], dict[str, Any]], invoice: Invoice, taxes: dict[str, float]) -> None:
    line_items = invoice.line_items or [_invoice_level_line_item(invoice, taxes)]
    for item in line_items:
        hsn_code = item.hsn_code or "unclassified"
        rate_percent = float(item.gst_rate_percent if item.gst_rate_percent is not None else invoice.gst_rate_percent or 0)
        key = (hsn_code, rate_percent)
        bucket = hsn_buckets.setdefault(
            key,
            {
                "hsn_code": hsn_code,
                "description": item.description,
                "quantity": 0.0,
                "unit": item.unit or "unit",
                "rate_percent": rate_percent,
                "taxable_value": 0.0,
                "integrated_tax": 0.0,
                "central_tax": 0.0,
                "state_tax": 0.0,
                "cess_amount": 0.0,
            },
        )
        bucket["quantity"] = round(bucket["quantity"] + float(item.quantity or 0), 2)
        bucket["taxable_value"] = round(bucket["taxable_value"] + float(item.taxable_value), 2)
        bucket["integrated_tax"] = round(bucket["integrated_tax"] + float(item.igst_amount), 2)
        bucket["central_tax"] = round(bucket["central_tax"] + float(item.cgst_amount), 2)
        bucket["state_tax"] = round(bucket["state_tax"] + float(item.sgst_amount), 2)
        bucket["cess_amount"] = round(bucket["cess_amount"] + float(item.cess_amount), 2)


def prepare_gstr1_return(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    seller_gstin: str,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local GSTR-1 payload for outward supplies."""
    period_start, period_end = _period_bounds(period)
    seller_state = _state_from_gstin(seller_gstin)
    batch_id = f"gstr1_{uuid4().hex[:12]}"
    b2b: list[dict[str, Any]] = []
    b2cl: list[dict[str, Any]] = []
    b2cs_buckets: dict[tuple[str, float], dict[str, float | str]] = {}
    hsn_buckets: dict[tuple[str, float], dict[str, Any]] = {}
    validation_errors: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []

    for invoice in repository.get_invoices():
        status = invoice.status.strip().lower()
        if status in EXCLUDED_STATUSES:
            excluded.append({"invoice_id": invoice.id, "code": f"status_{status}"})
            continue
        if invoice.date and (invoice.date < period_start or invoice.date > period_end):
            excluded.append({"invoice_id": invoice.id, "code": "outside_period"})
            continue

        customer = _find_customer(repository, invoice.customer_id)
        place_of_supply = _place_of_supply(customer, invoice)
        errors = _invoice_validation_errors(invoice, customer, place_of_supply)
        if errors:
            validation_errors.extend(errors)
            continue

        taxes = _component_tax(invoice, place_of_supply or "", seller_state)
        if customer and customer.gstin:
            b2b.append(_b2b_row(invoice, customer, place_of_supply or "", seller_state))
        elif seller_state and place_of_supply != seller_state and float(invoice.amount) >= B2CL_THRESHOLD:
            b2cl.append(_b2cl_row(invoice, place_of_supply or "", seller_state))
        else:
            key = (place_of_supply or "", float(invoice.gst_rate_percent or 0))
            bucket = b2cs_buckets.setdefault(key, _empty_b2cs_bucket(*key))
            bucket["taxable_value"] = round(float(bucket["taxable_value"]) + float(invoice.taxable_value or 0), 2)
            bucket["integrated_tax"] = round(float(bucket["integrated_tax"]) + taxes["integrated_tax"], 2)
            bucket["central_tax"] = round(float(bucket["central_tax"]) + taxes["central_tax"], 2)
            bucket["state_tax"] = round(float(bucket["state_tax"]) + taxes["state_tax"], 2)
            bucket["cess_amount"] = round(float(bucket["cess_amount"]) + taxes["cess_amount"], 2)

        _add_hsn_rows(hsn_buckets, invoice, taxes)

    hsn_rows = list(hsn_buckets.values())
    b2cs = list(b2cs_buckets.values())
    taxable_value = round(
        sum(float(row["taxable_value"]) for row in b2b)
        + sum(float(row["taxable_value"]) for row in b2cl)
        + sum(float(row["taxable_value"]) for row in b2cs),
        2,
    )
    tax_amount = round(
        sum(float(row["integrated_tax"]) + float(row["central_tax"]) + float(row["state_tax"]) + float(row["cess_amount"]) for row in b2b)
        + sum(float(row["integrated_tax"]) + float(row["central_tax"]) + float(row["state_tax"]) + float(row["cess_amount"]) for row in b2cl)
        + sum(float(row["integrated_tax"]) + float(row["central_tax"]) + float(row["state_tax"]) + float(row["cess_amount"]) for row in b2cs),
        2,
    )
    summary = {
        "b2b_invoices": len(b2b),
        "b2cl_invoices": len(b2cl),
        "b2cs_groups": len(b2cs),
        "hsn_rows": len(hsn_rows),
        "taxable_value": taxable_value,
        "tax_amount": tax_amount,
        "validation_errors": len(validation_errors),
    }
    tables = {
        "b2b": b2b,
        "b2cl": b2cl,
        "b2cs": b2cs,
        "hsn": hsn_rows,
        "excluded": excluded,
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_submit_performed": False,
        "limitation": LOCAL_GSTR1_LIMITATION,
    }
    approval_data = {
        "batch_id": batch_id,
        "period": period,
        "seller_gstin": seller_gstin,
        "summary": summary,
        "tables": tables,
        "validation_errors": validation_errors,
        "audit": audit,
        "mode": "local_contract_mock",
    }
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="prepare_gstr1_return",
        proposed_action=f"Review local GSTR-1 return draft for {period}",
        data=approval_data,
        reason="GSTR-1 return data affects statutory compliance; owner/accountant review is required before use.",
        source="gstr1",
        confidence=0.9,
        risk_level=RiskLevel.high,
        dedupe_key=f"gstr1_return:{client_id}:{period}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "period": period,
        "seller_gstin": seller_gstin,
        "summary": summary,
        "tables": tables,
        "validation_errors": validation_errors,
        "audit": audit,
    }
