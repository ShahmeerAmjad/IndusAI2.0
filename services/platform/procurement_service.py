# =======================
# Procurement Service (P2P)
# =======================

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class ProcurementService:
    """
    Procure-to-Pay: supplier management, purchase orders, goods receipt.
    """

    def __init__(self, db_manager, inventory_service, workflow_engine, logger):
        self.db = db_manager
        self.inventory = inventory_service
        self.workflow = workflow_engine
        self.logger = logger
        self._po_counter = 0
        self._gr_counter = 0

    async def _next_po_number(self) -> str:
        if not self.db.pool:
            self._po_counter += 1
            return f"PO-{self._po_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM purchase_orders")
                num = row["num"] if row else 1
                return f"PO-{num:06d}"
        except Exception:
            self._po_counter += 1
            return f"PO-{self._po_counter:06d}"

    async def _next_receipt_number(self) -> str:
        if not self.db.pool:
            self._gr_counter += 1
            return f"GR-{self._gr_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM goods_receipts")
                num = row["num"] if row else 1
                return f"GR-{num:06d}"
        except Exception:
            self._gr_counter += 1
            return f"GR-{self._gr_counter:06d}"

    # ------------------------------------------------------------------
    # Suppliers
    # ------------------------------------------------------------------

    async def create_supplier(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            supplier_id = str(uuid.uuid4())
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO suppliers
                        (id, supplier_code, name, contact_name, email, phone,
                         address, payment_terms, lead_time_days)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                    supplier_id, data["supplier_code"], data["name"],
                    data.get("contact_name"), data.get("email"),
                    data.get("phone"), data.get("address"),
                    data.get("payment_terms", "NET30"),
                    data.get("lead_time_days", 14),
                )
            return await self.get_supplier(supplier_id)
        except Exception as e:
            self.logger.error(f"Failed to create supplier: {e}")
            return None

    async def get_supplier(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM suppliers WHERE id = $1", supplier_id,
                )
                if not row:
                    return None
                result = dict(row)
                result["id"] = str(result["id"])
                if result.get("rating") is not None:
                    result["rating"] = float(result["rating"])
                if result.get("created_at"):
                    result["created_at"] = result["created_at"].isoformat()
                return result
        except Exception as e:
            self.logger.error(f"Failed to get supplier: {e}")
            return None

    async def list_suppliers(self, page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0
        offset = (page - 1) * page_size
        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM suppliers WHERE is_active = TRUE"
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    """
                    SELECT id, supplier_code, name, contact_name, email, phone,
                           payment_terms, lead_time_days, rating, is_active
                    FROM suppliers WHERE is_active = TRUE
                    ORDER BY name
                    LIMIT $1 OFFSET $2
                    """,
                    page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    if d.get("rating") is not None:
                        d["rating"] = float(d["rating"])
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list suppliers: {e}")
            return [], 0

    async def add_supplier_product(self, supplier_id: str, product_id: str,
                                   supplier_sku: Optional[str] = None,
                                   supplier_price: Optional[float] = None,
                                   lead_time_days: Optional[int] = None,
                                   is_preferred: bool = False) -> bool:
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO supplier_products
                        (id, supplier_id, product_id, supplier_sku,
                         supplier_price, lead_time_days, is_preferred)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (supplier_id, product_id) DO UPDATE
                        SET supplier_sku = COALESCE($4, supplier_products.supplier_sku),
                            supplier_price = COALESCE($5, supplier_products.supplier_price),
                            lead_time_days = COALESCE($6, supplier_products.lead_time_days),
                            is_preferred = $7
                    """,
                    str(uuid.uuid4()), supplier_id, product_id,
                    supplier_sku, supplier_price, lead_time_days, is_preferred,
                )
            return True
        except Exception as e:
            self.logger.error(f"Failed to add supplier product: {e}")
            return False

    # ------------------------------------------------------------------
    # Purchase Orders
    # ------------------------------------------------------------------

    async def create_purchase_order(self, data: Dict[str, Any],
                                    created_by: str = "system") -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None

        po_id = str(uuid.uuid4())
        po_number = await self._next_po_number()

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    subtotal = 0.0

                    for idx, line in enumerate(data.get("lines", []), start=1):
                        product = await conn.fetchrow(
                            "SELECT id, sku, name FROM products WHERE id = $1",
                            line["product_id"],
                        )
                        if not product:
                            return {"error": f"Product not found: {line['product_id']}"}

                        qty = float(line["quantity"])
                        unit_cost = float(line["unit_cost"])
                        line_total = round(qty * unit_cost, 2)
                        subtotal += line_total

                        await conn.execute(
                            """
                            INSERT INTO purchase_order_lines
                                (id, purchase_order_id, line_number, product_id,
                                 sku, description, quantity_ordered, unit_cost, line_total)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                            """,
                            str(uuid.uuid4()), po_id, idx,
                            line["product_id"], product["sku"], product["name"],
                            qty, unit_cost, line_total,
                        )

                    total_amount = subtotal

                    await conn.execute(
                        """
                        INSERT INTO purchase_orders
                            (id, po_number, supplier_id, status, expected_date,
                             subtotal, total_amount, notes, created_by)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        po_id, po_number, data["supplier_id"], "draft",
                        data.get("expected_date"), subtotal, total_amount,
                        data.get("notes"), created_by,
                    )

            self.logger.info(f"PO created: {po_number} (${total_amount:,.2f})")
            return await self.get_purchase_order(po_id)

        except Exception as e:
            self.logger.error(f"Failed to create PO: {e}")
            return {"error": str(e)}

    async def get_purchase_order(self, po_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT po.*, s.name as supplier_name
                    FROM purchase_orders po
                    JOIN suppliers s ON s.id = po.supplier_id
                    WHERE po.id = $1
                    """,
                    po_id,
                )
                if not row:
                    return None

                result = dict(row)
                result["id"] = str(result["id"])
                result["supplier_id"] = str(result["supplier_id"])
                for key in ("subtotal", "tax_amount", "shipping_amount", "total_amount"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("order_date", "approved_at", "created_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                if result.get("expected_date"):
                    result["expected_date"] = result["expected_date"].isoformat()

                lines = await conn.fetch(
                    """
                    SELECT pol.*, p.name as product_name
                    FROM purchase_order_lines pol
                    JOIN products p ON p.id = pol.product_id
                    WHERE pol.purchase_order_id = $1
                    ORDER BY pol.line_number
                    """,
                    po_id,
                )
                result["lines"] = []
                for line in lines:
                    d = dict(line)
                    d["id"] = str(d["id"])
                    d["purchase_order_id"] = str(d["purchase_order_id"])
                    d["product_id"] = str(d["product_id"])
                    for key in ("quantity_ordered", "quantity_received", "unit_cost", "line_total"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    result["lines"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get PO: {e}")
            return None

    async def list_purchase_orders(self, supplier_id: Optional[str] = None,
                                   status: Optional[str] = None,
                                   page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if supplier_id:
            conditions.append(f"po.supplier_id = ${idx}")
            params.append(supplier_id)
            idx += 1
        if status:
            conditions.append(f"po.status = ${idx}")
            params.append(status)
            idx += 1

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"""SELECT COUNT(*) as cnt FROM purchase_orders po
                        JOIN suppliers s ON s.id = po.supplier_id {where}""",
                    *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT po.id, po.po_number, po.supplier_id, s.name as supplier_name,
                           po.status, po.total_amount, po.expected_date, po.order_date
                    FROM purchase_orders po
                    JOIN suppliers s ON s.id = po.supplier_id
                    {where}
                    ORDER BY po.order_date DESC
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["supplier_id"] = str(d["supplier_id"])
                    if d.get("total_amount") is not None:
                        d["total_amount"] = float(d["total_amount"])
                    for key in ("order_date",):
                        if d.get(key):
                            d[key] = d[key].isoformat()
                    if d.get("expected_date"):
                        d["expected_date"] = d["expected_date"].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list POs: {e}")
            return [], 0

    async def submit_po(self, po_id: str) -> Optional[Dict[str, Any]]:
        return await self._update_po_status(po_id, "submitted", valid_from="draft")

    async def confirm_po(self, po_id: str) -> Optional[Dict[str, Any]]:
        return await self._update_po_status(po_id, "confirmed", valid_from="submitted")

    async def cancel_po(self, po_id: str) -> Optional[Dict[str, Any]]:
        po = await self.get_purchase_order(po_id)
        if not po:
            return {"error": "PO not found"}
        if po["status"] in ("received", "cancelled"):
            return {"error": f"Cannot cancel PO in '{po['status']}' status"}
        return await self._update_po_status(po_id, "cancelled")

    # ------------------------------------------------------------------
    # Goods Receipt
    # ------------------------------------------------------------------

    async def receive_goods(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Record goods receipt against a PO.
        Updates PO line received quantities and inventory.
        """
        if not self.db.pool:
            return None

        po = await self.get_purchase_order(data["purchase_order_id"])
        if not po:
            return {"error": "PO not found"}
        if po["status"] not in ("confirmed", "partial_received"):
            return {"error": f"Cannot receive goods for PO in '{po['status']}' status"}

        receipt_id = str(uuid.uuid4())
        receipt_number = await self._next_receipt_number()
        warehouse = data.get("warehouse_code", "MAIN")

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO goods_receipts
                            (id, receipt_number, purchase_order_id, received_by,
                             warehouse_code, notes)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        """,
                        receipt_id, receipt_number, data["purchase_order_id"],
                        data.get("received_by"), warehouse, data.get("notes"),
                    )

                    for line_data in data.get("lines", []):
                        po_line_id = line_data["po_line_id"]
                        qty_received = float(line_data["quantity_received"])
                        qty_rejected = float(line_data.get("quantity_rejected", 0))
                        qty_accepted = qty_received - qty_rejected

                        # Get product_id from PO line
                        po_line = await conn.fetchrow(
                            "SELECT product_id FROM purchase_order_lines WHERE id = $1",
                            po_line_id,
                        )
                        if not po_line:
                            continue

                        product_id = str(po_line["product_id"])

                        await conn.execute(
                            """
                            INSERT INTO goods_receipt_lines
                                (id, receipt_id, po_line_id, product_id,
                                 quantity_received, quantity_accepted,
                                 quantity_rejected, rejection_reason, bin_location)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                            """,
                            str(uuid.uuid4()), receipt_id, po_line_id,
                            product_id, qty_received, qty_accepted,
                            qty_rejected, line_data.get("rejection_reason"),
                            line_data.get("bin_location"),
                        )

                        # Update PO line received quantity
                        await conn.execute(
                            """
                            UPDATE purchase_order_lines
                            SET quantity_received = quantity_received + $1
                            WHERE id = $2
                            """,
                            qty_accepted, po_line_id,
                        )

                        # Update inventory
                        if qty_accepted > 0:
                            await self.inventory.receive_stock(
                                product_id, warehouse, qty_accepted,
                                data["purchase_order_id"],
                                line_data.get("bin_location"),
                            )

                    # Check if PO is fully received
                    remaining = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM purchase_order_lines
                        WHERE purchase_order_id = $1
                          AND quantity_received < quantity_ordered
                        """,
                        data["purchase_order_id"],
                    )

                    new_status = "received" if remaining == 0 else "partial_received"
                    await conn.execute(
                        "UPDATE purchase_orders SET status = $1, updated_at = NOW() WHERE id = $2",
                        new_status, data["purchase_order_id"],
                    )

            self.logger.info(f"Goods received: {receipt_number} for PO {po['po_number']}")
            return {
                "receipt_id": receipt_id,
                "receipt_number": receipt_number,
                "purchase_order_id": data["purchase_order_id"],
                "po_number": po["po_number"],
                "po_status": new_status,
                "warehouse_code": warehouse,
            }

        except Exception as e:
            self.logger.error(f"Goods receipt failed: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Auto-PO from Reorder Alerts
    # ------------------------------------------------------------------

    async def auto_generate_pos(self, warehouse_code: str = "MAIN") -> List[Dict[str, Any]]:
        """
        Generate purchase orders for items below reorder point,
        grouped by preferred supplier.
        """
        alerts = await self.inventory.get_reorder_alerts(warehouse_code)
        if not alerts:
            return []

        # Group by preferred supplier
        supplier_items: Dict[str, List[Dict[str, Any]]] = {}
        for alert in alerts:
            supplier = alert.get("preferred_supplier", "UNASSIGNED")
            if supplier not in supplier_items:
                supplier_items[supplier] = []
            supplier_items[supplier].append(alert)

        created_pos = []
        for supplier_name, items in supplier_items.items():
            if supplier_name == "UNASSIGNED":
                continue

            # Look up supplier
            if not self.db.pool:
                continue
            try:
                async with self.db.pool.acquire() as conn:
                    supplier_row = await conn.fetchrow(
                        "SELECT id FROM suppliers WHERE name = $1 AND is_active = TRUE",
                        supplier_name,
                    )
                    if not supplier_row:
                        continue

                    supplier_id = str(supplier_row["id"])

                    # Build PO lines
                    lines = []
                    for item in items:
                        # Get supplier price
                        sp = await conn.fetchrow(
                            """SELECT supplier_price FROM supplier_products
                               WHERE supplier_id = $1 AND product_id = $2""",
                            supplier_id, item["product_id"],
                        )
                        unit_cost = float(sp["supplier_price"]) if sp and sp["supplier_price"] else 0
                        if unit_cost == 0:
                            continue

                        lines.append({
                            "product_id": item["product_id"],
                            "quantity": item.get("reorder_qty", 100),
                            "unit_cost": unit_cost,
                        })

                    if lines:
                        po = await self.create_purchase_order({
                            "supplier_id": supplier_id,
                            "notes": "Auto-generated from reorder alerts",
                            "lines": lines,
                        })
                        if po and not po.get("error"):
                            created_pos.append(po)

            except Exception as e:
                self.logger.error(f"Auto-PO generation error: {e}")

        return created_pos

    async def _update_po_status(self, po_id: str, new_status: str,
                                valid_from: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                if valid_from:
                    row = await conn.fetchrow(
                        "SELECT status FROM purchase_orders WHERE id = $1", po_id,
                    )
                    if not row or row["status"] != valid_from:
                        return {"error": f"PO must be in '{valid_from}' status"}

                await conn.execute(
                    "UPDATE purchase_orders SET status = $1, updated_at = NOW() WHERE id = $2",
                    new_status, po_id,
                )
            return await self.get_purchase_order(po_id)
        except Exception as e:
            self.logger.error(f"Failed to update PO status: {e}")
            return None
