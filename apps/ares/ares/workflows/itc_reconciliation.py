"""Local ITC 2A/2B reconciliation contract."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import PurchaseInvoice, RiskLevel, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_ITC_LIMITATION = "Local ITC/2B reconciliation contract only; no GSTN 2A/2B API was called."
EXCLUDED_PURCHASE_STATUSES = {"cancelled", "void"}


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _supplier_by_id(repository: BusinessRepository) -> dict[str, Supplier]:
    return {supplier.id: supplier for supplier in repository.get_suppliers()}


def _portal_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry.get("supplier_gstin", "")).strip().upper(), str(entry.get("invoice_number", "")).strip().upper())


def _purchase_key(invoice: PurchaseInvoice) -> tuple[str, str]:
    return ((invoice.supplier_gstin or "").strip().upper(), invoice.invoice_number.strip().upper())


def _in_period(invoice_date: date | None, start: date, end: date) -> bool:
    return invoice_date is not None and start <= invoice_date <= end


def _entry_date(entry: dict[str, Any]) -> date | None:
    raw = entry.get("invoice_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        return date.fromisoformat(raw)
    return None


def _entry_amount(entry: dict[str, Any], field: str) -> float:
    return round(float(entry.get(field) or 0), 2)


def _purchase_payload(invoice: PurchaseInvoice, supplier: Supplier | None) -> dict[str, Any]:
    return {
        "purchase_invoice_id": invoice.id,
        "supplier_id": invoice.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "supplier_gstin": invoice.supplier_gstin,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.date.isoformat() if invoice.date else None,
        "taxable_value": float(invoice.taxable_value),
        "tax_amount": float(invoice.tax_amount),
        "status": invoice.status,
    }


def _portal_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "supplier_gstin": entry.get("supplier_gstin"),
        "invoice_number": entry.get("invoice_number"),
        "invoice_date": _entry_date(entry).isoformat() if _entry_date(entry) else None,
        "taxable_value": _entry_amount(entry, "taxable_value"),
        "tax_amount": _entry_amount(entry, "tax_amount"),
        "itc_eligible": bool(entry.get("itc_eligible", True)),
    }


def reconcile_itc_2b(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    portal_entries: list[dict[str, Any]],
    requested_by: str,
) -> dict[str, Any]:
    """Compare local purchase invoices with a structured local 2B-style extract."""
    period_start, period_end = _period_bounds(period)
    batch_id = f"itc_{uuid4().hex[:12]}"
    suppliers = _supplier_by_id(repository)
    purchase_invoices = [
        invoice
        for invoice in repository.get_purchase_invoices()
        if invoice.status.strip().lower() not in EXCLUDED_PURCHASE_STATUSES and _in_period(invoice.date, period_start, period_end)
    ]
    portal_by_key = {
        _portal_key(entry): entry
        for entry in portal_entries
        if _in_period(_entry_date(entry), period_start, period_end)
    }
    purchase_by_key = {_purchase_key(invoice): invoice for invoice in purchase_invoices}

    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    missing_in_2b: list[dict[str, Any]] = []
    extra_in_2b: list[dict[str, Any]] = []
    eligible_itc_amount = 0.0
    disputed_itc_amount = 0.0

    for key, invoice in purchase_by_key.items():
        supplier = suppliers.get(invoice.supplier_id or "")
        portal_entry = portal_by_key.get(key)
        if portal_entry is None:
            missing_in_2b.append(_purchase_payload(invoice, supplier))
            disputed_itc_amount = round(disputed_itc_amount + float(invoice.tax_amount), 2)
            continue
        portal_tax = _entry_amount(portal_entry, "tax_amount")
        book_tax = round(float(invoice.tax_amount), 2)
        if portal_tax != book_tax:
            mismatches.append(
                {
                    "purchase_invoice_id": invoice.id,
                    "supplier_gstin": invoice.supplier_gstin,
                    "invoice_number": invoice.invoice_number,
                    "book_tax_amount": book_tax,
                    "portal_tax_amount": portal_tax,
                    "code": "tax_amount_mismatch",
                }
            )
            disputed_itc_amount = round(disputed_itc_amount + book_tax, 2)
            continue
        matches.append({**_purchase_payload(invoice, supplier), "portal_tax_amount": portal_tax})
        if bool(portal_entry.get("itc_eligible", True)):
            eligible_itc_amount = round(eligible_itc_amount + book_tax, 2)

    for key, entry in portal_by_key.items():
        if key not in purchase_by_key:
            extra_in_2b.append(_portal_payload(entry))

    summary = {
        "matched": len(matches),
        "amount_mismatches": len(mismatches),
        "missing_in_2b": len(missing_in_2b),
        "extra_in_2b": len(extra_in_2b),
        "eligible_itc_amount": eligible_itc_amount,
        "disputed_itc_amount": disputed_itc_amount,
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_fetch_performed": False,
        "limitation": LOCAL_ITC_LIMITATION,
    }
    approval_data = {
        "batch_id": batch_id,
        "period": period,
        "summary": summary,
        "matches": matches,
        "mismatches": mismatches,
        "missing_in_2b": missing_in_2b,
        "extra_in_2b": extra_in_2b,
        "mode": "local_contract_mock",
    }
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_itc_reconciliation",
        proposed_action=f"Review local ITC 2B reconciliation for {period}",
        data=approval_data,
        reason="ITC reconciliation affects statutory input-credit claims; accountant review is required before action.",
        source="itc_reconciliation",
        confidence=0.88,
        risk_level=RiskLevel.high,
        dedupe_key=f"itc_2b:{client_id}:{period}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "period": period,
        "summary": summary,
        "matches": matches,
        "mismatches": mismatches,
        "missing_in_2b": missing_in_2b,
        "extra_in_2b": extra_in_2b,
        "audit": audit,
    }
