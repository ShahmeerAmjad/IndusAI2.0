# Neo4j End-to-End Wiring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the existing Neo4j knowledge graph infrastructure end-to-end so graph queries, sync, chat integration, embeddings, and frontend sourcing all work as a connected system.

**Architecture:** Event-driven sync hooks in platform services push data to Neo4j on every CRUD operation. A new graph API router exposes graph queries. The GraphRAG query engine is wired into the chat pipeline for MRO intents. A new React sourcing page provides the frontend interface.

**Tech Stack:** Python 3.12, FastAPI, neo4j async driver, React 18, TypeScript, Tailwind CSS, Voyage AI embeddings

---

### Task 1: Add Neo4j to Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example` (if it exists, otherwise skip)

**Step 1: Add Neo4j service to docker-compose.yml**

Add the Neo4j service after the `redis` service block, add the volume, and add Neo4j env vars to the backend service.

In `docker-compose.yml`, after the redis service (after line 41) and before the backend service, add:

```yaml
  # Neo4j Knowledge Graph
  neo4j:
    image: neo4j:5-community
    container_name: mro-neo4j
    restart: unless-stopped
    environment:
      NEO4J_AUTH: ${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-changeme}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: 256m
      NEO4J_server_memory_heap_max__size: 512m
    volumes:
      - neo4j_data:/data
    ports:
      - "7474:7474"
      - "7687:7687"
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "${NEO4J_USER:-neo4j}", "-p", "${NEO4J_PASSWORD:-changeme}", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - mro-network
```

Add to the backend service `environment` section:

```yaml
      # Neo4j
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: ${NEO4J_USER:-neo4j}
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:-changeme}
      VOYAGE_API_KEY: ${VOYAGE_API_KEY:-}
```

Add to the backend `depends_on` section:

```yaml
      neo4j:
        condition: service_healthy
```

Add to `volumes`:

```yaml
  neo4j_data:
    driver: local
```

**Step 2: Verify the YAML is valid**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && docker compose config --quiet`
Expected: No output (valid)

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "infra: add Neo4j 5 service to docker-compose"
```

---

### Task 2: Create GraphSyncService

**Files:**
- Create: `services/graph/sync.py`
- Test: `tests/test_graph_sync.py`

**Step 1: Write the failing test**

Create `tests/test_graph_sync.py`:

```python
"""Tests for GraphSyncService — PG-to-Neo4j sync."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_graph_service():
    svc = AsyncMock()
    svc.upsert_part = AsyncMock(return_value={"sku": "6204-2RS"})
    svc.update_inventory_cache = AsyncMock()
    svc.update_price_range = AsyncMock()
    return svc


@pytest.fixture
def mock_embedding_client():
    client = AsyncMock()
    client.embed_parts = AsyncMock(return_value=[[0.1] * 1024])
    return client


@pytest.fixture
def sync_service(mock_graph_service, mock_embedding_client):
    from services.graph.sync import GraphSyncService
    return GraphSyncService(
        graph_service=mock_graph_service,
        embedding_client=mock_embedding_client,
    )


@pytest.mark.asyncio
async def test_sync_product_upserts_part(sync_service, mock_graph_service):
    product = {
        "sku": "6204-2RS",
        "name": "Deep Groove Ball Bearing",
        "description": "Sealed bearing 20x47x14mm",
        "category": "Ball Bearings",
        "manufacturer": "SKF",
        "specs": [
            {"name": "bore_mm", "value": "20", "unit": "mm"},
        ],
    }
    await sync_service.sync_product(product)
    mock_graph_service.upsert_part.assert_called_once()
    call_kwargs = mock_graph_service.upsert_part.call_args
    assert call_kwargs[1]["sku"] == "6204-2RS"


@pytest.mark.asyncio
async def test_sync_product_generates_embedding(sync_service, mock_embedding_client, mock_graph_service):
    product = {"sku": "TEST-1", "name": "Test Part", "description": "A test"}
    await sync_service.sync_product(product)
    mock_embedding_client.embed_parts.assert_called_once()


@pytest.mark.asyncio
async def test_sync_product_skips_embedding_if_no_client(mock_graph_service):
    from services.graph.sync import GraphSyncService
    svc = GraphSyncService(graph_service=mock_graph_service, embedding_client=None)
    product = {"sku": "TEST-2", "name": "No Embed"}
    await svc.sync_product(product)
    mock_graph_service.upsert_part.assert_called_once()


@pytest.mark.asyncio
async def test_sync_inventory(sync_service, mock_graph_service):
    await sync_service.sync_inventory("6204-2RS", "MAIN", 150)
    mock_graph_service.update_inventory_cache.assert_called_once_with(
        sku="6204-2RS", warehouse="MAIN", qty_on_hand=150,
    )


@pytest.mark.asyncio
async def test_sync_price(sync_service, mock_graph_service):
    await sync_service.sync_price("6204-2RS", 5.50, 12.00)
    mock_graph_service.update_price_range.assert_called_once_with(
        sku="6204-2RS", min_price=5.50, max_price=12.00,
    )
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/test_graph_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.graph.sync'`

**Step 3: Write the implementation**

Create `services/graph/sync.py`:

```python
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
        """Sync a product from PostgreSQL to the Neo4j knowledge graph.

        Args:
            product: Dict with keys: sku, name, description, category,
                     manufacturer, specs (list of {name, value, unit}).
        """
        sku = product.get("sku", "")
        if not sku:
            return

        # Convert specs list [{name, value, unit}] to dict {name: {value, unit}}
        specs_dict = {}
        for spec in product.get("specs", []):
            if spec.get("name"):
                specs_dict[spec["name"]] = {
                    "value": spec.get("value", ""),
                    "unit": spec.get("unit", ""),
                }

        # Generate embedding if client available
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
        """Update inventory cache on the graph node."""
        try:
            await self._graph.update_inventory_cache(
                sku=sku, warehouse=warehouse, qty_on_hand=qty_on_hand,
            )
        except Exception as e:
            logger.error("Failed to sync inventory for %s: %s", sku, e)

    async def sync_price(self, sku: str, min_price: float, max_price: float) -> None:
        """Update price range on the graph node."""
        try:
            await self._graph.update_price_range(
                sku=sku, min_price=min_price, max_price=max_price,
            )
        except Exception as e:
            logger.error("Failed to sync price for %s: %s", sku, e)

    async def bulk_sync_products(self, db_manager) -> dict:
        """Full sync: read all products from PostgreSQL and push to Neo4j.

        Returns stats dict with count of synced products.
        """
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

                    # Fetch specs for this product
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/test_graph_sync.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add services/graph/sync.py tests/test_graph_sync.py
git commit -m "feat: add GraphSyncService — PG-to-Neo4j event-driven sync"
```

---

### Task 3: Add Sync Hooks to Platform Services

**Files:**
- Modify: `services/platform/product_service.py:11-14` (constructor)
- Modify: `services/platform/product_service.py:23-48` (create_product)
- Modify: `services/platform/product_service.py:114-143` (update_product)
- Modify: `services/platform/inventory_service.py:11-13` (constructor)
- Modify: `services/platform/inventory_service.py:136-162` (adjust_stock)
- Modify: `services/platform/inventory_service.py:265-298` (receive_stock)
- Modify: `main.py:266-288` (service wiring)
- Modify: `main.py:315-452` (lifespan — inject sync service)

**Step 1: Add `graph_sync` parameter to ProductService constructor**

In `services/platform/product_service.py`, modify the `__init__` to accept an optional sync service:

```python
class ProductService:
    def __init__(self, db_manager, erp_connector, logger, graph_sync=None):
        self.db = db_manager
        self.erp = erp_connector
        self.logger = logger
        self._graph_sync = graph_sync
```

**Step 2: Add sync hook at the end of `create_product`**

After `return await self.get_product(product_id)` on line 45, and before the `except` block, add:

```python
            product = await self.get_product(product_id)
            # Sync to knowledge graph
            if self._graph_sync and product:
                try:
                    await self._graph_sync.sync_product(product)
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for new product: %s", sync_err)
            return product
```

(Replace the existing `return await self.get_product(product_id)` line.)

**Step 3: Add sync hook at the end of `update_product`**

After `return await self.get_product(product_id)` on line 140, add:

```python
            product = await self.get_product(product_id)
            if self._graph_sync and product:
                try:
                    await self._graph_sync.sync_product(product)
                except Exception as sync_err:
                    self.logger.warning("Graph sync failed for updated product: %s", sync_err)
            return product
```

(Replace the existing `return await self.get_product(product_id)` line.)

**Step 4: Add `graph_sync` to InventoryService**

In `services/platform/inventory_service.py`, modify `__init__`:

```python
class InventoryService:
    def __init__(self, db_manager, logger, graph_sync=None):
        self.db = db_manager
        self.logger = logger
        self._graph_sync = graph_sync
```

**Step 5: Add sync hook in `adjust_stock`**

After the `_record_transaction` call in `adjust_stock` (line 158), before `return True`, add:

```python
            # Sync to knowledge graph
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
```

**Step 6: Add sync hook in `receive_stock`**

Same pattern — after the `_record_transaction` call in `receive_stock` (line 293), before `return True`:

```python
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
```

**Step 7: Wire sync service in `main.py` lifespan**

In the lifespan function, after the GraphRAG engine is created (~line 362), create the sync service and inject it:

```python
        # Create sync service
        from services.graph.sync import GraphSyncService
        graph_sync = GraphSyncService(
            graph_service=graph_service,
            embedding_client=embedding_client,
        )
        app.state.graph_sync = graph_sync

        # Inject into platform services
        product_service._graph_sync = graph_sync
        inventory_service._graph_sync = graph_sync
```

**Step 8: Add bulk sync on startup (debug mode)**

After the Neo4j demo data seed block (~line 451), add:

```python
    # Bulk sync PG products to Neo4j
    if neo4j_client and db_manager.pool:
        try:
            sync = getattr(app.state, "graph_sync", None)
            if sync:
                stats = await sync.bulk_sync_products(db_manager)
                logger.info("Bulk PG→Neo4j sync: %s", stats)
        except Exception as e:
            logger.warning("Bulk sync failed: %s", e)
```

**Step 9: Commit**

```bash
git add services/platform/product_service.py services/platform/inventory_service.py main.py
git commit -m "feat: add PG→Neo4j sync hooks in ProductService and InventoryService"
```

---

### Task 4: Create Graph API Routes

**Files:**
- Create: `routes/graph.py`
- Modify: `main.py` (register router)
- Test: `tests/test_graph_routes.py`

**Step 1: Write the failing test**

Create `tests/test_graph_routes.py`:

```python
"""Tests for graph API routes."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_graph_service():
    svc = AsyncMock()
    svc.get_part = AsyncMock(return_value={
        "sku": "6204-2RS", "name": "Ball Bearing", "manufacturer": "SKF",
        "specs": [{"name": "bore_mm", "value": 20, "unit": "mm"}],
        "cross_refs": [],
    })
    svc.search_parts_fulltext = AsyncMock(return_value=[
        {"node": {"sku": "6204-2RS", "name": "Ball Bearing", "manufacturer": "SKF", "score": 1.0}}
    ])
    svc.get_cross_references = AsyncMock(return_value=[])
    svc.get_compatible_parts = AsyncMock(return_value=[])
    svc.get_assembly_bom = AsyncMock(return_value=[])
    svc.get_graph_stats = AsyncMock(return_value={"nodes": {"Part": 30}, "edges": {"EQUIVALENT_TO": 6}})
    return svc


def test_graph_routes_module_imports():
    from routes.graph import router
    assert router.prefix == "/api/v1/graph"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/test_graph_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.graph'`

**Step 3: Write the implementation**

Create `routes/graph.py`:

```python
"""Graph API — browse and query the Neo4j knowledge graph."""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/graph", tags=["knowledge-graph"])

_graph_service = None
_graph_sync = None


def set_graph_services(graph_service, graph_sync=None):
    global _graph_service, _graph_sync
    _graph_service = graph_service
    _graph_sync = graph_sync


def _require_graph():
    if not _graph_service:
        raise HTTPException(status_code=503, detail="Knowledge graph unavailable")
    return _graph_service


@router.get("/parts/{sku}")
async def get_part(sku: str):
    """Get a part from the knowledge graph with specs, cross-refs, and compatible parts."""
    graph = _require_graph()
    part = await graph.get_part(sku)
    if not part:
        raise HTTPException(status_code=404, detail=f"Part {sku} not found in knowledge graph")

    # Enrich with compatible parts
    compatible = await graph.get_compatible_parts(sku)
    part["compatible_parts"] = compatible
    return part


@router.get("/parts/search/fulltext")
async def search_parts(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """Full-text search across parts in the knowledge graph."""
    graph = _require_graph()
    results = await graph.search_parts_fulltext(q, limit=limit)
    return {"results": results, "total": len(results), "query": q}


@router.get("/parts/{sku}/cross-refs")
async def get_cross_refs(sku: str):
    """Get cross-references for a part."""
    graph = _require_graph()
    refs = await graph.get_cross_references(sku)
    return {"sku": sku, "cross_references": refs}


@router.get("/parts/{sku}/compatible")
async def get_compatible(sku: str):
    """Get compatible parts."""
    graph = _require_graph()
    parts = await graph.get_compatible_parts(sku)
    return {"sku": sku, "compatible_parts": parts}


@router.get("/assemblies/{model}/bom")
async def get_bom(model: str):
    """Get Bill of Materials for an assembly."""
    graph = _require_graph()
    components = await graph.get_assembly_bom(model)
    if not components:
        raise HTTPException(status_code=404, detail=f"Assembly {model} not found")
    return {"assembly": model, "components": components}


@router.get("/stats")
async def get_graph_stats():
    """Get knowledge graph statistics (node and edge counts)."""
    graph = _require_graph()
    return await graph.get_graph_stats()


@router.post("/sync/{sku}")
async def sync_part(sku: str):
    """Manually trigger PG→Neo4j sync for a single part (admin)."""
    if not _graph_sync:
        raise HTTPException(status_code=503, detail="Sync service unavailable")

    # This would need to fetch from PG first — simplified for now
    return {"status": "sync_triggered", "sku": sku}
```

**Step 4: Register the router in main.py**

In `main.py`, add the import (after line 88):

```python
from routes.graph import router as graph_router, set_graph_services
```

Include the router (after line 487, where other routers are included):

```python
app.include_router(graph_router)
```

Wire services in the lifespan (after creating graph_sync):

```python
        set_graph_services(graph_service, graph_sync)
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/test_graph_routes.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add routes/graph.py tests/test_graph_routes.py main.py
git commit -m "feat: add graph API routes — browse and query Neo4j knowledge graph"
```

---

### Task 5: Wire GraphRAG into Chat Pipeline

**Files:**
- Modify: `services/business_logic.py:17-20` (constructor)
- Modify: `services/business_logic.py:34-59` (process_message)
- Modify: `services/business_logic.py:143-251` (_handle_product_inquiry)
- Modify: `services/business_logic.py:319-375` (_handle_technical_support)
- Modify: `main.py` (inject query_engine into business_logic)

**Step 1: Add `query_engine` to BusinessLogic constructor**

In `services/business_logic.py`, modify `__init__`:

```python
class BusinessLogic:
    def __init__(self, ai_service, db_manager, settings, escalation_service,
                 product_service=None, inventory_service=None,
                 pricing_service=None, order_service=None,
                 quote_service=None, customer_service=None, rma_service=None,
                 query_engine=None):
        self.ai_service = ai_service
        self.db_manager = db_manager
        self.settings = settings
        self.escalation_service = escalation_service
        self.products = product_service
        self.inventory = inventory_service
        self.pricing = pricing_service
        self.orders = order_service
        self.quotes = quote_service
        self.customers = customer_service
        self.rma = rma_service
        self.query_engine = query_engine
```

**Step 2: Add GraphRAG routing in `_handle_product_inquiry`**

At the very beginning of `_handle_product_inquiry` (line 143), before the regex matching, add a GraphRAG fast-path:

```python
    async def _handle_product_inquiry(self, message: CustomerMessage, context: Dict) -> BotResponse:
        # Try GraphRAG first if available
        if self.query_engine:
            try:
                result = await self.query_engine.process_query(message.content)
                if result.parts_found > 0:
                    return BotResponse(
                        content=result.response,
                        suggested_actions=["Get quote", "Check availability", "View cross-references"],
                        metadata={"graph_paths": result.graph_paths, "parts_found": result.parts_found},
                    )
            except Exception as e:
                self.logger.warning("GraphRAG product inquiry failed, falling back: %s", e)

        # Existing regex-based fallback below...
```

Note: `self.logger` doesn't exist on BusinessLogic — it uses `self.ai_service` for logging. Use a module-level logger instead. Add at the top of `business_logic.py`:

```python
import logging
logger = logging.getLogger(__name__)
```

And change `self.logger.warning` to `logger.warning`.

**Step 3: Add GraphRAG routing in `_handle_technical_support`**

Same pattern — for non-urgent technical queries, try GraphRAG for spec/compatibility answers. In `_handle_technical_support`, after the urgent check and before the keyword matching (around line 339):

```python
        else:
            # Try GraphRAG for technical spec questions
            if self.query_engine:
                try:
                    result = await self.query_engine.process_query(message.content)
                    if result.parts_found > 0:
                        return BotResponse(
                            content=result.response,
                            suggested_actions=["View specs", "Find alternatives", "Contact engineer"],
                        )
                except Exception:
                    pass  # Fall through to existing handlers
```

**Step 4: Inject query_engine into business_logic in main.py**

In `main.py` lifespan, after creating the query_engine (~line 362), inject it:

```python
        business_logic.query_engine = query_engine
```

**Step 5: Commit**

```bash
git add services/business_logic.py main.py
git commit -m "feat: wire GraphRAG into chat — product and technical queries use knowledge graph"
```

---

### Task 6: Add Embeddings to Demo Seed

**Files:**
- Modify: `services/graph/seed_demo.py:309-384` (seed_graph function)

**Step 1: Add optional embedding parameter to `seed_graph`**

Modify the `seed_graph` function signature and add embedding generation:

```python
async def seed_graph(graph_service, embedding_client=None) -> dict:
    """Seed the Neo4j knowledge graph with demo MRO data.

    Args:
        graph_service: GraphService instance.
        embedding_client: Optional VoyageEmbeddingClient for generating embeddings.

    Returns a summary dict with counts of created entities.
    """
    stats = {"parts": 0, "cross_refs": 0, "assemblies": 0, "components": 0, "embeddings": 0}

    all_parts = BEARINGS + FASTENERS + BELTS + SEALS_AND_MISC

    # Upsert all individual parts
    for part_data in all_parts:
        specs = part_data.get("specs", [])
        try:
            await graph_service.upsert_part(
                sku=part_data["sku"],
                name=part_data.get("name", ""),
                description=part_data.get("description", ""),
                category=part_data.get("category", ""),
                manufacturer=part_data.get("manufacturer", ""),
            )
            if specs:
                specs_dict = {
                    s["name"]: {"value": s["value"], "unit": s.get("unit", "")}
                    for s in specs if s.get("name")
                }
                await graph_service.set_part_specs(part_data["sku"], specs_dict)
            stats["parts"] += 1
        except Exception as e:
            logger.warning("Failed to seed part %s: %s", part_data.get("sku"), e)

    # Generate and store embeddings in batches
    if embedding_client:
        try:
            batch_size = 20
            for i in range(0, len(all_parts), batch_size):
                batch = all_parts[i:i + batch_size]
                # Build embedding input dicts
                embed_inputs = []
                for p in batch:
                    specs_text = ", ".join(
                        f"{s['name']}: {s['value']}" for s in p.get("specs", [])
                    )
                    embed_inputs.append({
                        "sku": p["sku"],
                        "name": p.get("name", ""),
                        "manufacturer": p.get("manufacturer", ""),
                        "category": p.get("category", ""),
                        "description": p.get("description", ""),
                        "specs": {s["name"]: s["value"] for s in p.get("specs", [])},
                    })

                embeddings = await embedding_client.embed_parts(embed_inputs)
                for part_data, embedding in zip(batch, embeddings):
                    try:
                        from services.graph.graph_service import GraphService
                        await graph_service._db.execute_write(
                            "MATCH (p:Part {sku: $sku}) SET p.embedding = $embedding",
                            {"sku": part_data["sku"], "embedding": embedding},
                        )
                        stats["embeddings"] += 1
                    except Exception as e:
                        logger.warning("Failed to store embedding for %s: %s", part_data["sku"], e)

            logger.info("Generated embeddings for %d parts", stats["embeddings"])
        except Exception as e:
            logger.warning("Embedding generation failed (non-fatal): %s", e)
```

Keep the rest of the function (cross-refs, compatibilities, assemblies) unchanged.

**Step 2: Update the seed call in main.py**

In `main.py`, update the Neo4j demo seed call (~line 447) to pass the embedding client:

```python
    if settings.debug and neo4j_client:
        try:
            from services.graph.seed_demo import seed_graph
            embed_client = getattr(app.state, "llm_router", None)
            embed_client = embed_client._embeddings if embed_client else None
            stats = await seed_graph(app.state.graph_service, embedding_client=embed_client)
            logger.info("Neo4j demo data seeded: %s", stats)
        except Exception as e:
            logger.error("Neo4j seed failed: %s", e)
```

**Step 3: Commit**

```bash
git add services/graph/seed_demo.py main.py
git commit -m "feat: generate vector embeddings for demo parts on seed"
```

---

### Task 7: Add Frontend Sourcing Page

**Files:**
- Create: `src/pages/Sourcing.tsx`
- Modify: `src/lib/api.ts` (add sourcing API method)
- Modify: `src/App.tsx` (add route)
- Modify: `src/components/layout/Sidebar.tsx` (add nav item)

**Step 1: Add sourcing types and API method to `src/lib/api.ts`**

After the `ChatResponse` interface (~line 199), add:

```typescript
export interface SourcingResult {
  sku: string;
  name: string;
  seller_name: string;
  unit_price: number;
  total_cost: number;
  transit_days: number;
  shipping_cost: number;
  distance_km: number;
  qty_available: number;
  manufacturer: string;
}

export interface SourcingResponse {
  response: string;
  parts_found: number;
  intent: string | null;
  sourcing_results: SourcingResult[];
}

export interface GraphPart {
  sku: string;
  name: string;
  manufacturer?: string;
  category?: string;
  description?: string;
  specs?: Array<{ name: string; value: string | number; unit?: string }>;
  cross_refs?: Array<{ sku: string; name?: string; type: string }>;
  compatible_parts?: Array<{ sku: string; name?: string; manufacturer?: string; context?: string }>;
}

export interface GraphSearchResult {
  results: Array<{ node: GraphPart; score: number }>;
  total: number;
  query: string;
}

export interface GraphStats {
  nodes: Record<string, number>;
  edges: Record<string, number>;
}
```

In the `api` object, add these methods before the closing `}`:

```typescript
  // Sourcing (AI-powered)
  searchSourcing: (query: string, qty = 1) =>
    fetch("/api/sourcing/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, qty }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Sourcing search failed: ${r.status}`);
      return r.json() as Promise<SourcingResponse>;
    }),

  // Knowledge Graph
  getGraphPart: (sku: string) => get<GraphPart>(`/graph/parts/${sku}`),
  searchGraph: (q: string, limit = 20) => get<GraphSearchResult>(`/graph/parts/search/fulltext?q=${encodeURIComponent(q)}&limit=${limit}`),
  getGraphStats: () => get<GraphStats>("/graph/stats"),
```

**Step 2: Create `src/pages/Sourcing.tsx`**

```tsx
import { useState } from "react";
import { api, type SourcingResponse } from "@/lib/api";
import { Search, Package, Truck, DollarSign, AlertCircle, Loader2 } from "lucide-react";

export default function Sourcing() {
  const [query, setQuery] = useState("");
  const [qty, setQty] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SourcingResponse | null>(null);
  const [error, setError] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.searchSourcing(query, qty);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">AI Parts Sourcing</h1>
        <p className="text-sm text-slate-500 mt-1">
          Search for MRO parts using natural language. Powered by knowledge graph + AI.
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Try "SKF 6204-2RS bearing" or "25mm bore ball bearing" or "M8 bolt grade 8.8"'
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <input
          type="number"
          value={qty}
          onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
          min={1}
          className="w-20 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-center"
          title="Quantity"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
        </button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* AI Response */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-100 text-blue-600">
                <Package className="h-3.5 w-3.5" />
              </div>
              <span className="text-sm font-medium text-slate-900">AI Response</span>
              {result.intent && (
                <span className="ml-auto rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
                  {result.intent}
                </span>
              )}
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-700">
                {result.parts_found} parts found
              </span>
            </div>
            <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap">
              {result.response}
            </div>
          </div>

          {/* Sourcing Results Table */}
          {result.sourcing_results.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
                <h3 className="text-sm font-semibold text-slate-900">
                  Sourcing Options ({result.sourcing_results.length})
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500 uppercase">
                      <th className="px-4 py-3">Part</th>
                      <th className="px-4 py-3">Seller</th>
                      <th className="px-4 py-3 text-right">Unit Price</th>
                      <th className="px-4 py-3 text-right">Total</th>
                      <th className="px-4 py-3 text-right">In Stock</th>
                      <th className="px-4 py-3 text-right">Delivery</th>
                      <th className="px-4 py-3 text-right">Distance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.sourcing_results.map((sr, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-900">{sr.sku}</div>
                          <div className="text-xs text-slate-500">{sr.manufacturer}</div>
                        </td>
                        <td className="px-4 py-3 text-slate-700">{sr.seller_name}</td>
                        <td className="px-4 py-3 text-right font-medium">
                          <DollarSign className="inline h-3 w-3 text-slate-400" />
                          {sr.unit_price.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-slate-900">
                          ${sr.total_cost.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right">{sr.qty_available}</td>
                        <td className="px-4 py-3 text-right">
                          <Truck className="inline h-3 w-3 text-slate-400 mr-1" />
                          {sr.transit_days}d
                        </td>
                        <td className="px-4 py-3 text-right text-slate-500">
                          {sr.distance_km > 0 ? `${sr.distance_km.toFixed(0)} km` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 3: Add route to `src/App.tsx`**

Add the lazy import after line 17:

```typescript
const Sourcing = lazy(() => import("@/pages/Sourcing"));
```

Add the route after the Chat route (line 43):

```tsx
          <Route path="/sourcing" element={<Suspense fallback={<PageLoader />}><Sourcing /></Suspense>} />
```

**Step 4: Add nav item to `src/components/layout/Sidebar.tsx`**

Import the `Search` icon (add to the import on line 3):

```typescript
import {
  LayoutDashboard,
  Package,
  Warehouse,
  ClipboardList,
  MessageSquareQuote,
  Truck,
  Receipt,
  RotateCcw,
  Bot,
  Radio,
  Search,
} from "lucide-react";
```

Add a new "Intelligence" nav section after "Front-Office" (~line 42):

```typescript
  {
    label: "Intelligence",
    items: [
      { to: "/sourcing", label: "AI Sourcing", icon: Search },
    ],
  },
```

**Step 5: Commit**

```bash
git add src/pages/Sourcing.tsx src/lib/api.ts src/App.tsx src/components/layout/Sidebar.tsx
git commit -m "feat: add frontend sourcing page with AI-powered part search"
```

---

### Task 8: Final Integration Test and Cleanup

**Files:**
- Modify: `main.py` (verify all wiring is correct)
- Run: Full test suite

**Step 1: Run the backend test suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (existing + new)

**Step 2: Run the frontend build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 3: Run the frontend tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm test`
Expected: All tests pass

**Step 4: Run linting**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run lint`
Expected: No errors

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete Neo4j end-to-end wiring — graph, sync, chat, embeddings, frontend"
```
