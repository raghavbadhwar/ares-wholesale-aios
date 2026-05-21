"""Batch-aware inventory helpers."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from apps.ares.ares.data.models import InventoryBatch, StockRecord
from apps.ares.ares.data.repository import BusinessRepository


def register_inventory_batch(
    *,
    repository: BusinessRepository,
    sku_id: str,
    batch_code: str,
    quantity: float,
    expiry_date: date | None = None,
    unit_cost: float | None = None,
    received_at: date | None = None,
    notes: str | None = None,
) -> InventoryBatch:
    batch = InventoryBatch(
        id=f"batch_{uuid4().hex[:12]}",
        sku_id=sku_id,
        batch_code=batch_code,
        quantity=float(quantity),
        expiry_date=expiry_date,
        unit_cost=unit_cost,
        received_at=received_at,
        notes=notes,
    )
    repository.upsert_inventory_batch(batch)

    matching_record = next((record for record in repository.get_stock_records() if record.sku_id == sku_id), None)
    if matching_record is None:
        repository.upsert_stock_record(
            StockRecord(
                sku_id=sku_id,
                name=sku_id,
                current_stock=float(quantity),
                reorder_level=0,
            )
        )
    else:
        repository.upsert_stock_record(
            matching_record.model_copy(update={"current_stock": matching_record.current_stock + float(quantity)})
        )
    return batch
