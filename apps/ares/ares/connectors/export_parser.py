"""CSV export parsers for Tally/Busy/Vyapar/Marg-style reports."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from uuid import uuid4

from apps.ares.ares.data.models import Invoice, StockRecord


class UnsupportedExportError(ValueError):
    pass


OUTSTANDING_COLUMN_ALIASES = {
    "amount": ("amount", "outstanding", "balance"),
    "customer": ("customer_id", "customer"),
    "invoice": ("invoice_number", "invoice", "id"),
    "due_date": ("due_date",),
    "status": ("status",),
}

STOCK_COLUMN_ALIASES = {
    "sku": ("sku_id", "sku", "product", "name"),
    "current_stock": ("current_stock", "stock"),
    "reorder_level": ("reorder_level", "min_stock"),
    "name": ("name", "product"),
    "unit": ("unit",),
    "supplier": ("supplier_id",),
}


def _rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() != ".csv":
        raise UnsupportedExportError("MVP parser supports CSV exports; convert XLSX to CSV first.")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = tuple(reader.fieldnames or ())
        if not headers:
            raise UnsupportedExportError(f"CSV file has no header row: {path.name}")
        return list(reader)


def _headers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return {header.strip() for header in (reader.fieldnames or []) if header and header.strip()}


def _require_columns(kind: str, headers: set[str], aliases: dict[str, tuple[str, ...]], required: tuple[str, ...]) -> None:
    missing = [field for field in required if not any(alias in headers for alias in aliases[field])]
    if missing:
        details = ", ".join(f"{field} ({'/'.join(aliases[field])})" for field in missing)
        raise UnsupportedExportError(f"Missing required columns for {kind} export: {details}")


def _pick(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def outstanding_export_contract() -> dict:
    return {
        "kind": "outstanding",
        "required": {
            "customer": list(OUTSTANDING_COLUMN_ALIASES["customer"]),
            "amount": list(OUTSTANDING_COLUMN_ALIASES["amount"]),
        },
        "optional": {
            "invoice": list(OUTSTANDING_COLUMN_ALIASES["invoice"]),
            "due_date": list(OUTSTANDING_COLUMN_ALIASES["due_date"]),
            "status": list(OUTSTANDING_COLUMN_ALIASES["status"]),
        },
    }


def stock_export_contract() -> dict:
    return {
        "kind": "stock",
        "required": {
            "sku": list(STOCK_COLUMN_ALIASES["sku"]),
            "current_stock": list(STOCK_COLUMN_ALIASES["current_stock"]),
        },
        "optional": {
            "reorder_level": list(STOCK_COLUMN_ALIASES["reorder_level"]),
            "name": list(STOCK_COLUMN_ALIASES["name"]),
            "unit": list(STOCK_COLUMN_ALIASES["unit"]),
            "supplier": list(STOCK_COLUMN_ALIASES["supplier"]),
        },
    }


def validate_outstanding_report(path: Path) -> dict:
    headers = _headers(path)
    _require_columns("outstanding", headers, OUTSTANDING_COLUMN_ALIASES, ("customer", "amount"))
    invoices = parse_outstanding_report(path)
    return {"kind": "outstanding", "headers": sorted(headers), "rows": len(invoices)}


def validate_stock_report(path: Path) -> dict:
    headers = _headers(path)
    _require_columns("stock", headers, STOCK_COLUMN_ALIASES, ("sku", "current_stock"))
    records = parse_stock_report(path)
    return {"kind": "stock", "headers": sorted(headers), "rows": len(records)}


def parse_outstanding_report(path: Path) -> list[Invoice]:
    headers = _headers(path)
    _require_columns("outstanding", headers, OUTSTANDING_COLUMN_ALIASES, ("customer", "amount"))

    invoices: list[Invoice] = []
    for row in _rows(path):
        amount_raw = _pick(row, *OUTSTANDING_COLUMN_ALIASES["amount"])
        amount = float(amount_raw or 0)
        if amount <= 0:
            continue
        invoice_no = _pick(row, *OUTSTANDING_COLUMN_ALIASES["invoice"]) or f"INV-{uuid4().hex[:6]}"
        due = _pick(row, *OUTSTANDING_COLUMN_ALIASES["due_date"])
        invoices.append(
            Invoice(
                id=_pick(row, "id") or f"inv_{uuid4().hex[:12]}",
                invoice_number=invoice_no,
                customer_id=_pick(row, *OUTSTANDING_COLUMN_ALIASES["customer"]) or None,
                amount=amount,
                due_date=date.fromisoformat(due) if due else None,
                status=_pick(row, *OUTSTANDING_COLUMN_ALIASES["status"]) or "open",
            )
        )
    if not invoices:
        raise UnsupportedExportError(f"No valid outstanding rows found in {path.name}")
    return invoices


def parse_stock_report(path: Path) -> list[StockRecord]:
    headers = _headers(path)
    _require_columns("stock", headers, STOCK_COLUMN_ALIASES, ("sku", "current_stock"))

    records: list[StockRecord] = []
    for row in _rows(path):
        sku = _pick(row, *STOCK_COLUMN_ALIASES["sku"])
        current_stock_raw = _pick(row, *STOCK_COLUMN_ALIASES["current_stock"])
        if not sku or current_stock_raw == "":
            continue
        records.append(
            StockRecord(
                sku_id=sku,
                name=_pick(row, *STOCK_COLUMN_ALIASES["name"]) or sku,
                current_stock=float(current_stock_raw or 0),
                reorder_level=float(_pick(row, *STOCK_COLUMN_ALIASES["reorder_level"]) or 0),
                unit=_pick(row, *STOCK_COLUMN_ALIASES["unit"]) or "unit",
                supplier_id=_pick(row, *STOCK_COLUMN_ALIASES["supplier"]) or None,
            )
        )
    if not records:
        raise UnsupportedExportError(f"No valid stock rows found in {path.name}")
    return records
