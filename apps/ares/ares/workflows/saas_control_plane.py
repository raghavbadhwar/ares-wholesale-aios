"""Local SaaS control-plane readiness contract."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.profiles import ClientProfile

LOCAL_SAAS_CONTROL_PLANE_LIMITATION = (
    "Local SaaS control-plane contract only; no hosted deployment, production auth, billing provider, "
    "subscription, or payment collection was created."
)


def prepare_saas_control_plane_readiness_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    profile: ClientProfile,
    requested_by: str,
    plan_tier: str,
    seat_limit: int,
    usage: dict[str, Any],
) -> dict[str, Any]:
    """Prepare a local readiness contract for hosted SaaS control-plane work."""
    active_users = int(usage.get("active_users", 0))
    active_clients = int(usage.get("active_clients", 1))
    usage_warnings = _usage_warnings(active_users=active_users, seat_limit=seat_limit)
    audit = _audit(requested_by=requested_by)
    result = {
        "mode": "local_contract_mock",
        "status": "needs_plan_review" if usage_warnings else "approval_required",
        "tenant": {
            "client_slug": profile.client_slug,
            "business_name": profile.business_name,
            "owner_name": profile.owner_name,
            "timezone": profile.timezone,
        },
        "plan": {
            "tier": plan_tier,
            "seat_limit": seat_limit,
            "active_users": active_users,
            "active_clients": active_clients,
        },
        "readiness": {
            "tenant_registry": "local_profile_only",
            "production_auth": "missing",
            "billing": "missing",
            "hosted_deployment": "missing",
            "plan_enforcement": "local_contract_only",
        },
        "usage_warnings": usage_warnings,
        "audit": audit,
    }
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_saas_control_plane_contract",
        proposed_action=f"Review SaaS control-plane contract for {profile.business_name}",
        data={**result, "mode": "local_contract_mock"},
        reason="Hosted SaaS, auth, and billing decisions affect tenant isolation, pricing, and customer access; owner/operator review is required.",
        source="saas_control_plane",
        confidence=0.8,
        risk_level=RiskLevel.high,
        dedupe_key=f"saas_control_plane:{client_id}:{plan_tier}:{uuid4().hex[:8]}",
    )
    result["approval_id"] = approval.id
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=approval.id,
            action_type="saas_control_plane_contract",
            status=result["status"],
            result={
                "tenant": result["tenant"],
                "plan": result["plan"],
                "usage_warnings": usage_warnings,
                "hosted_deployment_created": audit["hosted_deployment_created"],
                "production_auth_enabled": audit["production_auth_enabled"],
                "billing_provider_called": audit["billing_provider_called"],
                "limitation": audit["limitation"],
            },
        )
    )
    return result


def _usage_warnings(*, active_users: int, seat_limit: int) -> list[dict[str, int | str]]:
    if active_users > seat_limit:
        return [{"code": "seat_limit_exceeded", "active_users": active_users, "seat_limit": seat_limit}]
    return []


def _audit(*, requested_by: str) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": True,
        "hosted_deployment_created": False,
        "production_auth_enabled": False,
        "billing_provider_called": False,
        "subscription_created": False,
        "payment_collected": False,
        "limitation": LOCAL_SAAS_CONTROL_PLANE_LIMITATION,
    }
