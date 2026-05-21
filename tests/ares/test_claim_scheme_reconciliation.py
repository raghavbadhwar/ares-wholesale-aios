from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import (
    Brand,
    Invoice,
    InvoiceLineItem,
    Principal,
    ProductSKU,
    SchemeClaim,
    TradeScheme,
)
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.scheme_claims import reconcile_scheme_claims


def test_should_reconcile_scheme_claims_against_sales_invoice_eligibility() -> None:
    repo = InMemoryRepository.from_records(
        principals=[Principal(id="pr_hul", name="HUL")],
        brands=[Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel")],
        products=[ProductSKU(id="sku_surf", name="Surf Excel 1kg", principal_id="pr_hul", brand_id="br_surf")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_raj",
                date=date(2026, 5, 12),
                amount=11800,
                taxable_value=10000,
                tax_amount=1800,
                line_items=[
                    InvoiceLineItem(
                        sku_id="sku_surf",
                        description="Surf Excel 1kg",
                        hsn_code="3401",
                        quantity=10,
                        unit="BOX",
                        taxable_value=10000,
                    )
                ],
            )
        ],
        trade_schemes=[
            TradeScheme(
                id="scheme_surf_may",
                principal_id="pr_hul",
                brand_id="br_surf",
                name="May Surf Support",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
                payout_type="per_unit",
                payout_value=5,
            )
        ],
        scheme_claims=[
            SchemeClaim(
                id="claim_1",
                scheme_id="scheme_surf_may",
                principal_id="pr_hul",
                invoice_id="inv_1",
                sku_id="sku_surf",
                claim_amount=40,
                status="submitted",
            )
        ],
    )
    approvals = ApprovalService(repo)

    result = reconcile_scheme_claims(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        requested_by="owner",
    )

    assert approvals.requires_approval("review_scheme_claim_reconciliation") is True
    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "needs_review"
    assert result["summary"] == {
        "eligible_lines": 1,
        "matched_claims": 0,
        "claim_mismatches": 1,
        "missing_claims": 0,
        "eligible_amount": 50.0,
        "claimed_amount": 40.0,
        "disputed_amount": 10.0,
    }
    assert result["claim_mismatches"] == [
        {
            "scheme_id": "scheme_surf_may",
            "invoice_id": "inv_1",
            "sku_id": "sku_surf",
            "eligible_amount": 50.0,
            "claimed_amount": 40.0,
            "code": "claim_amount_mismatch",
        }
    ]
    assert result["audit"]["external_principal_portal_performed"] is False
    assert result["audit"]["limitation"] == "Local scheme claim reconciliation only; no principal portal or settlement API was called."
    assert repo.list_pending_approvals()[0].type == "review_scheme_claim_reconciliation"


def test_should_surface_missing_scheme_claims_for_eligible_sales() -> None:
    repo = InMemoryRepository.from_records(
        principals=[Principal(id="pr_hul", name="HUL")],
        brands=[Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel")],
        products=[ProductSKU(id="sku_surf", name="Surf Excel 1kg", principal_id="pr_hul", brand_id="br_surf")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                date=date(2026, 5, 12),
                amount=5900,
                taxable_value=5000,
                tax_amount=900,
                line_items=[
                    InvoiceLineItem(sku_id="sku_surf", description="Surf Excel 1kg", quantity=4, taxable_value=5000)
                ],
            )
        ],
        trade_schemes=[
            TradeScheme(
                id="scheme_surf_may",
                principal_id="pr_hul",
                brand_id="br_surf",
                name="May Surf Support",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
                payout_type="per_unit",
                payout_value=5,
            )
        ],
    )

    result = reconcile_scheme_claims(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        period="2026-05",
        requested_by="owner",
    )

    assert result["summary"]["missing_claims"] == 1
    assert result["missing_claims"] == [
        {
            "scheme_id": "scheme_surf_may",
            "invoice_id": "inv_1",
            "sku_id": "sku_surf",
            "eligible_amount": 20.0,
            "code": "claim_missing",
        }
    ]


def test_should_persist_scheme_and_claim_records_for_local_reconciliation(tmp_path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_trade_scheme(
        TradeScheme(
            id="scheme_surf_may",
            principal_id="pr_hul",
            brand_id="br_surf",
            name="May Surf Support",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            payout_type="per_unit",
            payout_value=5,
        )
    )
    repo.upsert_scheme_claim(
        SchemeClaim(
            id="claim_1",
            scheme_id="scheme_surf_may",
            principal_id="pr_hul",
            invoice_id="inv_1",
            sku_id="sku_surf",
            claim_amount=20,
        )
    )

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_trade_schemes()[0].name == "May Surf Support"
    assert reloaded.get_scheme_claims()[0].claim_amount == 20
