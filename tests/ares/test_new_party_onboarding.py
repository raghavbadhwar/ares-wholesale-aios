from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.party_onboarding import prepare_new_party_onboarding


def test_should_prepare_approval_gated_new_party_onboarding_draft() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)

    result = prepare_new_party_onboarding(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        proposed_customer_id="cust_new",
        party={
            "name": "New Retail",
            "phone": "+919999999999",
            "gstin": "27ABCDE1234F1Z5",
            "location": "MH",
            "credit_limit": 25000,
            "documents": {
                "gst_certificate": True,
                "address_proof": True,
                "owner_id": True,
            },
        },
        requested_by="salesman",
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["draft_customer"] == {
        "id": "cust_new",
        "name": "New Retail",
        "phone": "+919999999999",
        "gstin": "27ABCDE1234F1Z5",
        "location": "MH",
        "credit_limit": 25000.0,
        "status": "pending_onboarding",
    }
    assert result["summary"] == {
        "validation_errors": 0,
        "documents_present": 3,
        "documents_missing": 0,
        "credit_limit": 25000.0,
    }
    assert result["audit"] == {
        "requested_by": "salesman",
        "approval_required": True,
        "external_gstn_validation_called": False,
        "digilocker_called": False,
        "credit_bureau_called": False,
        "limitation": "Local new-party onboarding review only; no GSTN, DigiLocker, or credit-bureau integration was called.",
    }
    assert repo.get_customers() == []
    assert repo.list_pending_approvals()[0].type == "onboard_new_party"


def test_should_block_duplicate_party_onboarding_without_approval() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_existing", name="Existing Retail", phone="+919999999999", gstin="27ABCDE1234F1Z5")]
    )

    result = prepare_new_party_onboarding(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        proposed_customer_id="cust_new",
        party={"name": "Existing Retail", "phone": "+919999999999", "gstin": "27ABCDE1234F1Z5", "location": "MH"},
        requested_by="salesman",
    )

    assert result["status"] == "needs_review"
    assert result["validation_errors"] == [
        {"code": "duplicate_gstin", "existing_customer_id": "cust_existing"},
        {"code": "duplicate_phone", "existing_customer_id": "cust_existing"},
        {"code": "missing_document", "document": "gst_certificate"},
        {"code": "missing_document", "document": "address_proof"},
        {"code": "missing_document", "document": "owner_id"},
    ]
    assert repo.list_pending_approvals() == []
