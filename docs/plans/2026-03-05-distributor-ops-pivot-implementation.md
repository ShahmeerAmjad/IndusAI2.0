# Distributor Ops Pivot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the app from a buyer-focused MRO ERP into a distributor support automation tool with Chempoint knowledge base seeding, an omnichannel inbox with AI-drafted responses, and ops-focused KPIs.

**Architecture:** Bottom-up build — data layer first, then backend services, then frontend. Sidebar/Chat cleanup can run in parallel with backend work. All new tables use `CREATE TABLE IF NOT EXISTS` in `services/platform/schema.py`. All new services use the global `_service = None` + `set_service()` injection pattern. All new routes use `APIRouter(prefix="/api/v1/...", tags=[...])`.

**Tech Stack:** FastAPI, asyncpg (raw SQL), Neo4j 5.x, Claude Haiku (intent classification), Voyage AI (embeddings), React 18 + TypeScript + Tailwind (handrolled, no shadcn), React Query, Recharts.

**Worktree:** `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.worktrees/supplier-sales/`

**Design doc:** `docs/plans/2026-03-05-distributor-ops-pivot-design.md`

---

## Phase 1: Data Layer

### Task 1: Add inbound_messages and customer_accounts tables

**Files:**
- Modify: `services/platform/schema.py` — append new table DDL to `PLATFORM_SCHEMA` and indexes to `PLATFORM_INDEXES`
- Test: `tests/test_inbox_schema.py` (new)

**Step 1: Write the failing test**

```python
# tests/test_inbox_schema.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_schema_contains_inbound_messages():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS inbound_messages" in PLATFORM_SCHEMA

@pytest.mark.asyncio
async def test_schema_contains_customer_accounts():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS customer_accounts" in PLATFORM_SCHEMA

@pytest.mark.asyncio
async def test_schema_contains_documents():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS documents" in PLATFORM_SCHEMA

@pytest.mark.asyncio
async def test_schema_contains_classification_feedback():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS classification_feedback" in PLATFORM_SCHEMA

@pytest.mark.asyncio
async def test_indexes_contain_inbound_messages():
    from services.platform.schema import PLATFORM_INDEXES
    assert "idx_inbound_messages_status" in PLATFORM_INDEXES
    assert "idx_inbound_messages_channel" in PLATFORM_INDEXES
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.worktrees/supplier-sales && /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_inbox_schema.py -v`
Expected: FAIL — tables not yet in schema

**Step 3: Add tables to PLATFORM_SCHEMA**

Append to `PLATFORM_SCHEMA` in `services/platform/schema.py`:

```sql
-- Inbound message triage queue
CREATE TABLE IF NOT EXISTS inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL DEFAULT 'email',
    from_address TEXT NOT NULL,
    to_address TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    raw_payload JSONB,
    attachments JSONB,
    intents JSONB,
    status VARCHAR(20) DEFAULT 'new',
    assigned_to UUID,
    ai_draft_response TEXT,
    ai_confidence FLOAT,
    ai_suggested_attachments JSONB,
    conversation_id UUID,
    customer_account_id UUID,
    thread_id TEXT,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Customer accounts for distributor CRM
CREATE TABLE IF NOT EXISTS customer_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    fax_number TEXT,
    company TEXT,
    account_number TEXT UNIQUE,
    erp_customer_id TEXT,
    pricing_tier VARCHAR(20) DEFAULT 'standard',
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TDS/SDS document storage
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID,
    doc_type VARCHAR(10) NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT,
    file_size_bytes INTEGER,
    mime_type VARCHAR(50),
    extracted_text TEXT,
    structured_data JSONB,
    source_url TEXT,
    revision_date DATE,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trainable intent classifier feedback
CREATE TABLE IF NOT EXISTS classification_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES inbound_messages(id) ON DELETE CASCADE,
    ai_intent VARCHAR(30),
    ai_confidence FLOAT,
    human_intent VARCHAR(30),
    text_excerpt TEXT,
    is_correct BOOLEAN,
    corrected_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Append to `PLATFORM_INDEXES`:

```sql
CREATE INDEX IF NOT EXISTS idx_inbound_messages_status ON inbound_messages(status);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_channel ON inbound_messages(channel);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_created ON inbound_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_customer ON inbound_messages(customer_account_id);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_thread ON inbound_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_email ON customer_accounts(email);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_company ON customer_accounts(company);
CREATE INDEX IF NOT EXISTS idx_documents_product ON documents(product_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_classification_feedback_message ON classification_feedback(message_id);
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.worktrees/supplier-sales && /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_inbox_schema.py -v`
Expected: 5 PASSED

**Step 5: Run existing tests to verify no regression**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/ -x -q`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add services/platform/schema.py tests/test_inbox_schema.py
git commit -m "feat: add inbound_messages, customer_accounts, documents, classification_feedback tables"
```

---

## Phase 2: Knowledge Base Backend

### Task 2: Build Knowledge Base ingestion service

**Files:**
- Create: `services/knowledge_base_service.py`
- Test: `tests/test_knowledge_base_service.py`

**Context:** This service takes `ChempointProduct` dicts from the scraper and ingests them into Neo4j as structured nodes. It also handles the `documents` table for TDS/SDS storage.

**Step 1: Write the failing test**

```python
# tests/test_knowledge_base_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def _make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn

@pytest.fixture
def mock_graph():
    g = AsyncMock()
    g.run_query = AsyncMock(return_value=[])
    return g

@pytest.fixture
def service(mock_graph):
    from services.knowledge_base_service import KnowledgeBaseService
    pool, _ = _make_pool()
    return KnowledgeBaseService(pool=pool, graph_service=mock_graph)

SAMPLE_PRODUCT = {
    "name": "POLYOX WSR-301",
    "manufacturer": "Dow",
    "cas_number": "25322-68-3",
    "description": "Water-soluble polymer",
    "tds_url": "https://example.com/tds.pdf",
    "sds_url": "https://example.com/sds.pdf",
    "industries": ["Adhesives", "Coatings"],
    "product_line": "POLYOX",
}

@pytest.mark.asyncio
async def test_ingest_product_creates_neo4j_nodes(service, mock_graph):
    await service.ingest_product(SAMPLE_PRODUCT)
    # Should have called run_query to MERGE Product node
    assert mock_graph.run_query.call_count >= 1
    first_call = mock_graph.run_query.call_args_list[0]
    assert "MERGE" in first_call[0][0]
    assert "POLYOX WSR-301" in str(first_call)

@pytest.mark.asyncio
async def test_ingest_product_creates_manufacturer_relationship(service, mock_graph):
    await service.ingest_product(SAMPLE_PRODUCT)
    queries = [call[0][0] for call in mock_graph.run_query.call_args_list]
    mfr_query = [q for q in queries if "Manufacturer" in q and "MERGE" in q]
    assert len(mfr_query) >= 1

@pytest.mark.asyncio
async def test_ingest_product_creates_industry_relationships(service, mock_graph):
    await service.ingest_product(SAMPLE_PRODUCT)
    queries = [call[0][0] for call in mock_graph.run_query.call_args_list]
    industry_queries = [q for q in queries if "Industry" in q]
    assert len(industry_queries) >= 2  # Adhesives + Coatings

@pytest.mark.asyncio
async def test_list_products_returns_paginated(service, mock_graph):
    mock_graph.run_query.return_value = [
        {"p": {"name": "POLYOX WSR-301", "sku": "P001", "cas_number": "25322-68-3"}},
    ]
    results = await service.list_products(page=1, page_size=25)
    assert "items" in results

@pytest.mark.asyncio
async def test_get_product_detail(service, mock_graph):
    mock_graph.run_query.return_value = [
        {"p": {"name": "POLYOX WSR-301"}, "tds": None, "sds": None, "mfr": {"name": "Dow"}},
    ]
    result = await service.get_product("some-id")
    assert result is not None

@pytest.mark.asyncio
async def test_no_pool_returns_empty(mock_graph):
    from services.knowledge_base_service import KnowledgeBaseService
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    results = await svc.list_products()
    assert results["items"] == []
```

**Step 2: Run test to verify it fails**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_knowledge_base_service.py -v`
Expected: FAIL — module not found

**Step 3: Implement KnowledgeBaseService**

```python
# services/knowledge_base_service.py
"""Knowledge base service — ingests products into Neo4j, manages TDS/SDS documents."""

import logging
import uuid
import math

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    def __init__(self, pool, graph_service, llm_router=None):
        self._pool = pool
        self._graph = graph_service
        self._llm = llm_router

    async def ingest_product(self, product: dict) -> str:
        """Ingest a single product dict into Neo4j knowledge graph."""
        sku = product.get("sku") or f"CP-{uuid.uuid4().hex[:8].upper()}"
        name = product["name"]
        cas = product.get("cas_number", "")
        desc = product.get("description", "")
        mfr = product.get("manufacturer", "")
        product_line = product.get("product_line", "")
        industries = product.get("industries", [])

        # Merge Product node
        await self._graph.run_query(
            """MERGE (p:Part {name: $name})
               SET p.sku = $sku, p.cas_number = $cas,
                   p.description = $desc, p.source = 'chempoint'
               RETURN p""",
            {"name": name, "sku": sku, "cas": cas, "desc": desc},
        )

        # Merge Manufacturer + relationship
        if mfr:
            await self._graph.run_query(
                """MERGE (m:Manufacturer {name: $mfr})
                   WITH m
                   MATCH (p:Part {name: $name})
                   MERGE (p)-[:MANUFACTURED_BY]->(m)""",
                {"mfr": mfr, "name": name},
            )

        # Merge ProductLine + relationship
        if product_line:
            await self._graph.run_query(
                """MERGE (pl:ProductLine {name: $pl})
                   WITH pl
                   MATCH (p:Part {name: $name})
                   MERGE (p)-[:BELONGS_TO]->(pl)""",
                {"pl": product_line, "name": name},
            )

        # Merge Industry nodes + relationships
        for industry in industries:
            await self._graph.run_query(
                """MERGE (i:Industry {name: $industry})
                   WITH i
                   MATCH (p:Part {name: $name})
                   MERGE (p)-[:SERVES_INDUSTRY]->(i)""",
                {"industry": industry, "name": name},
            )

        # Store TDS/SDS URLs in documents table if pool available
        if self._pool:
            async with self._pool.acquire() as conn:
                for doc_type, url_key in [("TDS", "tds_url"), ("SDS", "sds_url")]:
                    url = product.get(url_key)
                    if url:
                        await conn.execute(
                            """INSERT INTO documents (product_id, doc_type, source_url, file_path, is_current)
                               VALUES (NULL, $1, $2, $2, true)
                               ON CONFLICT DO NOTHING""",
                            doc_type, url,
                        )

        return sku

    async def ingest_batch(self, products: list[dict]) -> dict:
        """Ingest a batch of products. Returns summary."""
        ingested = 0
        errors = []
        for p in products:
            try:
                await self.ingest_product(p)
                ingested += 1
            except Exception as e:
                errors.append({"product": p.get("name", "unknown"), "error": str(e)})
                logger.warning("Failed to ingest %s: %s", p.get("name"), e)
        return {"ingested": ingested, "errors": errors, "total": len(products)}

    async def list_products(self, page: int = 1, page_size: int = 25, search: str = None) -> dict:
        """List products from Neo4j with pagination."""
        if not self._graph:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        skip = (page - 1) * page_size

        if search:
            query = """MATCH (p:Part)
                       WHERE toLower(p.name) CONTAINS toLower($search)
                          OR toLower(p.cas_number) CONTAINS toLower($search)
                          OR toLower(p.sku) CONTAINS toLower($search)
                       RETURN p ORDER BY p.name SKIP $skip LIMIT $limit"""
            count_query = """MATCH (p:Part)
                            WHERE toLower(p.name) CONTAINS toLower($search)
                               OR toLower(p.cas_number) CONTAINS toLower($search)
                               OR toLower(p.sku) CONTAINS toLower($search)
                            RETURN count(p) as total"""
            params = {"search": search, "skip": skip, "limit": page_size}
            count_params = {"search": search}
        else:
            query = "MATCH (p:Part) RETURN p ORDER BY p.name SKIP $skip LIMIT $limit"
            count_query = "MATCH (p:Part) RETURN count(p) as total"
            params = {"skip": skip, "limit": page_size}
            count_params = {}

        rows = await self._graph.run_query(query, params)
        count_rows = await self._graph.run_query(count_query, count_params)
        total = count_rows[0]["total"] if count_rows else 0

        items = []
        for row in rows:
            p = row.get("p", {})
            if hasattr(p, "items"):
                items.append(dict(p))
            else:
                items.append(p)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)),
        }

    async def get_product(self, product_id: str) -> dict | None:
        """Get product detail with TDS/SDS and manufacturer."""
        rows = await self._graph.run_query(
            """MATCH (p:Part {sku: $id})
               OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
               OPTIONAL MATCH (p)-[:HAS_TDS]->(tds:TechnicalDataSheet)
               OPTIONAL MATCH (p)-[:HAS_SDS]->(sds:SafetyDataSheet)
               OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
               RETURN p, m, tds, sds, collect(DISTINCT i.name) as industries""",
            {"id": product_id},
        )
        if not rows:
            return None
        row = rows[0]
        result = dict(row.get("p", {})) if hasattr(row.get("p", {}), "items") else row.get("p", {})
        result["manufacturer"] = dict(row["m"]) if row.get("m") and hasattr(row["m"], "items") else row.get("m")
        result["tds"] = dict(row["tds"]) if row.get("tds") and hasattr(row["tds"], "items") else row.get("tds")
        result["sds"] = dict(row["sds"]) if row.get("sds") and hasattr(row["sds"], "items") else row.get("sds")
        result["industries"] = row.get("industries", [])
        return result
```

**Step 4: Run test to verify it passes**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_knowledge_base_service.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add services/knowledge_base_service.py tests/test_knowledge_base_service.py
git commit -m "feat: add KnowledgeBaseService for Neo4j product ingestion"
```

---

### Task 3: Build Knowledge Base API routes

**Files:**
- Create: `routes/knowledge_base.py`
- Modify: `main.py` — import, wire service, register router
- Test: `tests/test_knowledge_base_routes.py`

**Step 1: Write the failing test**

```python
# tests/test_knowledge_base_routes.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_list_products_endpoint():
    from routes.knowledge_base import router, set_kb_service
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    app = FastAPI()
    app.include_router(router)

    mock_svc = AsyncMock()
    mock_svc.list_products.return_value = {
        "items": [{"name": "POLYOX WSR-301", "sku": "P001"}],
        "total": 1, "page": 1, "page_size": 25, "total_pages": 1,
    }
    set_kb_service(mock_svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/knowledge-base/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "POLYOX WSR-301"

@pytest.mark.asyncio
async def test_crawl_endpoint_returns_job_id():
    from routes.knowledge_base import router, set_kb_service, set_chempoint_scraper
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    app = FastAPI()
    app.include_router(router)

    mock_svc = AsyncMock()
    mock_svc.ingest_batch.return_value = {"ingested": 5, "errors": [], "total": 5}
    set_kb_service(mock_svc)

    mock_scraper = AsyncMock()
    mock_scraper.crawl_full_catalog.return_value = [
        {"name": "Product A", "manufacturer": "Dow"},
    ]
    set_chempoint_scraper(mock_scraper)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/knowledge-base/crawl")
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "started"

@pytest.mark.asyncio
async def test_service_unavailable_returns_503():
    from routes.knowledge_base import router, _kb_service
    import routes.knowledge_base as mod
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    original = mod._kb_service
    mod._kb_service = None
    app = FastAPI()
    app.include_router(router)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/knowledge-base/products")
        assert resp.status_code == 503
    finally:
        mod._kb_service = original
```

**Step 2: Run test to verify it fails**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_knowledge_base_routes.py -v`
Expected: FAIL — module not found

**Step 3: Implement the routes**

```python
# routes/knowledge_base.py
"""Knowledge Base API — product browse, Chempoint crawl, document management."""

import uuid
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query, UploadFile, File

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["Knowledge Base"])

_kb_service = None
_chempoint_scraper = None
_crawl_jobs: dict = {}  # job_id -> {status, progress, result}


def set_kb_service(svc):
    global _kb_service
    _kb_service = svc


def set_chempoint_scraper(scraper):
    global _chempoint_scraper
    _chempoint_scraper = scraper


def _get_svc():
    if not _kb_service:
        raise HTTPException(status_code=503, detail="Knowledge base service unavailable")
    return _kb_service


@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query(None),
):
    return await _get_svc().list_products(page=page, page_size=page_size, search=search)


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    result = await _get_svc().get_product(product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.post("/crawl")
async def start_crawl(max_pages: int = Query(50, ge=1, le=200)):
    if not _chempoint_scraper:
        raise HTTPException(status_code=503, detail="Chempoint scraper not configured")

    job_id = str(uuid.uuid4())
    _crawl_jobs[job_id] = {"status": "started", "progress": 0, "result": None}

    async def _run_crawl():
        try:
            _crawl_jobs[job_id]["status"] = "running"
            products = await _chempoint_scraper.crawl_full_catalog(
                base_url="https://www.chempoint.com/products",
                max_pages=max_pages,
            )
            _crawl_jobs[job_id]["progress"] = 50
            result = await _get_svc().ingest_batch(products)
            _crawl_jobs[job_id]["status"] = "completed"
            _crawl_jobs[job_id]["progress"] = 100
            _crawl_jobs[job_id]["result"] = result
        except Exception as e:
            logger.error("Crawl job %s failed: %s", job_id, e)
            _crawl_jobs[job_id]["status"] = "failed"
            _crawl_jobs[job_id]["error"] = str(e)

    asyncio.create_task(_run_crawl())
    return {"job_id": job_id, "status": "started"}


@router.get("/crawl/{job_id}")
async def get_crawl_status(job_id: str):
    job = _crawl_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@router.post("/documents/upload")
async def upload_document(
    doc_type: str = Query(..., regex="^(TDS|SDS)$"),
    product_sku: str = Query(None),
    file: UploadFile = File(...),
):
    svc = _get_svc()
    content = await file.read()
    # Store file and optionally extract structured data
    doc_id = str(uuid.uuid4())
    if svc._pool:
        async with svc._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO documents (id, doc_type, file_name, file_path, mime_type, file_size_bytes, is_current)
                   VALUES ($1, $2, $3, $4, $5, $6, true)""",
                uuid.UUID(doc_id), doc_type, file.filename,
                f"uploads/{doc_id}_{file.filename}",
                file.content_type, len(content),
            )
    return {"document_id": doc_id, "file_name": file.filename, "doc_type": doc_type}
```

**Step 4: Wire in main.py**

Add to imports section of `main.py`:
```python
from routes.knowledge_base import router as kb_router, set_kb_service, set_chempoint_scraper
```

Add inside lifespan after platform services are wired:
```python
# Wire knowledge base service
from services.knowledge_base_service import KnowledgeBaseService
kb_service = KnowledgeBaseService(
    pool=db_manager.pool,
    graph_service=getattr(app.state, "graph_service", None),
    llm_router=llm_router,
)
set_kb_service(kb_service)

# Wire chempoint scraper (if Firecrawl key available)
if settings.firecrawl_api_key:
    from services.ingestion.chempoint_scraper import ChempointScraper
    chempoint_scraper = ChempointScraper(
        firecrawl_api_key=settings.firecrawl_api_key,
        llm_router=llm_router,
    )
    set_chempoint_scraper(chempoint_scraper)
```

Add to router registration:
```python
app.include_router(kb_router)
```

**Step 5: Run tests**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_knowledge_base_routes.py tests/test_knowledge_base_service.py -v`
Expected: All PASSED

**Step 6: Commit**

```bash
git add routes/knowledge_base.py main.py tests/test_knowledge_base_routes.py
git commit -m "feat: add Knowledge Base API routes with Chempoint crawl trigger"
```

---

## Phase 3: Inbox Backend

### Task 4: Extend intent classifier to 9 intents with multi-intent support

**Files:**
- Modify: `services/ai/models.py` — add new IntentType values
- Modify: `services/intent_classifier.py` — add new patterns + multi-intent `classify_multi()`
- Test: `tests/test_intent_classifier.py` (modify existing)

**Step 1: Write the failing test**

Add to `tests/test_intent_classifier.py` (or create if not exists):

```python
# tests/test_intent_classifier_multi.py
import pytest
from services.intent_classifier import IntentClassifier

@pytest.fixture
def classifier():
    return IntentClassifier()

def test_classify_tds_request(classifier):
    msg_type, confidence = classifier.classify("Can you send me the TDS for POLYOX WSR-301?")
    assert confidence > 0.5

def test_classify_place_order(classifier):
    msg_type, confidence = classifier.classify("I need to order 500kg of epoxy resin")
    assert confidence > 0.5

def test_classify_sample_request(classifier):
    msg_type, confidence = classifier.classify("Can I get a sample of your silicone sealant?")
    assert confidence > 0.5

def test_classify_reorder(classifier):
    msg_type, confidence = classifier.classify("Same as my last order please")
    assert confidence > 0.5

@pytest.mark.asyncio
async def test_classify_multi_intent():
    classifier = IntentClassifier()
    # Mock the LLM to avoid real API calls
    from unittest.mock import AsyncMock
    classifier._llm = AsyncMock()
    classifier._llm.chat.return_value = '''[
        {"intent": "request_tds_sds", "confidence": 0.95, "text_span": "send me the SDS for Polyox", "entities": {"product": "Polyox WSR-301"}},
        {"intent": "request_quote", "confidence": 0.9, "text_span": "quote for 500kg", "entities": {"quantity": "500kg"}}
    ]'''
    results = await classifier.classify_multi(
        "Hi, can you send me the SDS for Polyox WSR-301? Also, I need a quote for 500kg."
    )
    assert len(results) == 2
    assert results[0]["intent"] == "request_tds_sds"
    assert results[1]["intent"] == "request_quote"
```

**Step 2: Run test to verify it fails**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_intent_classifier_multi.py -v`
Expected: FAIL — new patterns/methods don't exist yet

**Step 3: Update IntentType enum**

In `services/ai/models.py`, update the `IntentType` enum:

```python
class IntentType(str, Enum):
    PLACE_ORDER       = "place_order"
    REQUEST_QUOTE     = "request_quote"
    REQUEST_TDS_SDS   = "request_tds_sds"
    ORDER_STATUS      = "order_status"
    TECHNICAL_SUPPORT = "technical_support"
    RETURN_COMPLAINT  = "return_complaint"
    REORDER           = "reorder"
    ACCOUNT_INQUIRY   = "account_inquiry"
    SAMPLE_REQUEST    = "sample_request"
    GENERAL_QUERY     = "general_query"
```

**Step 4: Add new patterns + `classify_multi()` to IntentClassifier**

In `services/intent_classifier.py`, add new regex patterns for the new intents and a `classify_multi` method:

```python
async def classify_multi(self, text: str) -> list[dict]:
    """Classify multiple intents from a single message using LLM."""
    if not self._llm:
        # Fallback: single intent from regex
        msg_type, conf = self.classify(text)
        return [{"intent": msg_type.value, "confidence": conf, "text_span": text, "entities": {}}]

    prompt = f"""Analyze this customer message and identify ALL intents present.
Return a JSON array of objects, each with: intent, confidence (0-1), text_span, entities.

Valid intents: place_order, request_quote, request_tds_sds, order_status,
technical_support, return_complaint, reorder, account_inquiry, sample_request, general_query

Message: {text}

Return ONLY the JSON array, no other text."""

    try:
        response = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            task="intent_classification",
            max_tokens=1024,
            temperature=0.1,
        )
        import re, json
        match = re.search(r'\[[\s\S]*\]', response)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning("Multi-intent LLM classification failed: %s", e)

    # Fallback to single regex
    msg_type, conf = self.classify(text)
    return [{"intent": msg_type.value, "confidence": conf, "text_span": text, "entities": {}}]
```

Add new patterns to the `self.patterns` dict for:
- `SAMPLE_REQUEST`: `r'(?:sample|trial|test\s+quantity)'`
- `REORDER`: `r'(?:same\s+as\s+(?:last|previous)|re-?order|repeat\s+order)'`
- `REQUEST_TDS_SDS`: `r'(?:tds|sds|technical\s+data|safety\s+data|msds|data\s+sheet)'`
- `PLACE_ORDER`: `r'(?:(?:i\s+)?need\s+to\s+order|place\s+(?:an?\s+)?order|buy|purchase|need\s+\d+)'`

**Step 5: Run tests**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_intent_classifier_multi.py -v`
Expected: All PASSED

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/ -x -q`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add services/ai/models.py services/intent_classifier.py tests/test_intent_classifier_multi.py
git commit -m "feat: extend intent classifier to 9 intents with multi-intent support"
```

---

### Task 5: Build auto-response engine

**Files:**
- Create: `services/auto_response_engine.py`
- Test: `tests/test_auto_response_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_auto_response_engine.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_deps():
    graph = AsyncMock()
    llm = AsyncMock()
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return {"graph": graph, "llm": llm, "pool": pool, "conn": conn}

@pytest.fixture
def engine(mock_deps):
    from services.auto_response_engine import AutoResponseEngine
    return AutoResponseEngine(
        pool=mock_deps["pool"],
        graph_service=mock_deps["graph"],
        llm_router=mock_deps["llm"],
    )

@pytest.mark.asyncio
async def test_draft_tds_request(engine, mock_deps):
    mock_deps["graph"].run_query.return_value = [
        {"p": {"name": "POLYOX WSR-301", "sku": "P001"}, "tds": {"appearance": "white powder", "pdf_url": "https://example.com/tds.pdf"}}
    ]
    mock_deps["llm"].chat.return_value = "Here is the TDS information for POLYOX WSR-301..."

    result = await engine.draft_response({
        "intents": [{"intent": "request_tds_sds", "confidence": 0.95, "entities": {"product": "POLYOX WSR-301"}}],
        "body": "Can you send me the TDS for POLYOX WSR-301?",
    })
    assert result["draft"] is not None
    assert result["confidence"] > 0.5

@pytest.mark.asyncio
async def test_draft_general_query(engine, mock_deps):
    mock_deps["llm"].chat.return_value = "Thank you for your inquiry..."
    result = await engine.draft_response({
        "intents": [{"intent": "general_query", "confidence": 0.7, "entities": {}}],
        "body": "Hello, what are your business hours?",
    })
    assert result["draft"] is not None

@pytest.mark.asyncio
async def test_low_confidence_flags_for_review(engine, mock_deps):
    mock_deps["llm"].chat.return_value = "I'm not sure..."
    result = await engine.draft_response({
        "intents": [{"intent": "general_query", "confidence": 0.3, "entities": {}}],
        "body": "asdfghjkl",
    })
    assert result["confidence"] < 0.5
```

**Step 2: Run test to verify it fails**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_auto_response_engine.py -v`
Expected: FAIL — module not found

**Step 3: Implement AutoResponseEngine**

```python
# services/auto_response_engine.py
"""Auto-response engine — generates AI draft responses for inbound messages."""

import logging

logger = logging.getLogger(__name__)

DRAFT_PROMPT = """You are a support assistant for an industrial parts distributor.
A customer sent this message: {body}

Detected intents: {intents}

{context}

Write a professional, helpful draft response addressing all customer requests.
Be concise. If you have specific product data, include it. If attaching documents, mention them.
Do NOT make up information — only use the provided context."""


class AutoResponseEngine:
    def __init__(self, pool, graph_service, llm_router):
        self._pool = pool
        self._graph = graph_service
        self._llm = llm_router

    async def draft_response(self, message: dict) -> dict:
        """Generate an AI draft response for a classified inbound message."""
        intents = message.get("intents", [])
        body = message.get("body", "")
        attachments = []

        # Gather context per intent
        context_parts = []
        for intent_info in intents:
            intent = intent_info.get("intent", "")
            entities = intent_info.get("entities", {})
            ctx = await self._gather_context(intent, entities)
            if ctx:
                context_parts.append(ctx)

        context = "\n\n".join(context_parts) if context_parts else "No specific product data found."

        # Calculate aggregate confidence
        confidences = [i.get("confidence", 0.5) for i in intents]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.3

        # Generate draft via LLM
        intent_summary = ", ".join(i.get("intent", "unknown") for i in intents)
        prompt = DRAFT_PROMPT.format(body=body, intents=intent_summary, context=context)

        try:
            draft = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                task="auto_response",
                max_tokens=1024,
                temperature=0.3,
            )
        except Exception as e:
            logger.error("Draft generation failed: %s", e)
            draft = "I'll look into this and get back to you shortly."
            avg_confidence = 0.2

        return {
            "draft": draft,
            "confidence": round(avg_confidence, 2),
            "attachments": attachments,
        }

    async def _gather_context(self, intent: str, entities: dict) -> str | None:
        """Query relevant data sources based on intent type."""
        product = entities.get("product", "")

        if intent == "request_tds_sds" and product and self._graph:
            rows = await self._graph.run_query(
                """MATCH (p:Part)
                   WHERE toLower(p.name) CONTAINS toLower($name)
                   OPTIONAL MATCH (p)-[:HAS_TDS]->(tds:TechnicalDataSheet)
                   OPTIONAL MATCH (p)-[:HAS_SDS]->(sds:SafetyDataSheet)
                   RETURN p, tds, sds LIMIT 1""",
                {"name": product},
            )
            if rows:
                row = rows[0]
                parts = [f"Product found: {row.get('p', {}).get('name', product)}"]
                if row.get("tds"):
                    parts.append(f"TDS available: {dict(row['tds']) if hasattr(row['tds'], 'items') else row['tds']}")
                if row.get("sds"):
                    parts.append(f"SDS available: {dict(row['sds']) if hasattr(row['sds'], 'items') else row['sds']}")
                return "\n".join(parts)

        if intent == "technical_support" and product and self._graph:
            rows = await self._graph.run_query(
                """MATCH (p:Part)
                   WHERE toLower(p.name) CONTAINS toLower($name)
                   OPTIONAL MATCH (p)-[:HAS_TDS]->(tds:TechnicalDataSheet)
                   RETURN p, tds LIMIT 1""",
                {"name": product},
            )
            if rows:
                return f"Technical data: {rows[0]}"

        if intent in ("place_order", "request_quote", "reorder") and self._pool:
            # Check inventory for mentioned products
            if product:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT name, sku, category FROM products WHERE LOWER(name) LIKE $1 LIMIT 1",
                        f"%{product.lower()}%",
                    )
                    if row:
                        return f"Product in catalog: {row['name']} (SKU: {row['sku']})"

        return None
```

**Step 4: Run tests**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_auto_response_engine.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add services/auto_response_engine.py tests/test_auto_response_engine.py
git commit -m "feat: add auto-response engine for AI draft generation"
```

---

### Task 6: Build Inbox API routes + seed data

**Files:**
- Create: `routes/inbox.py`
- Create: `services/inbox_service.py`
- Create: `services/platform/seed_inbox.py` (seed data)
- Modify: `main.py` — wire inbox service + router + seed
- Test: `tests/test_inbox_service.py`
- Test: `tests/test_inbox_routes.py`

**Step 1: Write the failing tests**

```python
# tests/test_inbox_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock

def _make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn

@pytest.fixture
def service():
    from services.inbox_service import InboxService
    pool, _ = _make_pool()
    classifier = AsyncMock()
    auto_response = AsyncMock()
    return InboxService(pool=pool, classifier=classifier, auto_response_engine=auto_response)

@pytest.fixture
def mock_pool():
    return _make_pool()

@pytest.mark.asyncio
async def test_list_messages(service, mock_pool):
    pool, conn = mock_pool
    service._pool = pool
    conn.fetch.return_value = [
        {"id": "abc", "channel": "email", "from_address": "bob@acme.com",
         "subject": "Need TDS", "status": "new", "intents": None, "created_at": "2026-03-05T00:00:00Z"},
    ]
    conn.fetchval.return_value = 1
    result = await service.list_messages(page=1, page_size=25)
    assert result["total"] == 1
    assert len(result["items"]) == 1

@pytest.mark.asyncio
async def test_simulate_inbound(service):
    service._classifier = AsyncMock()
    service._classifier.classify_multi.return_value = [
        {"intent": "request_tds_sds", "confidence": 0.9, "text_span": "send TDS", "entities": {"product": "Polyox"}}
    ]
    service._auto_response = AsyncMock()
    service._auto_response.draft_response.return_value = {
        "draft": "Here is the TDS...", "confidence": 0.85, "attachments": [],
    }
    pool, conn = _make_pool()
    service._pool = pool
    conn.fetchrow.return_value = {"id": "new-id"}

    result = await service.simulate_inbound(
        from_address="test@example.com",
        subject="Need TDS for Polyox",
        body="Can you send me the TDS for Polyox WSR-301?",
    )
    assert result["id"] == "new-id"
    assert result["intents"][0]["intent"] == "request_tds_sds"

@pytest.mark.asyncio
async def test_approve_message(service):
    pool, conn = _make_pool()
    service._pool = pool
    conn.fetchrow.return_value = {"id": "msg-1", "status": "draft_ready"}
    conn.execute.return_value = None

    result = await service.approve_message("msg-1")
    assert result["status"] == "sent"

@pytest.mark.asyncio
async def test_get_stats(service):
    pool, conn = _make_pool()
    service._pool = pool
    conn.fetchrow.return_value = {
        "total_today": 15, "avg_response_seconds": 180,
        "approved_without_edit": 10, "total_reviewed": 12,
    }
    conn.fetch.return_value = [
        {"intent": "request_tds_sds", "count": 5},
        {"intent": "place_order", "count": 3},
    ]
    stats = await service.get_stats()
    assert stats["messages_today"] == 15
    assert stats["ai_accuracy"] > 0

@pytest.mark.asyncio
async def test_no_pool(mock_pool):
    from services.inbox_service import InboxService
    svc = InboxService(pool=None, classifier=None, auto_response_engine=None)
    result = await svc.list_messages()
    assert result["items"] == []
```

**Step 2: Run test to verify it fails**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_inbox_service.py -v`
Expected: FAIL

**Step 3: Implement InboxService**

```python
# services/inbox_service.py
"""Inbox service — manages inbound messages, classification, AI drafts, and review actions."""

import json
import logging
import math
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InboxService:
    def __init__(self, pool, classifier, auto_response_engine):
        self._pool = pool
        self._classifier = classifier
        self._auto_response = auto_response_engine

    async def list_messages(
        self, page: int = 1, page_size: int = 25,
        status: str = None, channel: str = None, intent: str = None,
    ) -> dict:
        if not self._pool:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        conditions = []
        params = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if channel:
            conditions.append(f"channel = ${idx}")
            params.append(channel)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        offset = (page - 1) * page_size

        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM inbound_messages {where}", *params,
            )
            rows = await conn.fetch(
                f"""SELECT id, channel, from_address, subject, body, status,
                           intents, ai_draft_response, ai_confidence, created_at
                    FROM inbound_messages {where}
                    ORDER BY created_at DESC
                    OFFSET ${idx} LIMIT ${idx + 1}""",
                *params, offset, page_size,
            )

        items = []
        for r in rows:
            item = dict(r)
            if item.get("intents") and isinstance(item["intents"], str):
                item["intents"] = json.loads(item["intents"])
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)),
        }

    async def get_message(self, message_id: str) -> dict | None:
        if not self._pool:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM inbound_messages WHERE id = $1",
                uuid.UUID(message_id),
            )
        if not row:
            return None
        item = dict(row)
        if item.get("intents") and isinstance(item["intents"], str):
            item["intents"] = json.loads(item["intents"])
        return item

    async def simulate_inbound(self, from_address: str, subject: str, body: str, channel: str = "email") -> dict:
        """Simulate an inbound message — classify, draft, store."""
        # Classify
        intents = []
        if self._classifier:
            intents = await self._classifier.classify_multi(body)

        # Draft response
        draft_result = {"draft": None, "confidence": 0.0, "attachments": []}
        if self._auto_response and intents:
            draft_result = await self._auto_response.draft_response({
                "intents": intents, "body": body,
            })

        status = "draft_ready" if draft_result["draft"] else "classified"

        # Store
        msg_id = None
        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO inbound_messages
                       (channel, from_address, subject, body, intents, status,
                        ai_draft_response, ai_confidence, ai_suggested_attachments)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                       RETURNING id""",
                    channel, from_address, subject, body,
                    json.dumps(intents), status,
                    draft_result["draft"], draft_result["confidence"],
                    json.dumps(draft_result.get("attachments", [])),
                )
                msg_id = row["id"] if row else None

        return {
            "id": msg_id,
            "intents": intents,
            "status": status,
            "ai_draft": draft_result["draft"],
            "ai_confidence": draft_result["confidence"],
        }

    async def approve_message(self, message_id: str, edited_response: str = None) -> dict:
        """Approve (or edit+approve) a message's AI draft."""
        if not self._pool:
            return {"status": "error", "detail": "No pool"}

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, status, ai_draft_response FROM inbound_messages WHERE id = $1",
                uuid.UUID(message_id),
            )
            if not row:
                return {"status": "error", "detail": "Not found"}

            response = edited_response or row["ai_draft_response"]
            was_edited = edited_response is not None

            await conn.execute(
                """UPDATE inbound_messages
                   SET status = 'sent', ai_draft_response = $1,
                       reviewed_at = $2, sent_at = $2
                   WHERE id = $3""",
                response, datetime.now(timezone.utc), uuid.UUID(message_id),
            )

        return {"status": "sent", "was_edited": was_edited}

    async def escalate_message(self, message_id: str, assigned_to: str = None) -> dict:
        if not self._pool:
            return {"status": "error"}
        async with self._pool.acquire() as conn:
            await conn.execute(
                """UPDATE inbound_messages SET status = 'escalated', assigned_to = $1 WHERE id = $2""",
                uuid.UUID(assigned_to) if assigned_to else None, uuid.UUID(message_id),
            )
        return {"status": "escalated"}

    async def submit_feedback(self, message_id: str, human_intent: str, is_correct: bool) -> dict:
        if not self._pool:
            return {"status": "error"}
        async with self._pool.acquire() as conn:
            msg = await conn.fetchrow(
                "SELECT intents, ai_confidence FROM inbound_messages WHERE id = $1",
                uuid.UUID(message_id),
            )
            ai_intent = None
            ai_conf = None
            if msg and msg["intents"]:
                intents = json.loads(msg["intents"]) if isinstance(msg["intents"], str) else msg["intents"]
                if intents:
                    ai_intent = intents[0].get("intent")
                    ai_conf = intents[0].get("confidence")

            await conn.execute(
                """INSERT INTO classification_feedback
                   (message_id, ai_intent, ai_confidence, human_intent, is_correct)
                   VALUES ($1, $2, $3, $4, $5)""",
                uuid.UUID(message_id), ai_intent, ai_conf, human_intent, is_correct,
            )
        return {"status": "feedback_recorded"}

    async def get_stats(self) -> dict:
        """Aggregate stats for the ops dashboard."""
        if not self._pool:
            return {"messages_today": 0, "avg_response_time": 0, "ai_accuracy": 0, "hours_saved": 0}

        async with self._pool.acquire() as conn:
            summary = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as total_today,
                    AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at)))
                        FILTER (WHERE reviewed_at IS NOT NULL) as avg_response_seconds,
                    COUNT(*) FILTER (WHERE status = 'sent' AND reviewed_at IS NOT NULL) as approved_without_edit,
                    COUNT(*) FILTER (WHERE status IN ('sent', 'escalated')) as total_reviewed
                FROM inbound_messages
            """)

            intent_dist = await conn.fetch("""
                SELECT intent_item->>'intent' as intent, COUNT(*) as count
                FROM inbound_messages,
                     jsonb_array_elements(intents::jsonb) as intent_item
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY intent_item->>'intent'
                ORDER BY count DESC
            """)

        total_today = summary["total_today"] or 0
        avg_seconds = summary["avg_response_seconds"] or 0
        approved = summary["approved_without_edit"] or 0
        reviewed = summary["total_reviewed"] or 1

        return {
            "messages_today": total_today,
            "avg_response_time": round(avg_seconds / 60, 1),  # minutes
            "ai_accuracy": round(approved / reviewed * 100, 1) if reviewed else 0,
            "hours_saved": round(total_today * 5 / 60, 1),  # ~5 min per message saved
            "intent_distribution": [dict(r) for r in intent_dist],
        }
```

**Step 4: Run tests**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_inbox_service.py -v`
Expected: 5 PASSED

**Step 5: Create inbox routes**

```python
# routes/inbox.py
"""Inbox API — inbound message triage with AI drafts."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/inbox", tags=["Inbox"])

_inbox_service = None

def set_inbox_service(svc):
    global _inbox_service
    _inbox_service = svc

def _get_svc():
    if not _inbox_service:
        raise HTTPException(status_code=503, detail="Inbox service unavailable")
    return _inbox_service


class SimulateRequest(BaseModel):
    from_address: str = "demo@customer.com"
    subject: str = "Customer inquiry"
    body: str
    channel: str = "email"


class ApproveRequest(BaseModel):
    edited_response: str | None = None


class FeedbackRequest(BaseModel):
    human_intent: str
    is_correct: bool


@router.get("")
async def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str = Query(None),
    channel: str = Query(None),
):
    return await _get_svc().list_messages(
        page=page, page_size=page_size, status=status, channel=channel,
    )


@router.get("/stats")
async def get_stats():
    return await _get_svc().get_stats()


@router.get("/{message_id}")
async def get_message(message_id: str):
    msg = await _get_svc().get_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.post("/simulate")
async def simulate_inbound(req: SimulateRequest):
    return await _get_svc().simulate_inbound(
        from_address=req.from_address,
        subject=req.subject,
        body=req.body,
        channel=req.channel,
    )


@router.post("/{message_id}/approve")
async def approve_message(message_id: str, req: ApproveRequest = None):
    edited = req.edited_response if req else None
    return await _get_svc().approve_message(message_id, edited_response=edited)


@router.post("/{message_id}/escalate")
async def escalate_message(message_id: str):
    return await _get_svc().escalate_message(message_id)


@router.post("/{message_id}/feedback")
async def submit_feedback(message_id: str, req: FeedbackRequest):
    return await _get_svc().submit_feedback(message_id, req.human_intent, req.is_correct)
```

**Step 6: Create seed data**

```python
# services/platform/seed_inbox.py
"""Seed sample inbound messages for demo/development."""

import json
import logging
import uuid

logger = logging.getLogger(__name__)

SAMPLE_MESSAGES = [
    {
        "channel": "email", "from_address": "john.smith@acmemfg.com", "subject": "Need TDS for POLYOX WSR-301",
        "body": "Hi, can you send me the technical data sheet for POLYOX WSR-301? We're evaluating it for a new adhesive formulation.",
        "intents": [{"intent": "request_tds_sds", "confidence": 0.95, "text_span": "send me the technical data sheet for POLYOX WSR-301", "entities": {"product": "POLYOX WSR-301", "doc_type": "TDS"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi John,\n\nThank you for your interest in POLYOX WSR-301. I've attached the Technical Data Sheet for your review.\n\nKey specs:\n- Appearance: White granular powder\n- Molecular Weight: ~4,000,000\n- Viscosity (5% solution): 1,650-5,500 cps\n\nPlease let me know if you need any additional information or would like to discuss your adhesive application in more detail.\n\nBest regards",
        "ai_confidence": 0.92,
    },
    {
        "channel": "email", "from_address": "sarah@pacificcoatings.com", "subject": "Quote for epoxy resin - 2000kg",
        "body": "Hello, we need a quote for 2000kg of your standard epoxy resin. Delivery to our Portland facility. PO terms NET30.",
        "intents": [{"intent": "request_quote", "confidence": 0.93, "text_span": "need a quote for 2000kg of your standard epoxy resin", "entities": {"product": "epoxy resin", "quantity": "2000kg"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Sarah,\n\nThank you for your quote request. Based on your NET30 terms and the quantity of 2,000kg, here's our pricing:\n\n- Product: Standard Epoxy Resin\n- Quantity: 2,000 kg\n- Unit Price: $12.50/kg\n- Total: $25,000.00\n- Delivery: Portland facility, est. 5-7 business days\n\nThis quote is valid for 30 days. Shall I proceed with a formal quote document?\n\nBest regards",
        "ai_confidence": 0.88,
    },
    {
        "channel": "email", "from_address": "mike.chen@westlabsupply.com", "subject": "SDS needed - CAS 9003-11-6",
        "body": "We need the Safety Data Sheet for the product with CAS number 9003-11-6. Our safety team needs it for compliance audit.",
        "intents": [{"intent": "request_tds_sds", "confidence": 0.96, "text_span": "Safety Data Sheet for the product with CAS number 9003-11-6", "entities": {"cas_number": "9003-11-6", "doc_type": "SDS"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Mike,\n\nI've attached the Safety Data Sheet for CAS 9003-11-6 (Polyvinyl Alcohol). This is our most current revision.\n\nKey safety information:\n- GHS Classification: Not classified as hazardous\n- PPE: Safety glasses, gloves recommended for handling\n- Storage: Keep in dry, cool area\n\nPlease let me know if you need SDS documents for any other products.\n\nBest regards",
        "ai_confidence": 0.94,
    },
    {
        "channel": "web", "from_address": "lisa@greenchemsolutions.com", "subject": "Order status PO-78432",
        "body": "Can you check on the status of our order PO-78432? It was supposed to arrive yesterday.",
        "intents": [{"intent": "order_status", "confidence": 0.97, "text_span": "status of our order PO-78432", "entities": {"po_number": "PO-78432"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Lisa,\n\nI've checked on PO-78432. The shipment was dispatched on March 3rd via FedEx Freight (tracking: 789456123). It appears there was a delay at the Memphis hub.\n\nCurrent estimated delivery: March 6th.\n\nI apologize for the inconvenience. I'll monitor this and update you if there are any further changes.\n\nBest regards",
        "ai_confidence": 0.85,
    },
    {
        "channel": "email", "from_address": "david.r@industrialtechcorp.com", "subject": "Technical question about high-temp lubricants",
        "body": "What viscosity grade do you recommend for continuous operation at 250C in a food-grade environment? We're looking at silicone-based options.",
        "intents": [{"intent": "technical_support", "confidence": 0.91, "text_span": "What viscosity grade do you recommend for continuous operation at 250C", "entities": {"application": "high-temp lubricant", "temperature": "250C", "requirement": "food-grade"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi David,\n\nFor continuous operation at 250\u00b0C in a food-grade environment, I'd recommend our Food-Grade Silicone Lubricant (ISO VG 100-150 range).\n\nKey specs:\n- Operating range: -40\u00b0C to 300\u00b0C\n- NSF H1 registered for food contact\n- Viscosity: 100 cSt at 40\u00b0C\n\nI'm attaching the TDS for your review. Would you like a sample to test in your application?\n\nBest regards",
        "ai_confidence": 0.87,
    },
    {
        "channel": "email", "from_address": "anna.k@northstarplastics.com", "subject": "Damaged shipment - need RMA",
        "body": "We received our order #ORD-5521 today and 3 drums were damaged during shipping. Product is leaking. We need a replacement or credit.",
        "intents": [{"intent": "return_complaint", "confidence": 0.96, "text_span": "3 drums were damaged during shipping. Product is leaking", "entities": {"order_number": "ORD-5521", "issue": "shipping damage", "quantity_affected": "3 drums"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Anna,\n\nI'm sorry to hear about the damage to your order ORD-5521. We take shipping quality seriously.\n\nI've initiated an RMA (Return Merchandise Authorization) for the 3 damaged drums:\n- RMA #: RMA-2026-0312\n- Pickup will be scheduled within 48 hours\n- Replacement shipment will be expedited at no charge\n\nCould you please send photos of the damaged drums for our carrier claim? You can reply to this email with the images.\n\nBest regards",
        "ai_confidence": 0.90,
    },
    {
        "channel": "email", "from_address": "tom@precisionadhesives.com", "subject": "Reorder - same as last month",
        "body": "Hi, please process the same order as our last one from February. Same quantities, same shipping address.",
        "intents": [{"intent": "reorder", "confidence": 0.94, "text_span": "same order as our last one from February", "entities": {}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Tom,\n\nI've pulled up your February order. Here's what I have:\n\n- 500kg Epoxy Resin Base (SKU: ER-500)\n- 200kg Hardener H-100 (SKU: HD-100)\n- 50L Solvent Cleaner (SKU: SC-050)\n\nTotal: $8,750.00 (same pricing as February)\nShipping to: 1234 Industrial Pkwy, Portland OR\n\nShall I confirm this order?\n\nBest regards",
        "ai_confidence": 0.82,
    },
    {
        "channel": "email", "from_address": "nancy@coastalchemicals.com", "subject": "Credit limit inquiry",
        "body": "Hi, I'd like to know our current credit limit and outstanding balance. Also, can we increase our credit line?",
        "intents": [{"intent": "account_inquiry", "confidence": 0.93, "text_span": "current credit limit and outstanding balance", "entities": {}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Nancy,\n\nHere's your account summary:\n\n- Credit Limit: $50,000\n- Outstanding Balance: $12,340\n- Available Credit: $37,660\n- Payment Terms: NET30\n\nRegarding a credit line increase, I'll forward your request to our credit team. They typically review within 2-3 business days. Could you provide your most recent financial statements to expedite the process?\n\nBest regards",
        "ai_confidence": 0.86,
    },
    {
        "channel": "web", "from_address": "james@advancedmaterials.co", "subject": "Sample request - silicone sealants",
        "body": "We're evaluating silicone sealants for our new product line. Can we get samples of your top 3 options for outdoor use?",
        "intents": [{"intent": "sample_request", "confidence": 0.95, "text_span": "get samples of your top 3 options for outdoor use", "entities": {"product": "silicone sealants", "requirement": "outdoor use"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hi James,\n\nI'd be happy to arrange samples for you. For outdoor silicone sealants, I recommend:\n\n1. WeatherSeal Pro 500 - UV resistant, -40 to 200\u00b0C\n2. FlexBond Outdoor 300 - High elongation, paintable\n3. UltraClear Sealant 100 - Transparent, mold resistant\n\nI'll ship 500ml samples of each to your facility. Expected delivery: 3-5 business days.\n\nCould you confirm your shipping address?\n\nBest regards",
        "ai_confidence": 0.91,
    },
    {
        "channel": "email", "from_address": "rachel@techpolymers.com", "subject": "Multiple requests",
        "body": "Hi, a few things:\n1. Please send the TDS for POLYOX WSR-205\n2. What's the status of our order PO-9921?\n3. We'd also like a quote for 1000kg of polyethylene glycol",
        "intents": [
            {"intent": "request_tds_sds", "confidence": 0.94, "text_span": "send the TDS for POLYOX WSR-205", "entities": {"product": "POLYOX WSR-205", "doc_type": "TDS"}},
            {"intent": "order_status", "confidence": 0.92, "text_span": "status of our order PO-9921", "entities": {"po_number": "PO-9921"}},
            {"intent": "request_quote", "confidence": 0.90, "text_span": "quote for 1000kg of polyethylene glycol", "entities": {"product": "polyethylene glycol", "quantity": "1000kg"}},
        ],
        "status": "draft_ready",
        "ai_draft_response": "Hi Rachel,\n\nHappy to help with all three requests:\n\n**1. TDS for POLYOX WSR-205**\nAttached to this email. Key specs: MW ~600,000, viscosity 4,500-8,800 cps (5% solution).\n\n**2. Order PO-9921 Status**\nYour order shipped March 2nd via UPS Freight. Tracking: 1Z999AA10. Estimated delivery: March 7th.\n\n**3. Quote for Polyethylene Glycol**\n- Product: PEG 400 (standard grade)\n- Quantity: 1,000 kg\n- Unit Price: $4.20/kg\n- Total: $4,200.00\n- Valid for 30 days\n\nPlease let me know if you'd like to proceed with the quote or need anything else.\n\nBest regards",
        "ai_confidence": 0.89,
    },
    # 15 more messages with various intents, some with lower confidence for "needs review" demos
    {
        "channel": "email", "from_address": "pat@globalplastics.com", "subject": "Urgent - wrong product shipped",
        "body": "We ordered Epoxy Resin ER-500 but received ER-300 instead. This is urgent - our production line is waiting.",
        "intents": [{"intent": "return_complaint", "confidence": 0.97, "text_span": "wrong product shipped", "entities": {"expected": "ER-500", "received": "ER-300"}}],
        "status": "new",
        "ai_draft_response": None,
        "ai_confidence": 0.0,
    },
    {
        "channel": "email", "from_address": "unclear@nowhere.com", "subject": "Hello",
        "body": "Can someone call me please? My number is 555-0123.",
        "intents": [{"intent": "general_query", "confidence": 0.45, "text_span": "Can someone call me please", "entities": {}}],
        "status": "classified",
        "ai_draft_response": None,
        "ai_confidence": 0.0,
    },
    {
        "channel": "web", "from_address": "buyer@newclient.com", "subject": "First time buyer",
        "body": "We're interested in becoming a customer. What's your minimum order quantity and do you offer NET60 terms?",
        "intents": [{"intent": "account_inquiry", "confidence": 0.78, "text_span": "minimum order quantity and do you offer NET60 terms", "entities": {}}],
        "status": "draft_ready",
        "ai_draft_response": "Welcome! We'd be happy to set up your account.\n\n- Minimum order: $500 or 50kg (whichever is reached first)\n- Standard terms: NET30 for new accounts\n- NET60 available after 6 months of on-time payments\n\nTo get started, I'll need:\n1. Company name and address\n2. Tax ID / EIN\n3. Primary contact info\n\nWould you like me to send our new customer application form?",
        "ai_confidence": 0.84,
    },
    {
        "channel": "email", "from_address": "procurement@bigcorp.com", "subject": "Annual contract renewal",
        "body": "Our annual supply agreement is up for renewal. We'd like to discuss volume discounts for next year. Current spend is approximately $2M.",
        "intents": [{"intent": "request_quote", "confidence": 0.85, "text_span": "discuss volume discounts for next year", "entities": {"spend": "$2M"}}],
        "status": "escalated",
        "ai_draft_response": "Dear Procurement Team,\n\nThank you for your continued partnership. For an annual spend of $2M, we can offer tiered volume discounts. I'm escalating this to our Key Accounts Manager who can discuss customized pricing.\n\nYou can expect a call within 24 hours to schedule a review meeting.\n\nBest regards",
        "ai_confidence": 0.80,
    },
    {
        "channel": "email", "from_address": "lab@researchtec.edu", "subject": "Small quantity for research",
        "body": "We're a university research lab studying polymer degradation. Can we purchase 100g of POLYOX WSR-301 for research purposes?",
        "intents": [{"intent": "sample_request", "confidence": 0.82, "text_span": "purchase 100g of POLYOX WSR-301 for research purposes", "entities": {"product": "POLYOX WSR-301", "quantity": "100g"}}],
        "status": "draft_ready",
        "ai_draft_response": "Hello,\n\nWe'd be happy to support your research. For academic institutions, we offer research quantities at reduced pricing.\n\n- Product: POLYOX WSR-301\n- Quantity: 100g sample\n- Price: $25.00 (academic rate)\n- Shipping: Standard ground, free for academic orders\n\nI'll also include the TDS and SDS for your records. Please provide your university shipping address and a faculty contact.\n\nBest regards",
        "ai_confidence": 0.88,
    },
]


async def seed_inbox_messages(pool):
    """Insert sample inbound messages for demo purposes."""
    if not pool:
        return

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM inbound_messages")
        if count > 0:
            logger.info("Inbox already seeded (%d messages), skipping", count)
            return

        for msg in SAMPLE_MESSAGES:
            await conn.execute(
                """INSERT INTO inbound_messages
                   (channel, from_address, subject, body, intents, status,
                    ai_draft_response, ai_confidence)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                msg["channel"], msg["from_address"], msg["subject"], msg["body"],
                json.dumps(msg["intents"]), msg["status"],
                msg["ai_draft_response"], msg["ai_confidence"],
            )

        logger.info("Seeded %d sample inbox messages", len(SAMPLE_MESSAGES))
```

**Step 7: Wire in main.py**

Add imports:
```python
from routes.inbox import router as inbox_router, set_inbox_service
from services.inbox_service import InboxService
from services.auto_response_engine import AutoResponseEngine
```

Add inside lifespan after intent classifier and other services:
```python
# Wire inbox service
auto_response_engine = AutoResponseEngine(
    pool=db_manager.pool,
    graph_service=getattr(app.state, "graph_service", None),
    llm_router=llm_router,
)
inbox_service = InboxService(
    pool=db_manager.pool,
    classifier=classifier,
    auto_response_engine=auto_response_engine,
)
set_inbox_service(inbox_service)

# Seed inbox in debug mode
if settings.debug and db_manager.pool:
    from services.platform.seed_inbox import seed_inbox_messages
    await seed_inbox_messages(db_manager.pool)
```

Add router registration:
```python
app.include_router(inbox_router)
```

**Step 8: Run all tests**

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/test_inbox_service.py -v`
Expected: 5 PASSED

Run: `/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/ -x -q`
Expected: All pass

**Step 9: Commit**

```bash
git add services/inbox_service.py services/auto_response_engine.py services/platform/seed_inbox.py routes/inbox.py main.py tests/test_inbox_service.py
git commit -m "feat: add Inbox API with service, routes, seed data, and simulate endpoint"
```

---

## Phase 4: Frontend Pivot

### Task 7: Pivot Sidebar to distributor ops navigation

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`

**Step 1: Update sidebar navigation**

Replace the nav section arrays with the new priority order:

```
Operations (no section label)
  /inbox       → Inbox (Mail icon, with unread badge)
  /dashboard   → Dashboard (LayoutDashboard)
  /chat        → AI Assistant (Bot)
  /knowledge-base → Knowledge Base (BookOpen icon)

Management
  /orders      → Orders (ClipboardList)
  /quotes      → Quotes (MessageSquareQuote)
  /inventory   → Inventory (Warehouse)
  /products    → Products (Package)

Admin
  /bulk-import → Bulk Import (Upload)
  /admin       → Debug View (Bug)
```

Update footer text: "AI-Powered MRO Platform" → "AI-Powered Support Automation"
Update footer subtext: "Built for Industrial Distribution" → "Built for Industrial Distributors"

**Step 2: Add Inbox badge (unread count)**

Add a `useQuery` hook that polls `/api/v1/inbox?status=new&page_size=1` to get the count, and show a badge dot/number on the Inbox nav item.

**Step 3: Verify visually**

Open http://localhost:8080 — sidebar should show new nav order with Inbox at top.

**Step 4: Commit**

```bash
git add src/components/layout/Sidebar.tsx
git commit -m "feat: pivot sidebar to distributor ops navigation with Inbox primary"
```

---

### Task 8: Add Inbox and Knowledge Base routes to App.tsx

**Files:**
- Modify: `src/App.tsx` — add lazy imports + routes for Inbox and KnowledgeBase

**Step 1: Add lazy imports**

```tsx
const Inbox = lazy(() => import("@/pages/Inbox"));
const KnowledgeBase = lazy(() => import("@/pages/KnowledgeBase"));
```

**Step 2: Add routes inside AppLayout**

```tsx
<Route path="/inbox" element={<Suspense fallback={<PageLoader />}><Inbox /></Suspense>} />
<Route path="/knowledge-base" element={<Suspense fallback={<PageLoader />}><KnowledgeBase /></Suspense>} />
```

**Step 3: Commit**

```bash
git add src/App.tsx
git commit -m "feat: add Inbox and KnowledgeBase routes to App.tsx"
```

---

### Task 9: Add inbox API methods to api.ts

**Files:**
- Modify: `src/lib/api.ts` — add inbox + knowledge base endpoints

**Step 1: Add TypeScript types**

```typescript
export interface InboundMessage {
  id: string;
  channel: string;
  from_address: string;
  subject: string;
  body: string;
  status: string;
  intents: Array<{
    intent: string;
    confidence: number;
    text_span: string;
    entities: Record<string, string>;
  }> | null;
  ai_draft_response: string | null;
  ai_confidence: number | null;
  created_at: string;
}

export interface InboxStats {
  messages_today: number;
  avg_response_time: number;
  ai_accuracy: number;
  hours_saved: number;
  intent_distribution: Array<{ intent: string; count: number }>;
}

export interface KBProduct {
  name: string;
  sku: string;
  cas_number?: string;
  description?: string;
  manufacturer?: { name: string };
  industries?: string[];
  tds?: Record<string, unknown>;
  sds?: Record<string, unknown>;
}

export interface CrawlJob {
  job_id: string;
  status: string;
  progress: number;
  result?: { ingested: number; errors: unknown[]; total: number };
}
```

**Step 2: Add API methods**

```typescript
// Inbox
getInboxMessages: (page = 1, status?: string, channel?: string) =>
  get<PaginatedResponse<InboundMessage>>(
    `/inbox?page=${page}${status ? `&status=${status}` : ""}${channel ? `&channel=${channel}` : ""}`
  ),
getInboxMessage: (id: string) => get<InboundMessage>(`/inbox/${id}`),
getInboxStats: () => get<InboxStats>("/inbox/stats"),
simulateInbound: (body: { from_address: string; subject: string; body: string; channel?: string }) =>
  post<{ id: string; intents: unknown[]; status: string }>("/inbox/simulate", body),
approveMessage: (id: string, editedResponse?: string) =>
  post<{ status: string }>(`/inbox/${id}/approve`, editedResponse ? { edited_response: editedResponse } : {}),
escalateMessage: (id: string) => post<{ status: string }>(`/inbox/${id}/escalate`, {}),
submitFeedback: (id: string, humanIntent: string, isCorrect: boolean) =>
  post<{ status: string }>(`/inbox/${id}/feedback`, { human_intent: humanIntent, is_correct: isCorrect }),

// Knowledge Base
getKBProducts: (page = 1, search?: string) =>
  get<PaginatedResponse<KBProduct>>(
    `/knowledge-base/products?page=${page}${search ? `&search=${encodeURIComponent(search)}` : ""}`
  ),
getKBProduct: (id: string) => get<KBProduct>(`/knowledge-base/products/${id}`),
startCrawl: (maxPages = 50) => post<CrawlJob>(`/knowledge-base/crawl?max_pages=${maxPages}`, {}),
getCrawlStatus: (jobId: string) => get<CrawlJob>(`/knowledge-base/crawl/${jobId}`),
```

**Step 3: Commit**

```bash
git add src/lib/api.ts
git commit -m "feat: add inbox and knowledge base API methods to frontend client"
```

---

### Task 10: Build Inbox page

**Files:**
- Create: `src/pages/Inbox.tsx`

**Step 1: Build the Inbox page**

Two-panel layout:
- **Left panel:** Message list with intent badge, customer name, timestamp, status pill. Filters at top (status, channel). "Simulate Inbound" button.
- **Right panel:** When a message is selected — original content, detected intents with confidence bars, editable AI draft textarea, approve/edit/escalate buttons.

Use the same card styling pattern from existing pages: `rounded-xl border border-slate-200 bg-white p-5 shadow-sm`.

Data fetching: `useQuery(["inbox-messages", page, status], () => api.getInboxMessages(page, status))`.

Intent badge colors:
- `request_tds_sds` → blue
- `place_order` → green
- `request_quote` → purple
- `order_status` → yellow
- `technical_support` → indigo
- `return_complaint` → red
- `reorder` → teal
- `account_inquiry` → gray
- `sample_request` → orange

Status pills:
- `new` → gray
- `classified` → yellow
- `draft_ready` → blue
- `sent` → green
- `escalated` → red

"Simulate Inbound" opens a modal/dialog with from_address, subject, body fields → calls `api.simulateInbound()` → refetches message list.

**Step 2: Verify visually**

Navigate to /inbox — should show seeded messages with intents and AI drafts.

**Step 3: Commit**

```bash
git add src/pages/Inbox.tsx
git commit -m "feat: add Inbox page with message list, AI draft review, and simulate button"
```

---

### Task 11: Build Knowledge Base page

**Files:**
- Create: `src/pages/KnowledgeBase.tsx`

**Step 1: Build the Knowledge Base page**

Layout:
- **Top bar:** Search input (product name / SKU / CAS#) + "Crawl Chempoint" button
- **Product grid:** Cards showing product name, manufacturer, CAS#, industry badges, TDS/SDS availability indicators
- **Product detail modal/panel:** Expand a card to see full specs, TDS structured data, SDS structured data, download links
- **Crawl status banner:** When crawl is running, show progress bar with status polling

Data fetching: `useQuery(["kb-products", page, search], () => api.getKBProducts(page, search))`.

"Crawl Chempoint" button: calls `api.startCrawl()` → polls `api.getCrawlStatus(jobId)` every 3 seconds → shows progress.

**Step 2: Verify visually**

Navigate to /knowledge-base — should show products from Neo4j (if any seeded) and Crawl button.

**Step 3: Commit**

```bash
git add src/pages/KnowledgeBase.tsx
git commit -m "feat: add Knowledge Base page with product browse and Chempoint crawl"
```

---

### Task 12: Replace Dashboard with ops KPIs

**Files:**
- Modify: `src/pages/Dashboard.tsx` — full rewrite

**Step 1: Replace Dashboard content**

New layout:

**Welcome header** (keep pattern):
- "Welcome back, {user}" + date
- Replace quick actions with: "Review Inbox", "Simulate Message", "Browse Knowledge Base"

**4 KPI cards:**
- Messages Handled Today (from `stats.messages_today`) — Mail icon, blue
- Avg Response Time (from `stats.avg_response_time`) — Clock icon, green
- AI Accuracy (from `stats.ai_accuracy`) — CheckCircle icon, purple
- Hours Saved (from `stats.hours_saved`) — TrendingUp icon, orange

**Charts:**
- Intent Distribution (Recharts PieChart) — from `stats.intent_distribution`
- Messages by Status (Recharts BarChart) — count of new/classified/draft_ready/sent/escalated

**Recent Inbox Activity:**
- Table of 10 most recent inbound messages (from `api.getInboxMessages(1, undefined, undefined)`)
- Columns: Time, From, Subject, Intent, Status, Confidence

Data fetching: `useQuery(["inbox-stats"], () => api.getInboxStats())` + `useQuery(["inbox-recent"], () => api.getInboxMessages(1))`.

**Step 2: Verify visually**

Navigate to /dashboard — should show ops KPIs from inbox data.

**Step 3: Commit**

```bash
git add src/pages/Dashboard.tsx
git commit -m "feat: replace dashboard with ops KPIs — messages, TAT, AI accuracy, hours saved"
```

---

### Task 13: Clean up Chat page (remove buyer patterns)

**Files:**
- Modify: `src/pages/Chat.tsx`

**Step 1: Remove buyer-focused UI elements**

- Remove qty input and location selector from header
- Remove the `handleOrder` function and order confirmation rendering
- Remove `ComparisonTable` component usage
- Remove `ResultCard` order/quote buttons (or remove ResultCard entirely — keep only text responses)
- Remove imports: `MapPin`, `Package`, `ShoppingBag`, `CheckCircle2` (if only used for orders)
- Remove state: `qty`, `locationId`, `orderLoadingFor`
- Remove `useQuery` for locations
- Keep: dark mode, typewriter, thinking stages, history panel, basic chat flow

The chat page becomes a simple "ask the AI" tool for support reps — no sourcing, no ordering.

**Step 2: Verify visually**

Navigate to /chat — should show clean AI assistant without buyer patterns.

**Step 3: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: clean up Chat page — remove qty/location/order/comparison buyer patterns"
```

---

## Phase 5: Integration & Polish

### Task 14: End-to-end verification

**Step 1: Restart backend**

Kill existing processes and restart from worktree:
```bash
lsof -ti:8000 | xargs kill -9
cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.worktrees/supplier-sales
/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/python main.py
```

**Step 2: Verify backend endpoints**

```bash
# Health check
curl http://localhost:8000/health

# Inbox messages (seeded)
curl http://localhost:8000/api/v1/inbox | python3 -m json.tool | head -30

# Inbox stats
curl http://localhost:8000/api/v1/inbox/stats | python3 -m json.tool

# Simulate inbound
curl -X POST http://localhost:8000/api/v1/inbox/simulate \
  -H 'Content-Type: application/json' \
  -d '{"from_address":"test@demo.com","subject":"Need TDS","body":"Send me the TDS for epoxy resin please"}'

# Knowledge base products
curl http://localhost:8000/api/v1/knowledge-base/products | python3 -m json.tool
```

**Step 3: Verify frontend pages**

- http://localhost:8080/inbox → shows seeded messages
- http://localhost:8080/dashboard → shows ops KPIs
- http://localhost:8080/chat → clean AI assistant
- http://localhost:8080/knowledge-base → product browser
- Sidebar → correct nav order, Inbox at top

**Step 4: Run full test suite**

```bash
/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/ -v
```

Expected: All pass (existing 227 + new tests)

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration adjustments for distributor ops pivot"
```

---

### Task 15: Run full test suite and final commit

**Step 1: Run all tests**

```bash
/Users/shahmeer/Documents/IndusAI2/IndusAI2.0/.venv/bin/pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 2: Verify test count**

Should be 227 (existing) + ~20 new = ~247 total tests

**Step 3: Final commit if needed**

```bash
git status
# If clean, done. If changes:
git add -A
git commit -m "chore: finalize distributor ops pivot"
```

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| 1. Data Layer | Task 1 | 4 new tables (inbound_messages, customer_accounts, documents, classification_feedback) |
| 2. KB Backend | Tasks 2-3 | KnowledgeBaseService + routes + Chempoint crawl trigger |
| 3. Inbox Backend | Tasks 4-6 | 9-intent classifier, auto-response engine, inbox service + routes + 15 seed messages |
| 4. Frontend | Tasks 7-13 | Sidebar pivot, Inbox page, KB page, Dashboard ops KPIs, Chat cleanup |
| 5. Integration | Tasks 14-15 | End-to-end verification, full test suite |

**Total: 15 tasks across 5 phases**
