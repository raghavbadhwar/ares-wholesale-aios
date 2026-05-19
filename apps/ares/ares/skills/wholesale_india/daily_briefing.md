# Daily Briefing Skill

Trigger every morning or when the owner asks for today's business summary.

Inputs:
- Payment radar.
- Pending orders.
- Stock radar.
- Supplier/staff tasks.
- Pending approvals.

Reasoning rules:
- Lead with money, orders, stock, and top actions.
- Keep the output short enough for mobile chat.
- Use simple Indian English by default, and adapt to the client preference when configured.
- Avoid AI buzzwords and long explanations.

Outputs:
- Owner-ready daily brief.
- Top 3-5 actions.
- Pending approval count.

Edge cases:
- If a connector is missing, state the missing source and continue with available data.
- If there is no urgent action, say so plainly.

