from __future__ import annotations

from apps.ares.ares.data.models import BeatRoute, BeatRouteStop, Customer, Invoice, Order, Payment, StaffMember
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.salesman_performance import build_salesman_performance_scorecards


def test_should_build_salesman_scorecards_from_routes_orders_collections_and_overdues() -> None:
    repo = InMemoryRepository.from_records(
        staff_members=[
            StaffMember(id="staff_ravi", name="Ravi", role="salesman"),
            StaffMember(id="staff_amit", name="Amit", role="salesman"),
        ],
        customers=[
            Customer(id="cust_1", name="Raj Retail"),
            Customer(id="cust_2", name="Maya Retail"),
            Customer(id="cust_3", name="Kumar Retail"),
        ],
        beat_routes=[
            BeatRoute(
                id="route_ravi",
                name="Ravi Monday",
                staff_id="staff_ravi",
                stops=[
                    BeatRouteStop(customer_id="cust_1", sequence=1),
                    BeatRouteStop(customer_id="cust_2", sequence=2),
                ],
            ),
            BeatRoute(id="route_amit", name="Amit Monday", staff_id="staff_amit", stops=[BeatRouteStop(customer_id="cust_3", sequence=1)]),
        ],
        orders=[
            Order(id="ord_1", customer_id="cust_1", assigned_staff="staff_ravi", status="pending"),
            Order(id="ord_2", customer_id="cust_2", assigned_staff="staff_ravi", status="confirmed"),
        ],
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_2", amount=1000, status="overdue"),
            Invoice(id="inv_2", invoice_number="INV-2", customer_id="cust_3", amount=2000, status="overdue"),
        ],
        payments=[
            Payment(id="pay_1", customer_id="cust_1", amount=5000, status="reconciled"),
        ],
    )

    report = build_salesman_performance_scorecards(repository=repo)

    assert report["mode"] == "local_contract_mock"
    assert report["summary"] == {
        "salesmen": 2,
        "planned_stops": 3,
        "orders_captured": 2,
        "collected_amount": 5000.0,
        "overdue_amount": 3000.0,
        "needs_attention": 1,
    }
    assert report["scorecards"][0] == {
        "staff_id": "staff_ravi",
        "staff_name": "Ravi",
        "planned_stops": 2,
        "orders_captured": 2,
        "unique_order_customers": 2,
        "route_order_coverage_percent": 100.0,
        "collected_amount": 5000.0,
        "overdue_amount": 1000.0,
        "performance_score": 90,
        "performance_band": "strong",
    }
    assert report["scorecards"][1]["staff_id"] == "staff_amit"
    assert report["scorecards"][1]["performance_band"] == "needs_attention"
    assert report["audit"] == {
        "gps_tracking_called": False,
        "field_force_app_called": False,
        "live_attendance_called": False,
        "limitation": "Local salesman performance tracking only; no GPS, live attendance, or field-force integration was called.",
    }


def test_should_return_empty_salesman_scorecards_without_staff() -> None:
    report = build_salesman_performance_scorecards(repository=InMemoryRepository())

    assert report["summary"]["salesmen"] == 0
    assert report["scorecards"] == []
