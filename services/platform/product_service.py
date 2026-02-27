# =======================
# Product Catalog Service
# =======================

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple


class ProductService:
    """Manages the product catalog — CRUD, search, specs, cross-references."""

    def __init__(self, db_manager, erp_connector, logger, graph_sync=None):
        self.db = db_manager
        self.erp = erp_connector
        self.logger = logger
        self._graph_sync = graph_sync

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_product(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            product_id = str(uuid.uuid4())
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO products
                        (id, sku, name, description, category, subcategory,
                         manufacturer, manufacturer_part_number, uom, weight_lbs,
                         min_order_qty, lead_time_days, hazmat, country_of_origin)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                    """,
                    product_id, data["sku"], data["name"],
                    data.get("description"), data.get("category"),
                    data.get("subcategory"), data.get("manufacturer"),
                    data.get("manufacturer_part_number"),
                    data.get("uom", "EA"), data.get("weight_lbs"),
                    data.get("min_order_qty", 1), data.get("lead_time_days"),
                    data.get("hazmat", False), data.get("country_of_origin"),
                )
            product = await self.get_product(product_id)
            if self._graph_sync and product:
                try:
                    await self._graph_sync.sync_product(product)
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for new product: %s", sync_err)
            return product
        except Exception as e:
            self.logger.error(f"Failed to create product: {e}")
            return None

    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, sku, name, description, category, subcategory,
                           manufacturer, manufacturer_part_number, uom, weight_lbs,
                           is_active, min_order_qty, lead_time_days, hazmat,
                           country_of_origin, created_at, updated_at
                    FROM products WHERE id = $1
                    """,
                    product_id,
                )
                if not row:
                    return None

                product = dict(row)
                product["id"] = str(product["id"])
                for key in ("created_at", "updated_at"):
                    if product.get(key):
                        product[key] = product[key].isoformat()
                if product.get("weight_lbs"):
                    product["weight_lbs"] = float(product["weight_lbs"])

                # Fetch specs
                specs = await conn.fetch(
                    "SELECT spec_name, spec_value, spec_unit FROM product_specs WHERE product_id = $1",
                    product_id,
                )
                product["specs"] = [
                    {"name": s["spec_name"], "value": s["spec_value"], "unit": s["spec_unit"]}
                    for s in specs
                ]

                # Fetch cross-references
                xrefs = await conn.fetch(
                    """SELECT cross_ref_type, cross_ref_sku, manufacturer, notes
                       FROM product_cross_references WHERE product_id = $1""",
                    product_id,
                )
                product["cross_references"] = [dict(x) for x in xrefs]

                return product
        except Exception as e:
            self.logger.error(f"Failed to get product: {e}")
            return None

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM products WHERE sku = $1", sku,
                )
                if row:
                    return await self.get_product(str(row["id"]))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get product by SKU: {e}")
            return None

    async def update_product(self, product_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        # Build dynamic SET clause from non-None fields
        fields = []
        values = []
        idx = 1
        for key in ("name", "description", "category", "subcategory",
                     "manufacturer", "manufacturer_part_number", "uom",
                     "weight_lbs", "min_order_qty", "lead_time_days",
                     "hazmat", "country_of_origin", "is_active"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = ${idx}")
                values.append(data[key])
                idx += 1

        if not fields:
            return await self.get_product(product_id)

        fields.append(f"updated_at = NOW()")
        values.append(product_id)
        query = f"UPDATE products SET {', '.join(fields)} WHERE id = ${idx}"

        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(query, *values)
            product = await self.get_product(product_id)
            if self._graph_sync and product:
                try:
                    await self._graph_sync.sync_product(product)
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for updated product: %s", sync_err)
            return product
        except Exception as e:
            self.logger.error(f"Failed to update product: {e}")
            return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        manufacturer: Optional[str] = None,
        in_stock: Optional[bool] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search products with filters. Returns (items, total_count)."""
        if not self.db.pool:
            return [], 0

        conditions = ["p.is_active = TRUE"]
        params: list = []
        idx = 1

        if query:
            conditions.append(
                f"(p.sku ILIKE ${idx} OR p.name ILIKE ${idx} "
                f"OR p.description ILIKE ${idx} OR p.manufacturer ILIKE ${idx})"
            )
            params.append(f"%{query}%")
            idx += 1

        if category:
            conditions.append(f"p.category = ${idx}")
            params.append(category)
            idx += 1

        if manufacturer:
            conditions.append(f"p.manufacturer ILIKE ${idx}")
            params.append(f"%{manufacturer}%")
            idx += 1

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        # Join inventory if filtering by stock
        join = ""
        if in_stock is True:
            join = """
                INNER JOIN inventory inv ON inv.product_id = p.id
                    AND (inv.quantity_on_hand - inv.quantity_reserved) > 0
            """
        elif in_stock is False:
            join = """
                LEFT JOIN inventory inv ON inv.product_id = p.id
            """
            conditions.append(
                "(inv.id IS NULL OR (inv.quantity_on_hand - inv.quantity_reserved) <= 0)"
            )
            where = " AND ".join(conditions)

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(DISTINCT p.id) as cnt FROM products p {join} WHERE {where}",
                    *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT DISTINCT p.id, p.sku, p.name, p.category, p.subcategory,
                           p.manufacturer, p.uom, p.is_active, p.lead_time_days,
                           p.created_at
                    FROM products p {join}
                    WHERE {where}
                    ORDER BY p.name
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )

                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    items.append(d)

                return items, total
        except Exception as e:
            self.logger.error(f"Product search failed: {e}")
            return [], 0

    # ------------------------------------------------------------------
    # Specs & Cross-References
    # ------------------------------------------------------------------

    async def add_spec(self, product_id: str, spec_name: str, spec_value: str,
                       spec_unit: Optional[str] = None) -> bool:
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO product_specs (id, product_id, spec_name, spec_value, spec_unit)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    str(uuid.uuid4()), product_id, spec_name, spec_value, spec_unit,
                )
            return True
        except Exception as e:
            self.logger.error(f"Failed to add spec: {e}")
            return False

    async def add_cross_reference(self, product_id: str, cross_ref_type: str,
                                  cross_ref_sku: str, manufacturer: Optional[str] = None,
                                  notes: Optional[str] = None) -> bool:
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO product_cross_references
                        (id, product_id, cross_ref_type, cross_ref_sku, manufacturer, notes)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    str(uuid.uuid4()), product_id, cross_ref_type,
                    cross_ref_sku, manufacturer, notes,
                )
            return True
        except Exception as e:
            self.logger.error(f"Failed to add cross-reference: {e}")
            return False

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all product categories with counts."""
        if not self.db.pool:
            return []
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT category, subcategory, COUNT(*) as product_count
                    FROM products WHERE is_active = TRUE AND category IS NOT NULL
                    GROUP BY category, subcategory
                    ORDER BY category, subcategory
                    """
                )
                return [dict(r) for r in rows]
        except Exception as e:
            self.logger.error(f"Failed to get categories: {e}")
            return []
