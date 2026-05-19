# Order Management Skill

Trigger when a forwarded message, email, sheet update, or owner command looks like a new order or dispatch request.

Inputs:
- Raw message text.
- Sender or chat/customer hint.
- Product aliases and recent orders.
- Delivery date hints.

Reasoning rules:
- Extract customer, item, quantity, unit, and delivery timing.
- Treat phrases like "same maal" as ambiguous unless recent context is available.
- Create pending orders from clear messages.
- Create approval/clarification requests for unclear products, quantities, or customers.

Outputs:
- Structured order draft.
- Confidence score.
- Missing fields.
- Approval request when needed.

Edge cases:
- Do not overwrite final dispatch status without approval.
- Do not invent product SKUs when the product list is missing.

