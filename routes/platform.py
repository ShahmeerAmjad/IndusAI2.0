# =======================
# Platform API Routes — Full Back-Office / Middle-Office
# =======================
"""
FastAPI APIRouter with endpoints for:
- Products / Catalog
- Inventory
- Customers
- Orders (O2C)
- Quotes
- Pricing
- Suppliers / Purchase Orders (P2P)
- Invoices / Payments
- RMA / Returns
- Workflows
- Analytics
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from models.domain import (
    CustomerContractCreate, CustomerCreate, GoodsReceiptCreate,
    InvoiceCreate, InventoryAdjustment, OrderCreate, OrderStatusUpdate,
    PaymentCreate, PurchaseOrderCreate, ProductCreate, ProductUpdate,
    QuoteCreate, RMACreate, SupplierCreate, WorkflowAction,
    PriceListCreate, PriceListItemCreate,
)

router = APIRouter(prefix="/api/v1", tags=["platform"])

# Services are injected via app.state at startup (see main.py)
_services = {}


def set_services(services: dict):
    """Called from main.py to inject service instances."""
    _services.update(services)


def _svc(name: str):
    svc = _services.get(name)
    if not svc:
        raise HTTPException(status_code=503, detail=f"Service '{name}' not available")
    return svc


def _paginated(items, total, page, page_size):
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


# ===================================================================
# Products / Catalog
# ===================================================================

@router.post("/products", status_code=201)
async def create_product(data: ProductCreate):
    result = await _svc("products").create_product(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create product")
    return result


@router.get("/products")
async def list_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    in_stock: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("products").search_products(
        query=q, category=category, manufacturer=manufacturer,
        in_stock=in_stock, page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/products/categories")
async def get_categories():
    return await _svc("products").get_categories()


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    result = await _svc("products").get_product(product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.get("/products/sku/{sku}")
async def get_product_by_sku(sku: str):
    result = await _svc("products").get_product_by_sku(sku)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.patch("/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate):
    result = await _svc("products").update_product(
        product_id, data.model_dump(exclude_none=True),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


# ===================================================================
# Inventory
# ===================================================================

@router.get("/inventory")
async def list_inventory(
    warehouse: Optional[str] = None,
    low_stock: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    items, total = await _svc("inventory").get_all_stock(
        warehouse_code=warehouse, low_stock_only=low_stock,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/inventory/{product_id}")
async def get_stock(product_id: str, warehouse: str = "MAIN"):
    result = await _svc("inventory").get_stock(product_id, warehouse)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return result


@router.get("/inventory/sku/{sku}")
async def get_stock_by_sku(sku: str, warehouse: str = "MAIN"):
    result = await _svc("inventory").get_stock_by_sku(sku, warehouse)
    if not result:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return result


@router.post("/inventory/adjust")
async def adjust_inventory(data: InventoryAdjustment):
    ok = await _svc("inventory").adjust_stock(
        data.product_id, data.warehouse_code,
        data.adjustment_qty, data.reason,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Adjustment failed")
    return {"status": "adjusted"}


@router.get("/inventory/reorder-alerts")
async def get_reorder_alerts(warehouse: str = "MAIN"):
    return await _svc("inventory").get_reorder_alerts(warehouse)


@router.get("/inventory/{product_id}/transactions")
async def get_inventory_transactions(product_id: str, limit: int = 50):
    return await _svc("inventory").get_transactions(product_id, limit)


# ===================================================================
# Customers
# ===================================================================

@router.post("/customers", status_code=201)
async def create_customer(data: CustomerCreate):
    result = await _svc("customers").create_customer(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create customer")
    return result


@router.get("/customers")
async def list_customers(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("customers").list_customers(
        page=page, page_size=page_size, search=search,
    )
    return _paginated(items, total, page, page_size)


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    result = await _svc("customers").get_customer(customer_id)
    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.get("/customers/{customer_id}/credit")
async def check_credit(customer_id: str, amount: float = Query(..., gt=0)):
    return await _svc("customers").check_credit(customer_id, amount)


# ===================================================================
# Pricing
# ===================================================================

@router.get("/pricing/{product_id}")
async def get_price(product_id: str,
                    customer_id: Optional[str] = None,
                    quantity: float = Query(1, gt=0)):
    return await _svc("pricing").get_price(product_id, customer_id, quantity)


@router.get("/pricing/{product_id}/tiers")
async def get_bulk_pricing(product_id: str, customer_id: Optional[str] = None):
    return await _svc("pricing").get_bulk_pricing(product_id, customer_id)


@router.post("/price-lists", status_code=201)
async def create_price_list(data: PriceListCreate):
    result = await _svc("pricing").create_price_list(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create price list")
    return result


@router.get("/price-lists/{pl_id}")
async def get_price_list(pl_id: str):
    result = await _svc("pricing").get_price_list(pl_id)
    if not result:
        raise HTTPException(status_code=404, detail="Price list not found")
    return result


@router.post("/price-lists/{pl_id}/items")
async def add_price_list_item(pl_id: str, data: PriceListItemCreate):
    ok = await _svc("pricing").add_price_list_item(
        pl_id, data.product_id, float(data.unit_price), float(data.min_quantity),
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add price list item")
    return {"status": "added"}


@router.post("/contracts", status_code=201)
async def create_contract(data: CustomerContractCreate):
    result = await _svc("pricing").create_contract(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create contract")
    return result


@router.get("/customers/{customer_id}/contract")
async def get_active_contract(customer_id: str):
    result = await _svc("pricing").get_active_contract(customer_id)
    if not result:
        raise HTTPException(status_code=404, detail="No active contract")
    return result


# ===================================================================
# Orders (O2C)
# ===================================================================

@router.post("/orders", status_code=201)
async def create_order(data: OrderCreate):
    result = await _svc("orders").create_order(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/orders")
async def list_orders(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("orders").list_orders(
        customer_id=customer_id, status=status,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    result = await _svc("orders").get_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


@router.post("/orders/{order_id}/submit")
async def submit_order(order_id: str):
    result = await _svc("orders").submit_order(order_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to submit order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/orders/{order_id}/confirm")
async def confirm_order(order_id: str, approved_by: str = "admin"):
    result = await _svc("orders").confirm_order(order_id, approved_by)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to confirm order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/orders/{order_id}/ship")
async def ship_order(order_id: str, tracking_number: Optional[str] = None):
    result = await _svc("orders").ship_order(order_id, tracking_number)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to ship order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/orders/{order_id}/deliver")
async def deliver_order(order_id: str):
    result = await _svc("orders").deliver_order(order_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to deliver order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, reason: str = ""):
    result = await _svc("orders").cancel_order(order_id, reason)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to cancel order")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ===================================================================
# Quotes
# ===================================================================

@router.post("/quotes", status_code=201)
async def create_quote(data: QuoteCreate):
    result = await _svc("quotes").create_quote(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create quote")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/quotes")
async def list_quotes(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("quotes").list_quotes(
        customer_id=customer_id, status=status,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: str):
    result = await _svc("quotes").get_quote(quote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Quote not found")
    return result


@router.post("/quotes/{quote_id}/send")
async def send_quote(quote_id: str):
    result = await _svc("quotes").send_quote(quote_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to send quote")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(quote_id: str):
    result = await _svc("quotes").accept_quote(quote_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to accept quote")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/quotes/{quote_id}/convert")
async def convert_quote_to_order(quote_id: str):
    result = await _svc("quotes").convert_to_order(quote_id, _svc("orders"))
    if not result:
        raise HTTPException(status_code=400, detail="Failed to convert quote")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ===================================================================
# Suppliers & Purchase Orders (P2P)
# ===================================================================

@router.post("/suppliers", status_code=201)
async def create_supplier(data: SupplierCreate):
    result = await _svc("procurement").create_supplier(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create supplier")
    return result


@router.get("/suppliers")
async def list_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("procurement").list_suppliers(page, page_size)
    return _paginated(items, total, page, page_size)


@router.get("/suppliers/{supplier_id}")
async def get_supplier(supplier_id: str):
    result = await _svc("procurement").get_supplier(supplier_id)
    if not result:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return result


@router.post("/purchase-orders", status_code=201)
async def create_purchase_order(data: PurchaseOrderCreate):
    result = await _svc("procurement").create_purchase_order(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create PO")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/purchase-orders")
async def list_purchase_orders(
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("procurement").list_purchase_orders(
        supplier_id=supplier_id, status=status,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/purchase-orders/{po_id}")
async def get_purchase_order(po_id: str):
    result = await _svc("procurement").get_purchase_order(po_id)
    if not result:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return result


@router.post("/purchase-orders/{po_id}/submit")
async def submit_po(po_id: str):
    result = await _svc("procurement").submit_po(po_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to submit PO")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/purchase-orders/{po_id}/confirm")
async def confirm_po(po_id: str):
    result = await _svc("procurement").confirm_po(po_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to confirm PO")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/goods-receipts", status_code=201)
async def receive_goods(data: GoodsReceiptCreate):
    result = await _svc("procurement").receive_goods(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to receive goods")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/purchase-orders/auto-generate")
async def auto_generate_pos(warehouse: str = "MAIN"):
    results = await _svc("procurement").auto_generate_pos(warehouse)
    return {"generated_pos": len(results), "purchase_orders": results}


# ===================================================================
# Invoices & Payments
# ===================================================================

@router.post("/invoices", status_code=201)
async def create_invoice(data: InvoiceCreate):
    result = await _svc("invoices").create_invoice_from_order(
        data.order_id, data.payment_terms, data.notes,
    )
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create invoice")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/invoices")
async def list_invoices(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("invoices").list_invoices(
        customer_id=customer_id, status=status,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/invoices/overdue")
async def get_overdue_invoices():
    return await _svc("invoices").get_overdue_invoices()


@router.get("/invoices/aging")
async def get_ar_aging():
    return await _svc("invoices").get_ar_aging()


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    result = await _svc("invoices").get_invoice(invoice_id)
    if not result:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return result


@router.post("/invoices/{invoice_id}/send")
async def send_invoice(invoice_id: str):
    result = await _svc("invoices").send_invoice(invoice_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to send invoice")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/payments", status_code=201)
async def record_payment(data: PaymentCreate):
    result = await _svc("invoices").record_payment(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to record payment")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ===================================================================
# RMA / Returns
# ===================================================================

@router.post("/rma", status_code=201)
async def create_rma(data: RMACreate):
    result = await _svc("rma").create_rma(data.model_dump())
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create RMA")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/rma")
async def list_rmas(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = await _svc("rma").list_rmas(
        customer_id=customer_id, status=status,
        page=page, page_size=page_size,
    )
    return _paginated(items, total, page, page_size)


@router.get("/rma/{rma_id}")
async def get_rma(rma_id: str):
    result = await _svc("rma").get_rma(rma_id)
    if not result:
        raise HTTPException(status_code=404, detail="RMA not found")
    return result


@router.post("/rma/{rma_id}/approve")
async def approve_rma(rma_id: str):
    result = await _svc("rma").approve_rma(rma_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to approve RMA")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/rma/{rma_id}/receive")
async def receive_return(rma_id: str, warehouse: str = "MAIN"):
    result = await _svc("rma").receive_return(rma_id, warehouse)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to receive return")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/rma/{rma_id}/refund")
async def process_refund(rma_id: str):
    result = await _svc("rma").process_refund(rma_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to process refund")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ===================================================================
# Workflows
# ===================================================================

@router.get("/workflows")
async def list_pending_workflows(workflow_type: Optional[str] = None):
    return await _svc("workflow").get_pending_workflows(workflow_type)


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    result = await _svc("workflow").get_workflow(workflow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return result


@router.get("/workflows/{workflow_id}/actions")
async def get_workflow_actions(workflow_id: str):
    return await _svc("workflow").get_available_actions(workflow_id)


@router.post("/workflows/{workflow_id}/transition")
async def transition_workflow(workflow_id: str, data: WorkflowAction):
    result = await _svc("workflow").transition(
        workflow_id, data.action, data.performed_by, data.notes,
    )
    if not result:
        raise HTTPException(status_code=400, detail="Invalid transition")
    return result


# ===================================================================
# Analytics / Dashboard
# ===================================================================

@router.get("/analytics/dashboard")
async def get_dashboard_metrics():
    return await _svc("analytics").get_dashboard_metrics()


@router.get("/analytics/sales")
async def get_sales_summary(period: str = Query("month", pattern="^(day|week|month)$")):
    return await _svc("analytics").get_sales_summary(period)
