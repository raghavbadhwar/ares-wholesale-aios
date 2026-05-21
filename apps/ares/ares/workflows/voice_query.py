"""Local transcript-only voice query contract."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.orchestrator.router import route_text
from apps.ares.ares.reports.renderer import render_daily_brief, render_weekly_report
from apps.ares.ares.workflows.approval_center import list_pending
from apps.ares.ares.workflows.daily_brief import run_daily_brief
from apps.ares.ares.workflows.payment_radar import run_payment_radar
from apps.ares.ares.workflows.stock_radar import run_stock_radar
from apps.ares.ares.workflows.weekly_war_room import run_weekly_war_room

VOICE_QUERY_LIMITATION = (
    "Local voice-query contract only; no speech-to-text, IVR, telephony, or live voice integration was called."
)

_READ_ONLY_WORKFLOWS = {"daily-brief", "payment-radar", "stock-radar", "weekly-war-room", "approval-center"}


def handle_voice_query_transcript(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    transcript: str,
    requested_by: str,
    language: str = "english_hinglish",
    today: date | None = None,
) -> dict[str, Any]:
    """Route an already-transcribed local voice query and persist an audit log."""
    cleaned_transcript = transcript.strip()
    detected_workflow = route_text(cleaned_transcript)
    voice_query_id = f"voice_query_{uuid4().hex[:12]}"
    audit = {
        "requested_by": requested_by,
        "language": language,
        "speech_to_text_called": False,
        "ivr_called": False,
        "telephony_called": False,
        "approval_created": False,
        "limitation": VOICE_QUERY_LIMITATION,
    }

    if detected_workflow not in _READ_ONLY_WORKFLOWS:
        result = {
            "mode": "local_contract_mock",
            "voice_query_id": voice_query_id,
            "status": "needs_text_review",
            "transcript": cleaned_transcript,
            "detected_workflow": detected_workflow,
            "response_text": (
                "Voice transcript could not be mapped to a supported Ares workflow. "
                "Ask for a clearer text transcript."
            ),
            "payload": {},
            "audit": audit,
        }
        _save_audit_log(repository, client_id=client_id, result=result)
        return result

    payload, response_text = _run_read_only_workflow(
        repository=repository,
        approvals=approvals,
        client_id=client_id,
        workflow=detected_workflow,
        language=language,
        today=today,
    )
    result = {
        "mode": "local_contract_mock",
        "voice_query_id": voice_query_id,
        "status": "answered",
        "transcript": cleaned_transcript,
        "detected_workflow": detected_workflow,
        "response_text": response_text,
        "payload": payload,
        "audit": audit,
    }
    _save_audit_log(repository, client_id=client_id, result=result)
    return result


def _run_read_only_workflow(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    workflow: str,
    language: str,
    today: date | None,
) -> tuple[dict[str, Any], str]:
    if workflow == "payment-radar":
        payload = run_payment_radar(repository, approvals, client_id=client_id, today=today, create_approvals=False)
        return payload, _payment_message(payload)
    if workflow == "stock-radar":
        payload = run_stock_radar(repository, today=today)
        return payload, _stock_message(payload)
    if workflow == "daily-brief":
        payload = run_daily_brief(repository, approvals, client_id=client_id, language=language, today=today)
        return payload, render_daily_brief(payload)
    if workflow == "weekly-war-room":
        payload = run_weekly_war_room(repository)
        return payload, render_weekly_report(payload)
    payload = list_pending(approvals)
    return payload, payload["message"]


def _payment_message(payload: dict[str, Any]) -> str:
    return (
        f"Payment radar: INR {payload['total_outstanding']:.0f} outstanding, "
        f"{payload['overdue_count']} overdue invoices, "
        f"{payload.get('approvals_created', 0)} follow-ups drafted for approval."
    )


def _stock_message(payload: dict[str, Any]) -> str:
    return (
        f"Stock radar: {len(payload['low_stock'])} low-stock SKUs, "
        f"{len(payload['reorder_suggestions'])} reorder suggestions."
    )


def _save_audit_log(repository: BusinessRepository, *, client_id: str, result: dict[str, Any]) -> None:
    audit = result["audit"]
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=None,
            action_type="voice_query_transcript",
            status=result["status"],
            result={
                "voice_query_id": result["voice_query_id"],
                "transcript": result["transcript"],
                "detected_workflow": result["detected_workflow"],
                "response_text": result["response_text"],
                "speech_to_text_called": audit["speech_to_text_called"],
                "ivr_called": audit["ivr_called"],
                "telephony_called": audit["telephony_called"],
                "limitation": audit["limitation"],
            },
        )
    )
