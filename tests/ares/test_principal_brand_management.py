from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import Brand, Principal, ProductSKU
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.principal_brands import prepare_principal_brand_review


def test_should_prepare_local_principal_brand_review_with_product_margin_visibility() -> None:
    repo = InMemoryRepository.from_records(
        principals=[
            Principal(id="pr_hul", name="HUL", gstin="27HULXX1234F1Z5", payment_terms="30 days"),
            Principal(id="pr_pg", name="P&G", gstin="27PGXXX1234F1Z5", payment_terms="21 days"),
        ],
        brands=[
            Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel", category="detergent", default_margin_percent=12),
            Brand(id="br_ariel", principal_id="pr_pg", name="Ariel", category="detergent", default_margin_percent=10),
        ],
        products=[
            ProductSKU(
                id="sku_surf",
                name="Surf Excel 1kg",
                principal_id="pr_hul",
                brand_id="br_surf",
                current_stock=50,
                reorder_level=20,
                buying_price=100,
                selling_price=118,
            ),
            ProductSKU(
                id="sku_ariel",
                name="Ariel 1kg",
                principal_id="pr_pg",
                brand_id="br_ariel",
                current_stock=5,
                reorder_level=10,
                buying_price=110,
                selling_price=121,
            ),
        ],
    )
    approvals = ApprovalService(repo)

    review = prepare_principal_brand_review(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        requested_by="owner",
    )

    assert approvals.requires_approval("review_principal_brand_plan") is True
    assert review["mode"] == "local_contract_mock"
    assert review["status"] == "approval_required"
    assert review["summary"] == {
        "principals": 2,
        "brands": 2,
        "products_linked": 2,
        "low_stock_products": 1,
        "missing_links": 0,
    }
    assert review["principals"][0]["principal_name"] == "HUL"
    assert review["principals"][0]["brands"][0]["brand_name"] == "Surf Excel"
    assert review["principals"][0]["products"][0]["computed_margin_percent"] == 18.0
    assert review["principals"][1]["products"][0]["low_stock"] is True
    assert review["audit"]["external_principal_sync_performed"] is False
    assert review["audit"]["limitation"] == "Local principal/brand management surface only; no live principal, distributor, or ERP integration was called."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "review_principal_brand_plan"
    assert approval.data["summary"] == review["summary"]


def test_should_surface_products_missing_principal_or_brand_links() -> None:
    repo = InMemoryRepository.from_records(
        products=[
            ProductSKU(id="sku_unlinked", name="Loose Soap", current_stock=10, reorder_level=5),
            ProductSKU(id="sku_bad_brand", name="Bad Brand", principal_id="missing_principal", brand_id="missing_brand"),
        ]
    )

    review = prepare_principal_brand_review(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        requested_by="owner",
    )

    assert review["status"] == "needs_review"
    assert review["summary"]["missing_links"] == 2
    assert review["missing_links"] == [
        {"sku_id": "sku_unlinked", "name": "Loose Soap", "code": "principal_or_brand_missing"},
        {"sku_id": "sku_bad_brand", "name": "Bad Brand", "code": "principal_missing"},
        {"sku_id": "sku_bad_brand", "name": "Bad Brand", "code": "brand_missing"},
    ]


def test_should_persist_principal_and_brand_records_for_local_management(tmp_path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_principal(Principal(id="pr_hul", name="HUL", gstin="27HULXX1234F1Z5"))
    repo.upsert_brand(Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel"))

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_principals()[0].name == "HUL"
    assert reloaded.get_brands()[0].principal_id == "pr_hul"
