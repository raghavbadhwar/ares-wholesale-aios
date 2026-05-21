from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.profiles import ClientProfile
from apps.ares.ares.workflows.saas_control_plane import (
    LOCAL_SAAS_CONTROL_PLANE_LIMITATION,
    prepare_saas_control_plane_readiness_contract,
)


def test_should_prepare_local_saas_control_plane_readiness_contract_without_provisioning() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    profile = ClientProfile(client_slug="demo", business_name="Demo Distributors", owner_name="Owner")

    contract = prepare_saas_control_plane_readiness_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        profile=profile,
        requested_by="operator",
        plan_tier="pilot",
        seat_limit=3,
        usage={"active_users": 2, "active_clients": 1},
    )

    assert contract["mode"] == "local_contract_mock"
    assert contract["status"] == "approval_required"
    assert contract["tenant"]["client_slug"] == "demo"
    assert contract["plan"] == {"tier": "pilot", "seat_limit": 3, "active_users": 2, "active_clients": 1}
    assert contract["readiness"] == {
        "tenant_registry": "local_profile_only",
        "production_auth": "missing",
        "billing": "missing",
        "hosted_deployment": "missing",
        "plan_enforcement": "local_contract_only",
    }
    assert contract["audit"] == {
        "requested_by": "operator",
        "approval_required": True,
        "hosted_deployment_created": False,
        "production_auth_enabled": False,
        "billing_provider_called": False,
        "subscription_created": False,
        "payment_collected": False,
        "limitation": LOCAL_SAAS_CONTROL_PLANE_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "review_saas_control_plane_contract"
    assert repo.list_action_logs()[0].action_type == "saas_control_plane_contract"


def test_should_flag_local_plan_usage_over_limit_without_billing_enforcement() -> None:
    repo = InMemoryRepository()

    contract = prepare_saas_control_plane_readiness_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        profile=ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"),
        requested_by="operator",
        plan_tier="pilot",
        seat_limit=2,
        usage={"active_users": 4, "active_clients": 1},
    )

    assert contract["status"] == "needs_plan_review"
    assert contract["usage_warnings"] == [{"code": "seat_limit_exceeded", "active_users": 4, "seat_limit": 2}]
    assert contract["audit"]["billing_provider_called"] is False
    assert contract["audit"]["payment_collected"] is False
    assert contract["audit"]["limitation"] == LOCAL_SAAS_CONTROL_PLANE_LIMITATION
