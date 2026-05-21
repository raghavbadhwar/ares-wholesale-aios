"""JSON-backed persistent repository for Ares pilot clients."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from apps.ares.ares.data.models import (
    ActionExecutionLog,
    ApprovalRequest,
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
from apps.ares.ares.data.repository import InMemoryRepository

T = TypeVar("T", bound=BaseModel)


class JsonClientRepository(InMemoryRepository):
    """Persistent repository that mirrors each collection to a JSON file."""

    FILES = {
        "customers": ("customers.json", Customer),
        "business_gst_registrations": ("business_gst_registrations.json", BusinessGSTRegistration),
        "products": ("products.json", ProductSKU),
        "principals": ("principals.json", Principal),
        "brands": ("brands.json", Brand),
        "trade_schemes": ("trade_schemes.json", TradeScheme),
        "scheme_claims": ("scheme_claims.json", SchemeClaim),
        "purchase_orders": ("purchase_orders.json", PurchaseOrder),
        "goods_receipt_notes": ("goods_receipt_notes.json", GoodsReceiptNote),
        "suppliers": ("suppliers.json", Supplier),
        "staff_members": ("staff_members.json", StaffMember),
        "beat_routes": ("beat_routes.json", BeatRoute),
        "return_damage_cases": ("return_damage_cases.json", ReturnDamageCase),
        "logistics_shipments": ("logistics_shipments.json", LogisticsShipment),
        "orders": ("orders.json", Order),
        "invoices": ("invoices.json", Invoice),
        "payments": ("payments.json", Payment),
        "purchase_invoices": ("purchase_invoices.json", PurchaseInvoice),
        "post_dated_cheques": ("post_dated_cheques.json", PostDatedCheque),
        "stock_records": ("stock_records.json", StockRecord),
        "inventory_batches": ("inventory_batches.json", InventoryBatch),
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
        for item in self._load_model_list("business_gst_registrations.json", BusinessGSTRegistration): self.business_gst_registrations[item.id] = item
        for item in self._load_model_list("products.json", ProductSKU): self.products[item.id] = item
        for item in self._load_model_list("principals.json", Principal): self.principals[item.id] = item
        for item in self._load_model_list("brands.json", Brand): self.brands[item.id] = item
        for item in self._load_model_list("trade_schemes.json", TradeScheme): self.trade_schemes[item.id] = item
        for item in self._load_model_list("scheme_claims.json", SchemeClaim): self.scheme_claims[item.id] = item
        for item in self._load_model_list("purchase_orders.json", PurchaseOrder): self.purchase_orders[item.id] = item
        for item in self._load_model_list("goods_receipt_notes.json", GoodsReceiptNote): self.goods_receipt_notes[item.id] = item
        for item in self._load_model_list("suppliers.json", Supplier): self.suppliers[item.id] = item
        for item in self._load_model_list("staff_members.json", StaffMember): self.staff_members[item.id] = item
        for item in self._load_model_list("beat_routes.json", BeatRoute): self.beat_routes[item.id] = item
        for item in self._load_model_list("return_damage_cases.json", ReturnDamageCase): self.return_damage_cases[item.id] = item
        for item in self._load_model_list("logistics_shipments.json", LogisticsShipment): self.logistics_shipments[item.id] = item
        for item in self._load_model_list("orders.json", Order): self.orders[item.id] = item
        for item in self._load_model_list("invoices.json", Invoice): self.invoices[item.id] = item
        for item in self._load_model_list("payments.json", Payment): self.payments[item.id] = item
        for item in self._load_model_list("purchase_invoices.json", PurchaseInvoice): self.purchase_invoices[item.id] = item
        for item in self._load_model_list("post_dated_cheques.json", PostDatedCheque): self.post_dated_cheques[item.id] = item
        for item in self._load_model_list("stock_records.json", StockRecord): self.stock_records[item.sku_id] = item
        for item in self._load_model_list("inventory_batches.json", InventoryBatch): self.inventory_batches[item.id] = item
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
    def upsert_business_gst_registration(self, registration: BusinessGSTRegistration) -> BusinessGSTRegistration:
        saved = super().upsert_business_gst_registration(registration); self._flush("business_gst_registrations"); return saved
    def upsert_product(self, product: ProductSKU) -> ProductSKU:
        saved = super().upsert_product(product); self._flush("products"); return saved
    def upsert_principal(self, principal: Principal) -> Principal:
        saved = super().upsert_principal(principal); self._flush("principals"); return saved
    def upsert_brand(self, brand: Brand) -> Brand:
        saved = super().upsert_brand(brand); self._flush("brands"); return saved
    def upsert_trade_scheme(self, scheme: TradeScheme) -> TradeScheme:
        saved = super().upsert_trade_scheme(scheme); self._flush("trade_schemes"); return saved
    def upsert_scheme_claim(self, claim: SchemeClaim) -> SchemeClaim:
        saved = super().upsert_scheme_claim(claim); self._flush("scheme_claims"); return saved
    def upsert_purchase_order(self, order: PurchaseOrder) -> PurchaseOrder:
        saved = super().upsert_purchase_order(order); self._flush("purchase_orders"); return saved
    def upsert_goods_receipt_note(self, receipt: GoodsReceiptNote) -> GoodsReceiptNote:
        saved = super().upsert_goods_receipt_note(receipt); self._flush("goods_receipt_notes"); return saved
    def upsert_supplier(self, supplier: Supplier) -> Supplier:
        saved = super().upsert_supplier(supplier); self._flush("suppliers"); return saved
    def upsert_staff_member(self, staff_member: StaffMember) -> StaffMember:
        saved = super().upsert_staff_member(staff_member); self._flush("staff_members"); return saved
    def upsert_beat_route(self, route: BeatRoute) -> BeatRoute:
        saved = super().upsert_beat_route(route); self._flush("beat_routes"); return saved
    def upsert_return_damage_case(self, case: ReturnDamageCase) -> ReturnDamageCase:
        saved = super().upsert_return_damage_case(case); self._flush("return_damage_cases"); return saved
    def upsert_logistics_shipment(self, shipment: LogisticsShipment) -> LogisticsShipment:
        saved = super().upsert_logistics_shipment(shipment); self._flush("logistics_shipments"); return saved
    def create_order(self, order: Order) -> Order:
        saved = super().create_order(order); self._flush("orders"); return saved
    def update_order_status(self, order_id: str, status: str) -> Order:
        saved = super().update_order_status(order_id, status); self._flush("orders"); return saved
    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        saved = super().upsert_invoice(invoice); self._flush("invoices"); return saved
    def upsert_payment(self, payment: Payment) -> Payment:
        saved = super().upsert_payment(payment); self._flush("payments"); return saved
    def upsert_purchase_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        saved = super().upsert_purchase_invoice(invoice); self._flush("purchase_invoices"); return saved
    def upsert_post_dated_cheque(self, cheque: PostDatedCheque) -> PostDatedCheque:
        saved = super().upsert_post_dated_cheque(cheque); self._flush("post_dated_cheques"); return saved
    def upsert_stock_record(self, record: StockRecord) -> StockRecord:
        saved = super().upsert_stock_record(record); self._flush("stock_records"); return saved
    def upsert_inventory_batch(self, batch: InventoryBatch) -> InventoryBatch:
        saved = super().upsert_inventory_batch(batch); self._flush("inventory_batches"); return saved
    def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = super().create_approval(approval); self._flush("approvals"); return saved
    def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = super().update_approval(approval); self._flush("approvals"); return saved
    def save_memory(self, memory: BusinessMemory) -> BusinessMemory:
        saved = super().save_memory(memory); self._flush("memories"); return saved
    def log_workflow_run(self, run: WorkflowRun) -> WorkflowRun:
        saved = super().log_workflow_run(run); self._flush("workflow_runs"); return saved
    def save_action_log(self, log: ActionExecutionLog) -> ActionExecutionLog:
        saved = super().save_action_log(log); self._flush("action_logs"); return saved
