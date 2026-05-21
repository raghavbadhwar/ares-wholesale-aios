"""Memory agent for proposing durable business memories."""

from __future__ import annotations

from collections import Counter
from uuid import uuid4

from apps.ares.ares.data.models import BusinessMemory
from apps.ares.ares.memory.policies import MemoryCandidate, evaluate_memory_candidate


class MemoryAgent:
    """Small deterministic memory proposer for the concierge MVP."""

    def propose_from_payment_history(
        self,
        *,
        customer_id: str,
        late_payment_days: list[int],
        source: str = "payment_history",
    ) -> BusinessMemory | None:
        if len(late_payment_days) < 4:
            return None
        min_days = min(late_payment_days)
        max_days = max(late_payment_days)
        if min_days == max_days:
            pattern = f"{min_days} days late"
        else:
            pattern = f"{min_days}-{max_days} days late"
        candidate = MemoryCandidate(
            category="customer_payment_pattern",
            subject_id=customer_id,
            content=f"Customer usually pays {pattern}.",
            observations=len(late_payment_days),
            confidence=0.9,
            source=source,
        )
        decision = evaluate_memory_candidate(candidate)
        if not decision.save:
            return None
        return BusinessMemory(
            id=f"mem_{uuid4().hex[:12]}",
            category=candidate.category,
            subject_id=customer_id,
            content=candidate.content,
            confidence=candidate.confidence,
            source=source,
        )

    def propose_repeated_issue(
        self,
        *,
        subject_id: str,
        issue_labels: list[str],
        source: str = "operations_history",
    ) -> BusinessMemory | None:
        counts = Counter(label.strip().lower() for label in issue_labels if label.strip())
        if not counts:
            return None
        label, count = counts.most_common(1)[0]
        candidate = MemoryCandidate(
            category="repeated_issue",
            subject_id=subject_id,
            content=f"Repeated issue: {label}.",
            observations=count,
            confidence=0.8,
            source=source,
        )
        decision = evaluate_memory_candidate(candidate)
        if not decision.save:
            return None
        return BusinessMemory(
            id=f"mem_{uuid4().hex[:12]}",
            category=candidate.category,
            subject_id=subject_id,
            content=candidate.content,
            confidence=candidate.confidence,
            source=source,
        )

    def propose_from_pdc_bounces(
        self,
        *,
        party_id: str,
        bounce_count: int,
        source: str = "pdc_history",
    ) -> BusinessMemory | None:
        if bounce_count < 2:
            return None
        candidate = MemoryCandidate(
            category="pdc_bounce_pattern",
            subject_id=party_id,
            content=f"Party cheque discipline risk: bounced {bounce_count} times.",
            observations=bounce_count,
            confidence=0.9,
            source=source,
        )
        decision = evaluate_memory_candidate(candidate)
        if not decision.save:
            return None
        return BusinessMemory(
            id=f"mem_{uuid4().hex[:12]}",
            category=candidate.category,
            subject_id=party_id,
            content=candidate.content,
            confidence=candidate.confidence,
            source=source,
        )
