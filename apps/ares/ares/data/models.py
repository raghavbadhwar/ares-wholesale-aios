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


class ProductSKU(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
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
    invoice_number: str
    customer_id: str | None = None
    date: Date | None = None
    amount: float
    tax_amount: float | None = None
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
    confidence: float = 1.0
    status: str = "pending"


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
    name: str
    current_stock: float
    reorder_level: float
    unit: str = "unit"
    supplier_id: str | None = None
    sales_velocity: float | None = None
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
