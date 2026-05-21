from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.gstn_api import GSTN_API_CONTRACT_LIMITATION, prepare_gstn_api_exchange_contract


def test_should_prepare_approval_gated_gstn_api_contract_without_live_filing() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    contract = prepare_gstn_api_exchange_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        operation="gstr1_return_upload",
        gstin="27ABCDE1234F1Z5",
        requested_by="accountant",
        payload={"period": "2026-05", "sections": {"b2b": 2, "b2cs": 1}},
    )

    assert contract["mode"] == "local_contract_mock"
    assert contract["status"] == "approval_required"
    assert contract["request"]["operation"] == "gstr1_return_upload"
    assert contract["request"]["endpoint_key"] == "gstn.gstr1.upload"
    assert contract["request"]["queue_policy"] == {
        "max_retries": 3,
        "retry_backoff": "manual_review_required",
        "fallback": "accountant_manual_portal_review",
    }
    assert contract["request"]["payload_digest"]["period"] == "2026-05"
    assert contract["audit"] == {
        "requested_by": "accountant",
        "approval_required": True,
        "gstn_api_called": False,
        "nic_api_called": False,
        "sandbox_credentials_used": False,
        "statutory_filing_performed": False,
        "limitation": GSTN_API_CONTRACT_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "submit_gstn_api_request"

    log = repo.list_action_logs()[0]
    assert log.action_type == "gstn_api_contract_prepared"
    assert log.status == "approval_required"
    assert log.result["operation"] == "gstr1_return_upload"
    assert log.result["gstn_api_called"] is False


def test_should_validate_gstn_api_contract_before_approval() -> None:
    repo = InMemoryRepository()

    contract = prepare_gstn_api_exchange_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        operation="gstr2b_pull",
        gstin="",
        requested_by="accountant",
        payload={},
    )

    assert contract["mode"] == "local_contract_mock"
    assert contract["status"] == "validation_failed"
    assert contract["validation_errors"] == [
        {"code": "gstin_missing"},
        {"code": "period_missing", "field": "payload.period"},
    ]
    assert contract["audit"]["gstn_api_called"] is False
    assert contract["audit"]["limitation"] == GSTN_API_CONTRACT_LIMITATION
    assert repo.list_pending_approvals() == []
    assert repo.list_action_logs()[0].status == "validation_failed"
