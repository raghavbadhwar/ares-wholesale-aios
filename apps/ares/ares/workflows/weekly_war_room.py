"""Weekly management report workflow."""

from __future__ import annotations

from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.stock_radar import run_stock_radar


def run_weekly_war_room(repository: BusinessRepository) -> dict:
    stock = run_stock_radar(repository)
    invoices = repository.get_invoices()
    payments = repository.get_payments()
    orders = repository.list_orders()
    overdue = [invoice for invoice in repository.get_outstanding() if invoice.status == "overdue"]
    return {
        "sales_summary": {"orders": len(orders)},
        "collections_summary": {
            "open_invoices": len(repository.get_outstanding()),
            "payments_recorded": len(payments),
        },
        "overdue_trend": {"overdue_count": len(overdue)},
        "order_delays": {"pending_orders": len([order for order in orders if order.status == "pending"])},
        "stock_risks": stock,
        "top_customers": sorted(
            {invoice.customer_id for invoice in invoices if invoice.customer_id},
            key=str,
        )[:5],
        "dormant_customers": [],
        "supplier_issues": [],
        "next_week_priorities": ["Collections", "Dispatch hygiene", "Low stock review"],
    }

