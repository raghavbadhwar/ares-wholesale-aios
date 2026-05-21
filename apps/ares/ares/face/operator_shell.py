"""Local operator shell for Ares benchmark surfaces."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.profiles import ClientProfile

LOCAL_OPERATOR_SHELL_LIMITATION = (
    "Local operator shell only; no hosted SaaS infrastructure, production auth, billing, "
    "or live external integration is provided."
)


def build_operator_shell(
    *,
    profile: ClientProfile,
    repository: BusinessRepository,
    approvals: ApprovalService,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Build a local command-center payload over implemented Ares surfaces."""
    current_day = as_of or date.today()
    return {
        "mode": "local_operator_shell",
        "as_of": current_day.isoformat(),
        "client": {
            "client_slug": profile.client_slug,
            "business_name": profile.business_name,
            "owner_name": profile.owner_name,
            "language_preference": profile.language_preference,
            "timezone": profile.timezone,
        },
        "interface_order": ["whatsapp_first", "mobile_second", "web_dashboard_third", "voice_accessibility_layer"],
        "metrics": _metrics(repository, approvals, current_day),
        "sections": _sections(profile.client_slug),
        "readiness": {
            "local_operator_shell": True,
            "hosted_saas": False,
            "production_auth": False,
            "billing": False,
            "live_external_integrations": False,
        },
        "next_actions": [
            f"ares morning-run --client {profile.client_slug}",
            f"ares mobile-approvals --client {profile.client_slug}",
            f"ares run-workflow --client {profile.client_slug} --workflow daily-brief",
        ],
        "audit": {
            "approval_first": True,
            "local_only": True,
            "limitation": LOCAL_OPERATOR_SHELL_LIMITATION,
        },
    }


def render_operator_shell(shell: dict[str, Any]) -> str:
    """Render the local operator shell in a compact terminal-friendly format."""
    client = shell["client"]
    metrics = shell["metrics"]
    lines = [
        f"Ares local operator shell for {client['business_name']}",
        f"Client: {client['client_slug']}",
        "",
        "Today",
        f"- Pending approvals: {metrics['pending_approvals']}",
        f"- Pending orders: {metrics['pending_orders']}",
        f"- Overdue invoices: {metrics['overdue_invoices']}",
        f"- Low-stock SKUs: {metrics['low_stock_skus']}",
        "",
        "Sections",
    ]
    for section in shell["sections"]:
        lines.append(f"- {section['label']}: {', '.join(tile['label'] for tile in section['tiles'])}")
    lines.extend(
        [
            "",
            "Readiness",
            "- Local operator shell: yes",
            "- Hosted SaaS/auth/billing/live integrations: no",
            "",
            shell["audit"]["limitation"],
        ]
    )
    return "\n".join(lines)


def _metrics(repository: BusinessRepository, approvals: ApprovalService, as_of: date) -> dict[str, int]:
    return {
        "pending_approvals": len(approvals.list_pending_requests()),
        "pending_orders": len([order for order in repository.list_orders() if order.status == "pending"]),
        "overdue_invoices": len(
            [
                invoice
                for invoice in repository.get_outstanding()
                if invoice.status.strip().lower() == "overdue" or (invoice.due_date is not None and invoice.due_date < as_of)
            ]
        ),
        "low_stock_skus": len([record for record in repository.get_stock_records() if record.current_stock <= record.reorder_level]),
        "action_logs": len(repository.list_action_logs()),
    }


def _sections(client_slug: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "command_center",
            "label": "Command Center",
            "tiles": [
                _tile("morning_run", "Morning Run", f"ares morning-run --client {client_slug}"),
                _tile("daily_brief", "Daily Brief", f"ares run-workflow --client {client_slug} --workflow daily-brief"),
                _tile("weekly_war_room", "Weekly War Room", f"ares run-workflow --client {client_slug} --workflow weekly-war-room"),
            ],
        },
        {
            "id": "owner_approvals",
            "label": "Owner Approvals",
            "tiles": [
                _tile("approval_center", "Approval Center", f"ares approval-center --client {client_slug}"),
                _tile("mobile_approvals", "Mobile Approvals", f"ares mobile-approvals --client {client_slug}"),
                _tile("mobile_reply", "Mobile Reply", f"ares mobile-reply --client {client_slug} --reply 'approve appr_xxx'"),
            ],
        },
        {
            "id": "collections",
            "label": "Udhaar & Collections",
            "tiles": [
                _tile("payment_radar", "Payment Radar", f"ares run-workflow --client {client_slug} --workflow payment-radar"),
                _tile("collections_dashboard", "Collections Dashboard", "local workflow: build_collections_dashboard"),
                _tile("payment_gateway_contract", "Payment Gateway Contract", "local workflow: payment_gateway"),
            ],
        },
        {
            "id": "inventory",
            "label": "Inventory",
            "tiles": [
                _tile("stock_radar", "Stock Radar", f"ares run-workflow --client {client_slug} --workflow stock-radar"),
                _tile("auto_reorder", "Auto-Reorder", "local workflow: prepare_auto_reorder_plan"),
                _tile("festive_demand", "Festive Demand", "local workflow: prepare_festive_demand_plan"),
            ],
        },
        {
            "id": "compliance",
            "label": "GST & Compliance",
            "tiles": [
                _tile("gstr1", "GSTR-1 Draft", f"ares prepare-gstr1 --client {client_slug} --period YYYY-MM --seller-gstin GSTIN"),
                _tile("itc", "ITC Reconciliation", "local workflow: reconcile_itc_2b"),
                _tile("gstn_contract", "GSTN API Contract", "local workflow: prepare_gstn_api_exchange_contract"),
            ],
        },
        {
            "id": "integrations",
            "label": "Integration Contracts",
            "tiles": [
                _tile("accounting_sync", "Tally / Busy", "local workflow: prepare_accounting_sync_export"),
                _tile("logistics", "Logistics", "local workflow: prepare_logistics_dispatch"),
                _tile("aa_ondc", "AA / ONDC", "local workflows: account_aggregator, ondc_seller"),
            ],
        },
    ]


def _tile(tile_id: str, label: str, command: str) -> dict[str, str]:
    return {
        "id": tile_id,
        "label": label,
        "command": command,
        "status": "local_ready",
    }
