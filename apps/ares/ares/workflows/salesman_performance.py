"""Local salesman performance scorecards."""

from __future__ import annotations

from typing import Any

from apps.ares.ares.data.models import BeatRoute, StaffMember
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SALESMAN_PERFORMANCE_LIMITATION = (
    "Local salesman performance tracking only; no GPS, live attendance, or field-force integration was called."
)


def _routes_by_staff(repository: BusinessRepository) -> dict[str, list[BeatRoute]]:
    routes: dict[str, list[BeatRoute]] = {}
    for route in repository.get_beat_routes():
        if route.staff_id:
            routes.setdefault(route.staff_id, []).append(route)
    return routes


def _route_customer_ids(routes: list[BeatRoute]) -> list[str]:
    seen: list[str] = []
    for route in routes:
        for stop in sorted(route.stops, key=lambda item: item.sequence):
            if stop.customer_id not in seen:
                seen.append(stop.customer_id)
    return seen


def _orders_for_staff(repository: BusinessRepository, staff: StaffMember) -> list:
    return [order for order in repository.list_orders() if order.assigned_staff == staff.id]


def _coverage_percent(planned_customers: list[str], order_customers: set[str]) -> float:
    if not planned_customers:
        return 0.0
    covered = len([customer_id for customer_id in planned_customers if customer_id in order_customers])
    return round((covered / len(planned_customers)) * 100, 2)


def _collected_amount(repository: BusinessRepository, customers: set[str]) -> float:
    return round(
        sum(
            float(payment.amount)
            for payment in repository.get_payments()
            if payment.customer_id in customers and payment.status.strip().lower() == "reconciled"
        ),
        2,
    )


def _overdue_amount(repository: BusinessRepository, customers: set[str]) -> float:
    return round(
        sum(
            float(invoice.amount)
            for invoice in repository.get_invoices()
            if invoice.customer_id in customers and invoice.status.strip().lower() == "overdue"
        ),
        2,
    )


def _performance_score(*, coverage: float, collected: float, overdue: float) -> int:
    score = 70 + int(coverage * 0.2) + min(int(collected // 500), 10)
    if overdue > 0:
        score -= 10
    return max(min(score, 100), 0)


def _performance_band(*, coverage: float, overdue: float, score: int) -> str:
    if coverage == 0 and overdue > 0:
        return "needs_attention"
    if score >= 80:
        return "strong"
    if score >= 60:
        return "watch"
    return "needs_attention"


def build_salesman_performance_scorecards(*, repository: BusinessRepository) -> dict[str, Any]:
    """Build local salesman scorecards from route, order, collection, and overdue records."""
    routes_by_staff = _routes_by_staff(repository)
    scorecards: list[dict[str, Any]] = []

    for staff in repository.get_staff_members():
        routes = routes_by_staff.get(staff.id, [])
        planned_customers = _route_customer_ids(routes)
        planned_customer_set = set(planned_customers)
        orders = _orders_for_staff(repository, staff)
        order_customers = {order.customer_id for order in orders if order.customer_id}
        coverage = _coverage_percent(planned_customers, order_customers)
        collected = _collected_amount(repository, planned_customer_set)
        overdue = _overdue_amount(repository, planned_customer_set)
        score = _performance_score(coverage=coverage, collected=collected, overdue=overdue)
        band = _performance_band(coverage=coverage, overdue=overdue, score=score)
        scorecards.append(
            {
                "staff_id": staff.id,
                "staff_name": staff.name,
                "planned_stops": len(planned_customers),
                "orders_captured": len(orders),
                "unique_order_customers": len(order_customers),
                "route_order_coverage_percent": coverage,
                "collected_amount": collected,
                "overdue_amount": overdue,
                "performance_score": score,
                "performance_band": band,
            }
        )

    band_rank = {"strong": 0, "watch": 1, "needs_attention": 2}
    scorecards.sort(key=lambda row: (band_rank[row["performance_band"]], -row["performance_score"], row["staff_name"]))
    return {
        "mode": "local_contract_mock",
        "summary": {
            "salesmen": len(scorecards),
            "planned_stops": sum(int(row["planned_stops"]) for row in scorecards),
            "orders_captured": sum(int(row["orders_captured"]) for row in scorecards),
            "collected_amount": round(sum(float(row["collected_amount"]) for row in scorecards), 2),
            "overdue_amount": round(sum(float(row["overdue_amount"]) for row in scorecards), 2),
            "needs_attention": sum(1 for row in scorecards if row["performance_band"] == "needs_attention"),
        },
        "scorecards": scorecards,
        "audit": {
            "gps_tracking_called": False,
            "field_force_app_called": False,
            "live_attendance_called": False,
            "limitation": LOCAL_SALESMAN_PERFORMANCE_LIMITATION,
        },
    }
