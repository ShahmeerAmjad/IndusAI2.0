"""Knowledge graph CRUD operations for MRO parts ontology."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class GraphService:
    """Wraps all Neo4j CRUD for the MRO knowledge graph ontology."""

    def __init__(self, neo4j_client):
        self._db = neo4j_client

    # ------------------------------------------------------------------
    # Parts
    # ------------------------------------------------------------------

    async def upsert_part(self, sku: str, name: str, description: str = "",
                          category: str = "", manufacturer: str = "",
                          specs: dict | None = None,
                          embedding: list[float] | None = None) -> dict:
        """Create or update a Part node with manufacturer and category edges."""
        params = {
            "sku": sku, "name": name, "description": description,
            "category": category, "manufacturer": manufacturer,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        query = """
        MERGE (p:Part {sku: $sku})
        SET p.name = $name, p.description = $description,
            p.updated_at = $updated_at
        WITH p
        FOREACH (_ IN CASE WHEN $manufacturer <> '' THEN [1] ELSE [] END |
            MERGE (m:Manufacturer {name: $manufacturer})
            MERGE (p)-[:MANUFACTURED_BY]->(m)
        )
        WITH p
        FOREACH (_ IN CASE WHEN $category <> '' THEN [1] ELSE [] END |
            MERGE (c:Category {name: $category})
            MERGE (p)-[:BELONGS_TO]->(c)
        )
        RETURN p {.*}
        """

        results = await self._db.execute_write(query, params)

        # Set embedding separately (can't use FOREACH for list property)
        if embedding:
            await self._db.execute_write(
                "MATCH (p:Part {sku: $sku}) SET p.embedding = $embedding",
                {"sku": sku, "embedding": embedding},
            )

        # Set specs
        if specs:
            await self.set_part_specs(sku, specs)

        return results[0]["p"] if results else {}

    async def get_part(self, sku: str) -> dict | None:
        """Get part with all relationships (specs, cross-refs, manufacturer)."""
        query = """
        MATCH (p:Part {sku: $sku})
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
        OPTIONAL MATCH (p)-[hs:HAS_SPEC]->(s:Specification)
        OPTIONAL MATCH (p)-[xref:EQUIVALENT_TO|ALTERNATIVE_TO|REPLACES|REPLACED_BY]-(other:Part)
        RETURN p {.*,
            manufacturer: m.name,
            category: c.name,
            specs: collect(DISTINCT {name: s.name, value: hs.value, unit: hs.unit}),
            cross_refs: collect(DISTINCT {sku: other.sku, name: other.name, type: type(xref)})
        }
        """
        results = await self._db.execute_read(query, {"sku": sku})
        if not results:
            return None
        part = results[0]["p"]
        # Clean up empty spec/xref entries from OPTIONAL MATCH
        if part.get("specs"):
            part["specs"] = [s for s in part["specs"] if s.get("name")]
        if part.get("cross_refs"):
            part["cross_refs"] = [x for x in part["cross_refs"] if x.get("sku")]
        return part

    async def search_parts_fulltext(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across sku, name, description."""
        cypher = """
        CALL db.index.fulltext.queryNodes("part_search", $query)
        YIELD node, score
        OPTIONAL MATCH (node)-[:MANUFACTURED_BY]->(m:Manufacturer)
        RETURN node {.*, manufacturer: m.name, score: score}
        ORDER BY score DESC
        LIMIT $limit
        """
        return await self._db.execute_read(cypher, {"query": query, "limit": limit})

    async def search_parts_vector(self, embedding: list[float], limit: int = 20,
                                  min_score: float = 0.5) -> list[dict]:
        """Vector similarity search on part embeddings."""
        cypher = """
        CALL db.index.vector.queryNodes("part_embedding", $limit, $embedding)
        YIELD node, score
        WHERE score >= $min_score
        OPTIONAL MATCH (node)-[:MANUFACTURED_BY]->(m:Manufacturer)
        RETURN node {.*, manufacturer: m.name, score: score}
        ORDER BY score DESC
        """
        return await self._db.execute_read(
            cypher, {"embedding": embedding, "limit": limit, "min_score": min_score}
        )

    # ------------------------------------------------------------------
    # Cross-References
    # ------------------------------------------------------------------

    async def add_cross_reference(self, sku_a: str, sku_b: str,
                                  ref_type: str = "EQUIVALENT_TO",
                                  confidence: float = 1.0,
                                  source: str = "manual") -> dict:
        """Create a cross-reference between two parts."""
        valid_types = {"EQUIVALENT_TO", "ALTERNATIVE_TO", "REPLACES", "REPLACED_BY"}
        if ref_type not in valid_types:
            raise ValueError(f"ref_type must be one of {valid_types}")

        query = f"""
        MATCH (a:Part {{sku: $sku_a}})
        MATCH (b:Part {{sku: $sku_b}})
        MERGE (a)-[r:{ref_type}]->(b)
        SET r.confidence = $confidence, r.source = $source,
            r.created_at = $now
        RETURN a.sku AS from_sku, b.sku AS to_sku, type(r) AS type
        """
        results = await self._db.execute_write(query, {
            "sku_a": sku_a, "sku_b": sku_b,
            "confidence": confidence, "source": source,
            "now": datetime.now(timezone.utc).isoformat(),
        })
        return results[0] if results else {}

    async def get_cross_references(self, sku: str,
                                   ref_types: list[str] | None = None) -> list[dict]:
        """Get all cross-references for a part."""
        if ref_types:
            type_filter = "|".join(ref_types)
            query = f"""
            MATCH (p:Part {{sku: $sku}})-[r:{type_filter}]-(other:Part)
            OPTIONAL MATCH (other)-[:MANUFACTURED_BY]->(m:Manufacturer)
            RETURN other {{.*, manufacturer: m.name,
                          ref_type: type(r), confidence: r.confidence}}
            """
        else:
            query = """
            MATCH (p:Part {sku: $sku})-[r:EQUIVALENT_TO|ALTERNATIVE_TO|REPLACES|REPLACED_BY]-(other:Part)
            OPTIONAL MATCH (other)-[:MANUFACTURED_BY]->(m:Manufacturer)
            RETURN other {.*, manufacturer: m.name,
                          ref_type: type(r), confidence: r.confidence}
            """
        return await self._db.execute_read(query, {"sku": sku})

    async def resolve_part(self, query_sku: str) -> list[dict]:
        """Resolve a SKU to itself + all equivalents. Core disambiguation."""
        query = """
        MATCH (p:Part {sku: $sku})
        OPTIONAL MATCH (p)-[:EQUIVALENT_TO]-(eq:Part)
        OPTIONAL MATCH (eq)-[:MANUFACTURED_BY]->(m:Manufacturer)
        WITH p, collect(eq {.*, manufacturer: m.name}) AS equivalents
        RETURN p {.*} AS part, equivalents
        """
        results = await self._db.execute_read(query, {"sku": query_sku})
        if not results:
            return []

        row = results[0]
        all_parts = [row["part"]]
        all_parts.extend([e for e in row["equivalents"] if e.get("sku")])
        return all_parts

    # ------------------------------------------------------------------
    # Specifications
    # ------------------------------------------------------------------

    async def set_part_specs(self, sku: str, specs: dict) -> None:
        """Set specification values on a part (HAS_SPEC edges)."""
        for spec_name, spec_data in specs.items():
            if isinstance(spec_data, dict):
                value = spec_data.get("value")
                unit = spec_data.get("unit", "")
            else:
                value = spec_data
                unit = ""

            await self._db.execute_write(
                """
                MATCH (p:Part {sku: $sku})
                MERGE (s:Specification {name: $spec_name})
                MERGE (p)-[hs:HAS_SPEC]->(s)
                SET hs.value = $value, hs.unit = $unit
                """,
                {"sku": sku, "spec_name": spec_name, "value": value, "unit": unit},
            )

    async def find_parts_by_specs(self, spec_constraints: dict,
                                  limit: int = 20) -> list[dict]:
        """Find parts matching exact spec constraints (e.g., bore=25mm)."""
        conditions = []
        params: dict = {"limit": limit}
        for i, (name, value) in enumerate(spec_constraints.items()):
            param_name = f"spec_name_{i}"
            param_value = f"spec_value_{i}"
            conditions.append(
                f"EXISTS {{ MATCH (p)-[hs:HAS_SPEC]->(s:Specification {{name: ${param_name}}}) "
                f"WHERE hs.value = ${param_value} }}"
            )
            params[param_name] = name
            params[param_value] = value

        where_clause = " AND ".join(conditions)
        query = f"""
        MATCH (p:Part)
        WHERE {where_clause}
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        RETURN p {{.*, manufacturer: m.name}}
        LIMIT $limit
        """
        return await self._db.execute_read(query, params)

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    async def add_compatibility(self, sku_a: str, sku_b: str,
                                context: str = "") -> dict:
        """Mark two parts as compatible."""
        query = """
        MATCH (a:Part {sku: $sku_a})
        MATCH (b:Part {sku: $sku_b})
        MERGE (a)-[r:COMPATIBLE_WITH]->(b)
        SET r.context = $context
        RETURN a.sku AS from_sku, b.sku AS to_sku
        """
        results = await self._db.execute_write(
            query, {"sku_a": sku_a, "sku_b": sku_b, "context": context}
        )
        return results[0] if results else {}

    async def get_compatible_parts(self, sku: str) -> list[dict]:
        """Get all compatible parts with context."""
        query = """
        MATCH (p:Part {sku: $sku})-[r:COMPATIBLE_WITH]-(other:Part)
        OPTIONAL MATCH (other)-[:MANUFACTURED_BY]->(m:Manufacturer)
        RETURN other {.*, manufacturer: m.name, context: r.context}
        """
        return await self._db.execute_read(query, {"sku": sku})

    # ------------------------------------------------------------------
    # Assemblies / BOM
    # ------------------------------------------------------------------

    async def add_to_assembly(self, part_sku: str, assembly_model: str,
                              position: str | None = None, qty: int = 1) -> dict:
        """Add part as component of an assembly."""
        query = """
        MATCH (p:Part {sku: $sku})
        MERGE (a:Assembly {model: $model})
        MERGE (p)-[r:COMPONENT_OF]->(a)
        SET r.position = $position, r.quantity = $qty
        RETURN p.sku AS part, a.model AS assembly
        """
        results = await self._db.execute_write(
            query, {"sku": part_sku, "model": assembly_model,
                    "position": position, "qty": qty}
        )
        return results[0] if results else {}

    async def get_assembly_bom(self, assembly_model: str) -> list[dict]:
        """Get all components of an assembly (Bill of Materials)."""
        query = """
        MATCH (p:Part)-[r:COMPONENT_OF]->(a:Assembly {model: $model})
        OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
        RETURN p {.*, manufacturer: m.name,
                  position: r.position, quantity: r.quantity}
        ORDER BY r.position
        """
        return await self._db.execute_read(query, {"model": assembly_model})

    # ------------------------------------------------------------------
    # Multi-Hop Queries
    # ------------------------------------------------------------------

    async def find_alternatives_with_specs(self, sku: str,
                                           spec_constraints: dict | None = None) -> list[dict]:
        """Find equivalent/alternative parts, optionally filtered by specs."""
        query = """
        MATCH (p:Part {sku: $sku})-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt:Part)
        OPTIONAL MATCH (alt)-[hs:HAS_SPEC]->(s:Specification)
        OPTIONAL MATCH (alt)-[:MANUFACTURED_BY]->(m:Manufacturer)
        WITH alt, m, collect({name: s.name, value: hs.value, unit: hs.unit}) AS specs
        RETURN alt {.*, manufacturer: m.name, specs: specs}
        """
        results = await self._db.execute_read(query, {"sku": sku})

        # Filter by spec constraints in Python (simpler than dynamic Cypher)
        if spec_constraints and results:
            filtered = []
            for r in results:
                alt = r.get("alt", r)
                alt_specs = {s["name"]: s["value"] for s in alt.get("specs", []) if s.get("name")}
                match = all(
                    alt_specs.get(name) is not None and alt_specs[name] >= value
                    for name, value in spec_constraints.items()
                )
                if match:
                    filtered.append(r)
            return filtered

        return results

    async def find_replacement_kit(self, assembly_model: str) -> list[dict]:
        """Multi-hop: assembly -> components -> alternatives -> compatible accessories."""
        query = """
        MATCH (comp:Part)-[r:COMPONENT_OF]->(a:Assembly {model: $model})
        OPTIONAL MATCH (comp)-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt:Part)
        OPTIONAL MATCH (comp)-[:COMPATIBLE_WITH]-(acc:Part)
        OPTIONAL MATCH (comp)-[:MANUFACTURED_BY]->(cm:Manufacturer)
        OPTIONAL MATCH (alt)-[:MANUFACTURED_BY]->(am:Manufacturer)
        RETURN comp {.*, manufacturer: cm.name, position: r.position, quantity: r.quantity} AS component,
               collect(DISTINCT alt {.*, manufacturer: am.name}) AS alternatives,
               collect(DISTINCT acc {.*}) AS accessories
        """
        return await self._db.execute_read(query, {"model": assembly_model})

    # ------------------------------------------------------------------
    # Sync helpers (eventual consistency from PostgreSQL)
    # ------------------------------------------------------------------

    async def update_inventory_cache(self, sku: str, warehouse: str,
                                     qty_on_hand: int) -> None:
        """Update cached inventory on graph."""
        await self._db.execute_write(
            """
            MATCH (p:Part {sku: $sku})
            MERGE (w:Warehouse {code: $warehouse})
            MERGE (p)-[r:STOCKED_IN]->(w)
            SET r.qty_on_hand = $qty, r.updated_at = $now
            """,
            {"sku": sku, "warehouse": warehouse, "qty": qty_on_hand,
             "now": datetime.now(timezone.utc).isoformat()},
        )

    async def update_price_range(self, sku: str, min_price: float,
                                 max_price: float) -> None:
        """Update cached price range on graph for approximate filtering."""
        await self._db.execute_write(
            """
            MATCH (p:Part {sku: $sku})
            SET p.price_min = $min_price, p.price_max = $max_price
            """,
            {"sku": sku, "min_price": min_price, "max_price": max_price},
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_graph_stats(self) -> dict:
        """Return node/edge counts by type."""
        node_query = """
        CALL db.labels() YIELD label
        CALL {
            WITH label
            MATCH (n)
            WHERE label IN labels(n)
            RETURN count(n) AS cnt
        }
        RETURN label, cnt
        """
        edge_query = """
        CALL db.relationshipTypes() YIELD relationshipType AS type
        CALL {
            WITH type
            MATCH ()-[r]->()
            WHERE type(r) = type
            RETURN count(r) AS cnt
        }
        RETURN type, cnt
        """
        try:
            nodes = await self._db.execute_read(node_query)
            edges = await self._db.execute_read(edge_query)
            return {
                "nodes": {r["label"]: r["cnt"] for r in nodes},
                "edges": {r["type"]: r["cnt"] for r in edges},
            }
        except Exception as e:
            logger.warning("Could not get graph stats: %s", e)
            return {"nodes": {}, "edges": {}, "error": str(e)}
