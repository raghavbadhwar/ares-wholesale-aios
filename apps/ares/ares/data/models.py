"""Typed business objects for Ares Wholesale AIOS."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime as DateTime
from datetime import timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> DateTime:
    return DateTime.now(timezone.utc)


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    phone: str | None = None
    gstin: str | None = None
    location: str | None = None
    credit_limit: float | None = None
    payment_terms: str | None = None
    preferred_language: str = "english_hinglish"
    notes: str | None = None
    status: str = "active"


class BusinessGSTRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    gstin: str
    legal_name: str
    state_code: str
    state_name: str | None = None
    trade_name: str | None = None
    address: str | None = None
    is_default: bool = False
    composition_scheme: bool = False
    composition_turnover_limit: float = 15_000_000.0
    status: str = "active"


class ProductSKU(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: str | None = None
    unit: str = "unit"
    principal_id: str | None = None
    brand_id: str | None = None
    current_stock: float = 0
    reorder_level: float = 0
    supplier_id: str | None = None
    buying_price: float | None = None
    selling_price: float | None = None
    margin: float | None = None


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str | None = None
    name: str
    quantity: float
    unit: str = "unit"


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str | None = None
    source: str = "manual"
    raw_text: str | None = None
    file_id: str | None = None
    items: list[OrderItem] = Field(default_factory=list)
    requested_delivery_date: Date | None = None
    status: str = "pending"
    confidence: float = 1.0
    assigned_staff: str | None = None
    created_at: DateTime = Field(default_factory=utc_now)
    updated_at: DateTime = Field(default_factory=utc_now)


class InvoiceLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str | None = None
    description: str
    hsn_code: str | None = None
    quantity: float | None = None
    unit: str | None = None
    taxable_value: float
    gst_rate_percent: float | None = None
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    cess_amount: float = 0.0


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    invoice_number: str
    customer_id: str | None = None
    business_gstin_id: str | None = None
    date: Date | None = None
    amount: float
    taxable_value: float | None = None
    tax_amount: float | None = None
    gst_rate_percent: float | None = None
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    cess_amount: float = 0.0
    place_of_supply: str | None = None
    reverse_charge: bool = False
    invoice_type: str = "regular"
    ecommerce_gstin: str | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    due_date: Date | None = None
    status: str = "open"
    source_file: str | None = None


class Payment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str | None = None
    amount: float
    date: Date | None = None
    mode: str | None = None
    reference: str | None = None
    matched_invoice_id: str | None = None
    raw_source: dict[str, Any] = Field(default_factory=dict)
    candidate_invoice_ids: list[str] = Field(default_factory=list)
    unapplied_amount: float = 0.0
    audit_note: str | None = None
    confidence: float = 1.0
    status: str = "pending"


class PostDatedCheque(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    party_id: str
    amount: float
    cheque_date: Date
    bank_name: str
    cheque_number: str
    status: str = "scheduled"
    deposit_date: Date | None = None
    bounce_reason: str | None = None
    invoice_id: str | None = None
    notes: str | None = None


class Supplier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    phone: str | None = None
    gstin: str | None = None
    lead_time_days: int | None = None
    notes: str | None = None


class Principal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    gstin: str | None = None
    contact_phone: str | None = None
    payment_terms: str | None = None
    notes: str | None = None
    status: str = "active"


class Brand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    principal_id: str
    name: str
    category: str | None = None
    default_margin_percent: float | None = None
    scheme_notes: str | None = None
    status: str = "active"


class TradeScheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    principal_id: str
    brand_id: str | None = None
    name: str
    start_date: Date
    end_date: Date
    payout_type: str = "per_unit"
    payout_value: float
    status: str = "active"


class SchemeClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scheme_id: str
    principal_id: str
    invoice_id: str
    sku_id: str | None = None
    claim_amount: float
    status: str = "draft"


class PurchaseOrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    description: str
    quantity: float
    unit_cost: float


class PurchaseOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    supplier_id: str | None = None
    order_number: str
    order_date: Date | None = None
    lines: list[PurchaseOrderLine] = Field(default_factory=list)
    status: str = "open"


class GoodsReceiptNoteLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    description: str
    quantity_received: float


class GoodsReceiptNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    supplier_id: str | None = None
    purchase_order_id: str | None = None
    received_on: Date | None = None
    lines: list[GoodsReceiptNoteLine] = Field(default_factory=list)
    status: str = "received"


class PurchaseInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    supplier_id: str | None = None
    supplier_gstin: str | None = None
    purchase_order_id: str | None = None
    invoice_number: str
    date: Date | None = None
    due_date: Date | None = None
    taxable_value: float
    tax_amount: float
    gst_rate_percent: float | None = None
    line_items: list[PurchaseOrderLine] = Field(default_factory=list)
    tds_section: str | None = None
    tds_rate_percent: float | None = None
    tds_base_amount: float | None = None
    early_payment_discount_amount: float = 0.0
    early_payment_discount_deadline: Date | None = None
    status: str = "booked"
    source_file: str | None = None


class StockRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    name: str
    current_stock: float
    reorder_level: float
    unit: str = "unit"
    supplier_id: str | None = None
    sales_velocity: float | None = None
    last_updated: DateTime = Field(default_factory=utc_now)


class InventoryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sku_id: str
    batch_code: str
    quantity: float
    expiry_date: Date | None = None
    unit_cost: float | None = None
    received_at: Date | None = None
    notes: str | None = None


class StaffMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    phone: str | None = None
    status: str = "active"


class BeatRouteStop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    sequence: int
    planned_time: str | None = None
    notes: str | None = None


class BeatRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    staff_id: str | None = None
    weekday: str | None = None
    stops: list[BeatRouteStop] = Field(default_factory=list)
    status: str = "active"


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    owner: str | None = None
    due_at: DateTime | None = None
    status: str = "open"
    source: str | None = None


class Complaint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str | None = None
    summary: str
    status: str = "open"
    created_at: DateTime = Field(default_factory=utc_now)


class ReturnDamageCaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str | None = None
    quantity: float
    reason: str
    estimated_credit_value: float = 0.0


class ReturnDamageCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    customer_id: str
    invoice_id: str
    reported_on: Date
    requested_resolution: str
    items: list[ReturnDamageCaseItem] = Field(default_factory=list)
    status: str = "pending_review"
    created_at: DateTime = Field(default_factory=utc_now)


class LogisticsShipment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    invoice_id: str
    customer_id: str | None = None
    carrier: str
    packages: int = 1
    status: str = "pending_approval"
    delivery_status: str = "not_dispatched"
    tracking_number: str | None = None
    delivery_updates: list[dict[str, Any]] = Field(default_factory=list)
    created_at: DateTime = Field(default_factory=utc_now)


class BusinessRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    description: str
    sensitive: bool = False
    created_at: DateTime = Field(default_factory=utc_now)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    client_id: str
    proposed_action: str
    data: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    source: str = ""
    confidence: float = 1.0
    risk_level: RiskLevel = RiskLevel.medium
    status: ApprovalStatus = ApprovalStatus.pending
    created_at: DateTime = Field(default_factory=utc_now)
    decided_at: DateTime | None = None
    decided_by: str | None = None
    dedupe_key: str | None = None


class BusinessMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    subject_id: str | None = None
    content: str
    confidence: float = 1.0
    source: str = ""
    sensitive: bool = False
    created_at: DateTime = Field(default_factory=utc_now)
    updated_at: DateTime = Field(default_factory=utc_now)
    expires_at: DateTime | None = None


class WorkflowRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    workflow_name: str
    client_id: str
    status: str
    started_at: DateTime = Field(default_factory=utc_now)
    ended_at: DateTime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class ActionExecutionLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str
    approval_id: str | None = None
    action_type: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    executed_at: DateTime = Field(default_factory=utc_now)


class IngestedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    client_id: str
    raw_text: str = ""
    file_path: str | None = None
    file_id: str | None = None
    timestamp: DateTime = Field(default_factory=utc_now)
    sender: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class OrderExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: Order
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_approval: bool = False
