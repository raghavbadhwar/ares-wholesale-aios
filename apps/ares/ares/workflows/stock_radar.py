"""Stock radar workflow."""

from __future__ import annotations

from datetime import date
from collections import defaultdict

from apps.ares.ares.data.repository import BusinessRepository

NEAR_EXPIRY_WINDOW_DAYS = 30


def run_stock_radar(repository: BusinessRepository, *, today: date | None = None) -> dict:
    current_day = today or date.today()
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

    near_expiry_batches = []
    expired_batches = []
    expiry_summary: dict[str, dict[str, float | int | str]] = defaultdict(
        lambda: {"sku_id": "", "expiring_quantity": 0.0, "batch_count": 0}
    )
    for batch in repository.get_inventory_batches():
        if batch.expiry_date is None:
            continue
        days_to_expiry = (batch.expiry_date - current_day).days
        if days_to_expiry < 0:
            expired_batches.append(
                {
                    "batch_id": batch.id,
                    "sku_id": batch.sku_id,
                    "batch_code": batch.batch_code,
                    "quantity": batch.quantity,
                    "expiry_date": batch.expiry_date.isoformat(),
                    "days_past_expiry": abs(days_to_expiry),
                }
            )
            continue
        if days_to_expiry <= NEAR_EXPIRY_WINDOW_DAYS:
            near_expiry_batches.append(
                {
                    "batch_id": batch.id,
                    "sku_id": batch.sku_id,
                    "batch_code": batch.batch_code,
                    "quantity": batch.quantity,
                    "expiry_date": batch.expiry_date.isoformat(),
                    "days_to_expiry": days_to_expiry,
                }
            )
            summary = expiry_summary[batch.sku_id]
            summary["sku_id"] = batch.sku_id
            summary["expiring_quantity"] = float(summary["expiring_quantity"]) + batch.quantity
            summary["batch_count"] = int(summary["batch_count"]) + 1

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
        "near_expiry_batches": sorted(near_expiry_batches, key=lambda item: (item["days_to_expiry"], item["sku_id"])),
        "expired_batches": sorted(expired_batches, key=lambda item: (item["days_past_expiry"], item["sku_id"]), reverse=True),
        "sku_expiry_summary": sorted(expiry_summary.values(), key=lambda item: (int(item["batch_count"]) * -1, str(item["sku_id"]))),
    }
