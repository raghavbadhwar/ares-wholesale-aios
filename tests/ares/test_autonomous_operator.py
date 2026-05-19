from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.autonomy.runner import run_autonomous_cycle
from apps.ares.ares.connectors.auto_ingest import process_local_inbox
from apps.ares.ares.data.models import ApprovalStatus, Invoice
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.execution.actions import ActionExecutor, InMemoryMessageSender
from apps.ares.ares.face.owner_chat import handle_owner_reply, render_owner_approval_prompt
from apps.ares.ares.memory.loop import run_memory_loop
from apps.ares.ares.profiles import ClientProfile, write_client_profile
from apps.ares.ares.scheduling import build_cron_job_specs


def test_eyes_process_local_inbox_imports_exports_and_messages_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    root = tmp_path / ".ares" / "clients" / "demo"
    exports = root / "exports"
    inbox = root / "inbox"
    exports.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    (exports / "tally_outstanding.csv").write_text(
        "id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj,1000,overdue\n",
        encoding="utf-8",
    )
    (inbox / "raj_order.txt").write_text("Raj 2 dabba Maggi kal bhejna", encoding="utf-8")
    repo = JsonClientRepository(root / "data")

    first = process_local_inbox(client_id="demo", repository=repo)
    second = process_local_inbox(client_id="demo", repository=repo)

    assert first["exports_imported"] == 1
    assert first["orders_captured"] == 1
    assert second["exports_imported"] == 0
    assert second["orders_captured"] == 0
    assert repo.get_outstanding()[0].amount == 1000
    assert repo.list_orders()[0].items[0].name == "Maggi"


def test_hands_execute_approved_customer_message_and_audit(tmp_path: Path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    approvals = ApprovalService(repo)
    approval = approvals.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send reminder",
        data={"customer": "Raj", "draft": "Namaste Raj ji"},
        reason="test",
        source="test",
        confidence=0.9,
        dedupe_key="msg:1",
    )
    approvals.approve_request(approval.id, decided_by="owner")
    sender = InMemoryMessageSender()

    result = ActionExecutor(repo, message_sender=sender).execute_approved(approval.id)

    assert result.status == "executed"
    assert sender.sent_messages == [{"recipient": "Raj", "body": "Namaste Raj ji"}]
    assert JsonClientRepository(tmp_path / "data").list_action_logs()[0].approval_id == approval.id


def test_calendar_builds_autonomous_schedule_specs() -> None:
    specs = build_cron_job_specs(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))

    assert {spec.workflow for spec in specs} >= {"daily-brief", "payment-radar", "weekly-war-room", "autonomous-cycle"}
    assert any(spec.schedule == "0 9 * * *" for spec in specs)
    assert all("demo" in spec.prompt for spec in specs)


def test_memory_loop_saves_customer_payment_pattern(tmp_path: Path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    today = date.today()
    for idx, late_days in enumerate([7, 8, 9, 10], start=1):
        repo.upsert_invoice(
            Invoice(
                id=f"inv_{idx}",
                invoice_number=f"INV-{idx}",
                customer_id="Raj",
                amount=1000,
                due_date=today - timedelta(days=late_days),
                status="overdue",
            )
        )

    result = run_memory_loop(repo, today=today)

    assert result["memories_saved"] == 1
    assert "Raj" == repo.list_memories()[0].subject_id
    assert "7-10 days late" in repo.list_memories()[0].content


def test_face_owner_reply_approves_and_executes_message(tmp_path: Path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    approvals = ApprovalService(repo)
    approval = approvals.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send reminder",
        data={"customer": "Raj", "draft": "Please pay"},
        reason="test",
        source="test",
        confidence=0.9,
        dedupe_key="face:1",
    )
    sender = InMemoryMessageSender()
    prompt = render_owner_approval_prompt(approval)

    result = handle_owner_reply("approve", approvals=approvals, executor=ActionExecutor(repo, message_sender=sender), approval_id=approval.id, decided_by="owner")

    assert "Approve / Edit / Reject" in prompt
    assert result["decision"] == "approved"
    assert result["execution"]["status"] == "executed"
    assert sender.sent_messages[0]["body"] == "Please pay"


def test_autonomous_cycle_connects_eyes_memory_payment_and_face(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    root = tmp_path / ".ares" / "clients" / "demo"
    (root / "exports").mkdir(parents=True, exist_ok=True)
    (root / "exports" / "tally_outstanding.csv").write_text(
        "id,invoice_number,customer_id,amount,due_date,status\n"
        "inv_1,INV-1,Raj,1000,2026-01-01,overdue\n",
        encoding="utf-8",
    )

    result = run_autonomous_cycle("demo")

    assert result["ingestion"]["exports_imported"] == 1
    assert result["payment_radar"]["approvals_created"] == 1
    assert result["approval_center"]["count"] == 1
    assert "Approval needed" in result["owner_message"]
