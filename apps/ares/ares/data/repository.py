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
    Order,
    Payment,
    ProductSKU,
    StockRecord,
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
        self.payments[payment.id] = payment
        return payment

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

