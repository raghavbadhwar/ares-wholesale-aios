"""Daily owner command brief."""

from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.collections_dashboard import build_collections_dashboard
from apps.ares.ares.workflows.payment_radar import run_payment_radar
from apps.ares.ares.workflows.stock_radar import run_stock_radar
from apps.ares.ares.workflows.working_capital import build_working_capital_intelligence


def run_daily_brief(
    repository: BusinessRepository,
    approvals: ApprovalService,
    *,
    client_id: str,
    language: str = "english_hinglish",
    today: date | None = None,
    opening_cash: float = 0.0,
) -> dict:
    today = today or date.today()
    payment = run_payment_radar(repository, approvals, client_id=client_id, today=today, create_approvals=False)
    stock = run_stock_radar(repository)
    collections = build_collections_dashboard(repository=repository, as_of=today)
    working_capital = build_working_capital_intelligence(repository=repository, as_of=today, opening_cash=opening_cash)
    pending_orders = repository.list_orders(status="pending")
    pending_approvals = repository.list_pending_approvals()

    actions: list[str] = []
    if payment["priorities"]:
        top = payment["priorities"][0]
        actions.append(f"Follow up {top['customer_id']} for INR {top['amount']:.0f}.")
    if collections["priority_queue"]:
        top_collection = collections["priority_queue"][0]
        actions.append(f"Collect INR {top_collection['overdue_amount']:.0f} from {top_collection['customer_name']} ({top_collection['collection_priority']}).")
    if pending_orders:
        actions.append(f"Confirm/dispatch {len(pending_orders)} pending orders.")
    if stock["low_stock"]:
        actions.append(f"Review {len(stock['low_stock'])} low-stock SKUs.")
    if working_capital["risk_flags"]:
        actions.append(f"Review working capital risks; net working capital INR {working_capital['summary']['net_working_capital']:.0f}.")
    if pending_approvals:
        actions.append(f"Clear {len(pending_approvals)} pending approvals.")

    return {
        "language": language,
        "payments": payment,
        "collections": collections,
        "working_capital": working_capital,
        "orders": {"pending_count": len(pending_orders)},
        "stock": stock,
        "customers": {"inactive_count": 0, "reorder_opportunities": 0},
        "suppliers": {"followups_needed": 0},
        "staff_operations": {"open_tasks": 0},
        "top_actions": actions[:5],
        "pending_approvals": len(pending_approvals),
        "audit": {
            "scheduled_delivery_performed": False,
            "whatsapp_automation_performed": False,
            "limitation": "Local daily owner briefing only; no production scheduler or WhatsApp delivery automation was called.",
        },
    }
