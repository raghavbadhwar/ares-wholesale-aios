"""Local file/drop-folder ingestion for Ares pilot clients."""

from __future__ import annotations

from pathlib import Path

from apps.ares.ares.connectors.export_parser import UnsupportedExportError, parse_outstanding_report, parse_stock_report
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import IngestedEvent, StatutoryAdjustmentArtifact, StatutoryAdjustmentDocument, TaxAdjustment, TaxEvent
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


def ingest_structured_tax_adjustments(
    adjustments: list[dict],
    repository: BusinessRepository,
    *,
    source_reference: str,
    artifact_source: dict | None = None,
) -> dict:
    """Ingest local GST/GSP tax adjustment rows into the repository."""
    recorded = []
    adjustment_ids = []
    artifact_ids = []
    statutory_document_ids = []
    tax_event_ids = []
    for index, item in enumerate(adjustments, start=1):
        document_id = str(item.get("document_id") or item.get("purchase_invoice_id") or item.get("invoice_id") or f"tax_adjustment_{index}")
        document_number = str(item.get("document_number") or item.get("invoice_number") or document_id)
        document_type = str(item.get("document_type") or "invoice")
        action = str(item.get("action") or "amend")
        adjustment_id = str(item.get("id") or f"tax_adj_{document_id}_{index}")
        tax_event_id = f"tax_purchase_{document_id}" if document_type == "purchase_invoice" else f"tax_sales_{document_id}"
        event = TaxEvent(
            id=tax_event_id,
            event_type=str(item.get("event_type") or item.get("type") or "tax_adjustment"),
            source_type=str(item.get("source_type") or "gst_sandbox_adjustment"),
            source_id=str(item.get("source_id") or document_id),
            document_type=document_type,
            document_id=document_id,
            document_number=document_number,
            taxable_value=float(item.get("taxable_value") or 0),
            tax_amount=float(item.get("tax_amount") or 0),
            business_gstin_id=item.get("business_gstin_id"),
            status=str(item.get("status") or "posted"),
            metadata={
                "source_reference": source_reference,
                "artifact_source": artifact_source or {},
                **(item.get("metadata") or {}),
            },
        )
        repository.upsert_tax_event(event)
        repository.upsert_tax_adjustment(
            TaxAdjustment(
                id=adjustment_id,
                document_type=document_type,
                document_id=document_id,
                document_number=document_number,
                action=action,
                taxable_value=event.taxable_value,
                tax_amount=event.tax_amount,
                status=event.status,
                source_file=source_reference,
                metadata={"note": item.get("note"), "business_gstin_id": item.get("business_gstin_id")},
            )
        )
        artifact_id = f"artifact_{adjustment_id}"
        document_role = str(item.get("statutory_document_role") or ("credit_note" if action == "cancel" else "amendment_note"))
        repository.upsert_statutory_adjustment_artifact(
            StatutoryAdjustmentArtifact(
                id=artifact_id,
                adjustment_record_id=adjustment_id,
                provider=str((artifact_source or {}).get("provider") or "unknown"),
                source_kind=str((artifact_source or {}).get("source_kind") or "gst_sandbox_structured_ingest"),
                operation=(artifact_source or {}).get("operation"),
                source_file=source_reference,
                metadata=dict((artifact_source or {}).get("metadata") or {}),
            )
        )
        document_artifact_id = f"statdoc_{adjustment_id}"
        repository.upsert_statutory_adjustment_document(
            StatutoryAdjustmentDocument(
                id=document_artifact_id,
                adjustment_id=adjustment_id,
                document_role=document_role,
                document_id=document_id,
                metadata={"source_reference": source_reference},
            )
        )
        if document_type == "purchase_invoice" and document_id in getattr(repository, "purchase_invoices", {}):
            invoice = repository.purchase_invoices[document_id].model_copy(
                update={"taxable_value": event.taxable_value, "tax_amount": event.tax_amount}
            )
            repository.upsert_purchase_invoice(invoice)
        if document_type == "sales_invoice" and document_id in getattr(repository, "invoices", {}):
            invoice = repository.invoices[document_id].model_copy(update={"status": "cancelled" if action == "cancel" else repository.invoices[document_id].status})
            repository.upsert_invoice(invoice)
        recorded.append(event.model_dump(mode="json"))
        adjustment_ids.append(adjustment_id)
        artifact_ids.append(artifact_id)
        statutory_document_ids.append(document_artifact_id)
        tax_event_ids.append(tax_event_id)
    return {
        "status": "recorded",
        "records_ingested": len(recorded),
        "tax_events": recorded,
        "adjustment_ids": adjustment_ids,
        "artifact_ids": artifact_ids,
        "statutory_document_ids": statutory_document_ids,
        "tax_event_ids": tax_event_ids,
        "source_reference": source_reference,
        "audit": {
            "local_only": True,
            "live_tax_portal_called": False,
            "artifact_source": artifact_source or {},
        },
    }
