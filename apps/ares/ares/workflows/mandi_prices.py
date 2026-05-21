"""Local mandi price alert contract."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_MANDI_PRICE_LIMITATION = (
    "Local mandi price contract only; no Agmarknet API, external market feed, purchase order, "
    "or price-change execution was called."
)


def prepare_mandi_price_alerts(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    as_of: date,
    requested_by: str,
    relevant_commodities: list[str],
    nearby_apmcs: list[str],
    price_snapshots: list[dict[str, Any]],
    movement_threshold_percent: float = 5.0,
) -> dict[str, Any]:
    """Prepare local mandi price movement alerts for owner review."""
    groups = _group_relevant_snapshots(
        price_snapshots=price_snapshots,
        relevant_commodities=relevant_commodities,
        nearby_apmcs=nearby_apmcs,
    )
    alerts: list[dict[str, Any]] = []
    stale_price_points = 0

    for snapshots in groups.values():
        latest = snapshots[-1]
        if (as_of - latest["observed_on"]).days > 1:
            stale_price_points += 1
        if len(snapshots) < 2:
            continue
        previous = snapshots[-2]
        movement = _movement_percent(previous_price=previous["price_per_quintal"], latest_price=latest["price_per_quintal"])
        if abs(movement) < movement_threshold_percent:
            continue
        alerts.append(
            {
                "commodity": latest["commodity"],
                "apmc": latest["apmc"],
                "latest_price_per_quintal": latest["price_per_quintal"],
                "previous_price_per_quintal": previous["price_per_quintal"],
                "movement_percent": movement,
                "direction": "up" if movement > 0 else "down",
                "recommendation": _recommendation(movement),
                "data_lag_days": max((as_of - latest["observed_on"]).days, 0),
                "source": latest.get("source", "local_snapshot"),
            }
        )

    alerts.sort(key=lambda row: (abs(float(row["movement_percent"])), row["commodity"], row["apmc"]), reverse=True)
    summary = {
        "tracked_markets": len(groups),
        "alerts": len(alerts),
        "stale_price_points": stale_price_points,
        "movement_threshold_percent": float(movement_threshold_percent),
    }
    audit = _audit(requested_by=requested_by, approval_required=bool(alerts))
    if not alerts:
        return {
            "mode": "local_contract_mock",
            "status": "no_alerts",
            "as_of": as_of.isoformat(),
            "summary": summary,
            "alerts": [],
            "audit": audit,
        }

    batch_id = f"mandi_price_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_mandi_price_alert",
        proposed_action=f"Review {len(alerts)} local mandi price alerts",
        data={
            "batch_id": batch_id,
            "as_of": as_of.isoformat(),
            "summary": summary,
            "alerts": alerts,
            "mode": "local_contract_mock",
        },
        reason="Mandi price alerts can influence buying, customer pricing, and stock commitments; owner review is required first.",
        source="mandi_prices",
        confidence=0.8,
        risk_level=RiskLevel.medium,
        dedupe_key=f"mandi_price:{client_id}:{as_of.isoformat()}:{batch_id}",
    )
    return {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "as_of": as_of.isoformat(),
        "summary": summary,
        "alerts": alerts,
        "audit": audit,
    }


def _group_relevant_snapshots(
    *,
    price_snapshots: list[dict[str, Any]],
    relevant_commodities: list[str],
    nearby_apmcs: list[str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    relevant = {commodity.strip().lower() for commodity in relevant_commodities}
    apmcs = {apmc.strip().lower() for apmc in nearby_apmcs}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for snapshot in price_snapshots:
        normalized = _normalize_snapshot(snapshot)
        if normalized["commodity"].lower() not in relevant or normalized["apmc"].lower() not in apmcs:
            continue
        groups.setdefault((normalized["commodity"].lower(), normalized["apmc"].lower()), []).append(normalized)
    for snapshots in groups.values():
        snapshots.sort(key=lambda item: item["observed_on"])
    return groups


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    observed_on = snapshot["observed_on"]
    if isinstance(observed_on, str):
        observed_on = date.fromisoformat(observed_on)
    return {
        "commodity": str(snapshot["commodity"]).strip().lower(),
        "apmc": str(snapshot["apmc"]).strip().title(),
        "price_per_quintal": round(float(snapshot["price_per_quintal"]), 2),
        "observed_on": observed_on,
        "source": snapshot.get("source", "local_snapshot"),
    }


def _movement_percent(*, previous_price: float, latest_price: float) -> float:
    if previous_price <= 0:
        return 0.0
    return round(((latest_price - previous_price) / previous_price) * 100, 2)


def _recommendation(movement_percent: float) -> str:
    if movement_percent > 0:
        return "Review purchase timing; rising mandi price may justify faster customer repricing or supplier negotiation."
    return "Review purchase timing; falling mandi price may justify delaying non-urgent procurement."


def _audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "agmarknet_api_called": False,
        "external_market_feed_called": False,
        "purchase_order_placed": False,
        "price_change_executed": False,
        "limitation": LOCAL_MANDI_PRICE_LIMITATION,
    }
