"""Local file/drop-folder ingestion for Ares pilot clients."""

from __future__ import annotations

from pathlib import Path

from apps.ares.ares.connectors.export_parser import UnsupportedExportError, parse_outstanding_report, parse_stock_report
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import IngestedEvent
from apps.ares.ares.data.repository import BusinessRepository


def ingest_export_file(path: Path, repository: BusinessRepository) -> dict:
    """Ingest a known CSV export into the repository.

    Filenames containing outstanding/receivable/payment are treated as invoices;
    filenames containing stock/inventory are treated as stock reports.
    """
    lowered = path.name.lower()
    if any(token in lowered for token in ["outstanding", "receivable", "payment", "invoice"]):
        invoices = parse_outstanding_report(path)
        for invoice in invoices:
            repository.upsert_invoice(invoice)
        return {"kind": "outstanding", "records": len(invoices), "path": str(path)}
    if any(token in lowered for token in ["stock", "inventory"]):
        records = parse_stock_report(path)
        for record in records:
            repository.upsert_stock_record(record)
        return {"kind": "stock", "records": len(records), "path": str(path)}
    raise UnsupportedExportError(f"Cannot infer export type from filename: {path.name}")


def ingest_message_file(path: Path, *, client_id: str, sender: str | None = None) -> IngestedEvent:
    event = ingest_forwarded_message(
        client_id=client_id,
        sender=sender or path.stem,
        message_text=path.read_text(encoding="utf-8"),
    )
    return event.model_copy(update={"metadata": {**event.metadata, "file_path": str(path)}})
