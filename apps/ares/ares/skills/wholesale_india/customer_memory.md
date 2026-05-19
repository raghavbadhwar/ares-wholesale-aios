# Customer Memory Skill

Trigger when repeated customer behavior appears across orders, payments, complaints, or follow-ups.

Inputs:
- Payment history.
- Reorder history.
- Complaint history.
- Owner notes and business rules.

Reasoning rules:
- Save durable patterns, not one-off events.
- Prefer structured summaries over raw chat dumps.
- Ask approval before saving sensitive owner preferences or business rules.
- Update stale memories instead of accumulating contradictions.

Outputs:
- Memory suggestions.
- Duplicate/conflict warnings.
- Approved durable memory records.

Edge cases:
- A single late payment is not durable memory.
- Invoice-by-invoice status belongs in data, not memory.

