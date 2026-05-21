from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from apps.ares.ares.agents.memory_agent import MemoryAgent
from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import PostDatedCheque
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.memory.loop import run_memory_loop
from apps.ares.ares.workflows.payment_radar import run_payment_radar
from apps.ares.ares.workflows.pdc_tracker import register_post_dated_cheque


def test_register_post_dated_cheque_persists_and_surfaces_due_soon_summary() -> None:
    today = date.today()
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    cheque = register_post_dated_cheque(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        party_id="Raj Traders",
        amount=45000,
        cheque_date=today + timedelta(days=2),
        bank_name="HDFC Bank",
        cheque_number="123456",
    )

    assert cheque.party_id == "Raj Traders"
    assert repo.get_post_dated_cheques()[0].bank_name == "HDFC Bank"

    radar = run_payment_radar(repo, approvals, client_id="demo", today=today)

    assert radar["pdc_summary"]["upcoming_count"] == 1
    assert radar["pdc_summary"]["upcoming_amount"] == 45000.0
    assert radar["pdc_summary"]["upcoming"][0]["party_id"] == "Raj Traders"
    assert any(item.type == "deposit_pdc_cheque" for item in repo.list_pending_approvals())


def test_memory_loop_saves_bounce_pattern_for_repeat_pdc_bounces(tmp_path: Path) -> None:
    today = date.today()
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_1",
            party_id="Raj Traders",
            amount=12000,
            cheque_date=today - timedelta(days=10),
            bank_name="HDFC Bank",
            cheque_number="111111",
            status="bounced",
        )
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_2",
            party_id="Raj Traders",
            amount=18000,
            cheque_date=today - timedelta(days=3),
            bank_name="HDFC Bank",
            cheque_number="222222",
            status="bounced",
        )
    )

    result = run_memory_loop(repo, today=today)

    assert result["memories_saved"] == 1
    memories = repo.list_memories()
    assert memories[0].category == "pdc_bounce_pattern"
    assert "bounced 2 times" in memories[0].content


def test_register_bounced_cheque_triggers_section_138_followup() -> None:
    today = date.today()
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    register_post_dated_cheque(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        party_id="Raj Traders",
        amount=22000,
        cheque_date=today - timedelta(days=1),
        bank_name="ICICI Bank",
        cheque_number="777777",
        status="bounced",
    )

    pending = repo.list_pending_approvals()
    assert any(item.type == "section_138_followup" for item in pending)
    assert any(item.data.get("cheque_number") == "777777" for item in pending)
