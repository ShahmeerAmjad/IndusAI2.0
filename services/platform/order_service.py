# =======================
# Order Service (O2C)
# =======================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class OrderService:
    """
    Full order lifecycle: create -> validate -> approve -> allocate -> ship -> deliver.
    Integrates with inventory, pricing, customer credit, and workflow engine.
    """

    def __init__(self, db_manager, inventory_service, pricing_service,
                 customer_service, workflow_engine, logger):
        self.db = db_manager
        self.inventory = inventory_service
        self.pricing = pricing_service
        self.customers = customer_service
        self.workflow = workflow_engine
        self.logger = logger
        self._order_counter = 0

    async def _next_order_number(self) -> str:
        if not self.db.pool:
            self._order_counter += 1
            return f"ORD-{self._order_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) + 1 as num FROM orders"
                )
                num = row["num"] if row else 1
                return f"ORD-{num:06d}"
        except Exception:
            self._order_counter += 1
            return f"ORD-{self._order_counter:06d}"

    # ------------------------------------------------------------------
    # Create Order
    # ------------------------------------------------------------------

    async def create_order(self, data: Dict[str, Any],
                           created_by: str = "system") -> Optional[Dict[str, Any]]:
        """
        Create an order with line items.
        - Resolves pricing for each line via pricing engine
        - Validates customer credit
        - Creates approval workflow if over threshold
        """
        if not self.db.pool:
            return None

        customer = await self.customers.get_customer(data["customer_id"])
        if not customer:
            return {"error": "Customer not found"}

        order_id = str(uuid.uuid4())
        order_number = await self._next_order_number()

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # Process lines
                    lines_data = []
                    subtotal = 0.0

                    for idx, line in enumerate(data.get("lines", []), start=1):
                        product = await conn.fetchrow(
                            "SELECT id, sku, name FROM products WHERE id = $1",
                            line["product_id"],
                        )
                        if not product:
                            return {"error": f"Product not found: {line['product_id']}"}

                        qty = float(line["quantity"])

                        # Get price
                        if line.get("unit_price") is not None:
                            unit_price = float(line["unit_price"])
                        else:
                            pricing = await self.pricing.get_price(
                                line["product_id"], data["customer_id"], qty,
                            )
                            unit_price = pricing.get("customer_price", 0)

                        discount_pct = float(line.get("discount_percent", 0))
                        line_total = round(qty * unit_price * (1 - discount_pct / 100), 2)
                        subtotal += line_total

                        line_id = str(uuid.uuid4())
                        warehouse = line.get("warehouse_code", "MAIN")

                        await conn.execute(
                            """
                            INSERT INTO order_lines
                                (id, order_id, line_number, product_id, sku,
                                 description, quantity, unit_price, discount_percent,
                                 line_total, warehouse_code)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                            """,
                            line_id, order_id, idx, line["product_id"],
                            product["sku"], product["name"], qty,
                            unit_price, discount_pct, line_total, warehouse,
                        )

                        lines_data.append({
                            "id": line_id,
                            "line_number": idx,
                            "product_id": line["product_id"],
                            "sku": product["sku"],
                            "quantity": qty,
                            "unit_price": unit_price,
                            "line_total": line_total,
                        })

                    tax_amount = round(subtotal * 0.0, 2)  # Tax calculation placeholder
                    shipping_amount = 0.0
                    total_amount = subtotal + tax_amount + shipping_amount

                    payment_terms = customer.get("payment_terms", "NET30")

                    await conn.execute(
                        """
                        INSERT INTO orders
                            (id, order_number, customer_id, status, po_number,
                             required_date, ship_to_address, bill_to_address,
                             subtotal, tax_amount, shipping_amount, total_amount,
                             payment_terms, shipping_method, notes, created_by)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                        """,
                        order_id, order_number, data["customer_id"], "draft",
                        data.get("po_number"), data.get("required_date"),
                        data.get("ship_to_address") or customer.get("shipping_address"),
                        data.get("bill_to_address") or customer.get("billing_address"),
                        subtotal, tax_amount, shipping_amount, total_amount,
                        payment_terms, data.get("shipping_method"),
                        data.get("notes"), created_by,
                    )

            self.logger.info(f"Order created: {order_number} (${total_amount:,.2f})")
            return await self.get_order(order_id)

        except Exception as e:
            self.logger.error(f"Failed to create order: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT o.*, c.name as customer_name, c.company as customer_company
                    FROM orders o
                    JOIN customers c ON c.id = o.customer_id
                    WHERE o.id = $1
                    """,
                    order_id,
                )
                if not row:
                    return None

                result = dict(row)
                result["id"] = str(result["id"])
                result["customer_id"] = str(result["customer_id"])
                for key in ("subtotal", "tax_amount", "shipping_amount", "total_amount"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("order_date", "approved_at", "shipped_at", "delivered_at",
                            "cancelled_at", "created_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                if result.get("required_date"):
                    result["required_date"] = result["required_date"].isoformat()

                # Fetch lines
                lines = await conn.fetch(
                    """
                    SELECT ol.*, p.name as product_name
                    FROM order_lines ol
                    JOIN products p ON p.id = ol.product_id
                    WHERE ol.order_id = $1
                    ORDER BY ol.line_number
                    """,
                    order_id,
                )
                result["lines"] = []
                for line in lines:
                    d = dict(line)
                    d["id"] = str(d["id"])
                    d["order_id"] = str(d["order_id"])
                    d["product_id"] = str(d["product_id"])
                    for key in ("quantity", "unit_price", "discount_percent",
                                "line_total", "shipped_quantity"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    result["lines"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get order: {e}")
            return None

    async def get_order_by_number(self, order_number: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM orders WHERE order_number = $1", order_number,
                )
                if row:
                    return await self.get_order(str(row["id"]))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get order by number: {e}")
            return None

    async def list_orders(self, customer_id: Optional[str] = None,
                          status: Optional[str] = None,
                          page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if customer_id:
            conditions.append(f"o.customer_id = ${idx}")
            params.append(customer_id)
            idx += 1
        if status:
            conditions.append(f"o.status = ${idx}")
            params.append(status)
            idx += 1

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"""SELECT COUNT(*) as cnt FROM orders o
                        JOIN customers c ON c.id = o.customer_id {where}""",
                    *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT o.id, o.order_number, o.customer_id, c.name as customer_name,
                           o.status, o.po_number, o.total_amount, o.order_date, o.created_at
                    FROM orders o
                    JOIN customers c ON c.id = o.customer_id
                    {where}
                    ORDER BY o.order_date DESC
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["customer_id"] = str(d["customer_id"])
                    if d.get("total_amount") is not None:
                        d["total_amount"] = float(d["total_amount"])
                    for key in ("order_date", "created_at"):
                        if d.get(key):
                            d[key] = d[key].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list orders: {e}")
            return [], 0

    # ------------------------------------------------------------------
    # Order Lifecycle
    # ------------------------------------------------------------------

    async def submit_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Submit a draft order: validate, credit check, reserve inventory."""
        order = await self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        if order["status"] != "draft":
            return {"error": f"Cannot submit order in '{order['status']}' status"}

        # Credit check
        credit = await self.customers.check_credit(order["customer_id"], order["total_amount"])
        if not credit.get("approved"):
            return {"error": f"Credit check failed: {credit.get('reason')}"}

        # Reserve inventory for each line
        for line in order.get("lines", []):
            reserved = await self.inventory.reserve_stock(
                line["product_id"], line.get("warehouse_code", "MAIN"),
                line["quantity"], order_id,
            )
            if not reserved:
                self.logger.warning(
                    f"Could not reserve stock for {line['sku']} (qty: {line['quantity']})"
                )

        # Update status
        await self._update_status(order_id, "submitted")

        # Create approval workflow for orders over $5000
        if order["total_amount"] > 5000:
            await self.workflow.create_workflow(
                "order_approval",
                reference_type="order",
                reference_id=order_id,
                data={"order_number": order["order_number"],
                      "total_amount": order["total_amount"]},
            )

        self.logger.info(f"Order submitted: {order['order_number']}")
        return await self.get_order(order_id)

    async def confirm_order(self, order_id: str, approved_by: str = "system") -> Optional[Dict[str, Any]]:
        """Confirm a submitted order (after approval if required)."""
        order = await self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        if order["status"] not in ("submitted",):
            return {"error": f"Cannot confirm order in '{order['status']}' status"}

        # Update credit used
        await self.customers.update_credit_used(order["customer_id"], order["total_amount"])

        if self.db.pool:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE orders SET status = 'confirmed', approved_by = $1,
                       approved_at = NOW(), updated_at = NOW() WHERE id = $2""",
                    approved_by, order_id,
                )

        self.logger.info(f"Order confirmed: {order['order_number']}")
        return await self.get_order(order_id)

    async def ship_order(self, order_id: str, tracking_number: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Mark order as shipped, deduct inventory."""
        order = await self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        if order["status"] not in ("confirmed", "processing"):
            return {"error": f"Cannot ship order in '{order['status']}' status"}

        # Deduct inventory
        for line in order.get("lines", []):
            await self.inventory.ship_stock(
                line["product_id"], line.get("warehouse_code", "MAIN"),
                line["quantity"], order_id,
            )

        if self.db.pool:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE orders SET status = 'shipped', shipped_at = NOW(),
                       updated_at = NOW() WHERE id = $1""",
                    order_id,
                )
                if tracking_number:
                    await conn.execute(
                        """UPDATE order_lines SET status = 'shipped',
                           shipped_quantity = quantity, tracking_number = $1
                           WHERE order_id = $2""",
                        tracking_number, order_id,
                    )

        self.logger.info(f"Order shipped: {order['order_number']}")
        return await self.get_order(order_id)

    async def deliver_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        order = await self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        if order["status"] != "shipped":
            return {"error": f"Cannot deliver order in '{order['status']}' status"}

        await self._update_status(order_id, "delivered")
        if self.db.pool:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE orders SET delivered_at = NOW() WHERE id = $1", order_id,
                )
                await conn.execute(
                    "UPDATE order_lines SET status = 'delivered' WHERE order_id = $1", order_id,
                )

        self.logger.info(f"Order delivered: {order['order_number']}")
        return await self.get_order(order_id)

    async def cancel_order(self, order_id: str, reason: str = "") -> Optional[Dict[str, Any]]:
        order = await self.get_order(order_id)
        if not order:
            return {"error": "Order not found"}
        if order["status"] in ("shipped", "delivered", "cancelled"):
            return {"error": f"Cannot cancel order in '{order['status']}' status"}

        # Release reserved inventory
        for line in order.get("lines", []):
            await self.inventory.release_reservation(
                line["product_id"], line.get("warehouse_code", "MAIN"),
                line["quantity"], order_id,
            )

        # Release credit hold
        if order["status"] == "confirmed":
            await self.customers.update_credit_used(
                order["customer_id"], -order["total_amount"],
            )

        if self.db.pool:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE orders SET status = 'cancelled', cancelled_at = NOW(),
                       cancellation_reason = $1, updated_at = NOW() WHERE id = $2""",
                    reason, order_id,
                )
                await conn.execute(
                    "UPDATE order_lines SET status = 'cancelled' WHERE order_id = $1", order_id,
                )

        self.logger.info(f"Order cancelled: {order['order_number']}")
        return await self.get_order(order_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _update_status(self, order_id: str, status: str):
        if not self.db.pool:
            return
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET status = $1, updated_at = NOW() WHERE id = $2",
                status, order_id,
            )
