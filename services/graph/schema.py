"""Neo4j knowledge graph schema: constraints, indexes, and ontology setup."""

import logging

logger = logging.getLogger(__name__)

# Node constraints (uniqueness)
CONSTRAINTS = [
    "CREATE CONSTRAINT part_sku IF NOT EXISTS FOR (p:Part) REQUIRE p.sku IS UNIQUE",
    "CREATE CONSTRAINT manufacturer_name IF NOT EXISTS FOR (m:Manufacturer) REQUIRE m.name IS UNIQUE",
    "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT spec_name IF NOT EXISTS FOR (s:Specification) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT warehouse_code IF NOT EXISTS FOR (w:Warehouse) REQUIRE w.code IS UNIQUE",
    "CREATE CONSTRAINT supplier_code IF NOT EXISTS FOR (s:Supplier) REQUIRE s.code IS UNIQUE",
    "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.external_id IS UNIQUE",
    "CREATE CONSTRAINT assembly_model IF NOT EXISTS FOR (a:Assembly) REQUIRE a.model IS UNIQUE",
]

# Property indexes for common queries
INDEXES = [
    "CREATE INDEX part_name IF NOT EXISTS FOR (p:Part) ON (p.name)",
    "CREATE INDEX part_category IF NOT EXISTS FOR (p:Part) ON (p.category)",
    "CREATE INDEX part_manufacturer IF NOT EXISTS FOR (p:Part) ON (p.manufacturer)",
    "CREATE INDEX manufacturer_country IF NOT EXISTS FOR (m:Manufacturer) ON (m.country)",
    "CREATE INDEX category_parent IF NOT EXISTS FOR (c:Category) ON (c.parent)",
    "CREATE INDEX supplier_name IF NOT EXISTS FOR (s:Supplier) ON (s.name)",
]

# Full-text search index for natural language queries
FULLTEXT_INDEXES = [
    """CREATE FULLTEXT INDEX part_search IF NOT EXISTS
       FOR (p:Part) ON EACH [p.sku, p.name, p.description]""",
]

# Vector index for embeddings (Voyage AI voyage-3-large = 1024 dims)
VECTOR_INDEXES = [
    """CREATE VECTOR INDEX part_embedding IF NOT EXISTS
       FOR (p:Part) ON (p.embedding)
       OPTIONS {indexConfig: {
         `vector.dimensions`: 1024,
         `vector.similarity_function`: 'cosine'
       }}""",
]

# MRO Category taxonomy (seed data)
CATEGORY_TAXONOMY = {
    "Bearings": [
        "Ball Bearings", "Roller Bearings", "Needle Bearings",
        "Thrust Bearings", "Pillow Block Bearings", "Mounted Bearings"
    ],
    "Fasteners": [
        "Bolts", "Screws", "Nuts", "Washers", "Anchors", "Rivets", "Pins"
    ],
    "Power Transmission": [
        "V-Belts", "Timing Belts", "Chains", "Sprockets",
        "Gears", "Couplings", "Pulleys", "Sheaves"
    ],
    "Seals & Gaskets": [
        "O-Rings", "Oil Seals", "Gaskets", "Packing"
    ],
    "Motors & Drives": [
        "AC Motors", "DC Motors", "Gear Motors",
        "Variable Frequency Drives", "Servo Motors"
    ],
    "Hydraulics & Pneumatics": [
        "Cylinders", "Valves", "Pumps", "Fittings", "Hoses"
    ],
    "Electrical": [
        "Switches", "Relays", "Connectors", "Wire", "Circuit Breakers"
    ],
    "Safety & PPE": [
        "Gloves", "Eye Protection", "Hearing Protection",
        "Respiratory", "Fall Protection"
    ],
}


async def create_schema(neo4j_client) -> None:
    """Create all constraints, indexes, and seed the category taxonomy."""
    logger.info("Creating Neo4j knowledge graph schema...")

    for constraint in CONSTRAINTS:
        try:
            await neo4j_client.execute_write(constraint)
        except Exception as e:
            logger.debug("Constraint may already exist: %s", e)

    for index in INDEXES + FULLTEXT_INDEXES:
        try:
            await neo4j_client.execute_write(index)
        except Exception as e:
            logger.debug("Index may already exist: %s", e)

    for vector_idx in VECTOR_INDEXES:
        try:
            await neo4j_client.execute_write(vector_idx)
        except Exception as e:
            logger.debug("Vector index may already exist: %s", e)

    # Seed category taxonomy
    for parent, children in CATEGORY_TAXONOMY.items():
        await neo4j_client.execute_write(
            "MERGE (c:Category {name: $name})",
            {"name": parent},
        )
        for child in children:
            await neo4j_client.execute_write(
                """
                MERGE (parent:Category {name: $parent_name})
                MERGE (child:Category {name: $child_name})
                MERGE (child)-[:SUBCATEGORY_OF]->(parent)
                """,
                {"parent_name": parent, "child_name": child},
            )

    logger.info("Neo4j schema created with %d constraints, %d indexes, %d categories",
                len(CONSTRAINTS), len(INDEXES) + len(FULLTEXT_INDEXES) + len(VECTOR_INDEXES),
                sum(1 + len(v) for v in CATEGORY_TAXONOMY.values()))
