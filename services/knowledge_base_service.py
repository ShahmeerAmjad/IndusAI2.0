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

    async def get_graph_visualization(self, industry=None, manufacturer=None, limit=100):
        """Query Neo4j for nodes and edges, formatted for Neovis.js."""
        conditions = []
        params = {"limit": limit}

        if industry:
            conditions.append("(p)-[:SERVES_INDUSTRY]->(:Industry {name: $industry})")
            params["industry"] = industry
        if manufacturer:
            conditions.append("p.manufacturer = $manufacturer")
            params["manufacturer"] = manufacturer

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cypher = f"""
        MATCH (p:Part)
        {where}
        OPTIONAL MATCH (p)-[:HAS_TDS]->(t:TechnicalDataSheet)
        OPTIONAL MATCH (p)-[:HAS_SDS]->(s:SafetyDataSheet)
        OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(pl:ProductLine)
        OPTIONAL MATCH (pl)-[:MADE_BY]->(m:Manufacturer)
        RETURN p, t, s, i, pl, m
        LIMIT $limit
        """

        results = await self._graph.execute_read(cypher, params)

        nodes = {}
        edges = []

        for record in results:
            for key, label, color in [
                ("p", "Product", "#1e3a8a"),
                ("t", "TDS", "#7c3aed"),
                ("s", "SDS", "#dc2626"),
                ("i", "Industry", "#f59e0b"),
                ("pl", "ProductLine", "#0d9488"),
                ("m", "Manufacturer", "#059669"),
            ]:
                node = record.get(key)
                if node:
                    node_id = f"{label}:{node.get('sku') or node.get('name') or node.get('product_sku', '')}"
                    if node_id not in nodes:
                        nodes[node_id] = {
                            "id": node_id, "label": label,
                            "name": node.get("name") or node.get("sku") or node.get("product_sku", ""),
                            "color": color, "properties": dict(node),
                        }

        for record in results:
            p_id = f"Product:{record.get('p', {}).get('sku', '')}" if record.get("p") else None
            if not p_id:
                continue
            for key, label, rel in [
                ("t", "TDS", "HAS_TDS"), ("s", "SDS", "HAS_SDS"),
                ("i", "Industry", "SERVES_INDUSTRY"), ("pl", "ProductLine", "BELONGS_TO"),
            ]:
                target = record.get(key)
                if target:
                    t_id = f"{label}:{target.get('name') or target.get('product_sku', '')}"
                    edges.append({"source": p_id, "target": t_id, "relationship": rel})
            if record.get("pl") and record.get("m"):
                pl_id = f"ProductLine:{record['pl'].get('name', '')}"
                m_id = f"Manufacturer:{record['m'].get('name', '')}"
                edges.append({"source": pl_id, "target": m_id, "relationship": "MADE_BY"})

        return {"nodes": list(nodes.values()), "edges": edges}

    async def list_products(self, page: int = 1, page_size: int = 25,
                            search: str | None = None,
                            manufacturer: str | None = None,
                            industry: str | None = None,
                            has_tds: bool | None = None,
                            has_sds: bool | None = None) -> dict:
        """List Part nodes with optional search, manufacturer, industry, and doc filters."""
        skip = (page - 1) * page_size
        params: dict = {"skip": skip, "limit": page_size}

        conditions = []
        if search:
            conditions.append(
                "(toLower(p.name) CONTAINS toLower($search)"
                " OR toLower(p.sku) CONTAINS toLower($search)"
                " OR toLower(p.cas_number) CONTAINS toLower($search))"
            )
            params["search"] = search
        if manufacturer:
            conditions.append("m.name = $manufacturer")
            params["manufacturer"] = manufacturer
        if industry:
            conditions.append("i.name = $industry")
            params["industry"] = industry

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        having = []
        if has_tds is True:
            having.append("has_tds = true")
        elif has_tds is False:
            having.append("has_tds = false")
        if has_sds is True:
            having.append("has_sds = true")
        elif has_sds is False:
            having.append("has_sds = false")
        having_clause = f"WHERE {' AND '.join(having)}" if having else ""

        base = f"""
        MATCH (p:Part)
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
        OPTIONAL MATCH (p)-[:HAS_TDS]->(t:TechnicalDataSheet)
        OPTIONAL MATCH (p)-[:HAS_SDS]->(s:SafetyDataSheet)
        {where}
        WITH p, m.name AS manufacturer,
             collect(DISTINCT i.name) AS industries,
             count(DISTINCT t) > 0 AS has_tds,
             count(DISTINCT s) > 0 AS has_sds
        {having_clause}
        """

        count_query = base + "\nRETURN count(p) AS total"
        count_params = {k: v for k, v in params.items() if k not in ("skip", "limit")}
        count_result = await self._graph.execute_read(count_query, count_params)
        total = count_result[0]["total"] if count_result else 0

        data_query = base + """
        RETURN p {.*} AS product, manufacturer, industries, has_tds, has_sds
        ORDER BY p.name
        SKIP $skip LIMIT $limit
        """
        results = await self._graph.execute_read(data_query, params)

        items = []
        for row in results:
            item = dict(row["product"])
            item["manufacturer"] = row.get("manufacturer")
            item["industries"] = row.get("industries", [])
            item["has_tds"] = row.get("has_tds", False)
            item["has_sds"] = row.get("has_sds", False)
            items.append(item)

        return {"items": items, "page": page, "page_size": page_size, "total": total}

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
                       WHERE product_id = $1 AND is_current = true
                       ORDER BY created_at DESC""",
                    product_id,
                )
                for doc in docs:
                    if doc["doc_type"] == "TDS" and not product["tds_url"]:
                        product["tds_url"] = doc["source_url"]
                    elif doc["doc_type"] == "SDS" and not product["sds_url"]:
                        product["sds_url"] = doc["source_url"]

        return product

    async def get_filters(self) -> dict:
        """Return available filter values for the product catalog."""
        mfr_results = await self._graph.execute_read(
            "MATCH (m:Manufacturer) RETURN m.name AS name ORDER BY m.name", {}
        )
        ind_results = await self._graph.execute_read(
            "MATCH (i:Industry) RETURN i.name AS name ORDER BY i.name", {}
        )
        return {
            "manufacturers": [r["name"] for r in mfr_results],
            "industries": [r["name"] for r in ind_results],
        }

    async def get_product_extraction(self, sku: str) -> dict:
        """Return full TDS + SDS extracted fields for a product from Neo4j."""
        tds_results = await self._graph.execute_read(
            "MATCH (:Part {sku: $sku})-[:HAS_TDS]->(t:TechnicalDataSheet) RETURN t {.*} AS props",
            {"sku": sku},
        )
        sds_results = await self._graph.execute_read(
            "MATCH (:Part {sku: $sku})-[:HAS_SDS]->(s:SafetyDataSheet) RETURN s {.*} AS props",
            {"sku": sku},
        )

        tds_props = tds_results[0]["props"] if tds_results else {}
        sds_props = sds_results[0]["props"] if sds_results else {}

        tds_meta_keys = {"product_sku", "revision_date", "pdf_url"}
        sds_meta_keys = {"product_sku", "revision_date", "pdf_url", "cas_numbers"}

        tds_fields = {k: v for k, v in tds_props.items() if k not in tds_meta_keys}
        sds_fields = {k: v for k, v in sds_props.items() if k not in sds_meta_keys}

        return {
            "sku": sku,
            "tds": {
                "fields": tds_fields,
                "pdf_url": tds_props.get("pdf_url"),
                "revision_date": tds_props.get("revision_date"),
            },
            "sds": {
                "fields": sds_fields,
                "pdf_url": sds_props.get("pdf_url"),
                "revision_date": sds_props.get("revision_date"),
                "cas_numbers": sds_props.get("cas_numbers", []),
            },
        }
