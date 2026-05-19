from __future__ import annotations

from apps.ares.ares.agents.memory_agent import MemoryAgent
from apps.ares.ares.approvals.formatter import format_approval
from apps.ares.ares.approvals.service import ApprovalService, requires_approval
from apps.ares.ares.data.models import RiskLevel
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.memory.policies import MemoryCandidate, evaluate_memory_candidate


def test_sensitive_actions_require_approval() -> None:
    assert requires_approval("send_customer_message")
    assert requires_approval("mark_payment_received")
    assert not requires_approval("generate_report")
    assert requires_approval("generate_report", confidence=0.4)


def test_approval_service_lifecycle_and_formatter() -> None:
    repo = InMemoryRepository()
    service = ApprovalService(repo)

    approval = service.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send payment reminder",
        data={"customer": "Raj Traders"},
        reason="Invoice overdue",
        source="payment_radar",
        confidence=0.91,
        risk_level=RiskLevel.medium,
    )

    assert len(service.list_pending_requests()) == 1
    assert "Approve / Edit / Reject" in format_approval(approval)
    approved = service.approve_request(approval.id, decided_by="owner")
    assert approved.status == "approved"
    assert service.list_pending_requests() == []


def test_memory_policy_rejects_noise_and_accepts_patterns() -> None:
    noisy = MemoryCandidate(
        category="one_time_order",
        subject_id="cust_1",
        content="Ordered 10 boxes once.",
    )
    durable = MemoryCandidate(
        category="customer_payment_pattern",
        subject_id="cust_1",
        content="Usually pays late.",
        observations=4,
        confidence=0.9,
    )

    assert not evaluate_memory_candidate(noisy).save
    assert evaluate_memory_candidate(durable).save


def test_memory_agent_proposes_after_repeated_late_payments() -> None:
    agent = MemoryAgent()

    assert agent.propose_from_payment_history(customer_id="cust_1", late_payment_days=[8]) is None
    memory = agent.propose_from_payment_history(
        customer_id="cust_1",
        late_payment_days=[7, 8, 10, 9],
    )

    assert memory is not None
    assert memory.category == "customer_payment_pattern"
    assert "7-10 days late" in memory.content
