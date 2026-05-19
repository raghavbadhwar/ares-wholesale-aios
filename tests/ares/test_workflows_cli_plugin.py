from __future__ import annotations

from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.cli import main
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import Invoice, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.profiles import ClientProfile, write_client_profile
from apps.ares.ares.reports.renderer import render_daily_brief, render_weekly_report
from apps.ares.ares.skills.loader import load_vertical_skill_pack, load_workflow_skills
from apps.ares.ares.workflows.daily_brief import run_daily_brief
from apps.ares.ares.workflows.order_capture import capture_order
from apps.ares.ares.workflows.payment_match import match_payment
from apps.ares.ares.workflows.stock_radar import run_stock_radar
from apps.ares.ares.workflows.weekly_war_room import run_weekly_war_room
from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest


def _repo() -> InMemoryRepository:
    return InMemoryRepository.from_records(
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="Raj Traders",
                amount=50000,
                status="overdue",
            )
        ],
        stock_records=[StockRecord(sku_id="surf", name="Surf", current_stock=2, reorder_level=10)],
    )


def test_order_capture_creates_order_from_forwarded_text() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Raj Traders",
        message_text="Raj Traders 20 carton Surf kal bhejna",
    )

    order = capture_order(event, repo, approvals)

    assert order.items[0].quantity == 20
    assert order.items[0].unit == "carton"
    assert repo.list_pending_approvals() == []


def test_unclear_order_creates_approval_request() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(client_id="demo", sender="Raj", message_text="same maal bhej dena")

    order = capture_order(event, repo, approvals)

    assert order.confidence < 0.75
    assert len(repo.list_pending_approvals()) == 1


def test_payment_match_never_marks_final_without_approval() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    payment = match_payment(
        "Payment done INR 25000 UTR ABCD123456",
        client_id="demo",
        repository=repo,
        approvals=approvals,
        customer_hint="Raj Traders",
    )

    assert payment.status == "pending_approval"
    assert repo.list_pending_approvals()[0].type == "mark_payment_received"


def test_daily_and_weekly_reports_render() -> None:
    repo = _repo()
    approvals = ApprovalService(repo)

    daily = run_daily_brief(repo, approvals, client_id="demo")
    weekly = run_weekly_war_room(repo)

    assert "Ares Brief" in render_daily_brief(daily)
    assert "# Ares Weekly War Room" in render_weekly_report(weekly)


def test_stock_radar_flags_items_below_reorder_level() -> None:
    payload = run_stock_radar(_repo())

    assert payload["low_stock"][0]["sku_id"] == "surf"


def test_skill_loader_reads_vertical_and_workflow_skills() -> None:
    vertical = load_vertical_skill_pack("wholesale_india")
    workflow = load_workflow_skills("payment-radar")

    assert "payment_collection" in vertical
    assert "customer_memory" in workflow


def test_plugin_registers_cli_and_gateway_command() -> None:
    from plugins.ares import register

    manager = PluginManager()
    ctx = PluginContext(PluginManifest(name="ares"), manager)

    register(ctx)

    assert "ares" in manager._cli_commands
    assert manager._cli_commands["ares"]["handler_fn"].__name__ == "ares_command"
    assert "ares" in manager._plugin_commands


def test_cli_setup_creates_profile_and_prints_next_steps(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "setup",
            "--client",
            "demo",
            "--business-name",
            "Demo Wholesale",
            "--owner-name",
            "Owner",
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out
    assert "Ares setup complete" in output
    assert "ares autonomous-cycle --client demo" in output
    assert (tmp_path / ".ares" / "clients" / "demo" / "profile.yaml").exists()


def test_cli_run_workflow_from_sample_profile(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(
        ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner")
    )
    outstanding = tmp_path / "outstanding.csv"
    outstanding.write_text(
        "id,invoice_number,customer_id,amount,status\n"
        "inv_1,INV-1,Raj Traders,10000,overdue\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "run-workflow",
            "--client",
            "demo",
            "--workflow",
            "daily-brief",
            "--outstanding-csv",
            str(outstanding),
        ],
    )

    assert main() == 0
    assert "Ares Brief" in capsys.readouterr().out

