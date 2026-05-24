"""Local Beckn/ONDC seller payload builders."""

from __future__ import annotations

from uuid import uuid4


def _beckn_context(*, action: str, subscriber_id: str, transaction_id: str | None = None) -> dict:
    return {
        "domain": "nic2004:52110",
        "country": "IND",
        "city": "std:080",
        "action": action,
        "core_version": "1.2.0",
        "bap_id": subscriber_id,
        "bpp_id": subscriber_id,
        "transaction_id": transaction_id or f"txn_{uuid4().hex[:12]}",
        "message_id": f"msg_{uuid4().hex[:12]}",
    }


def publish_ondc_catalogue_via_beckn(*, repository, seller_id: str) -> dict:
    items = [
        {
            "id": product.id,
            "descriptor": {"name": product.name},
            "category_id": getattr(product, "category", None),
            "quantity": {"available": {"count": str(getattr(product, "current_stock", 0))}},
            "price": {"value": str(getattr(product, "selling_price", 0) or 0)},
        }
        for product in repository.get_products()
    ]
    payload = {
        "context": _beckn_context(action="on_search", subscriber_id=seller_id),
        "message": {"catalog": {"bpp/descriptor": {"name": seller_id}, "bpp/providers": [{"id": seller_id, "items": items}]}},
    }
    return {
        "mode": "local_beckn_payload",
        "ondc_network_called": False,
        "items_published": len(items),
        "beckn_payload": payload,
        "limitation": "Local Beckn payload only; no ONDC gateway call made.",
    }


def acknowledge_ondc_order_via_beckn(*, ondc_order_id: str, seller_id: str, ack_status: str) -> dict:
    state = "Accepted" if ack_status == "ACK" else "Cancelled"
    payload = {
        "context": _beckn_context(action="on_confirm", subscriber_id=seller_id),
        "message": {"order": {"id": ondc_order_id, "state": state}},
    }
    return {
        "mode": "local_beckn_payload",
        "ack_status": ack_status,
        "ondc_network_called": False,
        "beckn_payload": payload,
        "limitation": "Local Beckn payload only; no ONDC gateway call made.",
    }
