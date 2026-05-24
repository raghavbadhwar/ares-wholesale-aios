"""Local-only carrier sandbox contracts."""

from __future__ import annotations


LIMITATION = "Local contract mock only; no carrier API call is made."


def integrate_delhivery_sandbox(*, shipment: dict) -> dict:
    return {
        "mode": "local_contract_mock",
        "live_called": False,
        "status": "mock_pending",
        "waybill": None,
        "shipment_ref": shipment.get("invoice_id"),
        "limitation": LIMITATION,
        "audit": {"carrier_api_called": False},
    }


def integrate_shiprocket_sandbox(*, order: dict) -> dict:
    return {
        "mode": "local_contract_mock",
        "live_called": False,
        "status": "mock_pending",
        "order_id": None,
        "shipment_id": None,
        "order_ref": order.get("invoice_id"),
        "limitation": LIMITATION,
        "audit": {"carrier_api_called": False},
    }
