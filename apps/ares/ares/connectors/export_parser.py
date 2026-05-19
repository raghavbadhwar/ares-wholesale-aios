"""CSV export parsers for Tally/Busy/Vyapar/Marg-style reports."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from uuid import uuid4

from apps.ares.ares.data.models import Invoice, StockRecord


class UnsupportedExportError(ValueError):
    pass


def _rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() != ".csv":
        raise UnsupportedExportError("MVP parser supports CSV exports; convert XLSX to CSV first.")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_outstanding_report(path: Path) -> list[Invoice]:
    invoices: list[Invoice] = []
    for row in _rows(path):
        amount = float(row.get("amount") or row.get("outstanding") or row.get("balance") or 0)
        if amount <= 0:
            continue
        invoice_no = row.get("invoice_number") or row.get("invoice") or f"INV-{uuid4().hex[:6]}"
        due = row.get("due_date") or ""
        invoices.append(
            Invoice(
                id=row.get("id") or f"inv_{uuid4().hex[:12]}",
                invoice_number=invoice_no,
                customer_id=row.get("customer_id") or row.get("customer") or None,
                amount=amount,
                due_date=date.fromisoformat(due) if due else None,
                status=row.get("status") or "open",
            )
        )
    return invoices


def parse_stock_report(path: Path) -> list[StockRecord]:
    records: list[StockRecord] = []
    for row in _rows(path):
        sku = row.get("sku_id") or row.get("sku") or row.get("product") or row.get("name")
        if not sku:
            continue
        records.append(
            StockRecord(
                sku_id=sku,
                name=row.get("name") or row.get("product") or sku,
                current_stock=float(row.get("current_stock") or row.get("stock") or 0),
                reorder_level=float(row.get("reorder_level") or row.get("min_stock") or 0),
                unit=row.get("unit") or "unit",
                supplier_id=row.get("supplier_id") or None,
            )
        )
    return records

