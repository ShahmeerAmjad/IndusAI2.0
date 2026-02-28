# Neo4j End-to-End Wiring Design

**Date:** 2026-02-28
**Status:** Approved
**Scope:** Full stack — Docker, API routes, PG→Neo4j sync, chat integration, embeddings, frontend

---

## Problem

The Neo4j knowledge graph infrastructure (client, service, schema, seed data, GraphRAG query engine) exists but is not connected end-to-end. Neo4j isn't in Docker Compose, there are no REST endpoints to query the graph, platform CRUD doesn't sync to the graph, the chat doesn't use GraphRAG, parts lack embeddings for vector search, and the frontend has no sourcing UI.

## Solution

Wire 6 integration points to make the knowledge graph fully operational.

---

## 1. Add Neo4j to Docker Compose

Add Neo4j 5 Community service to `docker-compose.yml`:
- Image: `neo4j:5-community`
- Ports: 7474 (HTTP), 7687 (Bolt)
- Volume: `neo4j_data` for persistence
- Health check via `cypher-shell`
- APOC plugin enabled
- Backend depends on Neo4j (service_healthy)
- Pass `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` to backend

## 2. Graph API Routes (`routes/graph.py`)

New FastAPI router at `/api/v1/graph/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/parts/{sku}` | GET | Part with specs, cross-refs, compatible parts |
| `/parts/search` | GET | Fulltext search (`?q=bearing 6204`) |
| `/parts/{sku}/cross-refs` | GET | Cross-references |
| `/parts/{sku}/compatible` | GET | Compatible parts |
| `/assemblies/{model}/bom` | GET | Bill of materials |
| `/stats` | GET | Graph node/edge counts |
| `/parts/{sku}/sync` | POST | Manual PG→Neo4j sync (admin) |

All endpoints require authentication. Stats endpoint is admin-only.

## 3. PostgreSQL → Neo4j Sync (`services/graph/sync.py`)

`GraphSyncService` class:

```python
class GraphSyncService:
    def __init__(self, graph_service, embedding_client=None):
        ...

    async def sync_product(self, product: dict) -> None:
        """Sync a product from PG to Neo4j (upsert part + specs + embedding)."""

    async def sync_inventory(self, sku: str, warehouse: str, qty: int) -> None:
        """Update inventory cache on graph node."""

    async def sync_price(self, sku: str, min_price: float, max_price: float) -> None:
        """Update price range on graph node."""

    async def bulk_sync_products(self, db_manager) -> dict:
        """Full sync of all PG products to Neo4j. Used for initial load."""
```

**Hook points in platform services:**
- `ProductService.create_product()` → `sync_service.sync_product()`
- `ProductService.update_product()` → `sync_service.sync_product()`
- `InventoryService.adjust_inventory()` → `sync_service.sync_inventory()`
- `PricingService` price updates → `sync_service.sync_price()`

Sync service is injected via `main.py` lifespan after both PG and Neo4j are ready.

## 4. Wire GraphRAG into Chat

Modify `ChatbotEngine` or `BusinessLogic` to route MRO intents through `GraphRAGQueryEngine`:
- Intents: `part_lookup`, `inventory_check`, `quote_request`, `technical_support`
- Pass `query_engine` to business logic during lifespan init
- Fall back to existing AI service if GraphRAG is unavailable

## 5. Part Embeddings

- In `seed_demo.py`: after upserting parts, call `embedding_client.embed()` and store on Part node
- In `GraphSyncService.sync_product()`: generate embedding from `f"{name} {description} {specs_text}"`
- Graceful degradation: skip if no Voyage API key

## 6. Frontend Sourcing Page (`src/pages/Sourcing.tsx`)

New page accessible from sidebar:
- Search bar with natural language input
- Results section showing:
  - Matched parts with specs and cross-references
  - Sourcing options table (seller, price, delivery, distance)
  - Intent classification badge
- Add `searchSourcing()` method to `src/lib/api.ts`
- Add route `/sourcing` to `App.tsx`
- Add sidebar nav item

---

## Architecture After Wiring

```
Frontend (React)
  ├── Sourcing Page → POST /api/sourcing/search
  ├── Chat Page → POST /api/v1/message → GraphRAG pipeline
  └── Graph Browse → GET /api/v1/graph/parts/*

GraphRAG Query Engine (5 stages)
  Stage 1: Intent + Entity Extraction
  Stage 2: Neo4j Cypher Resolution
  Stage 3: Neo4j Vector Fallback (embeddings)
  Stage 4: Context Merge (+ PG inventory/pricing)
  Stage 4b: Seller Matching
  Stage 5: Claude LLM Response

Platform CRUD
  ProductService.create/update → GraphSyncService → Neo4j
  InventoryService.adjust → GraphSyncService → Neo4j
  PricingService.update → GraphSyncService → Neo4j

Docker Compose
  PostgreSQL ← Backend → Neo4j
                 ↑
               Redis
```

## Files to Create/Modify

**Create:**
- `services/graph/sync.py` — GraphSyncService
- `routes/graph.py` — Graph API router
- `src/pages/Sourcing.tsx` — Frontend sourcing page

**Modify:**
- `docker-compose.yml` — Add Neo4j service
- `main.py` — Wire sync service, graph router, inject into chat
- `services/platform/product_service.py` — Add sync hooks
- `services/platform/inventory_service.py` — Add sync hooks
- `services/platform/pricing_service.py` — Add sync hooks
- `services/business_logic.py` — Route intents through GraphRAG
- `services/graph/seed_demo.py` — Add embedding generation
- `src/lib/api.ts` — Add sourcing API method
- `src/App.tsx` — Add sourcing route
- `src/components/layout/Sidebar.tsx` or equivalent — Add nav item
