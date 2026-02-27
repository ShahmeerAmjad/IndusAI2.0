"""GraphSyncService — event-driven PostgreSQL-to-Neo4j synchronization."""

import logging

logger = logging.getLogger(__name__)


class GraphSyncService:
    """Syncs product, inventory, and pricing data from PostgreSQL to Neo4j.

    Designed to be called from platform service hooks on every CRUD operation.
    """

    def __init__(self, graph_service, embedding_client=None):
        self._graph = graph_service
        self._embeddings = embedding_client

    async def sync_product(self, product: dict) -> None:
        sku = product.get("sku", "")
        if not sku:
            return

        specs_dict = {}
        for spec in product.get("specs", []):
            if spec.get("name"):
                specs_dict[spec["name"]] = {
                    "value": spec.get("value", ""),
                    "unit": spec.get("unit", ""),
                }

        embedding = None
        if self._embeddings:
            try:
                embeddings = await self._embeddings.embed_parts([product])
                if embeddings:
                    embedding = embeddings[0]
            except Exception as e:
                logger.warning("Embedding generation failed for %s: %s", sku, e)

        try:
            await self._graph.upsert_part(
                sku=sku,
                name=product.get("name", ""),
                description=product.get("description", ""),
                category=product.get("category", ""),
                manufacturer=product.get("manufacturer", ""),
                specs=specs_dict if specs_dict else None,
                embedding=embedding,
            )
            logger.info("Synced product %s to Neo4j", sku)
        except Exception as e:
            logger.error("Failed to sync product %s to Neo4j: %s", sku, e)

    async def sync_inventory(self, sku: str, warehouse: str, qty_on_hand: int) -> None:
        try:
            await self._graph.update_inventory_cache(
                sku=sku, warehouse=warehouse, qty_on_hand=qty_on_hand,
            )
        except Exception as e:
            logger.error("Failed to sync inventory for %s: %s", sku, e)

    async def sync_price(self, sku: str, min_price: float, max_price: float) -> None:
        try:
            await self._graph.update_price_range(
                sku=sku, min_price=min_price, max_price=max_price,
            )
        except Exception as e:
            logger.error("Failed to sync price for %s: %s", sku, e)

    async def bulk_sync_products(self, db_manager) -> dict:
        if not db_manager.pool:
            return {"synced": 0, "error": "No database pool"}

        count = 0
        try:
            async with db_manager.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT p.sku, p.name, p.description, p.category,
                           p.manufacturer
                    FROM products p WHERE p.is_active = TRUE
                    """
                )
                for row in rows:
                    product = dict(row)
                    specs = await conn.fetch(
                        """SELECT spec_name AS name, spec_value AS value, spec_unit AS unit
                           FROM product_specs ps
                           JOIN products p ON p.id = ps.product_id
                           WHERE p.sku = $1""",
                        product["sku"],
                    )
                    product["specs"] = [dict(s) for s in specs]
                    await self.sync_product(product)
                    count += 1

            logger.info("Bulk sync complete: %d products", count)
            return {"synced": count}
        except Exception as e:
            logger.error("Bulk sync failed: %s", e)
            return {"synced": count, "error": str(e)}
