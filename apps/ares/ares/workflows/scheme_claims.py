"""Local scheme and principal claim reconciliation surface."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice, ProductSKU, RiskLevel, SchemeClaim, TradeScheme
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SCHEME_CLAIM_LIMITATION = "Local scheme claim reconciliation only; no principal portal or settlement API was called."


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _active_schemes(repository: BusinessRepository, start: date, end: date) -> list[TradeScheme]:
    return [
        scheme
        for scheme in repository.get_trade_schemes()
        if scheme.status == "active" and scheme.start_date <= end and scheme.end_date >= start
    ]


def _claim_key(claim: SchemeClaim) -> tuple[str, str, str | None]:
    return (claim.scheme_id, claim.invoice_id, claim.sku_id)


def _eligible_amount(scheme: TradeScheme, quantity: float, taxable_value: float) -> float:
    if scheme.payout_type == "percent":
        return round(taxable_value * (float(scheme.payout_value) / 100), 2)
    return round(quantity * float(scheme.payout_value), 2)


def _eligible_lines(
    *,
    invoices: list[Invoice],
    products: dict[str, ProductSKU],
    schemes: list[TradeScheme],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for invoice in invoices:
        if invoice.date is None or invoice.date < start or invoice.date > end:
            continue
        for item in invoice.line_items:
            if not item.sku_id:
                continue
            product = products.get(item.sku_id)
            if product is None:
                continue
            for scheme in schemes:
                if scheme.brand_id and scheme.brand_id != product.brand_id:
                    continue
                if scheme.principal_id != product.principal_id:
                    continue
                rows.append(
                    {
                        "scheme_id": scheme.id,
                        "invoice_id": invoice.id,
                        "sku_id": item.sku_id,
                        "eligible_amount": _eligible_amount(scheme, float(item.quantity or 0), float(item.taxable_value)),
                    }
                )
    return rows


def reconcile_scheme_claims(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    requested_by: str,
) -> dict[str, Any]:
    """Compare locally eligible scheme amounts against local principal claim records."""
    period_start, period_end = _period_bounds(period)
    schemes = _active_schemes(repository, period_start, period_end)
    products = {product.id: product for product in repository.get_products()}
    claims = {_claim_key(claim): claim for claim in repository.get_scheme_claims()}
    eligible_lines = _eligible_lines(
        invoices=repository.get_invoices(),
        products=products,
        schemes=schemes,
        start=period_start,
        end=period_end,
    )
    matched_claims: list[dict[str, Any]] = []
    claim_mismatches: list[dict[str, Any]] = []
    missing_claims: list[dict[str, Any]] = []
    claimed_amount = 0.0
    disputed_amount = 0.0

    for row in eligible_lines:
        key = (row["scheme_id"], row["invoice_id"], row["sku_id"])
        claim = claims.get(key)
        if claim is None:
            missing_claims.append({**row, "code": "claim_missing"})
            disputed_amount = round(disputed_amount + float(row["eligible_amount"]), 2)
            continue
        claimed_amount = round(claimed_amount + float(claim.claim_amount), 2)
        if round(float(claim.claim_amount), 2) == round(float(row["eligible_amount"]), 2):
            matched_claims.append({**row, "claim_id": claim.id, "claimed_amount": float(claim.claim_amount)})
            continue
        difference = round(float(row["eligible_amount"]) - float(claim.claim_amount), 2)
        disputed_amount = round(disputed_amount + abs(difference), 2)
        claim_mismatches.append(
            {
                "scheme_id": row["scheme_id"],
                "invoice_id": row["invoice_id"],
                "sku_id": row["sku_id"],
                "eligible_amount": float(row["eligible_amount"]),
                "claimed_amount": float(claim.claim_amount),
                "code": "claim_amount_mismatch",
            }
        )

    eligible_amount = round(sum(float(row["eligible_amount"]) for row in eligible_lines), 2)
    summary = {
        "eligible_lines": len(eligible_lines),
        "matched_claims": len(matched_claims),
        "claim_mismatches": len(claim_mismatches),
        "missing_claims": len(missing_claims),
        "eligible_amount": eligible_amount,
        "claimed_amount": claimed_amount,
        "disputed_amount": disputed_amount,
    }
    status = "needs_review" if claim_mismatches or missing_claims else "approval_required"
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_principal_portal_performed": False,
        "limitation": LOCAL_SCHEME_CLAIM_LIMITATION,
    }
    batch_id = f"scheme_claim_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_scheme_claim_reconciliation",
        proposed_action=f"Review local scheme claim reconciliation for {period}",
        data={
            "batch_id": batch_id,
            "period": period,
            "summary": summary,
            "matched_claims": matched_claims,
            "claim_mismatches": claim_mismatches,
            "missing_claims": missing_claims,
            "mode": "local_contract_mock",
        },
        reason="Scheme claim reconciliation affects principal receivables and margin recovery; owner review is required first.",
        source="scheme_claims",
        confidence=0.9 if status == "approval_required" else 0.72,
        risk_level=RiskLevel.medium,
        dedupe_key=f"scheme_claims:{client_id}:{period}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": status,
        "approval_id": approval.id,
        "summary": summary,
        "matched_claims": matched_claims,
        "claim_mismatches": claim_mismatches,
        "missing_claims": missing_claims,
        "audit": audit,
    }
