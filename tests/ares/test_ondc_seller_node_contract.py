from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ProductSKU
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.ondc_seller import (
    LOCAL_ONDC_SELLER_LIMITATION,
    ingest_ondc_order_contract,
    prepare_ondc_catalogue_sync_contract,
)


def test_should_prepare_approval_gated_ondc_catalogue_sync_contract_without_network_call() -> None:
    repo = InMemoryRepository.from_records(
        products=[
            ProductSKU(
                id="sku_soap",
                name="Soap Case",
                category="FMCG",
                current_stock=24,
                selling_price=250,
            )
        ]
    )
    approvals = ApprovalService(repo)

    catalogue = prepare_ondc_catalogue_sync_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        seller_id="seller_demo",
        requested_by="owner",
    )

    assert catalogue["mode"] == "local_contract_mock"
    assert catalogue["status"] == "approval_required"
    assert catalogue["summary"] == {"catalogue_items": 1, "out_of_stock_items": 0}
    assert catalogue["items"][0]["sku_id"] == "sku_soap"
    assert catalogue["items"][0]["available_quantity"] == 24.0
    assert catalogue["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "ondc_network_called": False,
        "catalogue_synced": False,
        "stock_committed": False,
        "logistics_api_called": False,
        "order_execution_performed": False,
        "limitation": LOCAL_ONDC_SELLER_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "sync_ondc_catalogue"


def test_should_ingest_ondc_order_as_local_order_contract_and_dedupe_stock_commitment() -> None:
    repo = InMemoryRepository.from_records(products=[ProductSKU(id="sku_soap", name="Soap Case", current_stock=24)])
    approvals = ApprovalService(repo)

    result = ingest_ondc_order_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        requested_by="owner",
        ondc_order={
            "ondc_order_id": "ondc_1",
            "buyer_id": "buyer_1",
            "items": [{"sku_id": "sku_soap", "name": "Soap Case", "quantity": 3, "unit": "case"}],
        },
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["order"]["source"] == "ondc_contract"
    assert result["order"]["file_id"] == "ondc_1"
    assert result["audit"]["ondc_network_called"] is False
    assert result["audit"]["stock_committed"] is False
    assert result["audit"]["limitation"] == LOCAL_ONDC_SELLER_LIMITATION
    assert repo.list_orders()[0].file_id == "ondc_1"
    assert repo.list_pending_approvals()[0].type == "add_order_to_dispatch_queue"

    duplicate = ingest_ondc_order_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        requested_by="owner",
        ondc_order={
            "ondc_order_id": "ondc_1",
            "buyer_id": "buyer_1",
            "items": [{"sku_id": "sku_soap", "name": "Soap Case", "quantity": 3, "unit": "case"}],
        },
    )

    assert duplicate["status"] == "duplicate_ignored"
    assert len(repo.list_orders()) == 1
    assert duplicate["audit"]["stock_committed"] is False
