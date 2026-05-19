# Payment Collection Skill

Trigger when the owner asks about payments, outstanding, receivables, overdue accounts, or collection priority.

Inputs:
- Outstanding invoices or ledger export.
- Payment promises and recent payment updates.
- Customer memory about payment behavior.
- Client credit rules.

Reasoning rules:
- Sort by amount, days overdue, risk, and customer importance.
- Draft reminders only; do not send them directly.
- Escalate low-confidence customer matches to approval.
- Use respectful Indian business tone with "ji" when useful.

Outputs:
- Collection priority list.
- Reminder drafts.
- Credit risk flags.
- Approval requests for any customer-facing message.

Edge cases:
- If due dates are missing, rank by amount and ask for updated export.
- If customer aliases conflict, request confirmation before ledger changes.

