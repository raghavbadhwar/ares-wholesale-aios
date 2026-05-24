"""Operator shell summary for the Ares dashboard."""

from __future__ import annotations

from typing import Any

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.profiles import ClientProfile


def build_operator_shell(
    *,
    profile: ClientProfile,
    repository: BusinessRepository,
    approvals: ApprovalService,
) -> dict[str, Any]:
    """Build a compact operations snapshot from local client state."""
    invoices = repository.get_invoices()
    outstanding = repository.get_outstanding()
    stock_records = repository.get_stock_records()
    low_stock = [record for record in stock_records if record.current_stock <= record.reorder_level]
    orders = repository.list_orders()
    pending_orders = [order for order in orders if order.status == "pending"]
    pending_approvals = approvals.list_pending_requests()
    memories = repository.list_memories()
    action_logs = repository.list_action_logs()

    overdue = [
        invoice
        for invoice in outstanding
        if str(invoice.status).lower() == "overdue"
    ]

    metrics = {
        "pending_approvals": len(pending_approvals),
        "pending_orders": len(pending_orders),
        "overdue_invoices": len(overdue),
        "low_stock_skus": len(low_stock),
        "customers": len(repository.get_customers()),
        "invoices": len(invoices),
        "outstanding_invoices": len(outstanding),
        "stock_records": len(stock_records),
        "memories": len(memories),
        "action_logs": len(action_logs),
    }

    next_actions: list[str] = []
    if pending_approvals:
        next_actions.append(f"Review {len(pending_approvals)} pending approval(s).")
    if overdue:
        next_actions.append(f"Follow up {len(overdue)} overdue invoice(s).")
    if pending_orders:
        next_actions.append(f"Confirm or dispatch {len(pending_orders)} pending order(s).")
    if low_stock:
        next_actions.append(f"Review {len(low_stock)} low-stock SKU(s).")
    if not next_actions:
        next_actions.append("No urgent local actions found.")

    readiness = "active" if any(metrics.values()) else "needs_data"
    return {
        "client_id": profile.client_slug,
        "business_name": profile.business_name,
        "owner_name": profile.owner_name,
        "metrics": metrics,
        "readiness": readiness,
        "sections": [
            {"id": "approvals", "label": "Approvals", "count": len(pending_approvals)},
            {"id": "collections", "label": "Collections", "count": len(overdue)},
            {"id": "orders", "label": "Orders", "count": len(pending_orders)},
            {"id": "inventory", "label": "Inventory", "count": len(low_stock)},
        ],
        "next_actions": next_actions,
    }


def render_operator_shell(shell: dict[str, Any]) -> str:
    """Render the operator shell as a plain text status block."""
    metrics = shell.get("metrics") or {}
    lines = [
        f"Ares operator shell for {shell.get('business_name') or shell.get('client_id')}",
        f"Readiness: {shell.get('readiness', 'unknown')}",
        "",
        "Metrics:",
        f"- Pending approvals: {metrics.get('pending_approvals', 0)}",
        f"- Pending orders: {metrics.get('pending_orders', 0)}",
        f"- Overdue invoices: {metrics.get('overdue_invoices', 0)}",
        f"- Low-stock SKUs: {metrics.get('low_stock_skus', 0)}",
        "",
        "Next actions:",
    ]
    lines.extend(f"- {action}" for action in shell.get("next_actions") or [])
    return "\n".join(lines)
