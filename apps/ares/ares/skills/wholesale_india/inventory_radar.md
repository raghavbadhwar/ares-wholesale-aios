# Inventory Radar Skill

Trigger when the owner asks about stock, low stock, reorder, fast-moving items, slow stock, or dead stock.

Inputs:
- Stock sheet/export.
- Product SKU list.
- Reorder levels.
- Supplier lead-time memory.
- Sales velocity when available.

Reasoning rules:
- Flag every SKU at or below reorder level.
- Suggest reorder quantity from reorder level and current stock.
- If velocity is missing, label the suggestion as stock-level based.
- Do not place purchase orders without approval.

Outputs:
- Low-stock list.
- Reorder suggestions.
- Fast-moving and slow/dead stock flags.

Edge cases:
- If units are inconsistent, ask the operator to normalize the product sheet.
- If stock file is stale, warn in the brief.

