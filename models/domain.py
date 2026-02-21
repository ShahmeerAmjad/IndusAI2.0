# =======================
# Domain Models — MRO Back-Office / Middle-Office Platform
# =======================
"""
Enums, Pydantic request/response models, and dataclasses for:
- Products & Catalog
- Inventory
- Orders (O2C)
- Quotes
- Pricing & Contracts
- Procurement (P2P)
- Billing & Invoicing
- Returns / RMA
- Workflows
- Customers (enhanced)
- Suppliers
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    PARTIALLY_SHIPPED = "partially_shipped"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class QuoteStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class POStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PARTIAL_RECEIVED = "partial_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIAL_PAID = "partial_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class RMAStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    RECEIVED = "received"
    INSPECTED = "inspected"
    REFUNDED = "refunded"
    REJECTED = "rejected"


class RMAReason(str, Enum):
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    DAMAGED = "damaged"
    NOT_NEEDED = "not_needed"
    WARRANTY = "warranty"


class PaymentMethod(str, Enum):
    CHECK = "check"
    WIRE = "wire"
    ACH = "ach"
    CREDIT_CARD = "credit_card"
    TERMS = "terms"


class InventoryTxnType(str, Enum):
    RECEIPT = "receipt"
    SHIPMENT = "shipment"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"
    RETURN = "return"
    RESERVATION = "reservation"
    RELEASE = "release"


class WorkflowType(str, Enum):
    ORDER_APPROVAL = "order_approval"
    PO_APPROVAL = "po_approval"
    RMA_APPROVAL = "rma_approval"
    CREDIT_CHECK = "credit_check"
    PRICE_OVERRIDE = "price_override"


class UnitOfMeasure(str, Enum):
    EACH = "EA"
    BOX = "BX"
    CASE = "CS"
    DOZEN = "DZ"
    FEET = "FT"
    GALLON = "GL"
    KILOGRAM = "KG"
    METER = "MT"
    PACK = "PK"
    PAIR = "PR"
    POUND = "LB"
    ROLL = "RL"
    SET = "ST"


# ---------------------------------------------------------------------------
# Product & Catalog
# ---------------------------------------------------------------------------

class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    manufacturer: Optional[str] = Field(None, max_length=255)
    manufacturer_part_number: Optional[str] = Field(None, max_length=100)
    uom: str = Field(default="EA", max_length=20)
    weight_lbs: Optional[Decimal] = None
    min_order_qty: int = Field(default=1, ge=1)
    lead_time_days: Optional[int] = Field(None, ge=0)
    hazmat: bool = False
    country_of_origin: Optional[str] = Field(None, max_length=3)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    uom: Optional[str] = None
    weight_lbs: Optional[Decimal] = None
    min_order_qty: Optional[int] = Field(None, ge=1)
    lead_time_days: Optional[int] = Field(None, ge=0)
    hazmat: Optional[bool] = None
    country_of_origin: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    uom: str = "EA"
    weight_lbs: Optional[float] = None
    is_active: bool = True
    min_order_qty: int = 1
    lead_time_days: Optional[int] = None
    hazmat: bool = False
    country_of_origin: Optional[str] = None
    specs: List[Dict[str, str]] = []
    cross_references: List[Dict[str, str]] = []
    created_at: Optional[str] = None


class ProductSpecCreate(BaseModel):
    spec_name: str = Field(..., max_length=100)
    spec_value: str = Field(..., max_length=500)
    spec_unit: Optional[str] = Field(None, max_length=50)


class CrossReferenceCreate(BaseModel):
    cross_ref_type: str = Field(..., pattern=r'^(replaces|replaced_by|compatible|alternative)$')
    cross_ref_sku: str = Field(..., max_length=50)
    manufacturer: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryResponse(BaseModel):
    product_id: str
    sku: str
    product_name: str
    warehouse_code: str
    quantity_on_hand: float = 0
    quantity_reserved: float = 0
    quantity_available: float = 0
    quantity_on_order: float = 0
    reorder_point: Optional[float] = None
    reorder_qty: Optional[float] = None
    safety_stock: float = 0
    bin_location: Optional[str] = None
    last_counted_at: Optional[str] = None


class InventoryAdjustment(BaseModel):
    product_id: str
    warehouse_code: str = Field(default="MAIN", max_length=20)
    adjustment_qty: float
    reason: str = Field(..., max_length=200)


class InventoryTransfer(BaseModel):
    product_id: str
    from_warehouse: str = Field(..., max_length=20)
    to_warehouse: str = Field(..., max_length=20)
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = None


class ReorderAlert(BaseModel):
    product_id: str
    sku: str
    product_name: str
    warehouse_code: str
    quantity_available: float
    reorder_point: float
    reorder_qty: float
    preferred_supplier: Optional[str] = None
    supplier_lead_time_days: Optional[int] = None


# ---------------------------------------------------------------------------
# Customer (enhanced)
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    external_id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    payment_terms: str = Field(default="NET30", max_length=50)
    credit_limit: Optional[Decimal] = None
    tax_exempt: bool = False
    tax_id: Optional[str] = Field(None, max_length=50)


class CustomerResponse(BaseModel):
    id: str
    external_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    payment_terms: str = "NET30"
    credit_limit: Optional[float] = None
    credit_used: Optional[float] = None
    tax_exempt: bool = False
    is_active: bool = True
    created_at: Optional[str] = None
    last_activity: Optional[str] = None


# ---------------------------------------------------------------------------
# Pricing & Contracts
# ---------------------------------------------------------------------------

class PriceListCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    currency: str = Field(default="USD", max_length=3)
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    is_default: bool = False


class PriceListItemCreate(BaseModel):
    product_id: str
    unit_price: Decimal = Field(..., gt=0)
    min_quantity: Decimal = Field(default=1, ge=1)


class CustomerContractCreate(BaseModel):
    customer_id: str
    contract_number: str = Field(..., max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    price_list_id: Optional[str] = None
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    payment_terms: str = Field(default="NET30", max_length=50)
    credit_limit: Optional[Decimal] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PricingResult(BaseModel):
    product_id: str
    sku: str
    product_name: str
    list_price: float
    customer_price: float
    discount_percent: float = 0
    quantity: float = 1
    total_price: float
    contract_number: Optional[str] = None
    price_list_name: Optional[str] = None
    margin_percent: Optional[float] = None


# ---------------------------------------------------------------------------
# Orders (O2C)
# ---------------------------------------------------------------------------

class OrderLineCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = None  # if None, uses pricing engine
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    warehouse_code: str = Field(default="MAIN", max_length=20)


class OrderCreate(BaseModel):
    customer_id: str
    po_number: Optional[str] = Field(None, max_length=50)
    required_date: Optional[date] = None
    ship_to_address: Optional[str] = None
    bill_to_address: Optional[str] = None
    shipping_method: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    lines: List[OrderLineCreate] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: str
    customer_name: Optional[str] = None
    status: str = "draft"
    po_number: Optional[str] = None
    order_date: Optional[str] = None
    required_date: Optional[str] = None
    ship_to_address: Optional[str] = None
    bill_to_address: Optional[str] = None
    subtotal: float = 0
    tax_amount: float = 0
    shipping_amount: float = 0
    total_amount: float = 0
    payment_terms: Optional[str] = None
    shipping_method: Optional[str] = None
    notes: Optional[str] = None
    lines: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None
    tracking_number: Optional[str] = None


class ShipmentCreate(BaseModel):
    lines: List[Dict[str, Any]]  # [{order_line_id, quantity_shipped, tracking_number}]
    shipping_method: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

class QuoteLineCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = None
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class QuoteCreate(BaseModel):
    customer_id: str
    valid_days: int = Field(default=30, ge=1, le=365)
    notes: Optional[str] = None
    lines: List[QuoteLineCreate] = Field(..., min_length=1)


class QuoteResponse(BaseModel):
    id: str
    quote_number: str
    customer_id: str
    customer_name: Optional[str] = None
    status: str = "draft"
    valid_until: Optional[str] = None
    subtotal: float = 0
    tax_amount: float = 0
    total_amount: float = 0
    notes: Optional[str] = None
    lines: List[Dict[str, Any]] = []
    converted_order_id: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Procurement (P2P)
# ---------------------------------------------------------------------------

class SupplierCreate(BaseModel):
    supplier_code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    payment_terms: str = Field(default="NET30", max_length=50)
    lead_time_days: int = Field(default=14, ge=0)


class SupplierResponse(BaseModel):
    id: str
    supplier_code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms: str = "NET30"
    lead_time_days: int = 14
    is_active: bool = True
    rating: Optional[float] = None
    created_at: Optional[str] = None


class POLineCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., gt=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    lines: List[POLineCreate] = Field(..., min_length=1)


class PurchaseOrderResponse(BaseModel):
    id: str
    po_number: str
    supplier_id: str
    supplier_name: Optional[str] = None
    status: str = "draft"
    order_date: Optional[str] = None
    expected_date: Optional[str] = None
    subtotal: float = 0
    tax_amount: float = 0
    shipping_amount: float = 0
    total_amount: float = 0
    notes: Optional[str] = None
    lines: List[Dict[str, Any]] = []
    created_at: Optional[str] = None


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: str
    warehouse_code: str = Field(default="MAIN", max_length=20)
    received_by: Optional[str] = None
    notes: Optional[str] = None
    lines: List[Dict[str, Any]] = Field(
        ..., min_length=1
    )  # [{po_line_id, quantity_received, quantity_rejected, rejection_reason, bin_location}]


# ---------------------------------------------------------------------------
# Billing & Invoicing
# ---------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    order_id: str
    payment_terms: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    order_id: Optional[str] = None
    customer_id: str
    customer_name: Optional[str] = None
    status: str = "draft"
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    subtotal: float = 0
    tax_amount: float = 0
    shipping_amount: float = 0
    total_amount: float = 0
    amount_paid: float = 0
    balance_due: float = 0
    payment_terms: Optional[str] = None
    lines: List[Dict[str, Any]] = []
    created_at: Optional[str] = None


class PaymentCreate(BaseModel):
    invoice_id: str
    amount: Decimal = Field(..., gt=0)
    payment_method: PaymentMethod
    reference_number: Optional[str] = Field(None, max_length=100)
    payment_date: Optional[date] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: str
    payment_number: str
    invoice_id: str
    customer_id: str
    amount: float
    payment_method: str
    reference_number: Optional[str] = None
    payment_date: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Returns / RMA
# ---------------------------------------------------------------------------

class RMALineCreate(BaseModel):
    order_line_id: str
    product_id: str
    quantity: Decimal = Field(..., gt=0)


class RMACreate(BaseModel):
    order_id: str
    customer_id: str
    reason: RMAReason
    description: Optional[str] = None
    lines: List[RMALineCreate] = Field(..., min_length=1)


class RMAResponse(BaseModel):
    id: str
    rma_number: str
    order_id: Optional[str] = None
    customer_id: str
    customer_name: Optional[str] = None
    status: str = "requested"
    reason: Optional[str] = None
    description: Optional[str] = None
    lines: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class WorkflowResponse(BaseModel):
    id: str
    workflow_type: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    current_state: str
    previous_state: Optional[str] = None
    assigned_to: Optional[str] = None
    data: Dict[str, Any] = {}
    transitions: List[Dict[str, Any]] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowAction(BaseModel):
    action: str = Field(..., max_length=50)
    performed_by: str = Field(..., max_length=100)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class DashboardMetrics(BaseModel):
    orders_today: int = 0
    orders_this_month: int = 0
    revenue_today: float = 0
    revenue_this_month: float = 0
    open_orders: int = 0
    pending_shipments: int = 0
    open_quotes: int = 0
    low_stock_items: int = 0
    open_pos: int = 0
    pending_invoices: int = 0
    overdue_invoices: int = 0
    open_rmas: int = 0
    top_products: List[Dict[str, Any]] = []
    top_customers: List[Dict[str, Any]] = []
    recent_orders: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Search / Filter
# ---------------------------------------------------------------------------

class ProductSearch(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    in_stock: Optional[bool] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
