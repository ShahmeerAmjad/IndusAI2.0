"""Seller service — manage seller profiles, warehouses, and listings."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SellerService:
    """CRUD for sellers, warehouses, and part listings."""

    def __init__(self, db_manager, logger=None):
        self._db = db_manager
        self._log = logger or logging.getLogger(__name__)

    async def create_seller(self, data: dict) -> dict | None:
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO seller_profiles (name, website, catalog_source, reliability_base)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id, name, website, catalog_source, reliability_base""",
                data["name"], data.get("website"), data.get("catalog_source", "manual"),
                data.get("reliability_base", 5.0),
            )
        return dict(row) if row else None

    async def get_seller(self, seller_id: str) -> dict | None:
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM seller_profiles WHERE id = $1", seller_id
            )
        return dict(row) if row else None

    async def upsert_listing(self, data: dict) -> dict | None:
        """Insert or update a seller listing. Dedup by (seller_id, sku, warehouse_id)."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO seller_listings
                   (seller_id, sku, part_sku, price, currency, qty_available,
                    warehouse_id, lead_time_days, reliability, source_type,
                    last_verified_at, stale_after)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now(), now() + interval '7 days')
                   ON CONFLICT (seller_id, sku, warehouse_id)
                   DO UPDATE SET price = $4, qty_available = $6,
                     lead_time_days = $8, reliability = $9,
                     last_verified_at = now(),
                     stale_after = now() + interval '7 days',
                     updated_at = now()
                   RETURNING id, seller_id, sku, part_sku, price, qty_available""",
                data["seller_id"], data["sku"], data.get("part_sku", data["sku"]),
                data["price"], data.get("currency", "USD"),
                data.get("qty_available", 0), data.get("warehouse_id"),
                data.get("lead_time_days", 3),
                data.get("reliability", 5.0), data.get("source_type", "manual"),
            )
        return dict(row) if row else None

    async def find_listings_for_parts(self, part_skus: list[str],
                                      min_qty: int = 1) -> list[dict]:
        """Find all seller listings for a set of part SKUs with sufficient stock."""
        if not part_skus:
            return []
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT sl.*, sp.name AS seller_name, sp.website AS seller_website,
                          l.lat, l.lng, l.city, l.state
                   FROM seller_listings sl
                   JOIN seller_profiles sp ON sp.id = sl.seller_id
                   LEFT JOIN seller_warehouses sw ON sw.id = sl.warehouse_id
                   LEFT JOIN locations l ON l.id = sw.location_id
                   WHERE sl.part_sku = ANY($1)
                     AND sl.qty_available >= $2
                   ORDER BY sl.price ASC""",
                part_skus, min_qty,
            )
        return [dict(r) for r in rows]

    async def get_stale_listings(self, limit: int = 100) -> list[dict]:
        """Get listings that need re-verification."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT sl.*, sp.name AS seller_name, sp.website
                   FROM seller_listings sl
                   JOIN seller_profiles sp ON sp.id = sl.seller_id
                   WHERE sl.stale_after < now()
                   ORDER BY sl.stale_after ASC
                   LIMIT $1""",
                limit,
            )
        return [dict(r) for r in rows]
