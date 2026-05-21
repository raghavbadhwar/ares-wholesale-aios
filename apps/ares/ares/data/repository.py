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
    BeatRoute,
    Brand,
    BusinessGSTRegistration,
    BusinessMemory,
    Customer,
    GoodsReceiptNote,
    InventoryBatch,
    Invoice,
    LogisticsShipment,
    Order,
    Payment,
    PostDatedCheque,
    Principal,
    ProductSKU,
    PurchaseOrder,
    PurchaseInvoice,
    ReturnDamageCase,
    SchemeClaim,
    Supplier,
    StockRecord,
    StaffMember,
    TradeScheme,
    WorkflowRun,
)


class BusinessRepository(ABC):
    @abstractmethod
    def get_customers(self) -> list[Customer]: ...

    @abstractmethod
    def upsert_customer(self, customer: Customer) -> Customer: ...

    @abstractmethod
    def get_business_gst_registrations(self) -> list[BusinessGSTRegistration]: ...

    @abstractmethod
    def upsert_business_gst_registration(self, registration: BusinessGSTRegistration) -> BusinessGSTRegistration: ...

    @abstractmethod
    def get_products(self) -> list[ProductSKU]: ...

    @abstractmethod
    def upsert_product(self, product: ProductSKU) -> ProductSKU: ...

    @abstractmethod
    def get_principals(self) -> list[Principal]: ...

    @abstractmethod
    def upsert_principal(self, principal: Principal) -> Principal: ...

    @abstractmethod
    def get_brands(self) -> list[Brand]: ...

    @abstractmethod
    def upsert_brand(self, brand: Brand) -> Brand: ...

    @abstractmethod
    def get_trade_schemes(self) -> list[TradeScheme]: ...

    @abstractmethod
    def upsert_trade_scheme(self, scheme: TradeScheme) -> TradeScheme: ...

    @abstractmethod
    def get_scheme_claims(self) -> list[SchemeClaim]: ...

    @abstractmethod
    def upsert_scheme_claim(self, claim: SchemeClaim) -> SchemeClaim: ...

    @abstractmethod
    def get_purchase_orders(self) -> list[PurchaseOrder]: ...

    @abstractmethod
    def upsert_purchase_order(self, order: PurchaseOrder) -> PurchaseOrder: ...

    @abstractmethod
    def get_goods_receipt_notes(self) -> list[GoodsReceiptNote]: ...

    @abstractmethod
    def upsert_goods_receipt_note(self, receipt: GoodsReceiptNote) -> GoodsReceiptNote: ...

    @abstractmethod
    def get_suppliers(self) -> list[Supplier]: ...

    @abstractmethod
    def upsert_supplier(self, supplier: Supplier) -> Supplier: ...

    @abstractmethod
    def get_staff_members(self) -> list[StaffMember]: ...

    @abstractmethod
    def upsert_staff_member(self, staff_member: StaffMember) -> StaffMember: ...

    @abstractmethod
    def get_beat_routes(self) -> list[BeatRoute]: ...

    @abstractmethod
    def upsert_beat_route(self, route: BeatRoute) -> BeatRoute: ...

    @abstractmethod
    def get_return_damage_cases(self) -> list[ReturnDamageCase]: ...

    @abstractmethod
    def upsert_return_damage_case(self, case: ReturnDamageCase) -> ReturnDamageCase: ...

    @abstractmethod
    def get_logistics_shipments(self) -> list[LogisticsShipment]: ...

    @abstractmethod
    def upsert_logistics_shipment(self, shipment: LogisticsShipment) -> LogisticsShipment: ...

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
    def get_purchase_invoices(self) -> list[PurchaseInvoice]: ...

    @abstractmethod
    def upsert_purchase_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice: ...

    @abstractmethod
    def get_post_dated_cheques(self) -> list[PostDatedCheque]: ...

    @abstractmethod
    def upsert_post_dated_cheque(self, cheque: PostDatedCheque) -> PostDatedCheque: ...

    @abstractmethod
    def get_stock_records(self) -> list[StockRecord]: ...

    @abstractmethod
    def upsert_stock_record(self, record: StockRecord) -> StockRecord: ...

    @abstractmethod
    def get_inventory_batches(self) -> list[InventoryBatch]: ...

    @abstractmethod
    def upsert_inventory_batch(self, batch: InventoryBatch) -> InventoryBatch: ...

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
        self.business_gst_registrations: dict[str, BusinessGSTRegistration] = {}
        self.products: dict[str, ProductSKU] = {}
        self.principals: dict[str, Principal] = {}
        self.brands: dict[str, Brand] = {}
        self.trade_schemes: dict[str, TradeScheme] = {}
        self.scheme_claims: dict[str, SchemeClaim] = {}
        self.purchase_orders: dict[str, PurchaseOrder] = {}
        self.goods_receipt_notes: dict[str, GoodsReceiptNote] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.staff_members: dict[str, StaffMember] = {}
        self.beat_routes: dict[str, BeatRoute] = {}
        self.return_damage_cases: dict[str, ReturnDamageCase] = {}
        self.logistics_shipments: dict[str, LogisticsShipment] = {}
        self.orders: dict[str, Order] = {}
        self.invoices: dict[str, Invoice] = {}
        self.payments: dict[str, Payment] = {}
        self.purchase_invoices: dict[str, PurchaseInvoice] = {}
        self.post_dated_cheques: dict[str, PostDatedCheque] = {}
        self.stock_records: dict[str, StockRecord] = {}
        self.inventory_batches: dict[str, InventoryBatch] = {}
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
        business_gst_registrations: Iterable[BusinessGSTRegistration] = (),
        products: Iterable[ProductSKU] = (),
        principals: Iterable[Principal] = (),
        brands: Iterable[Brand] = (),
        trade_schemes: Iterable[TradeScheme] = (),
        scheme_claims: Iterable[SchemeClaim] = (),
        purchase_orders: Iterable[PurchaseOrder] = (),
        goods_receipt_notes: Iterable[GoodsReceiptNote] = (),
        orders: Iterable[Order] = (),
        invoices: Iterable[Invoice] = (),
        stock_records: Iterable[StockRecord] = (),
        payments: Iterable[Payment] = (),
        suppliers: Iterable[Supplier] = (),
        purchase_invoices: Iterable[PurchaseInvoice] = (),
        staff_members: Iterable[StaffMember] = (),
        beat_routes: Iterable[BeatRoute] = (),
        return_damage_cases: Iterable[ReturnDamageCase] = (),
        logistics_shipments: Iterable[LogisticsShipment] = (),
        inventory_batches: Iterable[InventoryBatch] = (),
    ) -> "InMemoryRepository":
        repo = cls()
        for customer in customers:
            repo.upsert_customer(customer)
        for registration in business_gst_registrations:
            repo.upsert_business_gst_registration(registration)
        for product in products:
            repo.upsert_product(product)
        for principal in principals:
            repo.upsert_principal(principal)
        for brand in brands:
            repo.upsert_brand(brand)
        for scheme in trade_schemes:
            repo.upsert_trade_scheme(scheme)
        for claim in scheme_claims:
            repo.upsert_scheme_claim(claim)
        for order in purchase_orders:
            repo.upsert_purchase_order(order)
        for receipt in goods_receipt_notes:
            repo.upsert_goods_receipt_note(receipt)
        for supplier in suppliers:
            repo.upsert_supplier(supplier)
        for staff_member in staff_members:
            repo.upsert_staff_member(staff_member)
        for route in beat_routes:
            repo.upsert_beat_route(route)
        for case in return_damage_cases:
            repo.upsert_return_damage_case(case)
        for shipment in logistics_shipments:
            repo.upsert_logistics_shipment(shipment)
        for order in orders:
            repo.create_order(order)
        for invoice in invoices:
            repo.upsert_invoice(invoice)
        for invoice in purchase_invoices:
            repo.upsert_purchase_invoice(invoice)
        for record in stock_records:
            repo.upsert_stock_record(record)
        for batch in inventory_batches:
            repo.upsert_inventory_batch(batch)
        for payment in payments:
            repo.upsert_payment(payment)
        return repo

    def get_customers(self) -> list[Customer]:
        return list(self.customers.values())

    def upsert_customer(self, customer: Customer) -> Customer:
        self.customers[customer.id] = customer
        return customer

    def get_business_gst_registrations(self) -> list[BusinessGSTRegistration]:
        return list(self.business_gst_registrations.values())

    def upsert_business_gst_registration(self, registration: BusinessGSTRegistration) -> BusinessGSTRegistration:
        self.business_gst_registrations[registration.id] = registration
        return registration

    def get_products(self) -> list[ProductSKU]:
        return list(self.products.values())

    def upsert_product(self, product: ProductSKU) -> ProductSKU:
        self.products[product.id] = product
        return product

    def get_principals(self) -> list[Principal]:
        return list(self.principals.values())

    def upsert_principal(self, principal: Principal) -> Principal:
        self.principals[principal.id] = principal
        return principal

    def get_brands(self) -> list[Brand]:
        return list(self.brands.values())

    def upsert_brand(self, brand: Brand) -> Brand:
        self.brands[brand.id] = brand
        return brand

    def get_trade_schemes(self) -> list[TradeScheme]:
        return list(self.trade_schemes.values())

    def upsert_trade_scheme(self, scheme: TradeScheme) -> TradeScheme:
        self.trade_schemes[scheme.id] = scheme
        return scheme

    def get_scheme_claims(self) -> list[SchemeClaim]:
        return list(self.scheme_claims.values())

    def upsert_scheme_claim(self, claim: SchemeClaim) -> SchemeClaim:
        self.scheme_claims[claim.id] = claim
        return claim

    def get_purchase_orders(self) -> list[PurchaseOrder]:
        return list(self.purchase_orders.values())

    def upsert_purchase_order(self, order: PurchaseOrder) -> PurchaseOrder:
        self.purchase_orders[order.id] = order
        return order

    def get_goods_receipt_notes(self) -> list[GoodsReceiptNote]:
        return list(self.goods_receipt_notes.values())

    def upsert_goods_receipt_note(self, receipt: GoodsReceiptNote) -> GoodsReceiptNote:
        self.goods_receipt_notes[receipt.id] = receipt
        return receipt

    def get_suppliers(self) -> list[Supplier]:
        return list(self.suppliers.values())

    def upsert_supplier(self, supplier: Supplier) -> Supplier:
        self.suppliers[supplier.id] = supplier
        return supplier

    def get_staff_members(self) -> list[StaffMember]:
        return list(self.staff_members.values())

    def upsert_staff_member(self, staff_member: StaffMember) -> StaffMember:
        self.staff_members[staff_member.id] = staff_member
        return staff_member

    def get_beat_routes(self) -> list[BeatRoute]:
        return list(self.beat_routes.values())

    def upsert_beat_route(self, route: BeatRoute) -> BeatRoute:
        self.beat_routes[route.id] = route
        return route

    def get_return_damage_cases(self) -> list[ReturnDamageCase]:
        return list(self.return_damage_cases.values())

    def upsert_return_damage_case(self, case: ReturnDamageCase) -> ReturnDamageCase:
        self.return_damage_cases[case.id] = case
        return case

    def get_logistics_shipments(self) -> list[LogisticsShipment]:
        return list(self.logistics_shipments.values())

    def upsert_logistics_shipment(self, shipment: LogisticsShipment) -> LogisticsShipment:
        self.logistics_shipments[shipment.id] = shipment
        return shipment

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

    def get_purchase_invoices(self) -> list[PurchaseInvoice]:
        return list(self.purchase_invoices.values())

    def upsert_purchase_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        self.purchase_invoices[invoice.id] = invoice
        return invoice

    def get_post_dated_cheques(self) -> list[PostDatedCheque]:
        return list(self.post_dated_cheques.values())

    def upsert_post_dated_cheque(self, cheque: PostDatedCheque) -> PostDatedCheque:
        self.post_dated_cheques[cheque.id] = cheque
        return cheque

    def get_stock_records(self) -> list[StockRecord]:
        return list(self.stock_records.values())

    def upsert_stock_record(self, record: StockRecord) -> StockRecord:
        self.stock_records[record.sku_id] = record
        return record

    def get_inventory_batches(self) -> list[InventoryBatch]:
        return list(self.inventory_batches.values())

    def upsert_inventory_batch(self, batch: InventoryBatch) -> InventoryBatch:
        self.inventory_batches[batch.id] = batch
        return batch

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
