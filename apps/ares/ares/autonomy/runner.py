"""Autonomous Ares operator cycle."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.auto_ingest import process_local_inbox, validate_local_inputs
from apps.ares.ares.data.factory import create_repository_for_profile
from apps.ares.ares.face.owner_chat import render_owner_approval_prompt
from apps.ares.ares.memory.loop import run_memory_loop
from apps.ares.ares.profiles import load_client_profile
from apps.ares.ares.workflows.daily_brief import run_daily_brief
from apps.ares.ares.workflows.approval_center import list_pending
from apps.ares.ares.workflows.payment_radar import run_payment_radar


def run_autonomous_cycle(client_id: str) -> dict:
    """Run eyes + memory + draft-actions + owner-facing face summary."""
    profile = load_client_profile(client_id)
    repository = create_repository_for_profile(profile)
    approvals = ApprovalService(repository, required_actions=set(profile.approval_preferences.required_actions) or None)

    ingestion = process_local_inbox(client_id=profile.client_slug, repository=repository)
    memory = run_memory_loop(repository)
    payment_radar = run_payment_radar(repository, approvals, client_id=profile.client_slug)
    approval_center = list_pending(approvals)
    pending = approvals.list_pending_requests()
    owner_message = render_owner_approval_prompt(pending[0]) if pending else "No approvals pending. Ares cycle complete."
    return {
        "client_id": profile.client_slug,
        "ingestion": ingestion,
        "memory": memory,
        "payment_radar": payment_radar,
        "approval_center": approval_center,
        "owner_message": owner_message,
    }


def run_morning_run(client_id: str) -> dict:
    """Run the dashboard's morning command bundle for one client."""
    profile = load_client_profile(client_id)
    repository = create_repository_for_profile(profile)
    approvals = ApprovalService(repository, required_actions=set(profile.approval_preferences.required_actions) or None)

    validation = validate_local_inputs(client_id=profile.client_slug)
    ingestion = process_local_inbox(client_id=profile.client_slug, repository=repository)
    memory = run_memory_loop(repository)
    daily_brief = run_daily_brief(
        repository,
        approvals,
        client_id=profile.client_slug,
        language=profile.language_preference,
    )
    approval_center = list_pending(approvals)
    pending = approvals.list_pending_requests()
    owner_message = render_owner_approval_prompt(pending[0]) if pending else "No approvals pending. Morning run complete."

    return {
        "client_id": profile.client_slug,
        "validation": validation,
        "ingestion": ingestion,
        "memory": memory,
        "daily_brief": daily_brief,
        "approval_center": approval_center,
        "owner_message": owner_message,
    }
