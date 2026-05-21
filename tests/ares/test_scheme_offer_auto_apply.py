from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Brand, Order, OrderItem, Principal, ProductSKU, TradeScheme
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.scheme_offers import prepare_scheme_offer_applications


def test_should_suggest_best_active_scheme_for_order_line_and_require_approval() -> None:
    repo = InMemoryRepository.from_records(
        principals=[Principal(id="pr_hul", name="HUL")],
        brands=[Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel")],
        products=[
            ProductSKU(
                id="sku_surf",
                name="Surf Excel 1kg",
                principal_id="pr_hul",
                brand_id="br_surf",
                selling_price=100,
            )
        ],
        trade_schemes=[
            TradeScheme(
                id="scheme_percent",
                principal_id="pr_hul",
                brand_id="br_surf",
                name="10 percent off",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
                payout_type="percent",
                payout_value=10,
            ),
            TradeScheme(
                id="scheme_unit",
                principal_id="pr_hul",
                name="5 per unit",
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 31),
                payout_type="per_unit",
                payout_value=5,
            ),
        ],
    )
    approvals = ApprovalService(repo)
    order = Order(id="ord_1", customer_id="cust_1", items=[OrderItem(sku_id="sku_surf", name="Surf Excel 1kg", quantity=10)])

    result = prepare_scheme_offer_applications(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        order=order,
        as_of=date(2026, 5, 21),
        requested_by="salesman",
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["summary"] == {
        "eligible_lines": 1,
        "suggested_discount_amount": 100.0,
        "unmatched_lines": 0,
    }
    assert result["suggestions"] == [
        {
            "sku_id": "sku_surf",
            "product_name": "Surf Excel 1kg",
            "quantity": 10.0,
            "line_value": 1000.0,
            "scheme_id": "scheme_percent",
            "scheme_name": "10 percent off",
            "benefit_type": "percent",
            "benefit_value": 10.0,
            "suggested_discount_amount": 100.0,
        }
    ]
    assert result["audit"] == {
        "requested_by": "salesman",
        "approval_required": True,
        "external_principal_portal_called": False,
        "automatic_discount_posted": False,
        "limitation": "Local scheme/offer suggestion only; no principal portal validation or automatic discount execution was performed.",
    }
    assert repo.list_pending_approvals()[0].type == "apply_scheme_offer"
    assert repo.list_pending_approvals()[0].data["suggestions"][0]["scheme_id"] == "scheme_percent"


def test_should_return_noop_when_no_active_scheme_matches_order() -> None:
    repo = InMemoryRepository.from_records(
        products=[ProductSKU(id="sku_surf", name="Surf Excel 1kg", principal_id="pr_hul", brand_id="br_surf", selling_price=100)],
        trade_schemes=[
            TradeScheme(
                id="scheme_expired",
                principal_id="pr_hul",
                brand_id="br_surf",
                name="Expired",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 30),
                payout_type="percent",
                payout_value=10,
            )
        ],
    )
    order = Order(id="ord_1", customer_id="cust_1", items=[OrderItem(sku_id="sku_surf", name="Surf Excel 1kg", quantity=1)])

    result = prepare_scheme_offer_applications(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        order=order,
        as_of=date(2026, 5, 21),
        requested_by="salesman",
    )

    assert result["status"] == "no_applicable_schemes"
    assert result["suggestions"] == []
    assert repo.list_pending_approvals() == []
