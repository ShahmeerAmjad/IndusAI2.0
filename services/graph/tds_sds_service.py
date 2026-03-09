"""Neo4j graph operations for TDS/SDS nodes, Industry links, and pricing."""

import logging

logger = logging.getLogger(__name__)


class TDSSDSGraphService:
    def __init__(self, neo4j_client):
        self._neo4j = neo4j_client

    async def ensure_part(self, sku: str, name: str, manufacturer: str = "",
                          description: str = "") -> list:
        """Create or update a Part node with manufacturer edge."""
        cypher = """
        MERGE (p:Part {sku: $sku})
        SET p.name = $name, p.description = $desc
        WITH p
        FOREACH (_ IN CASE WHEN $mfr <> '' THEN [1] ELSE [] END |
            MERGE (m:Manufacturer {name: $mfr})
            MERGE (p)-[:MANUFACTURED_BY]->(m)
        )
        RETURN p.sku AS sku
        """
        return await self._neo4j.execute_write(
            cypher, {"sku": sku, "name": name, "mfr": manufacturer, "desc": description},
        )

    async def create_tds(self, product_sku: str, fields: dict) -> list:
        """Create or update a TechnicalDataSheet node linked to a Part."""
        revision_date = fields.pop("revision_date", "unknown")
        pdf_url = fields.pop("pdf_url", None)
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (t:TechnicalDataSheet {product_sku: $sku, revision_date: $rev})
        SET t += $props, t.pdf_url = $pdf_url
        MERGE (p)-[:HAS_TDS]->(t)
        RETURN t.product_sku AS id
        """
        return await self._neo4j.execute_write(
            cypher,
            {"sku": product_sku, "rev": revision_date,
             "props": fields, "pdf_url": pdf_url},
        )

    async def create_sds(self, product_sku: str, fields: dict) -> list:
        """Create or update a SafetyDataSheet node linked to a Part."""
        cas_numbers = fields.pop("cas_numbers", [])
        # Ensure cas_numbers is a flat list of strings (not dicts)
        if cas_numbers and isinstance(cas_numbers[0], dict):
            cas_numbers = [c.get("cas_number", str(c)) for c in cas_numbers]
        cas_numbers = [str(c) for c in cas_numbers if c]
        pdf_url = fields.pop("pdf_url", None)
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (s:SafetyDataSheet {product_sku: $sku, revision_date: $rev})
        SET s += $props, s.cas_numbers = $cas, s.pdf_url = $pdf_url
        MERGE (p)-[:HAS_SDS]->(s)
        RETURN s.product_sku AS id
        """
        return await self._neo4j.execute_write(
            cypher,
            {"sku": product_sku, "rev": fields.pop("revision_date", "unknown"),
             "props": fields, "cas": cas_numbers, "pdf_url": pdf_url},
        )

    async def link_product_to_industry(self, product_sku: str, industry_name: str) -> list:
        """Link a Part to an Industry node."""
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (i:Industry {name: $industry})
        MERGE (p)-[:SERVES_INDUSTRY]->(i)
        RETURN i.name AS industry
        """
        return await self._neo4j.execute_write(
            cypher, {"sku": product_sku, "industry": industry_name},
        )

    async def link_product_to_product_line(self, product_sku: str,
                                            line_name: str,
                                            manufacturer: str) -> list:
        """Link a Part to a ProductLine and Manufacturer."""
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (pl:ProductLine {name: $line})
        MERGE (m:Manufacturer {name: $mfr})
        MERGE (p)-[:BELONGS_TO]->(pl)
        MERGE (pl)-[:MADE_BY]->(m)
        RETURN pl.name AS product_line
        """
        return await self._neo4j.execute_write(
            cypher,
            {"sku": product_sku, "line": line_name, "mfr": manufacturer},
        )

    async def set_price(self, product_sku: str, price_data: dict) -> list:
        """Set a PricePoint for a Part."""
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (pp:PricePoint {product_sku: $sku})
        SET pp.unit_price = $unit_price,
            pp.currency = $currency,
            pp.uom = $uom,
            pp.min_qty = $min_qty
        MERGE (p)-[:PRICED_AT]->(pp)
        RETURN pp.unit_price AS price
        """
        return await self._neo4j.execute_write(
            cypher,
            {
                "sku": product_sku,
                "unit_price": price_data.get("unit_price"),
                "currency": price_data.get("currency", "USD"),
                "uom": price_data.get("uom", "ea"),
                "min_qty": price_data.get("min_qty", 1),
            },
        )

    async def set_inventory(self, product_sku: str, warehouse_code: str,
                            stock_data: dict) -> list:
        """Set inventory stock level for a Part at a Warehouse."""
        cypher = """
        MATCH (p:Part {sku: $sku})
        MERGE (w:Warehouse {code: $wh})
        MERGE (p)-[r:STOCKED_AT]->(w)
        SET r.qty = $qty, r.updated_at = datetime()
        RETURN r.qty AS qty
        """
        return await self._neo4j.execute_write(
            cypher,
            {"sku": product_sku, "wh": warehouse_code,
             "qty": stock_data.get("qty", 0)},
        )

    async def get_tds_properties(self, product_sku: str) -> dict:
        """Get TDS properties for a product."""
        cypher = """
        MATCH (p:Part {sku: $sku})-[:HAS_TDS]->(t:TechnicalDataSheet)
        RETURN t {.*} AS props
        """
        results = await self._neo4j.execute_read(cypher, {"sku": product_sku})
        if results:
            return results[0]
        return {}

    async def get_sds_properties(self, product_sku: str) -> dict:
        """Get SDS properties for a product."""
        cypher = """
        MATCH (p:Part {sku: $sku})-[:HAS_SDS]->(s:SafetyDataSheet)
        RETURN s {.*} AS props
        """
        results = await self._neo4j.execute_read(cypher, {"sku": product_sku})
        if results:
            return results[0]
        return {}

    async def find_products_by_industry(self, industry_name: str) -> list[dict]:
        """Find all products serving a given industry."""
        cypher = """
        MATCH (p:Part)-[:SERVES_INDUSTRY]->(i:Industry {name: $industry})
        RETURN p.sku AS sku, p.name AS name, p.manufacturer AS manufacturer
        """
        return await self._neo4j.execute_read(
            cypher, {"industry": industry_name},
        )
