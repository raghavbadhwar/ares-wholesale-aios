"""Natural-language router for the Ares owner-facing assistant."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.autonomy.runner import run_autonomous_cycle
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.reports.renderer import render_daily_brief, render_weekly_report
from apps.ares.ares.workflows.approval_center import list_pending
from apps.ares.ares.workflows.daily_brief import run_daily_brief
from apps.ares.ares.workflows.payment_radar import run_payment_radar
from apps.ares.ares.workflows.stock_radar import run_stock_radar
from apps.ares.ares.workflows.weekly_war_room import run_weekly_war_room


WORKFLOW_ALIASES = {
    "payment-radar": ("payment", "paise", "outstanding", "collection", "receivable"),
    "stock-radar": ("stock", "inventory", "low stock", "khatam"),
    "weekly-war-room": ("weekly", "war room", "report", "hafta"),
    "approval-center": ("approval", "approve", "pending approvals"),
    "daily-brief": ("daily", "brief", "aaj", "today", "subah"),
    "autonomous-cycle": ("autonomous", "auto cycle", "operator", "run yourself"),
}


def route_text(text: str) -> str:
    normalized = text.lower()
    for workflow, aliases in WORKFLOW_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return workflow
    return "fallback"


class AresRouter:
    def __init__(
        self,
        repository: BusinessRepository,
        approvals: ApprovalService,
        *,
        client_id: str,
        language: str = "english_hinglish",
    ) -> None:
        self.repository = repository
        self.approvals = approvals
        self.client_id = client_id
        self.language = language

    def handle(self, text: str) -> dict:
        workflow = route_text(text)
        return self.run_workflow(workflow)

    def run_workflow(self, workflow: str) -> dict:
        if workflow == "daily-brief":
            payload = run_daily_brief(
                self.repository,
                self.approvals,
                client_id=self.client_id,
                language=self.language,
            )
            return {"workflow": workflow, "payload": payload, "message": render_daily_brief(payload)}
        if workflow == "payment-radar":
            payload = run_payment_radar(self.repository, self.approvals, client_id=self.client_id)
            return {"workflow": workflow, "payload": payload, "message": _payment_message(payload)}
        if workflow == "stock-radar":
            payload = run_stock_radar(self.repository)
            return {"workflow": workflow, "payload": payload, "message": _stock_message(payload)}
        if workflow == "order-capture":
            orders = self.repository.list_orders()
            payload = {
                "orders_captured": len(orders),
                "pending_orders": len([order for order in orders if order.status == "pending"]),
            }
            return {
                "workflow": workflow,
                "payload": payload,
                "message": (
                    f"Order capture: {payload['orders_captured']} orders loaded, "
                    f"{payload['pending_orders']} pending."
                ),
            }
        if workflow == "weekly-war-room":
            payload = run_weekly_war_room(self.repository)
            return {"workflow": workflow, "payload": payload, "message": render_weekly_report(payload)}
        if workflow == "approval-center":
            payload = list_pending(self.approvals)
            return {"workflow": workflow, "payload": payload, "message": payload["message"]}
        if workflow == "autonomous-cycle":
            payload = run_autonomous_cycle(self.client_id)
            return {"workflow": workflow, "payload": payload, "message": payload["owner_message"]}
        return {
            "workflow": "fallback",
            "payload": {},
            "message": (
                "I can run daily brief, payment radar, stock radar, weekly report, "
                "or approval center. Share an export/file if data is missing."
            ),
        }


def _payment_message(payload: dict) -> str:
    return (
        f"Payment radar: INR {payload['total_outstanding']:.0f} outstanding, "
        f"{payload['overdue_count']} overdue invoices, "
        f"{len(payload['priorities'])} follow-ups drafted for approval."
    )


def _stock_message(payload: dict) -> str:
    return (
        f"Stock radar: {len(payload['low_stock'])} low-stock SKUs, "
        f"{len(payload['reorder_suggestions'])} reorder suggestions."
    )
