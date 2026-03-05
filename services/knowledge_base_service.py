"""Knowledge base service — ingests products into Neo4j and stores TDS/SDS URLs in PostgreSQL."""

import logging
import uuid

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Manages the product knowledge base backed by Neo4j (graph) and PostgreSQL (documents)."""

    def __init__(self, pool, graph_service, llm_router=None):
        """
        Args:
            pool: asyncpg connection pool (or None if PG unavailable).
            graph_service: Neo4j client with execute_write / execute_read.
            llm_router: optional LLM router (reserved for future enrichment).
        """
        self._pool = pool
        self._graph = graph_service
        self._llm = llm_router

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_product(self, product: dict) -> str:
        """Ingest a single product dict into Neo4j and store doc URLs in PG.

        Returns the generated SKU.
        """
        sku = product.get("sku") or f"CP-{uuid.uuid4().hex[:8].upper()}"
        name = product.get("name", "")
        cas_number = product.get("cas_number", "")
        description = product.get("description", "")
        manufacturer = product.get("manufacturer")
        product_line = product.get("product_line")
        industries = product.get("industries") or []
        tds_url = product.get("tds_url")
        sds_url = product.get("sds_url")

        # 1. MERGE the Part node (with manufacturer + product_line in one query)
        merge_query = """
        MERGE (p:Part {sku: $sku})
        SET p.name = $name, p.cas_number = $cas_number,
            p.description = $description, p.source = 'chempoint'
        """
        merge_parts = []
        merge_params: dict = {
            "sku": sku, "name": name,
            "cas_number": cas_number, "description": description,
        }

        if manufacturer:
            merge_parts.append("""
            WITH p
            MERGE (m:Manufacturer {name: $manufacturer})
            MERGE (p)-[:MANUFACTURED_BY]->(m)
            """)
            merge_params["manufacturer"] = manufacturer

        if product_line:
            merge_parts.append("""
            WITH p
            MERGE (pl:ProductLine {name: $product_line})
            MERGE (p)-[:BELONGS_TO]->(pl)
            """)
            merge_params["product_line"] = product_line

        full_query = merge_query + "\n".join(merge_parts) + "\nRETURN p"
        await self._graph.execute_write(full_query, merge_params)

        # 2. MERGE Industry nodes + relationships
        for industry in industries:
            await self._graph.execute_write(
                """
                MATCH (p:Part {sku: $sku})
                MERGE (i:Industry {name: $industry})
                MERGE (p)-[:SERVES_INDUSTRY]->(i)
                """,
                {"sku": sku, "industry": industry},
            )

        # 3. Store TDS/SDS URLs in PostgreSQL documents table
        if self._pool and (tds_url or sds_url):
            async with self._pool.acquire() as conn:
                if tds_url:
                    await conn.execute(
                        """INSERT INTO documents (doc_type, file_path, file_name, source_url)
                           VALUES ('TDS', $1, $2, $1)""",
                        tds_url, f"TDS_{name}",
                    )
                if sds_url:
                    await conn.execute(
                        """INSERT INTO documents (doc_type, file_path, file_name, source_url)
                           VALUES ('SDS', $1, $2, $1)""",
                        sds_url, f"SDS_{name}",
                    )

        logger.info("Ingested product %s (sku=%s)", name, sku)
        return sku

    async def ingest_batch(self, products: list[dict]) -> dict:
        """Ingest a list of products with per-item error handling.

        Returns dict with keys: total, ingested, errors.
        """
        if not products:
            return {"total": 0, "ingested": 0, "errors": []}

        ingested = 0
        errors: list[dict] = []

        for idx, product in enumerate(products):
            try:
                await self.ingest_product(product)
                ingested += 1
            except Exception as exc:
                logger.warning("Failed to ingest product %d: %s", idx, exc)
                errors.append({"index": idx, "name": product.get("name"), "error": str(exc)})

        return {"total": len(products), "ingested": ingested, "errors": errors}

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def list_products(self, page: int = 1, page_size: int = 25,
                            search: str | None = None) -> dict:
        """List Part nodes from Neo4j with optional search and pagination."""
        skip = (page - 1) * page_size
        params: dict = {"skip": skip, "limit": page_size}

        if search:
            query = """
            MATCH (p:Part)
            WHERE toLower(p.name) CONTAINS toLower($search)
               OR toLower(p.sku) CONTAINS toLower($search)
               OR toLower(p.cas_number) CONTAINS toLower($search)
            RETURN p {.*}
            ORDER BY p.name
            SKIP $skip LIMIT $limit
            """
            params["search"] = search
        else:
            query = """
            MATCH (p:Part)
            RETURN p {.*}
            ORDER BY p.name
            SKIP $skip LIMIT $limit
            """

        results = await self._graph.execute_read(query, params)
        items = [row["p"] for row in results]
        return {"items": items, "page": page, "page_size": page_size}

    async def get_product(self, product_id: str) -> dict | None:
        """Get a single product with manufacturer, product line, industries, and doc URLs."""
        query = """
        MATCH (p:Part {sku: $sku})
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(pl:ProductLine)
        OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
        RETURN p {.*},
               m.name AS manufacturer,
               pl.name AS product_line,
               collect(DISTINCT i.name) AS industries
        """
        results = await self._graph.execute_read(query, {"sku": product_id})
        if not results:
            return None

        row = results[0]
        product = dict(row["p"])
        product["manufacturer"] = row.get("manufacturer")
        product["product_line"] = row.get("product_line")
        product["industries"] = row.get("industries", [])

        # Fetch TDS/SDS URLs from PostgreSQL documents table
        product["tds_url"] = None
        product["sds_url"] = None
        if self._pool:
            async with self._pool.acquire() as conn:
                docs = await conn.fetch(
                    """SELECT doc_type, source_url FROM documents
                       WHERE file_name = $1 AND is_current = true
                       ORDER BY created_at DESC""",
                    product_id,
                )
                for doc in docs:
                    if doc["doc_type"] == "TDS" and not product["tds_url"]:
                        product["tds_url"] = doc["source_url"]
                    elif doc["doc_type"] == "SDS" and not product["sds_url"]:
                        product["sds_url"] = doc["source_url"]

        return product
