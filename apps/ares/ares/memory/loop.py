"""Continuous memory loop for Ares."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from apps.ares.ares.agents.memory_agent import MemoryAgent
from apps.ares.ares.data.repository import BusinessRepository


def run_memory_loop(repository: BusinessRepository, *, today: date | None = None) -> dict:
    """Inspect current business state and save durable non-sensitive memories."""
    today = today or date.today()
    agent = MemoryAgent()
    existing_keys = {(memory.category, memory.subject_id, memory.content) for memory in repository.list_memories()}
    late_by_customer: dict[str, list[int]] = defaultdict(list)
    for invoice in repository.get_invoices():
        if invoice.customer_id and invoice.due_date and invoice.status in {"open", "overdue"}:
            late_days = max((today - invoice.due_date).days, 0)
            if late_days > 0:
                late_by_customer[invoice.customer_id].append(late_days)

    saved = 0
    for customer_id, late_days in late_by_customer.items():
        memory = agent.propose_from_payment_history(customer_id=customer_id, late_payment_days=late_days)
        if memory is None:
            continue
        key = (memory.category, memory.subject_id, memory.content)
        if key in existing_keys:
            continue
        repository.save_memory(memory)
        existing_keys.add(key)
        saved += 1
    return {"memories_saved": saved}
