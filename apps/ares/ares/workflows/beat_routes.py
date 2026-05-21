"""Local beat-route planning contract."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import BeatRoute, Customer, Invoice, Order, RiskLevel, StaffMember
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_BEAT_ROUTE_LIMITATION = "Local beat-route planning contract only; no GPS, WhatsApp, or live field-force tracking was performed."


def _find_route(repository: BusinessRepository, route_id: str) -> BeatRoute:
    for route in repository.get_beat_routes():
        if route.id == route_id:
            return route
    raise KeyError(f"Beat route not found: {route_id}")


def _staff_by_id(repository: BusinessRepository) -> dict[str, StaffMember]:
    return {staff.id: staff for staff in repository.get_staff_members()}


def _customer_by_id(repository: BusinessRepository) -> dict[str, Customer]:
    return {customer.id: customer for customer in repository.get_customers()}


def _invoice_totals(customer_id: str, invoices: list[Invoice]) -> tuple[float, float, int]:
    relevant = [invoice for invoice in invoices if invoice.customer_id == customer_id and invoice.status in {"open", "overdue"}]
    outstanding = round(sum(float(invoice.amount) for invoice in relevant), 2)
    overdue = round(sum(float(invoice.amount) for invoice in relevant if invoice.status == "overdue"), 2)
    overdue_count = sum(1 for invoice in relevant if invoice.status == "overdue")
    return outstanding, overdue, overdue_count


def _open_orders(customer_id: str, orders: list[Order]) -> list[str]:
    return [
        order.id
        for order in orders
        if order.customer_id == customer_id and order.status in {"pending", "captured", "confirmed"}
    ]


def prepare_beat_route_plan(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    route_id: str,
    visit_date: date,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local beat-route plan for a salesman visit day."""
    route = _find_route(repository, route_id)
    staff_members = _staff_by_id(repository)
    customers = _customer_by_id(repository)
    staff = staff_members.get(route.staff_id or "")
    invoices = repository.get_invoices()
    orders = repository.list_orders()
    validation_errors: list[dict[str, Any]] = []
    if route.staff_id and staff is None:
        validation_errors.append({"code": "staff_missing", "staff_id": route.staff_id})
    if not route.stops:
        validation_errors.append({"code": "route_has_no_stops"})

    stops: list[dict[str, Any]] = []
    for stop in sorted(route.stops, key=lambda item: item.sequence):
        customer = customers.get(stop.customer_id)
        if customer is None:
            validation_errors.append({"code": "customer_missing", "customer_id": stop.customer_id, "sequence": stop.sequence})
            continue
        outstanding_amount, overdue_amount, overdue_count = _invoice_totals(customer.id, invoices)
        open_order_ids = _open_orders(customer.id, orders)
        coverage_risk = overdue_amount > 0
        stops.append(
            {
                "sequence": stop.sequence,
                "planned_time": stop.planned_time,
                "customer_id": customer.id,
                "customer_name": customer.name,
                "phone": customer.phone,
                "location": customer.location,
                "open_order_ids": open_order_ids,
                "outstanding_amount": outstanding_amount,
                "overdue_amount": overdue_amount,
                "overdue_invoice_count": overdue_count,
                "coverage_risk": coverage_risk,
                "notes": stop.notes,
            }
        )

    summary = {
        "stops": len(stops),
        "open_orders": sum(len(stop["open_order_ids"]) for stop in stops),
        "overdue_invoices": sum(int(stop["overdue_invoice_count"]) for stop in stops),
        "coverage_risk_count": sum(1 for stop in stops if stop["coverage_risk"]),
        "total_outstanding": round(sum(float(stop["outstanding_amount"]) for stop in stops), 2),
    }
    status = "needs_review" if validation_errors else "approval_required"
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_dispatch_performed": False,
        "limitation": LOCAL_BEAT_ROUTE_LIMITATION,
    }
    batch_id = f"beat_{uuid4().hex[:12]}"
    route_payload = {
        "route_id": route.id,
        "name": route.name,
        "staff_id": route.staff_id,
        "staff_name": staff.name if staff else None,
        "visit_date": visit_date.isoformat(),
    }
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="plan_beat_route",
        proposed_action=f"Review beat route plan for {route.name} on {visit_date.isoformat()}",
        data={
            "batch_id": batch_id,
            "route_id": route_id,
            "visit_date": visit_date.isoformat(),
            "summary": summary,
            "route": route_payload,
            "stops": stops,
            "validation_errors": validation_errors,
            "mode": "local_contract_mock",
        },
        reason="Beat-route plans affect salesman workload and retailer coverage; owner approval is required first.",
        source="beat_routes",
        confidence=0.9 if not validation_errors else 0.65,
        risk_level=RiskLevel.medium,
        dedupe_key=f"beat_route:{client_id}:{route_id}:{visit_date.isoformat()}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": status,
        "approval_id": approval.id,
        "route": route_payload,
        "summary": summary,
        "stops": stops,
        "validation_errors": validation_errors,
        "audit": audit,
    }
