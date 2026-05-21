from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import BeatRoute, BeatRouteStop, Customer, Invoice, Order, StaffMember
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.beat_routes import prepare_beat_route_plan


def test_should_prepare_approval_gated_beat_route_plan_with_customer_risk_context() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_raj", name="Raj Traders", phone="+919999999991", location="Andheri"),
            Customer(id="cust_delhi", name="Delhi Retail", phone="+919999999992", location="Bandra"),
        ],
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_raj", amount=5000, status="overdue"),
            Invoice(id="inv_2", invoice_number="INV-2", customer_id="cust_delhi", amount=3000, status="open"),
        ],
        staff_members=[StaffMember(id="staff_amit", name="Amit", role="salesman", phone="+919888888888")],
        beat_routes=[
            BeatRoute(
                id="beat_west",
                name="Mumbai West Beat",
                staff_id="staff_amit",
                stops=[
                    BeatRouteStop(customer_id="cust_raj", sequence=1, planned_time="10:00"),
                    BeatRouteStop(customer_id="cust_delhi", sequence=2, planned_time="11:30"),
                ],
            )
        ],
    )
    repo.create_order(Order(id="ord_1", customer_id="cust_raj", status="pending"))
    approvals = ApprovalService(repo)

    plan = prepare_beat_route_plan(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        route_id="beat_west",
        visit_date=date(2026, 5, 22),
        requested_by="owner",
    )

    assert approvals.requires_approval("plan_beat_route") is True
    assert plan["mode"] == "local_contract_mock"
    assert plan["status"] == "approval_required"
    assert plan["summary"] == {
        "stops": 2,
        "open_orders": 1,
        "overdue_invoices": 1,
        "coverage_risk_count": 1,
        "total_outstanding": 8000.0,
    }
    assert plan["route"]["name"] == "Mumbai West Beat"
    assert plan["route"]["staff_name"] == "Amit"
    assert plan["stops"][0]["customer_name"] == "Raj Traders"
    assert plan["stops"][0]["open_order_ids"] == ["ord_1"]
    assert plan["stops"][0]["overdue_amount"] == 5000.0
    assert plan["stops"][0]["coverage_risk"] is True
    assert plan["audit"]["external_dispatch_performed"] is False
    assert plan["audit"]["limitation"] == "Local beat-route planning contract only; no GPS, WhatsApp, or live field-force tracking was performed."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "plan_beat_route"
    assert approval.data["route_id"] == "beat_west"
    assert approval.data["summary"] == plan["summary"]


def test_should_surface_beat_route_validation_errors_for_missing_staff_and_customer() -> None:
    repo = InMemoryRepository.from_records(
        beat_routes=[
            BeatRoute(
                id="beat_bad",
                name="Broken Beat",
                staff_id="missing_staff",
                stops=[BeatRouteStop(customer_id="missing_customer", sequence=1)],
            )
        ]
    )

    plan = prepare_beat_route_plan(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        route_id="beat_bad",
        visit_date=date(2026, 5, 22),
        requested_by="owner",
    )

    assert plan["status"] == "needs_review"
    assert plan["summary"]["stops"] == 0
    assert plan["validation_errors"] == [
        {"code": "staff_missing", "staff_id": "missing_staff"},
        {"code": "customer_missing", "customer_id": "missing_customer", "sequence": 1},
    ]
    assert repo.list_pending_approvals()[0].type == "plan_beat_route"


def test_should_persist_staff_and_beat_route_records_for_local_route_planning(tmp_path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_staff_member(StaffMember(id="staff_amit", name="Amit", role="salesman"))
    repo.upsert_beat_route(
        BeatRoute(
            id="beat_west",
            name="Mumbai West Beat",
            staff_id="staff_amit",
            stops=[BeatRouteStop(customer_id="cust_raj", sequence=1)],
        )
    )

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_staff_members()[0].name == "Amit"
    assert reloaded.get_beat_routes()[0].stops[0].customer_id == "cust_raj"
