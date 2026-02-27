# IndusAI 3.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a knowledge graph-powered MRO intelligence platform merging v1's AI depth + v2's platform breadth + Neo4j knowledge graph.

**Architecture:** Neo4j as core intelligence layer (parts, specs, cross-refs, compatibility). PostgreSQL for transactional data (orders, invoices, inventory). Claude LLM layer (Opus/Sonnet/Haiku) with circuit breaker. Voyage AI for embeddings. React frontend with graph visualization.

**Tech Stack:** Python 3.12, FastAPI, Neo4j 5.x, PostgreSQL 16, Redis 7, React 18, TypeScript, Vite, neo4j Python driver, Anthropic SDK, Voyage AI SDK (voyageai), Recharts, react-force-graph.

**Design Doc:** `docs/plans/2026-02-23-indusai3-knowledge-graph-design.md`

**Source Codebases:**
- v2 (current): `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/`
- v1 (porting from): `/Users/shahmeer/Documents/IndusAI-main/B2B-Omnichannel-Skynet/`

---

## Phase 1: Foundation (Tasks 1-8)

### Task 1: Add Neo4j to Infrastructure

**Files:**
- Modify: `docker-compose.yml` (add Neo4j service)
- Modify: `requirements.txt` (add neo4j driver)
- Modify: `.env.example` (add Neo4j config)
- Create: `services/graph/neo4j_client.py`

**Step 1: Update docker-compose.yml**

Add Neo4j service after the redis service block (after line ~41):

```yaml
  neo4j:
    image: neo4j:5.26-community
    container_name: indusai_neo4j
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-changeme}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD-SHELL", "neo4j status || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - mro-network
```

Add `neo4j_data` and `neo4j_logs` to the volumes section.

Add `neo4j` to the backend service `depends_on` with health check.

**Step 2: Update requirements.txt**

Add after existing dependencies:

```
# Knowledge Graph
neo4j==5.27.0
```

**Step 3: Update .env.example**

Add:

```ini
# Neo4j Knowledge Graph
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
```

**Step 4: Create Neo4j client**

Create `services/graph/__init__.py` (empty) and `services/graph/neo4j_client.py`:

```python
"""Async Neo4j client for knowledge graph operations."""

import logging
from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase, AsyncDriver

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Manages Neo4j connection lifecycle and provides query execution."""

    def __init__(self, uri: str, user: str, password: str):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", self._uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            logger.info("Neo4j connection closed")

    @asynccontextmanager
    async def session(self, database: str = "neo4j"):
        async with self._driver.session(database=database) as session:
            yield session

    async def execute_read(self, query: str, parameters: dict | None = None):
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def execute_write(self, query: str, parameters: dict | None = None):
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def health_check(self) -> dict:
        try:
            result = await self.execute_read("RETURN 1 AS ok")
            return {"status": "healthy", "connected": True}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
```

**Step 5: Write test for Neo4j client**

Create `tests/__init__.py` and `tests/test_neo4j_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from services.graph.neo4j_client import Neo4jClient


def test_neo4j_client_init():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    assert client._uri == "bolt://localhost:7687"
    assert client._user == "neo4j"
    assert client._driver is None
```

**Step 6: Run test**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/test_neo4j_client.py -v`

**Step 7: Commit**

```bash
git add services/graph/ docker-compose.yml requirements.txt .env.example tests/test_neo4j_client.py
git commit -m "feat: add Neo4j infrastructure and async client"
```

---

### Task 2: Create Knowledge Graph Schema (Ontology)

**Files:**
- Create: `services/graph/schema.py`

**Step 1: Write the graph schema creation module**

```python
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

# Vector index for embeddings (Neo4j 5.x)
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
```

**Step 2: Commit**

```bash
git add services/graph/schema.py
git commit -m "feat: add Neo4j ontology schema with MRO taxonomy"
```

---

### Task 3: Port v1 Part Number Parsers

**Files:**
- Create: `services/ai/__init__.py`
- Create: `services/ai/part_number_parser.py` (port from v1 `app/ai/part_number_parser.py`)
- Create: `services/ai/entity_extractor.py` (port from v1 `app/ai/entity_extractor.py`)
- Create: `services/ai/models.py` (shared schemas)
- Create: `tests/test_part_parser.py`

**Step 1: Create shared AI models**

Port the Pydantic schemas from v1's `app/models/schemas/part.py` and `app/models/schemas/common.py` into a single file `services/ai/models.py`. Include:
- `PartCategory` enum (BEARING, METRIC_FASTENER, IMPERIAL_FASTENER, BELT, UNKNOWN)
- `ParsedPart` dataclass (raw_input, category, parsed, confidence)
- `EntityResult` dataclass (part_numbers, quantities, order_numbers)
- `IntentType` enum (ORDER_STATUS, PART_LOOKUP, INVENTORY_CHECK, QUOTE_REQUEST, TECHNICAL_SUPPORT, ACCOUNT_INQUIRY, RETURN_REQUEST, GENERAL_QUERY)
- `IntentResult` dataclass (intent, confidence, requires_clarification)

**Step 2: Port part_number_parser.py**

Copy v1's `app/ai/part_number_parser.py` (337 lines) to `services/ai/part_number_parser.py`. Update imports to reference `services.ai.models` instead of `app.models.schemas.part`. Keep all parsing logic intact:
- `PartNumberParser` class with `parse()`, `parse_single()`
- All regex patterns: BEARING_PATTERN, METRIC_FASTENER_PATTERN, IMPERIAL_FASTENER_PATTERN, BELT_PATTERN
- Decoder lookup tables: BEARING_SERIES, BORE_LOOKUP, METRIC_COARSE_PITCH, FRACTION_TO_DECIMAL

**Step 3: Port entity_extractor.py**

Copy v1's `app/ai/entity_extractor.py` (108 lines) to `services/ai/entity_extractor.py`. Update imports. Keep:
- `EntityExtractor` class with `extract()`, `_extract_part_numbers()`, `_extract_quantities()`, `_extract_order_numbers()`
- All 19 part number regex patterns
- All 6 quantity patterns
- All 3 order number patterns

**Step 4: Write tests**

Create `tests/test_part_parser.py`:

```python
from services.ai.part_number_parser import PartNumberParser
from services.ai.entity_extractor import EntityExtractor
from services.ai.models import PartCategory


class TestPartNumberParser:
    def setup_method(self):
        self.parser = PartNumberParser()

    def test_parse_bearing(self):
        results = self.parser.parse("6204-2RS")
        assert len(results) >= 1
        assert results[0].category == PartCategory.BEARING

    def test_parse_metric_fastener(self):
        results = self.parser.parse("M8x1.25x30")
        assert len(results) >= 1
        assert results[0].category == PartCategory.METRIC_FASTENER

    def test_parse_imperial_fastener(self):
        results = self.parser.parse("1/4-20 x 1.5")
        assert len(results) >= 1
        assert results[0].category == PartCategory.IMPERIAL_FASTENER

    def test_parse_belt(self):
        results = self.parser.parse("A48")
        assert len(results) >= 1
        assert results[0].category == PartCategory.BELT

    def test_parse_multiple(self):
        results = self.parser.parse("I need 6204-2RS and M8x1.25x30")
        assert len(results) >= 2

    def test_parse_empty(self):
        results = self.parser.parse("")
        assert len(results) == 0


class TestEntityExtractor:
    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_extract_part_numbers(self):
        result = self.extractor.extract("I need bearing 6204-2RS")
        assert "6204-2RS" in result.part_numbers

    def test_extract_quantities(self):
        result = self.extractor.extract("I need 100 of 6204-2RS")
        assert len(result.quantities) > 0

    def test_extract_order_number(self):
        result = self.extractor.extract("What's the status of ORD-12345?")
        assert "ORD-12345" in result.order_numbers
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_part_parser.py -v`

**Step 6: Commit**

```bash
git add services/ai/ tests/test_part_parser.py
git commit -m "feat: port v1 part number parsers and entity extractor"
```

---

### Task 4: Build Claude LLM Router + Voyage AI Embeddings

**Files:**
- Create: `services/ai/llm_router.py`
- Create: `services/ai/claude_client.py`
- Create: `services/ai/embedding_client.py`
- Modify: `services/ai_service.py` (keep circuit breaker, rewire to router)
- Modify: `requirements.txt` (add voyageai)
- Modify: `.env.example` (add VOYAGE_API_KEY)
- Create: `tests/test_llm_router.py`

**Step 1: Update requirements.txt**

Add:
```
# AI / LLM
voyageai>=0.3.0
```

**Step 2: Update .env.example**

Add:
```ini
# Voyage AI (embeddings)
VOYAGE_API_KEY=
```

**Step 3: Create Claude client**

`services/ai/claude_client.py`:

Port from v2's `services/ai_service.py` (circuit breaker) + v1's `app/ai/llm_client.py` (Anthropic chat). Include:
- `ClaudeClient` with circuit breaker from v2
- Model tiers: `fast` = claude-haiku-4-5, `standard` = claude-sonnet-4-6, `heavy` = claude-opus-4-6
- `chat()` method with retry + exponential backoff
- Task-based model routing:
  - `intent_classification` → fast (Haiku)
  - `entity_extraction` → fast (Haiku)
  - `response_generation` → standard (Sonnet)
  - `catalog_normalization` → standard (Sonnet)
  - `graph_construction` → standard (Sonnet)
  - `complex_reasoning` → heavy (Opus)

**Step 4: Create Voyage AI embedding client**

`services/ai/embedding_client.py`:

```python
"""Voyage AI embedding client for vector operations."""

import logging
import voyageai

logger = logging.getLogger(__name__)


class VoyageEmbeddingClient:
    """Handles all embedding operations via Voyage AI."""

    def __init__(self, api_key: str, model: str = "voyage-3-large"):
        self._client = voyageai.AsyncClient(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed texts using Voyage AI.

        Args:
            texts: List of strings to embed.
            input_type: "document" for indexing, "query" for search queries.
        """
        result = await self._client.embed(texts, model=self._model, input_type=input_type)
        return result.embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]
```

**Step 5: Create LLM Router**

`services/ai/llm_router.py`:

```python
"""Claude LLM router with task-based model selection."""

import logging

logger = logging.getLogger(__name__)

TASK_MODELS = {
    "intent_classification": "claude-haiku-4-5",
    "entity_extraction": "claude-haiku-4-5",
    "response_generation": "claude-sonnet-4-6",
    "catalog_normalization": "claude-sonnet-4-6",
    "graph_construction": "claude-sonnet-4-6",
    "complex_reasoning": "claude-opus-4-6",
}


class LLMRouter:
    """Routes LLM requests to the appropriate Claude model by task type.
    Uses Voyage AI for all embedding operations."""

    def __init__(self, claude_client, embedding_client):
        self._claude = claude_client
        self._embeddings = embedding_client

    async def chat(self, messages: list[dict], system: str | None = None,
                   task: str = "response_generation", max_tokens: int = 1024,
                   temperature: float = 0.3) -> str:
        model = TASK_MODELS.get(task, TASK_MODELS["response_generation"])
        return await self._claude.chat(
            messages, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature
        )

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        return await self._embeddings.embed(texts, input_type=input_type)

    async def embed_query(self, query: str) -> list[float]:
        return await self._embeddings.embed_query(query)
```

**Step 6: Write tests and commit**

```bash
git add services/ai/llm_router.py services/ai/claude_client.py services/ai/embedding_client.py tests/test_llm_router.py requirements.txt .env.example
git commit -m "feat: add Claude LLM router with Voyage AI embeddings"
```

---

### Task 5: Build Graph Service (Core CRUD)

**Files:**
- Create: `services/graph/graph_service.py`
- Create: `tests/test_graph_service.py`

**Step 1: Implement GraphService**

This service wraps all Neo4j CRUD for the MRO ontology. Key methods:

```python
"""Knowledge graph CRUD operations for MRO parts ontology."""

class GraphService:
    def __init__(self, neo4j_client):
        self._db = neo4j_client

    # --- Parts ---
    async def upsert_part(self, sku, name, description, category, manufacturer,
                          specs=None, embedding=None) -> dict:
        """Create or update a Part node with manufacturer and category edges."""

    async def get_part(self, sku) -> dict | None:
        """Get part with all relationships (specs, cross-refs, manufacturer)."""

    async def search_parts_fulltext(self, query, limit=20) -> list[dict]:
        """Full-text search across sku, name, description."""

    async def search_parts_vector(self, embedding, limit=20, filters=None) -> list[dict]:
        """Vector similarity search on part embeddings."""

    # --- Cross-References ---
    async def add_cross_reference(self, sku_a, sku_b, ref_type="EQUIVALENT_TO",
                                  confidence=1.0, source="manual") -> dict:
        """Create bidirectional cross-reference between two parts."""

    async def get_cross_references(self, sku, ref_types=None) -> list[dict]:
        """Get all cross-references for a part, optionally filtered by type."""

    async def resolve_part(self, query_sku) -> list[dict]:
        """Resolve a SKU to itself + all equivalents. Core disambiguation."""

    # --- Specifications ---
    async def set_part_specs(self, sku, specs: dict) -> None:
        """Set specification values on a part (HAS_SPEC edges)."""

    async def find_parts_by_specs(self, spec_constraints: dict, limit=20) -> list[dict]:
        """Find parts matching exact spec constraints (e.g., bore=25mm)."""

    # --- Compatibility ---
    async def add_compatibility(self, sku_a, sku_b, context) -> dict:
        """Mark two parts as compatible (e.g., bearing fits in housing)."""

    async def get_compatible_parts(self, sku) -> list[dict]:
        """Get all compatible parts with context."""

    # --- Assemblies / BOM ---
    async def add_to_assembly(self, part_sku, assembly_model, position=None, qty=1):
        """Add part as component of an assembly."""

    async def get_assembly_bom(self, assembly_model) -> list[dict]:
        """Get all components of an assembly (Bill of Materials)."""

    # --- Multi-Hop Queries ---
    async def find_alternatives_with_specs(self, sku, spec_constraints=None) -> list[dict]:
        """Find equivalent/alternative parts, optionally filtered by specs."""
        # Cypher: MATCH (p:Part {sku})-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt)
        #         WHERE spec_constraints
        #         RETURN alt with specs

    async def find_replacement_kit(self, assembly_model) -> list[dict]:
        """Multi-hop: assembly → components → alternatives → compatible accessories."""

    # --- Sync ---
    async def update_inventory_cache(self, sku, warehouse, qty_on_hand):
        """Update cached inventory on graph (eventual consistency from PG)."""

    async def update_price_range(self, sku, min_price, max_price):
        """Update cached price range on graph for approximate filtering."""

    # --- Stats ---
    async def get_graph_stats(self) -> dict:
        """Return node/edge counts by type."""
```

**Step 2: Implement each method with Cypher queries**

Each method should use `self._db.execute_read()` or `self._db.execute_write()` with parameterized Cypher.

Example for `upsert_part`:
```cypher
MERGE (p:Part {sku: $sku})
SET p.name = $name, p.description = $description, p.updated_at = datetime()
WITH p
MERGE (m:Manufacturer {name: $manufacturer})
MERGE (p)-[:MANUFACTURED_BY]->(m)
WITH p
MERGE (c:Category {name: $category})
MERGE (p)-[:BELONGS_TO]->(c)
RETURN p
```

Example for `find_alternatives_with_specs`:
```cypher
MATCH (p:Part {sku: $sku})-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt:Part)
OPTIONAL MATCH (alt)-[hs:HAS_SPEC]->(s:Specification)
WITH alt, collect({name: s.name, value: hs.value, unit: hs.unit}) AS specs
WHERE ALL(sc IN $spec_constraints WHERE
  ANY(s IN specs WHERE s.name = sc.name AND s.value >= sc.min_value))
RETURN alt {.*, specs: specs}
```

**Step 3: Write tests and commit**

```bash
git add services/graph/graph_service.py tests/test_graph_service.py
git commit -m "feat: add GraphService with MRO CRUD and multi-hop queries"
```

---

### Task 6: Build Catalog Ingestion Pipeline

**Files:**
- Create: `services/ingestion/__init__.py`
- Create: `services/ingestion/parser.py` (Stage 1: Parse & Extract)
- Create: `services/ingestion/normalizer.py` (Stage 2: LLM Normalization)
- Create: `services/ingestion/resolver.py` (Stage 3: Entity Resolution)
- Create: `services/ingestion/graph_builder.py` (Stage 4: Graph Construction)
- Create: `services/ingestion/pipeline.py` (Orchestrator)
- Port: v1's `app/services/scraper_service.py` → `services/ingestion/parser.py`
- Create: `tests/test_ingestion.py`

**Step 1: Parser (Stage 1)**

Port v1's scraper_service.py (415 lines). The parser handles:
- CSV/Excel parsing via pandas (column normalization, flexible mapping)
- PDF extraction via pdfplumber (table-aware, chunked for LLM)
- HTML scraping via BeautifulSoup (from v1's `_fetch_page`, `_clean_html`, `_find_next_page`)
- LLM-powered extraction for unstructured content (from v1's `_extract_with_llm`)

```python
class CatalogParser:
    async def parse_csv(self, file_bytes: bytes) -> list[dict]: ...
    async def parse_pdf(self, file_bytes: bytes) -> list[dict]: ...
    async def scrape_url(self, url: str, max_pages: int = 5) -> list[dict]: ...
```

**Step 2: Normalizer (Stage 2)**

Uses v1's part_number_parser + LLM for:
- Part number parsing and category detection
- Spec extraction and unit standardization
- Manufacturer identification

```python
class CatalogNormalizer:
    def __init__(self, part_parser, llm_router): ...
    async def normalize(self, raw_products: list[dict]) -> list[NormalizedProduct]: ...
```

**Step 3: Resolver (Stage 3)**

Entity resolution against existing graph:
- Exact match on SKU
- Fuzzy match on name/description (fuzzywuzzy from v1)
- Cross-reference detection
- Confidence scoring (high/medium/low)
- Returns: matched, new, or needs_review

```python
class EntityResolver:
    def __init__(self, graph_service): ...
    async def resolve(self, products: list[NormalizedProduct]) -> ResolutionResult: ...
```

**Step 4: Graph Builder (Stage 4)**

Writes resolved entities to Neo4j:
- Create/update Part nodes with properties
- Create Manufacturer, Category edges
- Create HAS_SPEC edges for specifications
- Create EQUIVALENT_TO edges for detected cross-references
- Generate and store vector embeddings

```python
class GraphBuilder:
    def __init__(self, graph_service, llm_router): ...
    async def build(self, resolved: ResolutionResult) -> BuildResult: ...
```

**Step 5: Pipeline Orchestrator**

```python
class IngestionPipeline:
    def __init__(self, parser, normalizer, resolver, builder): ...

    async def ingest_csv(self, file_bytes: bytes) -> IngestionResult:
        raw = await self.parser.parse_csv(file_bytes)
        normalized = await self.normalizer.normalize(raw)
        resolved = await self.resolver.resolve(normalized)
        built = await self.builder.build(resolved)
        return IngestionResult(
            total=len(raw), created=built.created, updated=built.updated,
            needs_review=len(resolved.needs_review), errors=built.errors
        )
```

**Step 6: Tests and commit**

```bash
git add services/ingestion/ tests/test_ingestion.py
git commit -m "feat: add 4-stage catalog ingestion pipeline"
```

---

### Task 7: Build GraphRAG Query Engine

**Files:**
- Create: `services/graphrag/__init__.py`
- Create: `services/graphrag/query_engine.py` (5-stage pipeline)
- Create: `services/graphrag/context_merger.py`
- Modify: `services/intent_classifier.py` (enhance with v1's LLM-based classification)
- Modify: `services/business_logic.py` (rewire handlers to use graph)
- Create: `tests/test_query_engine.py`

**Step 1: Implement QueryEngine**

The 5-stage pipeline from the design doc:

```python
class GraphRAGQueryEngine:
    def __init__(self, graph_service, llm_router, intent_classifier,
                 entity_extractor, part_parser, inventory_service, pricing_service):
        ...

    async def process_query(self, message: str, customer_id: str | None = None) -> QueryResult:
        # Stage 1: Intent + Entity Extraction
        intent = await self.intent_classifier.classify(message)
        entities = self.entity_extractor.extract(message)
        parsed_parts = self.part_parser.parse(message)

        # Stage 2: Graph Resolution
        graph_results = await self._resolve_via_graph(entities, intent)

        # Stage 3: Vector Fallback (if graph has no results)
        if not graph_results:
            graph_results = await self._vector_fallback(message, entities)

        # Stage 4: Context Assembly
        context = await self._assemble_context(
            graph_results, entities, customer_id
        )

        # Stage 5: LLM Response Generation
        response = await self._generate_response(message, context, intent)

        return QueryResult(
            response=response,
            intent=intent,
            entities=entities,
            graph_path=graph_results.path,  # For explainability
            sources=context.sources,
        )
```

**Step 2: Implement ContextMerger**

Merges graph results + vector results + PostgreSQL data (inventory, pricing):

```python
class ContextMerger:
    def __init__(self, inventory_service, pricing_service):
        ...

    async def merge(self, graph_results, vector_results, customer_id=None) -> MergedContext:
        # For each part in results:
        #   - Fetch inventory from PostgreSQL
        #   - Fetch pricing from PostgreSQL (customer-specific if customer_id)
        #   - Attach graph relationships (equivalents, specs, compatibility)
        # Return structured context for LLM
```

**Step 3: Enhance intent_classifier.py**

Replace v2's regex-only classifier with v1's dual-mode (LLM + regex fallback):
- Keep v2's pattern structure but add LLM classification as primary mode
- Add `IntentType.INVENTORY_CHECK`, `QUOTE_REQUEST`, `ACCOUNT_INQUIRY` from v1
- Use LLM router's `fast` tier for classification

**Step 4: Rewire business_logic.py**

Update each `_handle_*` method to use `GraphRAGQueryEngine` instead of direct database queries:
- `_handle_product_inquiry()` → `query_engine.process_query()` with PART_LOOKUP intent
- `_handle_order_status()` → keep PostgreSQL-direct (orders are transactional)
- `_handle_price_request()` → graph for part resolution + PG for exact pricing
- `_handle_returns()` → keep PostgreSQL-direct (RMA is transactional)

**Step 5: Tests and commit**

```bash
git add services/graphrag/ tests/test_query_engine.py
git commit -m "feat: add 5-stage GraphRAG query engine"
```

---

### Task 8: Wire Everything into main.py

**Files:**
- Modify: `main.py` (add Neo4j lifecycle, register services)
- Create: `services/graph/seed_demo.py` (demo data for graph)

**Step 1: Update main.py lifespan**

In the `lifespan()` context manager (line 282-337), add:

```python
# After database initialization (~line 294):
# Initialize Neo4j
from services.graph.neo4j_client import Neo4jClient
from services.graph.schema import create_schema
from services.graph.graph_service import GraphService

neo4j_client = Neo4jClient(
    uri=settings.neo4j_uri,
    user=settings.neo4j_user,
    password=settings.neo4j_password,
)
await neo4j_client.connect()
await create_schema(neo4j_client)
graph_service = GraphService(neo4j_client)

# Initialize LLM Router (Claude + Voyage AI)
from services.ai.llm_router import LLMRouter
from services.ai.claude_client import ClaudeClient
from services.ai.embedding_client import VoyageEmbeddingClient

claude_client = ClaudeClient(api_key=settings.anthropic_api_key)
embedding_client = VoyageEmbeddingClient(api_key=settings.voyage_api_key)
llm_router = LLMRouter(claude_client=claude_client, embedding_client=embedding_client)

# Initialize GraphRAG Engine
from services.graphrag.query_engine import GraphRAGQueryEngine
query_engine = GraphRAGQueryEngine(
    graph_service=graph_service,
    llm_router=llm_router,
    intent_classifier=classifier,
    entity_extractor=entity_extractor,
    part_parser=part_parser,
    inventory_service=inventory_svc,
    pricing_service=pricing_svc,
)
```

Add `VOYAGE_API_KEY` and Neo4j settings to the Settings class.

**Step 2: Add Neo4j cleanup to lifespan shutdown**

```python
yield  # After this, shutdown begins
await neo4j_client.close()  # Add before database close
```

**Step 3: Create demo seed data for graph**

`services/graph/seed_demo.py` — Populate Neo4j with ~50 MRO parts (bearings, fasteners, belts) with:
- Cross-references between manufacturers (SKF ↔ NSK ↔ FAG ↔ Timken)
- Specifications (bore, OD, width, load ratings, temperature ratings)
- Category assignments
- 2-3 assemblies with BOM relationships
- Supplier relationships

**Step 4: Update health endpoint**

Add Neo4j status to `/health/detailed` endpoint.

**Step 5: Commit**

```bash
git add main.py services/graph/seed_demo.py
git commit -m "feat: wire Neo4j, LLM router, and GraphRAG into application lifecycle"
```

---

## Phase 2: Intelligence (Tasks 9-13)

### Task 9: Implement Multi-Hop Reasoning

**Files:**
- Modify: `services/graphrag/query_engine.py` (add multi-hop methods)
- Modify: `services/graph/graph_service.py` (add traversal queries)

Implement the multi-hop reasoning patterns from the design doc:
- Assembly → BOM → Components → Alternatives → Compatible Accessories
- Part → Equivalents → Specs Comparison → Best Match
- Customer History → Preferred Brands → Filtered Alternatives

Key Cypher patterns:
```cypher
// Multi-hop: Find replacement kit for assembly
MATCH (a:Assembly {model: $model})-[:CONTAINS]->(p:Part)
OPTIONAL MATCH (p)-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt:Part)
OPTIONAL MATCH (p)-[:COMPATIBLE_WITH]->(acc:Part)
RETURN p, collect(DISTINCT alt) AS alternatives, collect(DISTINCT acc) AS accessories
```

**Commit:** `feat: add multi-hop reasoning to GraphRAG engine`

---

### Task 10: Vector Embeddings in Neo4j

**Files:**
- Create: `services/graph/embedding_service.py`
- Modify: `services/graph/graph_service.py` (add vector search methods)

Implement:
- `EmbeddingService.embed_part()` — Build rich text from part data (port v1's `build_embedding_text()`)
- `EmbeddingService.embed_query()` — Embed user query for search
- `GraphService.search_parts_vector()` — Neo4j vector index query
- `GraphService.hybrid_search()` — Combine vector similarity + graph traversal + full-text

Port the hybrid search weighting from v1 (70% vector + 30% keyword) and add graph-based re-ranking.

**Commit:** `feat: add vector embeddings and hybrid search to knowledge graph`

---

### Task 11: Neo4j ↔ PostgreSQL Sync Service

**Files:**
- Create: `services/sync/__init__.py`
- Create: `services/sync/sync_service.py`

Implement event-driven sync:
- **Inventory sync (PG → Neo4j):** When inventory is adjusted via platform API, update `STOCKED_IN` edge properties in Neo4j.
- **Product sync (Neo4j → PG):** When parts are created/updated in graph via ingestion, mirror to PostgreSQL products table for order/invoice joins.
- **Price sync (PG → Neo4j):** When pricing changes, update `price_range` properties on Part nodes.

Implementation: Hook into existing platform service methods (inventory_service, product_service, pricing_service) to publish sync events.

**Commit:** `feat: add Neo4j ↔ PostgreSQL sync service`

---

### Task 12: Enhanced Chat with Graph-Powered Responses

**Files:**
- Modify: `services/business_logic.py` (rewire all handlers)
- Create: `services/ai/prompts.py` (port v1 prompts + new graph-aware prompts)

Rewrite the chat response pipeline to:
1. Use GraphRAG query engine for all part-related intents
2. Include graph traversal path in response metadata (for explainability)
3. Add "suggested actions" based on graph context (e.g., "View alternatives", "Check compatible housings")
4. Port v1's system prompt and response templates

**Commit:** `feat: enhance chat with graph-powered responses and explainability`

---

### Task 13: API Endpoints for Graph Operations

**Files:**
- Create: `routes/graph.py` (new router for graph-specific endpoints)
- Modify: `main.py` (register graph router)
- Modify: `routes/platform.py` (enhance existing product endpoints)

New endpoints:
```
GET  /api/v1/graph/parts/{sku}/relationships    — All relationships for a part
GET  /api/v1/graph/parts/{sku}/equivalents       — Cross-references
GET  /api/v1/graph/parts/{sku}/compatible        — Compatible parts
GET  /api/v1/graph/parts/{sku}/specs             — Specifications
GET  /api/v1/graph/assemblies/{model}/bom        — Bill of Materials
GET  /api/v1/graph/search                        — Hybrid graph+vector search
POST /api/v1/graph/query                         — Natural language graph query
GET  /api/v1/graph/stats                         — Graph statistics

POST /api/v1/catalog/import                      — Upload CSV/PDF for ingestion
POST /api/v1/catalog/scrape                      — Scrape supplier URL
GET  /api/v1/catalog/import/{job_id}/status       — Ingestion job status
GET  /api/v1/catalog/review-queue                 — Low-confidence matches needing review
POST /api/v1/catalog/review/{item_id}/approve     — Approve a match
POST /api/v1/catalog/review/{item_id}/reject      — Reject a match
```

Enhance existing endpoints:
- `GET /api/v1/products/{id}` — Add graph context (equivalents, compatibility, specs)
- `POST /api/v1/message` — Return graph traversal path in response metadata

**Commit:** `feat: add graph and catalog API endpoints`

---

## Phase 3: Frontend Integration (Tasks 14-18)

### Task 14: Graph Explorer Page

**Files:**
- Create: `src/pages/GraphExplorer.tsx`
- Modify: `src/App.tsx` (add route)
- Modify: `src/components/layout/Sidebar.tsx` (add nav item)
- Modify: `src/lib/api.ts` (add graph API methods)
- Modify: `package.json` (add react-force-graph or vis-network)

Build a force-directed graph visualization:
- Click a part → show node with connections radiating out
- Edge labels show relationship types (EQUIVALENT_TO, COMPATIBLE_WITH, etc.)
- Color-code nodes by type (Part=blue, Manufacturer=green, Category=orange)
- Click edges to see properties (confidence, source, verified)
- Search bar to find starting node
- Zoom, pan, drag interactions

**Commit:** `feat: add Graph Explorer page with interactive visualization`

---

### Task 15: Catalog Import Page

**Files:**
- Create: `src/pages/CatalogImport.tsx`
- Modify: `src/App.tsx` (add route)
- Modify: `src/lib/api.ts` (add catalog import methods)

Build a catalog import interface:
- Drag-and-drop zone for CSV/PDF/Excel files
- URL input for web scraping
- Progress bar showing 4 stages (Parse → Normalize → Resolve → Build)
- Summary card: created, updated, needs_review counts
- "Review Queue" tab for low-confidence matches
- Each review item shows: detected entity, matched entity, confidence, approve/reject buttons

**Commit:** `feat: add Catalog Import page with review queue`

---

### Task 16: Cross-Reference Manager Page

**Files:**
- Create: `src/pages/CrossReferences.tsx`
- Modify: `src/App.tsx` (add route)

Table view of all cross-references:
- Columns: Part A (SKU, name, mfg), Relationship, Part B (SKU, name, mfg), Confidence, Source, Verified
- Filter by relationship type, manufacturer, confidence level
- Inline edit/verify buttons
- Bulk actions: verify selected, merge duplicates
- Add new cross-reference form

**Commit:** `feat: add Cross-Reference Manager page`

---

### Task 17: Enhanced Product Detail (Part Intelligence Card)

**Files:**
- Modify: `src/pages/ProductDetail.tsx` (enhance with graph data)
- Modify: `src/lib/api.ts` (add graph context to product fetch)

Add new sections to the existing product detail page:
- **Equivalents** — Table of cross-referenced parts with manufacturer, confidence
- **Compatible Parts** — Parts that fit with this one, with context labels
- **Specifications** — Structured spec table from graph (not just JSONB dump)
- **Assembly Membership** — Which assemblies this part belongs to
- **Mini Graph** — Small force-directed view centered on this part
- **Purchase History** — (if customer context) how often they've bought this

**Commit:** `feat: enhance ProductDetail with graph intelligence card`

---

### Task 18: Enhanced Chat with Reasoning Display

**Files:**
- Modify: `src/pages/Chat.tsx` (add reasoning panel)

Enhance the chat interface:
- When the AI uses graph traversal, show the path below the response
- Visual breadcrumb: `SKF 6205-2RS → EQUIVALENT_TO → NSK 6205DDU → HAS_SPEC → temp: 220°C`
- Collapsible "How I found this" section
- Clickable part references that navigate to ProductDetail

**Commit:** `feat: add reasoning display to chat interface`

---

## Phase 4: Polish & Pitch (Tasks 19-22)

### Task 19: Demo Dataset

**Files:**
- Modify: `services/graph/seed_demo.py` (expand to 500+ parts)
- Create: `data/demo/` (sample CSV catalogs for import demo)

Create a realistic demo dataset:
- 500+ MRO parts across all categories (bearings, fasteners, belts, seals, motors)
- 200+ cross-reference relationships across 5 manufacturers (SKF, NSK, FAG, Timken, NTN)
- 50+ compatibility relationships (bearing ↔ housing, motor ↔ bearing)
- 10 assemblies with BOM (conveyor systems, pump assemblies, motor assemblies)
- Realistic specifications (dimensions, load ratings, temperature ratings, materials)
- Sample CSV catalogs that can be imported during demo

**Commit:** `feat: add comprehensive MRO demo dataset`

---

### Task 20: Performance Optimization

**Files:**
- Modify: `services/graph/graph_service.py` (add caching, optimize Cypher)
- Modify: `services/graphrag/query_engine.py` (add result caching)

Optimize:
- Add Redis caching for frequently accessed graph queries (part lookups, common cross-refs)
- Optimize Cypher queries with `PROFILE` to identify slow patterns
- Add Neo4j composite indexes for common query patterns
- Implement query result pagination for large result sets
- Add connection pooling configuration for Neo4j driver

**Commit:** `perf: optimize graph queries and add caching layer`

---

### Task 21: End-to-End Tests

**Files:**
- Create: `tests/test_e2e_graphrag.py`
- Create: `tests/test_e2e_ingestion.py`
- Create: `tests/test_e2e_chat.py`

Test scenarios:
1. **Ingestion → Search:** Upload CSV → verify parts appear in graph → search returns them
2. **Cross-reference resolution:** Add equivalents → query "NSK equivalent of SKF 6205" → returns correct match
3. **Multi-hop reasoning:** Seed assembly → query "replace bearings in motor X" → returns full kit
4. **Spec matching:** Seed parts with specs → query "bearing with 25mm bore and 200C rating" → returns exact matches
5. **Chat integration:** Send message → verify graph-powered response includes correct data
6. **Fallback behavior:** Disable Neo4j → verify system degrades to v2 behavior

**Commit:** `test: add end-to-end tests for GraphRAG pipeline`

---

### Task 22: Update Docker, CI/CD, and Documentation

**Files:**
- Modify: `docker-compose.yml` (finalize Neo4j config)
- Modify: `.github/workflows/ci.yml` (add backend tests, Neo4j service)
- Modify: `README.md` (update setup instructions)
- Modify: `Dockerfile` (add neo4j driver to image)

Update CI pipeline to:
- Spin up Neo4j test container
- Run backend pytest suite
- Run frontend Vitest suite
- Build Docker image with all new dependencies

Update README with:
- New architecture diagram
- Neo4j setup instructions
- Demo walkthrough (import catalog → search → chat)
- Environment variable documentation

**Commit:** `chore: update infrastructure, CI/CD, and documentation`

---

## Task Dependency Graph

```
Task 1 (Neo4j infra) ──┬── Task 2 (Schema) ──── Task 5 (GraphService)
                        │                              │
Task 3 (Parsers) ──────┼── Task 6 (Ingestion) ←──────┤
                        │                              │
Task 4 (LLM Router) ──┼── Task 7 (GraphRAG Engine) ──┼── Task 8 (Wire main.py)
                        │         │                    │
                        │         ├── Task 9 (Multi-hop)
                        │         ├── Task 10 (Vectors)
                        │         └── Task 12 (Enhanced Chat)
                        │
                        ├── Task 11 (Sync) ←── Task 5
                        ├── Task 13 (API endpoints) ←── Tasks 5,7
                        │
                        ├── Task 14 (Graph Explorer UI) ←── Task 13
                        ├── Task 15 (Catalog Import UI) ←── Task 13
                        ├── Task 16 (Cross-Ref Manager) ←── Task 13
                        ├── Task 17 (Product Detail) ←── Task 13
                        ├── Task 18 (Chat Reasoning) ←── Task 12
                        │
                        ├── Task 19 (Demo Data) ←── Tasks 5,6
                        ├── Task 20 (Performance) ←── Tasks 7,9
                        ├── Task 21 (E2E Tests) ←── Tasks 7,8,12
                        └── Task 22 (CI/CD/Docs) ←── All
```

## Parallelization Opportunities

These tasks can run in parallel:
- **Tasks 1-4** can all start immediately (infrastructure, parsers, LLM router are independent)
- **Tasks 9, 10, 11** can run in parallel once Task 8 is done
- **Tasks 14, 15, 16, 17** can run in parallel once Task 13 is done
- **Tasks 19, 20** can run in parallel
