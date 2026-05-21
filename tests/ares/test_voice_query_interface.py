from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.voice_query import VOICE_QUERY_LIMITATION, handle_voice_query_transcript


def test_should_route_voice_transcript_to_payment_radar_without_live_voice_stack() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                amount=12000,
                due_date=date(2026, 5, 1),
                status="overdue",
            )
        ]
    )
    approvals = ApprovalService(repo)

    result = handle_voice_query_transcript(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        transcript="Aaj ka payment batao",
        requested_by="owner",
        today=date(2026, 5, 21),
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "answered"
    assert result["detected_workflow"] == "payment-radar"
    assert result["transcript"] == "Aaj ka payment batao"
    assert result["response_text"] == "Payment radar: INR 12000 outstanding, 1 overdue invoices, 0 follow-ups drafted for approval."
    assert result["payload"]["overdue_count"] == 1
    assert result["payload"]["approvals_created"] == 0
    assert result["audit"] == {
        "requested_by": "owner",
        "language": "english_hinglish",
        "speech_to_text_called": False,
        "ivr_called": False,
        "telephony_called": False,
        "approval_created": False,
        "limitation": VOICE_QUERY_LIMITATION,
    }
    assert repo.list_pending_approvals() == []

    audit_log = repo.list_action_logs()[0]
    assert audit_log.action_type == "voice_query_transcript"
    assert audit_log.status == "answered"
    assert audit_log.result["transcript"] == "Aaj ka payment batao"
    assert audit_log.result["detected_workflow"] == "payment-radar"
    assert audit_log.result["speech_to_text_called"] is False


def test_should_audit_unmatched_voice_transcript_without_running_workflow() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    result = handle_voice_query_transcript(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        transcript="garbled audio",
        requested_by="salesman",
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "needs_text_review"
    assert result["detected_workflow"] == "fallback"
    assert result["payload"] == {}
    assert result["response_text"] == "Voice transcript could not be mapped to a supported Ares workflow. Ask for a clearer text transcript."
    assert result["audit"]["approval_created"] is False
    assert result["audit"]["limitation"] == VOICE_QUERY_LIMITATION
    assert repo.list_pending_approvals() == []

    audit_log = repo.list_action_logs()[0]
    assert audit_log.action_type == "voice_query_transcript"
    assert audit_log.status == "needs_text_review"
    assert audit_log.result["detected_workflow"] == "fallback"
