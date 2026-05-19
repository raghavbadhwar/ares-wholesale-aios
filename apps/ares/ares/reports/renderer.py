"""Mobile-friendly report rendering for Ares workflows."""

from __future__ import annotations


def render_daily_brief(brief: dict) -> str:
    payments = brief["payments"]
    stock = brief["stock"]
    lines = [
        "🧠 Ares Brief — Aaj ka command center",
        "",
        "💰 Payments",
        f"• INR {payments['total_outstanding']:.0f} outstanding",
        f"• {payments['overdue_count']} overdue invoices",
        "",
        "📦 Orders",
        f"• {brief['orders']['pending_count']} pending orders",
        "",
        "🏬 Stock",
        f"• {len(stock['low_stock'])} items low stock",
        f"• {len(stock['fast_moving'])} fast-moving items flagged",
        "",
        "✅ Top actions",
    ]
    if brief["top_actions"]:
        lines.extend(f"{index}. {action}" for index, action in enumerate(brief["top_actions"], start=1))
    else:
        lines.append("1. No urgent action from current data.")
    lines.extend(["", f"🔐 Pending approvals: {brief['pending_approvals']}"])
    return "\n".join(lines)


def render_weekly_report(report: dict) -> str:
    lines = [
        "# Ares Weekly War Room",
        "",
        "## Sales",
        f"- Orders captured: {report['sales_summary']['orders']}",
        "",
        "## Collections",
        f"- Open invoices: {report['collections_summary']['open_invoices']}",
        f"- Payments recorded: {report['collections_summary']['payments_recorded']}",
        "",
        "## Stock Risks",
        f"- Low-stock SKUs: {len(report['stock_risks']['low_stock'])}",
        "",
        "## Next Week Priorities",
    ]
    lines.extend(f"- {item}" for item in report["next_week_priorities"])
    return "\n".join(lines)

