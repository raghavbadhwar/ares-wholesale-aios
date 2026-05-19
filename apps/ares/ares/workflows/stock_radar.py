"""Stock radar workflow."""

from __future__ import annotations

from apps.ares.ares.data.repository import BusinessRepository


def run_stock_radar(repository: BusinessRepository) -> dict:
    low_stock = []
    fast_moving = []
    slow_moving = []
    for record in repository.get_stock_records():
        if record.current_stock <= record.reorder_level:
            low_stock.append(record)
        if record.sales_velocity is not None and record.sales_velocity >= max(record.reorder_level, 1):
            fast_moving.append(record)
        if record.sales_velocity == 0:
            slow_moving.append(record)

    return {
        "low_stock": [record.model_dump(mode="json") for record in low_stock],
        "reorder_suggestions": [
            {
                "sku_id": record.sku_id,
                "name": record.name,
                "suggested_quantity": max(record.reorder_level * 2 - record.current_stock, record.reorder_level),
                "unit": record.unit,
            }
            for record in low_stock
        ],
        "fast_moving": [record.model_dump(mode="json") for record in fast_moving],
        "slow_moving": [record.model_dump(mode="json") for record in slow_moving],
    }

