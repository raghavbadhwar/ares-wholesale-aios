"""Repository abstraction for Ares business data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from apps.ares.ares.data.models import (
    ActionExecutionLog,
    ApprovalRequest,
    ApprovalStatus,
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
    StatutoryAdjustmentArtifact,
    StatutoryAdjustmentDocument,
    TaxEvent,
    TaxAdjustment,
    WorkflowRun,
)


class BusinessRepository(ABC):
    @abstractmethod
    def get_customers(self) -> list[Customer]: ...

    @abstractmethod
    def upsert_customer(self, customer: Customer) -> Customer: ...

    @abstractmethod
    def get_products(self) -> list[ProductSKU]: ...

    @abstractmethod
    def upsert_product(self, product: ProductSKU) -> ProductSKU: ...

    @abstractmethod
    def create_order(self, order: Order) -> Order: ...

    @abstractmethod
    def list_orders(self, *, status: str | None = None) -> list[Order]: ...

    @abstractmethod
    def update_order_status(self, order_id: str, status: str) -> Order: ...

    @abstractmethod
    def get_invoices(self) -> list[Invoice]: ...

    @abstractmethod
    def upsert_invoice(self, invoice: Invoice) -> Invoice: ...

    @abstractmethod
    def get_payments(self) -> list[Payment]: ...

    @abstractmethod
    def upsert_payment(self, payment: Payment) -> Payment: ...

    @abstractmethod
    def get_stock_records(self) -> list[StockRecord]: ...

    @abstractmethod
    def upsert_stock_record(self, record: StockRecord) -> StockRecord: ...

    @abstractmethod
    def get_outstanding(self) -> list[Invoice]: ...

    @abstractmethod
    def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest: ...

    @abstractmethod
    def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest: ...

    @abstractmethod
    def list_pending_approvals(self) -> list[ApprovalRequest]: ...

    @abstractmethod
    def list_approvals(self) -> list[ApprovalRequest]: ...

    def find_approval(self, approval_id: str) -> ApprovalRequest | None:
        for approval in self.list_approvals():
            if approval.id == approval_id:
                return approval
        return None

    def find_pending_approval(self, *, client_id: str, action_type: str, dedupe_key: str) -> ApprovalRequest | None:
        for approval in self.list_pending_approvals():
            if approval.client_id == client_id and approval.type == action_type and approval.dedupe_key == dedupe_key:
                return approval
        return None

    @abstractmethod
    def save_memory(self, memory: BusinessMemory) -> BusinessMemory: ...

    @abstractmethod
    def list_memories(self) -> list[BusinessMemory]: ...

    @abstractmethod
    def log_workflow_run(self, run: WorkflowRun) -> WorkflowRun: ...

    @abstractmethod
    def save_action_log(self, log: ActionExecutionLog) -> ActionExecutionLog: ...

    @abstractmethod
    def list_action_logs(self) -> list[ActionExecutionLog]: ...


class InMemoryRepository(BusinessRepository):
    """Deterministic repository for tests, demos, and concierge dry runs."""

    def __init__(self) -> None:
        self.customers: dict[str, Customer] = {}
        self.products: dict[str, ProductSKU] = {}
        self.orders: dict[str, Order] = {}
        self.invoices: dict[str, Invoice] = {}
        self.payments: dict[str, Payment] = {}
        self.purchase_invoices: dict[str, PurchaseInvoice] = {}
        self.supplier_payments: dict[str, SupplierPayment] = {}
        self.supplier_payment_allocations: dict[str, SupplierPaymentAllocation] = {}
        self.tax_events: dict[str, TaxEvent] = {}
        self.tax_adjustments: dict[str, TaxAdjustment] = {}
        self.statutory_adjustment_artifacts: dict[str, StatutoryAdjustmentArtifact] = {}
        self.statutory_adjustment_documents: dict[str, StatutoryAdjustmentDocument] = {}
        self.ledger_entries: dict[str, LedgerEntry] = {}
        self.stock_records: dict[str, StockRecord] = {}
        self.approvals: dict[str, ApprovalRequest] = {}
        self.memories: dict[str, BusinessMemory] = {}
        self.workflow_runs: dict[str, WorkflowRun] = {}
        self.action_logs: dict[str, ActionExecutionLog] = {}
        self.metadata: dict[str, dict] = defaultdict(dict)

    @classmethod
    def from_records(
        cls,
        *,
        customers: Iterable[Customer] = (),
        products: Iterable[ProductSKU] = (),
        invoices: Iterable[Invoice] = (),
        stock_records: Iterable[StockRecord] = (),
        payments: Iterable[Payment] = (),
        purchase_invoices: Iterable[PurchaseInvoice] = (),
        supplier_payments: Iterable[SupplierPayment] = (),
        supplier_payment_allocations: Iterable[SupplierPaymentAllocation] = (),
        tax_events: Iterable[TaxEvent] = (),
        ledger_entries: Iterable[LedgerEntry] = (),
    ) -> "InMemoryRepository":
        repo = cls()
        for customer in customers:
            repo.upsert_customer(customer)
        for product in products:
            repo.upsert_product(product)
        for invoice in invoices:
            repo.upsert_invoice(invoice)
        for record in stock_records:
            repo.upsert_stock_record(record)
        for payment in payments:
            repo.upsert_payment(payment)
        for invoice in purchase_invoices:
            repo.upsert_purchase_invoice(invoice)
        for payment in supplier_payments:
            repo.upsert_supplier_payment(payment)
        for allocation in supplier_payment_allocations:
            repo.upsert_supplier_payment_allocation(allocation)
        for event in tax_events:
            repo.upsert_tax_event(event)
        for entry in ledger_entries:
            repo.upsert_ledger_entry(entry)
        return repo

    def get_customers(self) -> list[Customer]:
        return list(self.customers.values())

    def upsert_customer(self, customer: Customer) -> Customer:
        self.customers[customer.id] = customer
        return customer

    def get_products(self) -> list[ProductSKU]:
        return list(self.products.values())

    def upsert_product(self, product: ProductSKU) -> ProductSKU:
        self.products[product.id] = product
        return product

    def create_order(self, order: Order) -> Order:
        self.orders[order.id] = order
        return order

    def list_orders(self, *, status: str | None = None) -> list[Order]:
        orders = list(self.orders.values())
        if status:
            return [order for order in orders if order.status == status]
        return orders

    def update_order_status(self, order_id: str, status: str) -> Order:
        order = self.orders[order_id]
        updated = order.model_copy(update={"status": status, "updated_at": datetime.now(order.updated_at.tzinfo)})
        self.orders[order_id] = updated
        return updated

    def get_invoices(self) -> list[Invoice]:
        return list(self.invoices.values())

    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        self.invoices[invoice.id] = invoice
        return invoice

    def get_payments(self) -> list[Payment]:
        return list(self.payments.values())

    def upsert_payment(self, payment: Payment) -> Payment:
        if payment.external_event_id:
            existing = self.find_payment_by_external_event_id(payment.external_event_id)
            if existing is not None:
                return existing
        self.payments[payment.id] = payment
        return payment

    def find_payment_by_external_event_id(self, external_event_id: str) -> Payment | None:
        for payment in self.payments.values():
            if payment.external_event_id == external_event_id:
                return payment
        return None

    def effective_invoice_projection(self, invoice: Invoice) -> dict:
        paid = sum(payment.amount for payment in self.payments.values() if payment.matched_invoice_id == invoice.id and payment.status in {"reconciled", "paid"})
        amount = float(invoice.total_amount or invoice.amount or 0)
        if paid >= amount and amount > 0:
            status = "paid"
        elif paid > 0:
            status = "partially_paid"
        else:
            status = invoice.status
        return {**invoice.model_dump(mode="json"), "status": status, "paid_amount": paid}

    def get_purchase_invoices(self) -> list[PurchaseInvoice]:
        return list(self.purchase_invoices.values())

    def upsert_purchase_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        self.purchase_invoices[invoice.id] = invoice
        self._refresh_purchase_invoice_contract(invoice.id)
        return invoice

    def get_supplier_payments(self) -> list[SupplierPayment]:
        return list(self.supplier_payments.values())

    def upsert_supplier_payment(self, payment: SupplierPayment) -> SupplierPayment:
        if payment.external_event_id:
            existing = self.find_supplier_payment_by_external_event_id(payment.external_event_id)
            if existing is not None:
                return existing
        self.supplier_payments[payment.id] = payment
        if payment.matched_purchase_invoice_id:
            self._refresh_purchase_invoice_contract(payment.matched_purchase_invoice_id)
        return payment

    def find_supplier_payment_by_external_event_id(self, external_event_id: str) -> SupplierPayment | None:
        for payment in self.supplier_payments.values():
            if payment.external_event_id == external_event_id:
                return payment
        return None

    def get_supplier_payment_allocations(self) -> list[SupplierPaymentAllocation]:
        return list(self.supplier_payment_allocations.values())

    def upsert_supplier_payment_allocation(self, allocation: SupplierPaymentAllocation) -> SupplierPaymentAllocation:
        self.supplier_payment_allocations[allocation.id] = allocation
        self._refresh_purchase_invoice_contract(allocation.purchase_invoice_id)
        return allocation

    def get_tax_events(self) -> list[TaxEvent]:
        return list(self.tax_events.values())

    def upsert_tax_event(self, event: TaxEvent) -> TaxEvent:
        self.tax_events[event.id] = event
        if event.source_type == "purchase_invoice":
            self._refresh_purchase_invoice_contract(event.source_id)
        return self.tax_events[event.id]

    def get_tax_adjustments(self) -> list[TaxAdjustment]:
        return list(self.tax_adjustments.values())

    def upsert_tax_adjustment(self, adjustment: TaxAdjustment) -> TaxAdjustment:
        self.tax_adjustments[adjustment.id] = adjustment
        return adjustment

    def get_statutory_adjustment_artifacts(self) -> list[StatutoryAdjustmentArtifact]:
        return list(self.statutory_adjustment_artifacts.values())

    def upsert_statutory_adjustment_artifact(self, artifact: StatutoryAdjustmentArtifact) -> StatutoryAdjustmentArtifact:
        self.statutory_adjustment_artifacts[artifact.id] = artifact
        return artifact

    def get_statutory_adjustment_documents(self) -> list[StatutoryAdjustmentDocument]:
        return list(self.statutory_adjustment_documents.values())

    def upsert_statutory_adjustment_document(self, document: StatutoryAdjustmentDocument) -> StatutoryAdjustmentDocument:
        self.statutory_adjustment_documents[document.id] = document
        return document

    def get_ledger_entries(self) -> list[LedgerEntry]:
        return sorted(
            self.ledger_entries.values(),
            key=lambda entry: (entry.entry_type.startswith("purchase_invoice"), entry.id),
        )

    def upsert_ledger_entry(self, entry: LedgerEntry) -> LedgerEntry:
        self.ledger_entries[entry.id] = entry
        return entry

    def effective_purchase_invoice_projection(self, invoice: PurchaseInvoice) -> dict:
        paid = sum(
            allocation.amount
            for allocation in self.supplier_payment_allocations.values()
            if allocation.purchase_invoice_id == invoice.id and allocation.status == "posted"
        )
        tax_event = self.tax_events.get(f"tax_purchase_{invoice.id}")
        if tax_event is not None:
            total = float(tax_event.taxable_value or 0) + float(tax_event.tax_amount or 0)
        else:
            total = float(invoice.taxable_value or 0) + float(invoice.tax_amount or 0)
        if paid >= total and total > 0:
            status = "paid"
        elif paid > 0:
            status = "partially_paid"
        elif invoice.status == "open":
            status = "booked"
        else:
            status = invoice.status
        return {**invoice.model_dump(mode="json"), "status": status, "paid_amount": paid}

    def _refresh_purchase_invoice_contract(self, purchase_invoice_id: str) -> None:
        invoice = self.purchase_invoices.get(purchase_invoice_id)
        if invoice is None:
            return
        projection = self.effective_purchase_invoice_projection(invoice)
        metadata = {
            "invoice_status": projection["status"],
            "raw_invoice_status": invoice.status,
        }
        tax_id = f"tax_purchase_{invoice.id}"
        existing_tax = self.tax_events.get(tax_id)
        self.tax_events[tax_id] = TaxEvent(
            id=tax_id,
            event_type=(existing_tax.event_type if existing_tax else "purchase_input_tax"),
            source_type="purchase_invoice",
            source_id=invoice.id,
            document_type="purchase_invoice",
            document_id=invoice.id,
            document_number=invoice.invoice_number,
            event_date=(existing_tax.event_date if existing_tax else invoice.date),
            taxable_value=(existing_tax.taxable_value if existing_tax else invoice.taxable_value),
            tax_amount=(existing_tax.tax_amount if existing_tax else invoice.tax_amount),
            business_gstin_id=(existing_tax.business_gstin_id if existing_tax else invoice.business_gstin_id),
            status=(existing_tax.status if existing_tax else "posted"),
            metadata=metadata,
        )
        ledger_id = f"led_purchase_{invoice.id}_base"
        existing_ledger = self.ledger_entries.get(ledger_id)
        self.ledger_entries[ledger_id] = LedgerEntry(
            id=ledger_id,
            entry_type=(existing_ledger.entry_type if existing_ledger else "purchase_invoice_base"),
            source_type="purchase_invoice",
            source_id=invoice.id,
            amount=self.tax_events[tax_id].taxable_value,
            debit_account=(existing_ledger.debit_account if existing_ledger else "Purchase"),
            credit_account=(existing_ledger.credit_account if existing_ledger else "Accounts Payable"),
            status=(existing_ledger.status if existing_ledger else "posted"),
            metadata=metadata,
        )

    def get_stock_records(self) -> list[StockRecord]:
        return list(self.stock_records.values())

    def upsert_stock_record(self, record: StockRecord) -> StockRecord:
        self.stock_records[record.sku_id] = record
        return record

    def get_outstanding(self) -> list[Invoice]:
        return [invoice for invoice in self.invoices.values() if invoice.status in {"open", "overdue"}]

    def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        if approval.dedupe_key:
            existing = self.find_pending_approval(client_id=approval.client_id, action_type=approval.type, dedupe_key=approval.dedupe_key)
            if existing is not None:
                return existing
        self.approvals[approval.id] = approval
        return approval

    def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        self.approvals[approval.id] = approval
        return approval

    def list_pending_approvals(self) -> list[ApprovalRequest]:
        return [item for item in self.approvals.values() if item.status == ApprovalStatus.pending]

    def list_approvals(self) -> list[ApprovalRequest]:
        return list(self.approvals.values())

    def save_memory(self, memory: BusinessMemory) -> BusinessMemory:
        self.memories[memory.id] = memory
        return memory

    def list_memories(self) -> list[BusinessMemory]:
        return list(self.memories.values())

    def log_workflow_run(self, run: WorkflowRun) -> WorkflowRun:
        self.workflow_runs[run.id] = run
        return run

    def save_action_log(self, log: ActionExecutionLog) -> ActionExecutionLog:
        self.action_logs[log.id] = log
        return log

    def list_action_logs(self) -> list[ActionExecutionLog]:
        return list(self.action_logs.values())
