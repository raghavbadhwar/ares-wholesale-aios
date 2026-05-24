"""JSON-backed persistent repository for Ares pilot clients."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from apps.ares.ares.data.models import (
    ActionExecutionLog,
    ApprovalRequest,
    BusinessMemory,
    Customer,
    Invoice,
    LedgerEntry,
    Order,
    Payment,
    ProductSKU,
    PurchaseInvoice,
    StockRecord,
    SupplierPayment,
    SupplierPaymentAllocation,
    TaxEvent,
    WorkflowRun,
)
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.hardening import append_client_audit_event, redact_action_log_record, redact_workflow_run_record

T = TypeVar("T", bound=BaseModel)


class JsonClientRepository(InMemoryRepository):
    """Persistent repository that mirrors each collection to a JSON file."""

    FILES = {
        "customers": ("customers.json", Customer),
        "products": ("products.json", ProductSKU),
        "orders": ("orders.json", Order),
        "invoices": ("invoices.json", Invoice),
        "payments": ("payments.json", Payment),
        "purchase_invoices": ("purchase_invoices.json", PurchaseInvoice),
        "supplier_payments": ("supplier_payments.json", SupplierPayment),
        "supplier_payment_allocations": ("supplier_payment_allocations.json", SupplierPaymentAllocation),
        "tax_events": ("tax_events.json", TaxEvent),
        "ledger_entries": ("ledger_entries.json", LedgerEntry),
        "stock_records": ("stock_records.json", StockRecord),
        "approvals": ("approvals.json", ApprovalRequest),
        "memories": ("memories.json", BusinessMemory),
        "workflow_runs": ("workflow_runs.json", WorkflowRun),
        "action_logs": ("action_logs.json", ActionExecutionLog),
    }

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_model_list(self, name: str, model: type[T]) -> list[T]:
        path = self.data_dir / name
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt Ares data file: {path}") from exc
        if not isinstance(data, list):
            raise ValueError(f"Ares data file must contain a list: {path}")
        return [model.model_validate(item) for item in data]

    def _write_model_list(self, name: str, items: list[BaseModel]) -> None:
        path = self.data_dir / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = [item.model_dump(mode="json") for item in items]
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def _load_all(self) -> None:
        for item in self._load_model_list("customers.json", Customer): self.customers[item.id] = item
        for item in self._load_model_list("products.json", ProductSKU): self.products[item.id] = item
        for item in self._load_model_list("orders.json", Order): self.orders[item.id] = item
        for item in self._load_model_list("invoices.json", Invoice): self.invoices[item.id] = item
        for item in self._load_model_list("payments.json", Payment): self.payments[item.id] = item
        for item in self._load_model_list("purchase_invoices.json", PurchaseInvoice): self.purchase_invoices[item.id] = item
        for item in self._load_model_list("supplier_payments.json", SupplierPayment): self.supplier_payments[item.id] = item
        for item in self._load_model_list("supplier_payment_allocations.json", SupplierPaymentAllocation): self.supplier_payment_allocations[item.id] = item
        for item in self._load_model_list("tax_events.json", TaxEvent): self.tax_events[item.id] = item
        for item in self._load_model_list("ledger_entries.json", LedgerEntry): self.ledger_entries[item.id] = item
        for item in self._load_model_list("stock_records.json", StockRecord): self.stock_records[item.sku_id] = item
        for item in self._load_model_list("approvals.json", ApprovalRequest): self.approvals[item.id] = item
        for item in self._load_model_list("memories.json", BusinessMemory): self.memories[item.id] = item
        for item in self._load_model_list("workflow_runs.json", WorkflowRun): self.workflow_runs[item.id] = item
        for item in self._load_model_list("action_logs.json", ActionExecutionLog): self.action_logs[item.id] = item

    def _flush(self, collection: str) -> None:
        values = list(getattr(self, collection).values())
        filename = self.FILES[collection][0]
        self._write_model_list(filename, values)

    def upsert_customer(self, customer: Customer) -> Customer:
        saved = super().upsert_customer(customer); self._flush("customers"); return saved
    def upsert_product(self, product: ProductSKU) -> ProductSKU:
        saved = super().upsert_product(product); self._flush("products"); return saved
    def create_order(self, order: Order) -> Order:
        saved = super().create_order(order); self._flush("orders"); return saved
    def update_order_status(self, order_id: str, status: str) -> Order:
        saved = super().update_order_status(order_id, status); self._flush("orders"); return saved
    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        saved = super().upsert_invoice(invoice); self._flush("invoices"); return saved
    def upsert_payment(self, payment: Payment) -> Payment:
        saved = super().upsert_payment(payment); self._flush("payments"); return saved
    def upsert_purchase_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        saved = super().upsert_purchase_invoice(invoice); self._flush("purchase_invoices"); self._flush("tax_events"); self._flush("ledger_entries"); return saved
    def upsert_supplier_payment(self, payment: SupplierPayment) -> SupplierPayment:
        saved = super().upsert_supplier_payment(payment); self._flush("supplier_payments"); self._flush("tax_events"); self._flush("ledger_entries"); return saved
    def upsert_supplier_payment_allocation(self, allocation: SupplierPaymentAllocation) -> SupplierPaymentAllocation:
        saved = super().upsert_supplier_payment_allocation(allocation); self._flush("supplier_payment_allocations"); self._flush("tax_events"); self._flush("ledger_entries"); return saved
    def upsert_tax_event(self, event: TaxEvent) -> TaxEvent:
        saved = super().upsert_tax_event(event); self._flush("tax_events"); self._flush("ledger_entries"); return saved
    def upsert_ledger_entry(self, entry: LedgerEntry) -> LedgerEntry:
        saved = super().upsert_ledger_entry(entry); self._flush("ledger_entries"); return saved
    def upsert_stock_record(self, record: StockRecord) -> StockRecord:
        saved = super().upsert_stock_record(record); self._flush("stock_records"); return saved
    def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = super().create_approval(approval); self._flush("approvals"); return saved
    def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = super().update_approval(approval); self._flush("approvals"); return saved
    def save_memory(self, memory: BusinessMemory) -> BusinessMemory:
        saved = super().save_memory(memory); self._flush("memories"); return saved
    def log_workflow_run(self, run: WorkflowRun) -> WorkflowRun:
        redacted = WorkflowRun.model_validate(redact_workflow_run_record(run.model_dump(mode="json")))
        saved = super().log_workflow_run(redacted); self._flush("workflow_runs")
        append_client_audit_event(saved.client_id, event_type="workflow_run", payload=saved.model_dump(mode="json"))
        return saved
    def save_action_log(self, log: ActionExecutionLog) -> ActionExecutionLog:
        redacted = ActionExecutionLog.model_validate(redact_action_log_record(log.model_dump(mode="json")))
        saved = super().save_action_log(redacted); self._flush("action_logs")
        append_client_audit_event(saved.client_id, event_type="action_log", payload=saved.model_dump(mode="json"))
        return saved
