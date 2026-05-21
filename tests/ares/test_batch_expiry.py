from __future__ import annotations

from datetime import date, timedelta

from apps.ares.ares.data.models import InventoryBatch, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.stock_batches import register_inventory_batch
from apps.ares.ares.workflows.stock_radar import run_stock_radar


def test_register_inventory_batch_updates_stock_record_totals() -> None:
    repo = InMemoryRepository()
    repo.upsert_stock_record(
        StockRecord(
            sku_id="sku_1",
            name="Parle G",
            current_stock=10,
            reorder_level=25,
            unit="box",
        )
    )

    batch = register_inventory_batch(
        repository=repo,
        sku_id="sku_1",
        batch_code="B-101",
        quantity=40,
        expiry_date=date.today() + timedelta(days=120),
        unit_cost=12.5,
    )

    assert batch.batch_code == "B-101"
    refreshed = repo.get_stock_records()[0]
    assert refreshed.current_stock == 50
    assert repo.get_inventory_batches()[0].unit_cost == 12.5


def test_stock_radar_surfaces_near_expiry_and_expired_batches() -> None:
    repo = InMemoryRepository()
    repo.upsert_stock_record(
        StockRecord(
            sku_id="sku_1",
            name="Parle G",
            current_stock=100,
            reorder_level=20,
            unit="box",
        )
    )
    today = date.today()
    register_inventory_batch(
        repository=repo,
        sku_id="sku_1",
        batch_code="EXP-SOON",
        quantity=15,
        expiry_date=today + timedelta(days=10),
    )
    register_inventory_batch(
        repository=repo,
        sku_id="sku_1",
        batch_code="EXPIRED",
        quantity=5,
        expiry_date=today - timedelta(days=2),
    )

    radar = run_stock_radar(repo, today=today)

    assert radar["near_expiry_batches"][0]["batch_code"] == "EXP-SOON"
    assert radar["near_expiry_batches"][0]["days_to_expiry"] == 10
    assert radar["expired_batches"][0]["batch_code"] == "EXPIRED"
    assert radar["expired_batches"][0]["days_past_expiry"] == 2


def test_stock_radar_groups_expiry_risk_by_sku() -> None:
    repo = InMemoryRepository()
    repo.upsert_stock_record(
        StockRecord(
            sku_id="sku_2",
            name="Bourbon",
            current_stock=20,
            reorder_level=10,
            unit="box",
        )
    )
    today = date.today()
    register_inventory_batch(
        repository=repo,
        sku_id="sku_2",
        batch_code="B-201",
        quantity=8,
        expiry_date=today + timedelta(days=14),
    )
    register_inventory_batch(
        repository=repo,
        sku_id="sku_2",
        batch_code="B-202",
        quantity=4,
        expiry_date=today + timedelta(days=5),
    )

    radar = run_stock_radar(repo, today=today)

    assert radar["sku_expiry_summary"][0]["sku_id"] == "sku_2"
    assert radar["sku_expiry_summary"][0]["expiring_quantity"] == 12
    assert radar["sku_expiry_summary"][0]["batch_count"] == 2
