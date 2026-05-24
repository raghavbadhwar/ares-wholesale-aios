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
    client_id: str | None = None
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
    source_file: str | None = None


class ProductSKU(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str | None = None
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: str | None = None
    unit: str = "unit"
    current_stock: float = 0
    reorder_level: float = 0
    supplier_id: str | None = None
    buying_price: float | None = None
    selling_price: float | None = None
    margin: float | None = None
    source_file: str | None = None


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


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str | None = None
    invoice_number: str
    customer_id: str | None = None
    customer_gstin: str | None = None
    date: Date | None = None
    amount: float
    taxable_value: float | None = None
    tax_amount: float | None = None
    gst_rate_percent: float | None = None
    place_of_supply: str | None = None
    total_amount: float | None = None
    due_date: Date | None = None
    status: str = "open"
    source_file: str | None = None


class Payment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str | None = None
    customer_id: str | None = None
    amount: float
    date: Date | None = None
    mode: str | None = None
    reference: str | None = None
    matched_invoice_id: str | None = None
    confidence: float = 1.0
    status: str = "pending"
    provider: str | None = None
    external_event_id: str | None = None
    source_event_type: str | None = None
    signature_verification_status: str | None = None
    source_file: str | None = None
    raw_source: dict[str, Any] = Field(default_factory=dict)


class PurchaseInvoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str | None = None
    business_gstin_id: str | None = None
    supplier_id: str
    supplier_gstin: str | None = None
    invoice_number: str
    date: Date | None = None
    taxable_value: float = 0
    tax_amount: float = 0
    gst_rate_percent: float | None = None
    status: str = "booked"
    source_file: str | None = None


class SupplierPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str | None = None
    supplier_id: str
    amount: float
    date: Date | None = None
    mode: str | None = None
    reference: str | None = None
    matched_purchase_invoice_id: str | None = None
    unapplied_amount: float = 0
    status: str = "pending"
    provider: str | None = None
    external_event_id: str | None = None
    source_event_type: str | None = None
    signature_verification_status: str | None = None


class SupplierPaymentAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    supplier_payment_id: str
    purchase_invoice_id: str
    amount: float
    status: str = "posted"


class TaxEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    event_type: str
    source_type: str
    source_id: str
    document_type: str
    document_id: str
    document_number: str
    event_date: Date | None = None
    taxable_value: float
    tax_amount: float
    business_gstin_id: str | None = None
    status: str = "posted"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaxAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_type: str
    document_id: str
    document_number: str | None = None
    action: str
    taxable_value: float
    tax_amount: float
    status: str = "booked"
    source_file: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatutoryAdjustmentArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    adjustment_record_id: str | None = None
    provider: str
    source_kind: str
    operation: str | None = None
    source_file: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatutoryAdjustmentDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    adjustment_id: str
    document_role: str
    document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    entry_type: str
    source_type: str
    source_id: str
    amount: float
    debit_account: str | None = None
    credit_account: str | None = None
    status: str = "posted"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Supplier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    phone: str | None = None
    lead_time_days: int | None = None
    notes: str | None = None


class StockRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    client_id: str | None = None
    name: str
    current_stock: float
    reorder_level: float
    unit: str = "unit"
    supplier_id: str | None = None
    sales_velocity: float | None = None
    source_file: str | None = None
    last_updated: DateTime = Field(default_factory=utc_now)


class StaffMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    phone: str | None = None
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
    correlation_id: str | None = None
    idempotency_key: str | None = None
    status: str
    started_at: DateTime = Field(default_factory=utc_now)
    ended_at: DateTime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_digest: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    output_digest: str | None = None
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
