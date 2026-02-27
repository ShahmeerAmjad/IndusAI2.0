# =======================
# Inventory Management Service
# =======================

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class InventoryService:
    """Manages inventory: stock levels, reservations, adjustments, transfers, reorder alerts."""

    def __init__(self, db_manager, logger, graph_sync=None):
        self.db = db_manager
        self.logger = logger
        self._graph_sync = graph_sync

    # ------------------------------------------------------------------
    # Stock Queries
    # ------------------------------------------------------------------

    async def get_stock(self, product_id: str, warehouse_code: str = "MAIN") -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT i.product_id, p.sku, p.name as product_name,
                           i.warehouse_code, i.quantity_on_hand, i.quantity_reserved,
                           (i.quantity_on_hand - i.quantity_reserved) as quantity_available,
                           i.quantity_on_order, i.reorder_point, i.reorder_qty,
                           i.safety_stock, i.bin_location, i.last_counted_at, i.updated_at
                    FROM inventory i
                    JOIN products p ON p.id = i.product_id
                    WHERE i.product_id = $1 AND i.warehouse_code = $2
                    """,
                    product_id, warehouse_code,
                )
                if not row:
                    return None
                result = dict(row)
                result["product_id"] = str(result["product_id"])
                for key in ("quantity_on_hand", "quantity_reserved", "quantity_available",
                            "quantity_on_order", "reorder_point", "reorder_qty", "safety_stock"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("last_counted_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                return result
        except Exception as e:
            self.logger.error(f"Failed to get stock: {e}")
            return None

    async def get_stock_by_sku(self, sku: str, warehouse_code: str = "MAIN") -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM products WHERE sku = $1", sku,
                )
                if row:
                    return await self.get_stock(str(row["id"]), warehouse_code)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get stock by SKU: {e}")
            return None

    async def get_all_stock(self, warehouse_code: Optional[str] = None,
                            low_stock_only: bool = False,
                            page: int = 1, page_size: int = 50) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if warehouse_code:
            conditions.append(f"i.warehouse_code = ${idx}")
            params.append(warehouse_code)
            idx += 1

        if low_stock_only:
            conditions.append(
                "(i.quantity_on_hand - i.quantity_reserved) <= COALESCE(i.reorder_point, 0)"
            )

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"""SELECT COUNT(*) as cnt FROM inventory i
                        JOIN products p ON p.id = i.product_id {where}""",
                    *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT i.product_id, p.sku, p.name as product_name,
                           i.warehouse_code, i.quantity_on_hand, i.quantity_reserved,
                           (i.quantity_on_hand - i.quantity_reserved) as quantity_available,
                           i.quantity_on_order, i.reorder_point, i.bin_location
                    FROM inventory i
                    JOIN products p ON p.id = i.product_id
                    {where}
                    ORDER BY p.sku
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )

                items = []
                for row in rows:
                    d = dict(row)
                    d["product_id"] = str(d["product_id"])
                    for key in ("quantity_on_hand", "quantity_reserved",
                                "quantity_available", "quantity_on_order", "reorder_point"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to get all stock: {e}")
            return [], 0

    # ------------------------------------------------------------------
    # Stock Mutations
    # ------------------------------------------------------------------

    async def adjust_stock(self, product_id: str, warehouse_code: str,
                           qty: float, reason: str,
                           created_by: str = "system") -> bool:
        """Adjust quantity on hand (positive = add, negative = subtract)."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO inventory (id, product_id, warehouse_code, quantity_on_hand)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (product_id, warehouse_code) DO UPDATE
                            SET quantity_on_hand = inventory.quantity_on_hand + $4,
                                updated_at = NOW()
                        """,
                        str(uuid.uuid4()), product_id, warehouse_code, qty,
                    )
                    await self._record_transaction(
                        conn, product_id, warehouse_code,
                        "adjustment", qty, "adjustment", None, reason, created_by,
                    )
            if self._graph_sync:
                try:
                    stock = await self.get_stock(product_id, warehouse_code)
                    if stock:
                        await self._graph_sync.sync_inventory(
                            stock["sku"], warehouse_code,
                            int(stock.get("quantity_on_hand", 0)),
                        )
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for inventory: %s", sync_err)
            return True
        except Exception as e:
            self.logger.error(f"Stock adjustment failed: {e}")
            return False

    async def reserve_stock(self, product_id: str, warehouse_code: str,
                            qty: float, order_id: str) -> bool:
        """Reserve stock for an order. Checks availability first."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT quantity_on_hand, quantity_reserved
                        FROM inventory
                        WHERE product_id = $1 AND warehouse_code = $2
                        FOR UPDATE
                        """,
                        product_id, warehouse_code,
                    )
                    if not row:
                        self.logger.warning(f"No inventory record for {product_id} in {warehouse_code}")
                        return False

                    available = float(row["quantity_on_hand"]) - float(row["quantity_reserved"])
                    if available < qty:
                        self.logger.warning(
                            f"Insufficient stock: need {qty}, available {available}"
                        )
                        return False

                    await conn.execute(
                        """
                        UPDATE inventory
                        SET quantity_reserved = quantity_reserved + $1, updated_at = NOW()
                        WHERE product_id = $2 AND warehouse_code = $3
                        """,
                        qty, product_id, warehouse_code,
                    )
                    await self._record_transaction(
                        conn, product_id, warehouse_code,
                        "reservation", qty, "order", order_id,
                        f"Reserved for order {order_id}", "system",
                    )
            return True
        except Exception as e:
            self.logger.error(f"Stock reservation failed: {e}")
            return False

    async def release_reservation(self, product_id: str, warehouse_code: str,
                                  qty: float, order_id: str) -> bool:
        """Release previously reserved stock."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE inventory
                        SET quantity_reserved = GREATEST(quantity_reserved - $1, 0),
                            updated_at = NOW()
                        WHERE product_id = $2 AND warehouse_code = $3
                        """,
                        qty, product_id, warehouse_code,
                    )
                    await self._record_transaction(
                        conn, product_id, warehouse_code,
                        "release", -qty, "order", order_id,
                        f"Released reservation for order {order_id}", "system",
                    )
            return True
        except Exception as e:
            self.logger.error(f"Release reservation failed: {e}")
            return False

    async def ship_stock(self, product_id: str, warehouse_code: str,
                         qty: float, order_id: str) -> bool:
        """Deduct shipped quantity from on-hand and reserved."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE inventory
                        SET quantity_on_hand = quantity_on_hand - $1,
                            quantity_reserved = GREATEST(quantity_reserved - $1, 0),
                            updated_at = NOW()
                        WHERE product_id = $2 AND warehouse_code = $3
                        """,
                        qty, product_id, warehouse_code,
                    )
                    await self._record_transaction(
                        conn, product_id, warehouse_code,
                        "shipment", -qty, "order", order_id,
                        f"Shipped for order {order_id}", "system",
                    )
            return True
        except Exception as e:
            self.logger.error(f"Ship stock failed: {e}")
            return False

    async def receive_stock(self, product_id: str, warehouse_code: str,
                            qty: float, po_id: str,
                            bin_location: Optional[str] = None) -> bool:
        """Receive stock from a purchase order."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    update_bin = ", bin_location = $4" if bin_location else ""
                    params: list = [qty, product_id, warehouse_code]
                    if bin_location:
                        params.append(bin_location)

                    await conn.execute(
                        f"""
                        INSERT INTO inventory (id, product_id, warehouse_code, quantity_on_hand, bin_location)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (product_id, warehouse_code) DO UPDATE
                            SET quantity_on_hand = inventory.quantity_on_hand + EXCLUDED.quantity_on_hand,
                                bin_location = COALESCE(EXCLUDED.bin_location, inventory.bin_location),
                                updated_at = NOW()
                        """,
                        str(uuid.uuid4()), product_id, warehouse_code, qty, bin_location,
                    )
                    await self._record_transaction(
                        conn, product_id, warehouse_code,
                        "receipt", qty, "po", po_id,
                        f"Received from PO {po_id}", "system",
                    )
            if self._graph_sync:
                try:
                    stock = await self.get_stock(product_id, warehouse_code)
                    if stock:
                        await self._graph_sync.sync_inventory(
                            stock["sku"], warehouse_code,
                            int(stock.get("quantity_on_hand", 0)),
                        )
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for received stock: %s", sync_err)
            return True
        except Exception as e:
            self.logger.error(f"Receive stock failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Reorder Alerts
    # ------------------------------------------------------------------

    async def get_reorder_alerts(self, warehouse_code: str = "MAIN") -> List[Dict[str, Any]]:
        """Get products below reorder point."""
        if not self.db.pool:
            return []
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT i.product_id, p.sku, p.name as product_name,
                           i.warehouse_code,
                           (i.quantity_on_hand - i.quantity_reserved) as quantity_available,
                           i.reorder_point, i.reorder_qty,
                           sp.name as preferred_supplier,
                           sp_prod.lead_time_days as supplier_lead_time_days
                    FROM inventory i
                    JOIN products p ON p.id = i.product_id
                    LEFT JOIN supplier_products sp_prod ON sp_prod.product_id = p.id AND sp_prod.is_preferred = TRUE
                    LEFT JOIN suppliers sp ON sp.id = sp_prod.supplier_id
                    WHERE i.warehouse_code = $1
                      AND i.reorder_point IS NOT NULL
                      AND (i.quantity_on_hand - i.quantity_reserved) <= i.reorder_point
                    ORDER BY (i.quantity_on_hand - i.quantity_reserved) ASC
                    """,
                    warehouse_code,
                )
                results = []
                for row in rows:
                    d = dict(row)
                    d["product_id"] = str(d["product_id"])
                    for key in ("quantity_available", "reorder_point", "reorder_qty"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    results.append(d)
                return results
        except Exception as e:
            self.logger.error(f"Failed to get reorder alerts: {e}")
            return []

    # ------------------------------------------------------------------
    # Transaction History
    # ------------------------------------------------------------------

    async def get_transactions(self, product_id: str,
                               limit: int = 50) -> List[Dict[str, Any]]:
        if not self.db.pool:
            return []
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, product_id, warehouse_code, transaction_type,
                           quantity, reference_type, reference_id, notes,
                           created_by, created_at
                    FROM inventory_transactions
                    WHERE product_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    product_id, limit,
                )
                results = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["product_id"] = str(d["product_id"])
                    if d.get("reference_id"):
                        d["reference_id"] = str(d["reference_id"])
                    if d.get("quantity") is not None:
                        d["quantity"] = float(d["quantity"])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    results.append(d)
                return results
        except Exception as e:
            self.logger.error(f"Failed to get inventory transactions: {e}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _record_transaction(conn, product_id, warehouse_code,
                                  txn_type, qty, ref_type, ref_id,
                                  notes, created_by):
        await conn.execute(
            """
            INSERT INTO inventory_transactions
                (id, product_id, warehouse_code, transaction_type, quantity,
                 reference_type, reference_id, notes, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            str(uuid.uuid4()), product_id, warehouse_code,
            txn_type, qty, ref_type, ref_id, notes, created_by,
        )
