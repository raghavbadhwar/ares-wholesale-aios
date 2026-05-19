"""Daily owner command brief."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.payment_radar import run_payment_radar
from apps.ares.ares.workflows.stock_radar import run_stock_radar


def run_daily_brief(
    repository: BusinessRepository,
    approvals: ApprovalService,
    *,
    client_id: str,
    language: str = "english_hinglish",
) -> dict:
    payment = run_payment_radar(repository, approvals, client_id=client_id, create_approvals=False)
    stock = run_stock_radar(repository)
    pending_orders = repository.list_orders(status="pending")
    pending_approvals = repository.list_pending_approvals()

    actions: list[str] = []
    if payment["priorities"]:
        top = payment["priorities"][0]
        actions.append(f"Follow up {top['customer_id']} for INR {top['amount']:.0f}.")
    if pending_orders:
        actions.append(f"Confirm/dispatch {len(pending_orders)} pending orders.")
    if stock["low_stock"]:
        actions.append(f"Review {len(stock['low_stock'])} low-stock SKUs.")
    if pending_approvals:
        actions.append(f"Clear {len(pending_approvals)} pending approvals.")

    return {
        "language": language,
        "payments": payment,
        "orders": {"pending_count": len(pending_orders)},
        "stock": stock,
        "customers": {"inactive_count": 0, "reorder_opportunities": 0},
        "suppliers": {"followups_needed": 0},
        "staff_operations": {"open_tasks": 0},
        "top_actions": actions[:5],
        "pending_approvals": len(pending_approvals),
    }

