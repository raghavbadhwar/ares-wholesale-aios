from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.mandi_prices import LOCAL_MANDI_PRICE_LIMITATION, prepare_mandi_price_alerts


def test_should_prepare_approval_gated_mandi_price_alert_from_local_price_snapshots() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    report = prepare_mandi_price_alerts(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        as_of=date(2026, 5, 21),
        requested_by="owner",
        relevant_commodities=["wheat"],
        nearby_apmcs=["Indore"],
        price_snapshots=[
            {
                "commodity": "wheat",
                "apmc": "Indore",
                "price_per_quintal": 2000,
                "observed_on": date(2026, 5, 20),
                "source": "local_csv_upload",
            },
            {
                "commodity": "wheat",
                "apmc": "Indore",
                "price_per_quintal": 2200,
                "observed_on": date(2026, 5, 21),
                "source": "local_csv_upload",
            },
            {
                "commodity": "wheat",
                "apmc": "Bhopal",
                "price_per_quintal": 2100,
                "observed_on": date(2026, 5, 21),
                "source": "local_csv_upload",
            },
        ],
    )

    assert report["mode"] == "local_contract_mock"
    assert report["status"] == "approval_required"
    assert report["summary"] == {
        "tracked_markets": 1,
        "alerts": 1,
        "stale_price_points": 0,
        "movement_threshold_percent": 5.0,
    }
    assert report["alerts"] == [
        {
            "commodity": "wheat",
            "apmc": "Indore",
            "latest_price_per_quintal": 2200.0,
            "previous_price_per_quintal": 2000.0,
            "movement_percent": 10.0,
            "direction": "up",
            "recommendation": "Review purchase timing; rising mandi price may justify faster customer repricing or supplier negotiation.",
            "data_lag_days": 0,
            "source": "local_csv_upload",
        }
    ]
    assert report["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "agmarknet_api_called": False,
        "external_market_feed_called": False,
        "purchase_order_placed": False,
        "price_change_executed": False,
        "limitation": LOCAL_MANDI_PRICE_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "review_mandi_price_alert"


def test_should_return_noop_when_mandi_price_movement_is_below_threshold() -> None:
    repo = InMemoryRepository()

    report = prepare_mandi_price_alerts(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        as_of=date(2026, 5, 21),
        requested_by="owner",
        relevant_commodities=["wheat"],
        nearby_apmcs=["Indore"],
        price_snapshots=[
            {"commodity": "wheat", "apmc": "Indore", "price_per_quintal": 2000, "observed_on": date(2026, 5, 20)},
            {"commodity": "wheat", "apmc": "Indore", "price_per_quintal": 2040, "observed_on": date(2026, 5, 21)},
        ],
    )

    assert report["mode"] == "local_contract_mock"
    assert report["status"] == "no_alerts"
    assert report["alerts"] == []
    assert report["summary"]["movement_threshold_percent"] == 5.0
    assert report["audit"]["agmarknet_api_called"] is False
    assert report["audit"]["limitation"] == LOCAL_MANDI_PRICE_LIMITATION
    assert repo.list_pending_approvals() == []
