# Ingestion Pipeline Hardening & Scale — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all demo blockers, harden the ingestion pipeline with cancel/max_products/error handling, replace the custom canvas graph with react-force-graph-2d, add CSV/Excel import, fix product search, add context compaction for cost optimization, and add batch email processing.

**Architecture:** Fix-forward approach — patch existing services in-place (no rewrites). Each slice is independent and can be committed separately. TDD throughout: write failing test → implement → verify → commit.

**Tech Stack:** FastAPI, Neo4j, PostgreSQL, React 18, react-force-graph-2d, Anthropic SDK (>=0.74.1), pdfplumber, WebSocket

---

## Slice A: Search & Products (3 tasks)

### Task 1: Fix `list_products` to return total count

**Files:**
- Modify: `services/knowledge_base_service.py:197-224`
- Test: `tests/test_knowledge_base_routes.py`

**Step 1: Write the failing test**

Add to `tests/test_knowledge_base_routes.py` in `TestListProducts`:

```python
@pytest.mark.asyncio
async def test_list_products_includes_total(self):
    mock_svc = get_kb_service()
    mock_svc.list_products = AsyncMock(return_value={
        "items": [{"sku": "X-1", "name": "Product X"}],
        "page": 1, "page_size": 25, "total": 42,
    })
    app = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/knowledge-base/products")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert data["total"] == 42
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base_routes.py::TestListProducts::test_list_products_includes_total -v`
Expected: FAIL — `total` not in response

**Step 3: Implement total count in `list_products`**

In `services/knowledge_base_service.py`, replace lines 197-224 with:

```python
    async def list_products(self, page: int = 1, page_size: int = 25,
                            search: str | None = None) -> dict:
        """List Part nodes from Neo4j with optional search and pagination."""
        skip = (page - 1) * page_size
        params: dict = {"skip": skip, "limit": page_size}

        if search:
            count_query = """
            MATCH (p:Part)
            WHERE toLower(p.name) CONTAINS toLower($search)
               OR toLower(p.sku) CONTAINS toLower($search)
               OR toLower(p.cas_number) CONTAINS toLower($search)
            RETURN count(p) AS total
            """
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
            count_query = "MATCH (p:Part) RETURN count(p) AS total"
            query = """
            MATCH (p:Part)
            RETURN p {.*}
            ORDER BY p.name
            SKIP $skip LIMIT $limit
            """

        count_result = await self._graph.execute_read(count_query,
                                                       {k: v for k, v in params.items() if k == "search"})
        total = count_result[0]["total"] if count_result else 0

        results = await self._graph.execute_read(query, params)
        items = [row["p"] for row in results]
        return {"items": items, "page": page, "page_size": page_size, "total": total}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_knowledge_base_routes.py::TestListProducts -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/knowledge_base_service.py tests/test_knowledge_base_routes.py
git commit -m "fix: add total count to list_products for pagination"
```

---

### Task 2: Fix `get_product` PG document lookup (wrong column)

**Files:**
- Modify: `services/knowledge_base_service.py:248-258`
- Test: `tests/test_knowledge_base_routes.py`

**Step 1: Write the failing test**

Add to `tests/test_knowledge_base_routes.py` in `TestGetProduct`:

```python
@pytest.mark.asyncio
async def test_get_product_includes_doc_urls(self):
    mock_svc = get_kb_service()
    mock_svc.get_product = AsyncMock(return_value={
        "sku": "NOVEC-72DA", "name": "Novec 72DA",
        "manufacturer": "3M", "tds_url": "https://example.com/tds.pdf",
        "sds_url": "https://example.com/sds.pdf",
    })
    app = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/knowledge-base/products/NOVEC-72DA")
    data = resp.json()
    assert data["tds_url"] == "https://example.com/tds.pdf"
    assert data["sds_url"] == "https://example.com/sds.pdf"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base_routes.py::TestGetProduct::test_get_product_includes_doc_urls -v`
Expected: FAIL (current code queries `file_name = $1` with product_id, which never matches)

**Step 3: Fix the PG query**

In `services/knowledge_base_service.py`, replace lines 252-258:

```python
            async with self._pool.acquire() as conn:
                docs = await conn.fetch(
                    """SELECT doc_type, source_url FROM documents
                       WHERE product_id = $1 AND is_current = true
                       ORDER BY created_at DESC""",
                    product_id,
                )
```

The bug: was `WHERE file_name = $1` but documents table stores `product_id` as a separate column. The `product_id` param is the UUID from the products table, not the file name.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_knowledge_base_routes.py::TestGetProduct -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/knowledge_base_service.py tests/test_knowledge_base_routes.py
git commit -m "fix: use product_id column in document lookup instead of file_name"
```

---

### Task 3: Switch frontend search to KB products endpoint

**Files:**
- Modify: `src/lib/api.ts:510`
- Modify: `src/pages/KnowledgeBase.tsx:22-26`

**Step 1: Update api.ts**

In `src/lib/api.ts`, replace line 510:

```typescript
  searchGraph: (q: string, limit = 20) => get<GraphSearchResult>(`/graph/parts/search/fulltext?q=${encodeURIComponent(q)}&limit=${limit}`),
```

Add a new function (after line 510):

```typescript
  searchProducts: (q: string, page = 1, pageSize = 25) =>
    get<{ items: GraphPart[]; page: number; page_size: number; total: number }>(
      `/knowledge-base/products?search=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`
    ),
```

**Step 2: Update KnowledgeBase.tsx to use new endpoint**

In `src/pages/KnowledgeBase.tsx`, replace the useQuery block (lines 22-26) with:

```typescript
  const { data: searchData, isLoading } = useQuery({
    queryKey: ["kb-products", searchTerm],
    queryFn: () => api.searchProducts(searchTerm),
    enabled: searchTerm.length >= 2,
  });
```

And update references from `searchData?.results` or `searchData?.parts` to `searchData?.items` throughout the component.

**Step 3: Verify frontend builds**

Run: `npm run build`
Expected: BUILD SUCCESS

**Step 4: Commit**

```bash
git add src/lib/api.ts src/pages/KnowledgeBase.tsx
git commit -m "fix: switch product search from legacy graph endpoint to KB products"
```

---

## Slice B: Ingestion Pipeline Hardening (6 tasks)

### Task 4: Guard empty product names in `_make_sku`

**Files:**
- Modify: `services/ingestion/seed_chempoint.py:13-15`
- Modify: `services/ingestion/seed_chempoint.py:86-105`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

Add to `tests/test_seed_chempoint.py`:

```python
@pytest.mark.asyncio
async def test_empty_product_name_skipped():
    """Products with empty names should be skipped, not create bad SKUs."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "", "manufacturer": "ACME"},
        {"name": "   ", "manufacturer": "ACME"},
        {"name": "Valid Product", "manufacturer": "3M",
         "description": "Good product"},
    ])
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
        return_value={"id": "uuid-1", "sku": "VALID-PRODUCT"})
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_url("https://example.com", on_progress=lambda e: None)

    assert stats["products_created"] == 1
    assert stats["errors"] == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_chempoint.py::test_empty_product_name_skipped -v`
Expected: FAIL — empty names currently produce bad SKUs like "CP-" and attempt insert

**Step 3: Implement the guard**

In `services/ingestion/seed_chempoint.py`, update `_process_product` (line 86):

```python
    async def _process_product(self, product_data: dict, stats: dict,
                                _emit=None) -> None:
        """Process a single product: create in PG, download docs, build graph."""
        _emit = _emit or (lambda e: None)
        name = product_data.get("name", "").strip()
        if not name:
            raise ValueError("Product has empty name — skipping")
        sku = _make_sku(name)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_chempoint.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/ingestion/seed_chempoint.py tests/test_seed_chempoint.py
git commit -m "fix: guard empty product names in seed pipeline"
```

---

### Task 5: Enforce `max_products` as global cap across industries

**Files:**
- Modify: `services/ingestion/seed_chempoint.py:71-84`
- Modify: `routes/ingestion_ws.py:65-90`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_max_products_enforced_across_industries():
    """seed_from_industries stops after max_products globally."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    call_count = 0
    async def mock_scrape_industry(url):
        nonlocal call_count
        call_count += 1
        return [{"name": f"Product-{call_count}-{i}", "url": f"https://ex.com/p{i}"}
                for i in range(5)]

    mock_scraper.scrape_industry_page = AsyncMock(side_effect=mock_scrape_industry)
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "P", "manufacturer": "M", "description": "D"}
    ])
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
        return_value={"id": "uuid-1", "sku": "P"})
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_industries(
        ["https://ex.com/ind1", "https://ex.com/ind2", "https://ex.com/ind3"],
        on_progress=lambda e: None,
        max_products=3,
    )

    assert stats["products_created"] <= 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_chempoint.py::test_max_products_enforced_across_industries -v`
Expected: FAIL — `seed_from_industries` doesn't accept `max_products`

**Step 3: Implement max_products**

In `services/ingestion/seed_chempoint.py`, update `seed_from_industries`:

```python
    async def seed_from_industries(self, industry_urls: list[str],
                                    on_progress=None,
                                    max_products: int = 0) -> dict:
        """Batch scrape multiple industry pages.

        Args:
            max_products: Global cap on products to create. 0 = unlimited.
        """
        _emit = on_progress or (lambda e: None)
        combined = {"products_created": 0, "tds_stored": 0,
                    "sds_stored": 0, "industries_linked": 0, "errors": 0}

        for idx, url in enumerate(industry_urls):
            if max_products and combined["products_created"] >= max_products:
                _emit({"stage": "capped", "detail": f"Reached max_products={max_products}"})
                break
            _emit({"stage": "discovering", "detail": f"Industry {idx+1}/{len(industry_urls)}: {url}"})
            sub = await self.seed_from_industry(url, on_progress=on_progress,
                                                 max_products_remaining=(
                                                     max_products - combined["products_created"]
                                                     if max_products else 0))
            for k in combined:
                combined[k] += sub.get(k, 0)

        return combined
```

Also update `seed_from_industry` to accept and enforce the cap:

```python
    async def seed_from_industry(self, url: str, on_progress=None,
                                  max_products_remaining: int = 0) -> dict:
        """Scrape an industry page then process each product."""
        product_summaries = await self._scraper.scrape_industry_page(url)
        stats = {"products_created": 0, "tds_stored": 0, "sds_stored": 0,
                 "industries_linked": 0, "errors": 0}

        for summary in product_summaries:
            if max_products_remaining and stats["products_created"] >= max_products_remaining:
                break
            product_url = summary.get("url")
            if product_url:
                sub_stats = await self.seed_from_url(product_url, on_progress=on_progress)
                for k in stats:
                    stats[k] += sub_stats.get(k, 0)

        return stats
```

Then in `routes/ingestion_ws.py` line 82, pass `max_products` through:

```python
            stats = await _pipeline.seed_from_industries(
                req.industry_urls, on_progress=_broadcast_fn,
                max_products=req.max_products,
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_chempoint.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/ingestion/seed_chempoint.py routes/ingestion_ws.py tests/test_seed_chempoint.py
git commit -m "feat: enforce max_products global cap across batch industries"
```

---

### Task 6: Add cancel endpoint + cancellation flag

**Files:**
- Modify: `services/ingestion/seed_chempoint.py`
- Modify: `routes/ingestion_ws.py`
- Test: `tests/test_ingestion_ws.py`

**Step 1: Write the failing test**

Add to `tests/test_ingestion_ws.py`:

```python
def test_cancel_job():
    app = _make_test_app()
    from routes.ingestion_ws import _jobs
    _jobs["test-job-1"] = {"status": "running", "result": None}
    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/jobs/test-job-1/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    _jobs.clear()

def test_cancel_job_not_found():
    app = _make_test_app()
    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/jobs/nonexistent/cancel")
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion_ws.py::test_cancel_job -v`
Expected: FAIL — no `/cancel` endpoint exists

**Step 3: Implement cancel**

In `routes/ingestion_ws.py`, add a cancellation set and endpoint:

```python
_cancelled: set[str] = set()
```

Add the cancel endpoint after the existing routes:

```python
@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    _cancelled.add(job_id)
    _jobs[job_id]["status"] = "cancelled"
    await _broadcast(job_id, {"stage": "cancelled", "detail": "Job cancelled by user"})
    return {"job_id": job_id, "status": "cancelled"}
```

Add a helper function to check cancellation:

```python
def is_cancelled(job_id: str) -> bool:
    return job_id in _cancelled
```

In `services/ingestion/seed_chempoint.py`, add cancellation check. Add `cancel_check` callback parameter to `seed_from_url`:

```python
    async def seed_from_url(self, url: str, on_progress=None,
                            cancel_check=None) -> dict:
        _emit = on_progress or (lambda e: None)
        _is_cancelled = cancel_check or (lambda: False)
        # ...
        for i, product_data in enumerate(products):
            if _is_cancelled():
                _emit({"stage": "cancelled", "detail": f"Cancelled after {i} products"})
                break
            # ... rest of loop
```

Similarly for `seed_from_industry` and `seed_from_industries`.

In `routes/ingestion_ws.py`, pass the cancellation checker to the pipeline:

```python
    cancel_fn = lambda: is_cancelled(job_id)
    stats = await _pipeline.seed_from_url(req.url, on_progress=_broadcast_fn,
                                           cancel_check=cancel_fn)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingestion_ws.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add routes/ingestion_ws.py services/ingestion/seed_chempoint.py tests/test_ingestion_ws.py
git commit -m "feat: add cancel endpoint and cancellation flag for ingestion jobs"
```

---

### Task 7: Fix broadcast error on batch job failure

**Files:**
- Modify: `routes/ingestion_ws.py:65-90`
- Test: `tests/test_ingestion_ws.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_batch_job_broadcasts_error_on_failure():
    """Batch job should broadcast an error event when pipeline raises."""
    from routes.ingestion_ws import _jobs, _job_events, _cancelled
    import routes.ingestion_ws as mod

    mock_pipeline = MagicMock()
    mock_pipeline.seed_from_industries = AsyncMock(side_effect=Exception("Firecrawl down"))
    mod._pipeline = mock_pipeline

    # Simulate the _run_batch coroutine directly
    job_id = "fail-job"
    _jobs[job_id] = {"status": "running", "result": None}
    mod._job_events[job_id] = []

    from routes.ingestion_ws import router
    # Call the internal _run function
    # We need to test the except block broadcasts properly
    try:
        await mod._run_batch(job_id, ["https://ex.com/ind1"], 50)
    except Exception:
        pass

    assert _jobs[job_id]["status"] == "failed"
    error_events = [e for e in mod._job_events[job_id] if e.get("stage") == "error"]
    assert len(error_events) >= 1

    _jobs.clear()
    _job_events.clear()
    _cancelled.discard(job_id)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion_ws.py::test_batch_job_broadcasts_error_on_failure -v`
Expected: FAIL — no `_run_batch` function exists (it's inline in the endpoint)

**Step 3: Extract batch runner and fix error broadcast**

Refactor the batch start endpoint to use a named async function:

```python
async def _run_batch(job_id: str, industry_urls: list[str], max_products: int):
    """Run batch ingestion with proper error broadcasting."""
    try:
        cancel_fn = lambda: is_cancelled(job_id)
        broadcast_fn = lambda event: asyncio.ensure_future(_broadcast(job_id, event))
        stats = await _pipeline.seed_from_industries(
            industry_urls, on_progress=broadcast_fn,
            max_products=max_products, cancel_check=cancel_fn,
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = stats
        await _broadcast(job_id, {"stage": "done", "detail": str(stats)})
    except Exception as exc:
        logger.error("Batch ingestion %s failed: %s", job_id, exc)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(exc)}
        await _broadcast(job_id, {"stage": "error", "detail": str(exc)})
```

Do the same for `_run_single`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingestion_ws.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add routes/ingestion_ws.py tests/test_ingestion_ws.py
git commit -m "fix: broadcast error event on batch ingestion failure"
```

---

### Task 8: Track upsert vs insert counts

**Files:**
- Modify: `services/ingestion/seed_chempoint.py:94-105`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_tracks_created_vs_updated():
    """Pipeline should distinguish new products from updated ones."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "New Product", "manufacturer": "3M"},
        {"name": "Existing Product", "manufacturer": "3M"},
    ])

    # First call returns xmax=0 (INSERT), second returns xmax!=0 (UPDATE)
    call_count = 0
    async def mock_fetchrow(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        row = MagicMock()
        row.__getitem__ = lambda self, k: {"id": f"uuid-{call_count}", "sku": f"P-{call_count}",
                                            "xmax": 0 if call_count == 1 else 1}[k]
        row.get = lambda k, d=None: {"id": f"uuid-{call_count}", "sku": f"P-{call_count}",
                                      "xmax": 0 if call_count == 1 else 1}.get(k, d)
        return row

    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_url("https://example.com", on_progress=lambda e: None)

    assert stats["products_created"] == 1
    assert stats["products_updated"] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_chempoint.py::test_tracks_created_vs_updated -v`
Expected: FAIL — `products_updated` key doesn't exist

**Step 3: Implement upsert tracking**

In `services/ingestion/seed_chempoint.py`, update the stats dict and the PG query:

```python
        stats = {
            "products_created": 0,
            "products_updated": 0,
            "tds_stored": 0,
            "sds_stored": 0,
            "industries_linked": 0,
            "errors": 0,
        }
```

In `_process_product`, change the INSERT query to include `xmax`:

```python
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO products (sku, name, manufacturer, description, is_active)
                   VALUES ($1, $2, $3, $4, TRUE)
                   ON CONFLICT (sku) DO UPDATE SET name = $2, manufacturer = $3
                   RETURNING id, sku, xmax""",
                sku, name, manufacturer, product_data.get("description", ""),
            )

        product_id = str(row["id"])
        # xmax = 0 means INSERT, > 0 means UPDATE
        if row.get("xmax", 0) == 0:
            stats["products_created"] += 1
        else:
            stats["products_updated"] += 1
```

Also update `seed_from_industry` and `seed_from_industries` combined dicts to include `products_updated`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_chempoint.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/ingestion/seed_chempoint.py tests/test_seed_chempoint.py
git commit -m "feat: track products_created vs products_updated in pipeline stats"
```

---

### Task 9: Add `chempoint_extraction` to LLM router task models

**Files:**
- Modify: `services/ai/llm_router.py:11-18`
- Test: `tests/test_seed_chempoint.py` (existing tests cover indirectly)

**Step 1: Add the task mapping**

In `services/ai/llm_router.py`, add to `TASK_MODELS`:

```python
TASK_MODELS = {
    "intent_classification": "fast",
    "entity_extraction": "fast",
    "chempoint_extraction": "fast",    # Haiku — product data extraction from HTML
    "chempoint_navigation": "fast",    # Haiku — page type classification
    "response_generation": "standard",
    "catalog_normalization": "standard",
    "graph_construction": "standard",
    "tds_extraction": "standard",      # Sonnet — confidence-scored TDS/SDS fields
    "sds_extraction": "standard",
    "complex_reasoning": "heavy",
}
```

**Step 2: Verify no tests break**

Run: `pytest tests/ -x -q`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add services/ai/llm_router.py
git commit -m "feat: add chempoint and document extraction task models to LLM router"
```

---

## Slice C: Document Service Hardening (4 tasks)

### Task 10: Strip markdown fences from `_call_llm` responses

**Files:**
- Modify: `services/document_service.py:153-158`
- Test: `tests/test_document_service.py`

**Step 1: Write the failing test**

Add to `tests/test_document_service.py`:

```python
@pytest.mark.asyncio
async def test_call_llm_strips_markdown_fences():
    """_call_llm should handle LLM responses wrapped in ```json fences."""
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    svc._ai.chat = AsyncMock(return_value='```json\n{"density": "1.05 g/mL"}\n```')
    result = await svc._call_llm("Extract fields")
    assert result == {"density": "1.05 g/mL"}

@pytest.mark.asyncio
async def test_call_llm_strips_triple_backtick_only():
    """_call_llm should handle responses with ``` but no json tag."""
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    svc._ai.chat = AsyncMock(return_value='```\n{"pH": "7.0"}\n```')
    result = await svc._call_llm("Extract fields")
    assert result == {"pH": "7.0"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_document_service.py::test_call_llm_strips_markdown_fences -v`
Expected: FAIL — `json.loads` fails on markdown-wrapped response

**Step 3: Implement markdown stripping**

Replace `_call_llm` in `services/document_service.py`:

```python
    async def _call_llm(self, prompt: str) -> dict:
        """Call AI service and parse JSON response."""
        if self._ai is None:
            raise RuntimeError("AI service not configured")
        raw = await self._ai.chat(prompt)
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            # Remove closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return json.loads(cleaned)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_document_service.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/document_service.py tests/test_document_service.py
git commit -m "fix: strip markdown fences from LLM responses before JSON parsing"
```

---

### Task 11: Add text truncation to old extraction methods

**Files:**
- Modify: `services/document_service.py:94-100`
- Test: `tests/test_document_service.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_extract_tds_fields_truncates_long_text():
    """Old extract_tds_fields should truncate text to 8000 chars."""
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    captured_prompt = None
    async def capture_chat(prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return '{"density": "1.0"}'
    svc._ai.chat = capture_chat

    long_text = "A" * 20000
    await svc.extract_tds_fields(long_text)

    # The text portion of the prompt should be truncated
    assert len(captured_prompt) < 10000  # 8000 chars + prompt template
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_document_service.py::test_extract_tds_fields_truncates_long_text -v`
Expected: FAIL — old methods don't truncate

**Step 3: Add truncation**

In `services/document_service.py`, update lines 94-100:

```python
    async def extract_tds_fields(self, text: str) -> dict:
        """Use LLM to extract structured TDS fields from raw text."""
        return await self._call_llm(TDS_EXTRACTION_PROMPT.format(text=text[:8000]))

    async def extract_sds_fields(self, text: str) -> dict:
        """Use LLM to extract structured SDS fields from raw text."""
        return await self._call_llm(SDS_EXTRACTION_PROMPT.format(text=text[:8000]))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_document_service.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/document_service.py tests/test_document_service.py
git commit -m "fix: add 8000-char text truncation to legacy extraction methods"
```

---

### Task 12: Add pdfplumber to requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: Add the dependency**

In `requirements.txt`, after the `reportlab` line (34), add:

```
pdfplumber>=0.10,<1.0
```

**Step 2: Verify install**

Run: `pip install pdfplumber>=0.10`
Expected: Installs successfully

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "fix: add missing pdfplumber dependency to requirements.txt"
```

---

### Task 13: CSV/Excel import service

**Files:**
- Create: `services/ingestion/csv_import_service.py`
- Modify: `routes/ingestion_ws.py` (add import endpoint)
- Test: `tests/test_csv_import.py`

**Step 1: Write the failing tests**

Create `tests/test_csv_import.py`:

```python
"""Tests for CSV/Excel product import service."""
import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ingestion.csv_import_service import CSVImportService


def _make_service():
    pipeline = MagicMock()
    pipeline._process_product = AsyncMock()
    pipeline._process_document = AsyncMock()
    return CSVImportService(pipeline)


@pytest.mark.asyncio
async def test_parse_csv_standard_headers():
    svc = _make_service()
    csv_content = b"name,manufacturer,cas_number,description\nNovec 72DA,3M,64742-49-0,Heavy-duty solvent\n"
    products = await svc.parse_file(io.BytesIO(csv_content), "products.csv")
    assert len(products) == 1
    assert products[0]["name"] == "Novec 72DA"
    assert products[0]["manufacturer"] == "3M"
    assert products[0]["cas_number"] == "64742-49-0"


@pytest.mark.asyncio
async def test_parse_csv_nonstandard_headers():
    """Claude Haiku maps non-standard column names."""
    svc = _make_service()
    svc._map_columns = AsyncMock(return_value={
        "Product Name": "name",
        "Supplier": "manufacturer",
        "CAS #": "cas_number",
    })
    csv_content = b"Product Name,Supplier,CAS #\nNovec 72DA,3M,64742-49-0\n"
    products = await svc.parse_file(io.BytesIO(csv_content), "products.csv")
    assert len(products) == 1
    assert products[0]["name"] == "Novec 72DA"


@pytest.mark.asyncio
async def test_parse_xlsx():
    """Excel files should also be parseable."""
    svc = _make_service()
    # Create minimal xlsx in memory using openpyxl
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["name", "manufacturer"])
    ws.append(["Product A", "Acme Corp"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    products = await svc.parse_file(buf, "products.xlsx")
    assert len(products) == 1
    assert products[0]["name"] == "Product A"


@pytest.mark.asyncio
async def test_dry_run_returns_preview():
    svc = _make_service()
    csv_content = b"name,manufacturer\nP1,M1\nP2,M2\nP3,M3\nP4,M4\nP5,M5\nP6,M6\n"
    preview = await svc.dry_run(io.BytesIO(csv_content), "products.csv")
    assert len(preview["sample_rows"]) == 5  # First 5 only
    assert preview["total_rows"] == 6
    assert "name" in preview["columns"]


@pytest.mark.asyncio
async def test_import_creates_products():
    svc = _make_service()
    svc._pipeline._process_product = AsyncMock()
    svc._pipeline._db = MagicMock()
    products = [{"name": "P1", "manufacturer": "M1"}]
    stats = await svc.import_products(products, on_progress=lambda e: None)
    svc._pipeline._process_product.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_csv_import.py -v`
Expected: FAIL — `CSVImportService` doesn't exist

**Step 3: Implement CSVImportService**

Create `services/ingestion/csv_import_service.py`:

```python
"""CSV/Excel product import service.

Parses uploaded files, maps columns to product schema,
and feeds products into the same pipeline as web scraping.
"""

import csv
import io
import logging

logger = logging.getLogger(__name__)

STANDARD_COLUMNS = {
    "name", "product_name", "manufacturer", "cas_number",
    "description", "product_line", "industry", "industries",
    "tds_url", "sds_url", "tds_file", "sds_file",
}

COLUMN_ALIASES = {
    "product_name": "name",
    "product name": "name",
    "supplier": "manufacturer",
    "mfg": "manufacturer",
    "cas": "cas_number",
    "cas #": "cas_number",
    "cas_no": "cas_number",
    "desc": "description",
    "industries": "industry",
}


class CSVImportService:
    def __init__(self, pipeline, llm_router=None):
        self._pipeline = pipeline
        self._llm = llm_router

    async def parse_file(self, file_obj: io.BytesIO, filename: str) -> list[dict]:
        """Parse CSV or Excel file into list of product dicts."""
        if filename.endswith((".xlsx", ".xls")):
            return self._parse_excel(file_obj)
        return self._parse_csv(file_obj)

    def _parse_csv(self, file_obj: io.BytesIO) -> list[dict]:
        text = file_obj.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        column_map = {col: COLUMN_ALIASES.get(col.lower().strip(), col.lower().strip())
                      for col in (reader.fieldnames or [])}
        products = []
        for row in reader:
            product = {}
            for orig_col, mapped_col in column_map.items():
                val = row.get(orig_col, "").strip()
                if val:
                    if mapped_col == "industry":
                        product["industries"] = [i.strip() for i in val.split(",")]
                    else:
                        product[mapped_col] = val
            if product.get("name"):
                products.append(product)
        return products

    def _parse_excel(self, file_obj: io.BytesIO) -> list[dict]:
        from openpyxl import load_workbook
        wb = load_workbook(file_obj, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return []
        headers = [str(h).strip().lower() if h else "" for h in rows[0]]
        column_map = {h: COLUMN_ALIASES.get(h, h) for h in headers}
        products = []
        for row in rows[1:]:
            product = {}
            for i, val in enumerate(row):
                if i < len(headers) and val is not None:
                    mapped = column_map.get(headers[i], headers[i])
                    val_str = str(val).strip()
                    if mapped == "industry":
                        product["industries"] = [v.strip() for v in val_str.split(",")]
                    else:
                        product[mapped] = val_str
            if product.get("name"):
                products.append(product)
        wb.close()
        return products

    async def dry_run(self, file_obj: io.BytesIO, filename: str) -> dict:
        """Preview import: return first 5 rows and column mapping."""
        products = await self.parse_file(file_obj, filename)
        columns = list(products[0].keys()) if products else []
        return {
            "columns": columns,
            "sample_rows": products[:5],
            "total_rows": len(products),
        }

    async def import_products(self, products: list[dict],
                               on_progress=None) -> dict:
        """Import parsed products through the seed pipeline."""
        _emit = on_progress or (lambda e: None)
        stats = {"products_created": 0, "products_updated": 0,
                 "tds_stored": 0, "sds_stored": 0,
                 "industries_linked": 0, "errors": 0}

        for i, product in enumerate(products):
            _emit({"stage": "importing", "current": i + 1,
                   "total": len(products), "product": product.get("name", "")})
            try:
                await self._pipeline._process_product(product, stats, _emit)
            except Exception as e:
                logger.warning("Import failed for %s: %s", product.get("name"), e)
                stats["errors"] += 1

        return stats
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_csv_import.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/ingestion/csv_import_service.py tests/test_csv_import.py
git commit -m "feat: add CSV/Excel product import service with column mapping"
```

---

## Slice D: Graph Visualization (3 tasks)

### Task 14: Fix graph-viz backend (materialize results, all industries)

**Files:**
- Modify: `services/knowledge_base_service.py:128-195`
- Modify: `services/knowledge_base_service.py:137` (manufacturer filter)
- Test: `tests/test_knowledge_base_routes.py`

**Step 1: Write the failing test**

Add to `tests/test_knowledge_base_routes.py`:

```python
@pytest.mark.asyncio
async def test_graph_viz_with_manufacturer_filter():
    """Manufacturer filter should use relationship, not property."""
    mock_svc = get_kb_service()
    mock_svc.get_graph_visualization = AsyncMock(return_value={"nodes": [], "edges": []})
    app = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/knowledge-base/graph-viz?manufacturer=3M")
    assert resp.status_code == 200
    # Verify the service was called with manufacturer param
    mock_svc.get_graph_visualization.assert_called_once()
    call_kwargs = mock_svc.get_graph_visualization.call_args
    assert call_kwargs.kwargs.get("manufacturer") == "3M" or call_kwargs.args[1] == "3M"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base_routes.py::TestGraphVisualization::test_graph_viz_with_manufacturer_filter -v`

**Step 3: Fix the backend**

In `services/knowledge_base_service.py`, fix `get_graph_visualization`:

1. **Materialize results** — change line 154 area to `results = list(await ...)`
2. **Fix manufacturer filter** — change line 137 from property to relationship:
   ```python
   if manufacturer:
       conditions.append("(p)-[:BELONGS_TO]->(:ProductLine)-[:MADE_BY]->(:Manufacturer {name: $manufacturer})")
       params["manufacturer"] = manufacturer
   ```
3. **Add industry list endpoint** — Add method to get all industries:
   ```python
   async def get_all_industries(self) -> list[str]:
       results = await self._graph.execute_read(
           "MATCH (i:Industry) RETURN i.name AS name ORDER BY name")
       return [r["name"] for r in results]
   ```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_knowledge_base_routes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/knowledge_base_service.py tests/test_knowledge_base_routes.py
git commit -m "fix: materialize graph-viz results, fix manufacturer filter, add industry list"
```

---

### Task 15: Install react-force-graph-2d and rebuild GraphExplorer

**Files:**
- Modify: `package.json`
- Rewrite: `src/components/graph/GraphExplorer.tsx`

**Step 1: Install the library**

Run: `npm install react-force-graph-2d`

**Step 2: Rewrite GraphExplorer**

Replace `src/components/graph/GraphExplorer.tsx` entirely:

```tsx
import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "@/lib/api";
import { Search } from "lucide-react";

const NODE_COLORS: Record<string, string> = {
  Product: "#1e3a8a",
  Manufacturer: "#059669",
  ProductLine: "#0d9488",
  Industry: "#f59e0b",
  TDS: "#7c3aed",
  SDS: "#dc2626",
};

const NODE_SIZES: Record<string, number> = {
  Product: 8,
  Manufacturer: 6,
  ProductLine: 6,
  Industry: 6,
  TDS: 4,
  SDS: 4,
};

type GraphNode = {
  id: string;
  label: string;
  name: string;
  color: string;
  properties: Record<string, unknown>;
};
type GraphEdge = { source: string; target: string; relationship: string };

export default function GraphExplorer() {
  const [industry, setIndustry] = useState<string>("");
  const [manufacturer, setManufacturer] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [depth, setDepth] = useState<"products" | "products+docs" | "full">("full");
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: vizData, isLoading } = useQuery({
    queryKey: ["graph-viz", industry, manufacturer],
    queryFn: () => api.getGraphViz(industry || undefined, manufacturer || undefined),
  });

  const { data: industries } = useQuery({
    queryKey: ["industries"],
    queryFn: () => api.getIndustries(),
  });

  // Filter nodes by depth
  const filteredData = useCallback(() => {
    if (!vizData) return { nodes: [], links: [] };
    let nodes = vizData.nodes as GraphNode[];
    let edges = vizData.edges as GraphEdge[];

    if (depth === "products") {
      nodes = nodes.filter((n) => n.label === "Product");
      const nodeIds = new Set(nodes.map((n) => n.id));
      edges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    } else if (depth === "products+docs") {
      nodes = nodes.filter((n) => ["Product", "TDS", "SDS"].includes(n.label));
      const nodeIds = new Set(nodes.map((n) => n.id));
      edges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    }

    return {
      nodes,
      links: edges.map((e) => ({ source: e.source, target: e.target, label: e.relationship })),
    };
  }, [vizData, depth]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as GraphNode);
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 500);
      graphRef.current.zoom(3, 500);
    }
  }, []);

  const handleNodeDoubleClick = useCallback((node: any) => {
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 300);
      graphRef.current.zoom(5, 300);
    }
  }, []);

  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height: Math.max(height, 400) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const graphData = filteredData();

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select value={industry} onChange={(e) => setIndustry(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Industries</option>
          {(industries || []).map((ind: string) => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
        <select value={depth} onChange={(e) => setDepth(e.target.value as any)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="full">Full Graph</option>
          <option value="products+docs">Products + Documents</option>
          <option value="products">Products Only</option>
        </select>
        <span className="text-xs text-gray-500">
          {graphData.nodes.length} nodes · {graphData.links.length} edges
        </span>
      </div>

      {/* Graph */}
      <div ref={containerRef} className="border rounded-lg bg-gray-50 relative" style={{ height: 500 }}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-gray-400">Loading graph...</div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            nodeLabel={(node: any) => `${node.label}: ${node.name}`}
            nodeColor={(node: any) => NODE_COLORS[node.label] || "#666"}
            nodeVal={(node: any) => NODE_SIZES[node.label] || 4}
            linkLabel={(link: any) => link.label}
            linkColor={() => "#d1d5db"}
            linkDirectionalArrowLength={3}
            onNodeClick={handleNodeClick}
            onNodeDblClick={handleNodeDoubleClick}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              if (globalScale < 1.5) return; // Hide labels when zoomed out
              const label = node.name?.substring(0, 25) || "";
              const fontSize = 10 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "#374151";
              ctx.fillText(label, node.x, node.y + 10 / globalScale);
            }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {Object.entries(NODE_COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Selected node panel */}
      {selectedNode && (
        <div className="border rounded-lg p-4 bg-white shadow-sm">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-medium px-2 py-0.5 rounded"
                style={{ backgroundColor: NODE_COLORS[selectedNode.label] + "20",
                         color: NODE_COLORS[selectedNode.label] }}>
                {selectedNode.label}
              </span>
              <h3 className="font-semibold mt-1">{selectedNode.name}</h3>
            </div>
            <button onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-1 text-sm">
            {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
              <div key={k}>
                <span className="text-gray-500">{k}:</span>{" "}
                <span>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Add `getIndustries` to api.ts**

In `src/lib/api.ts`, add before the closing `};`:

```typescript
  getIndustries: () => get<string[]>("/knowledge-base/industries"),
```

Also add the backend route in `routes/knowledge_base.py`:

```python
@router.get("/industries")
async def list_industries():
    svc = _get_svc()
    return await svc.get_all_industries()
```

**Step 4: Verify frontend builds**

Run: `npm run build`
Expected: BUILD SUCCESS

**Step 5: Commit**

```bash
git add package.json package-lock.json src/components/graph/GraphExplorer.tsx src/lib/api.ts routes/knowledge_base.py services/knowledge_base_service.py
git commit -m "feat: replace canvas graph with react-force-graph-2d, add depth/industry filters"
```

---

### Task 16: Add cancel button to IngestionPanel frontend

**Files:**
- Modify: `src/components/ingestion/IngestionPanel.tsx`
- Modify: `src/lib/api.ts`

**Step 1: Add cancel API method**

In `src/lib/api.ts`, add to the ingestion section:

```typescript
  cancelIngestion: (jobId: string) =>
    post<{ job_id: string; status: string }>(`/ingestion/jobs/${jobId}/cancel`, {}),
```

**Step 2: Add cancel button to IngestionPanel**

In `src/components/ingestion/IngestionPanel.tsx`, add a cancel mutation after the existing mutations:

```typescript
  const cancelJob = useMutation({
    mutationFn: () => jobId ? api.cancelIngestion(jobId) : Promise.reject("No job"),
    onSuccess: () => {
      setEvents(prev => [...prev, { stage: "cancelled", detail: "Cancelled by user" }]);
    },
  });
```

Add the cancel button in the job progress area (after the progress bar):

```tsx
{jobId && events[events.length - 1]?.stage !== "done" &&
 events[events.length - 1]?.stage !== "cancelled" && (
  <button
    onClick={() => cancelJob.mutate()}
    className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
    disabled={cancelJob.isPending}
  >
    Cancel
  </button>
)}
```

**Step 3: Verify frontend builds**

Run: `npm run build`
Expected: BUILD SUCCESS

**Step 4: Commit**

```bash
git add src/components/ingestion/IngestionPanel.tsx src/lib/api.ts
git commit -m "feat: add cancel button to ingestion panel"
```

---

## Slice E: Context Compaction (3 tasks)

### Task 17: Upgrade anthropic SDK and add compaction support to LLM router

**Files:**
- Modify: `requirements.txt`
- Modify: `services/ai/llm_router.py`
- Test: `tests/test_llm_router.py` (create if not exists)

**Step 1: Update requirements.txt**

Change `anthropic>=0.40,<1.0` to:

```
anthropic>=0.74.1,<1.0
```

**Step 2: Write the failing test**

Create `tests/test_llm_router_compaction.py`:

```python
"""Tests for LLM router context compaction support."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.ai.llm_router import LLMRouter


@pytest.mark.asyncio
async def test_chat_with_compaction_passthrough():
    """chat_with_compaction should pass compaction_control to SDK."""
    mock_claude = MagicMock()
    mock_claude.chat = AsyncMock(return_value="result")
    router = LLMRouter(claude_client=mock_claude, embedding_client=MagicMock())

    result = await router.chat_with_compaction(
        messages=[{"role": "user", "content": "test"}],
        task="chempoint_extraction",
        max_tokens=1024,
        compaction_control={"enabled": True, "context_token_threshold": 5000},
    )

    # Should still return a string result
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_chat_with_compaction_disabled_falls_back():
    """When compaction_control is None, should use regular chat."""
    mock_claude = MagicMock()
    mock_claude.chat = AsyncMock(return_value="regular result")
    router = LLMRouter(claude_client=mock_claude, embedding_client=MagicMock())

    result = await router.chat_with_compaction(
        messages=[{"role": "user", "content": "test"}],
        task="response_generation",
        max_tokens=1024,
        compaction_control=None,
    )

    assert result == "regular result"
    mock_claude.chat.assert_called_once()
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_llm_router_compaction.py -v`
Expected: FAIL — `chat_with_compaction` doesn't exist

**Step 4: Implement compaction support**

Add to `services/ai/llm_router.py`:

```python
    async def chat_with_compaction(
        self,
        messages: list[dict],
        task: str = "response_generation",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        system: str | None = None,
        compaction_control: dict | None = None,
    ) -> str:
        """Chat with optional automatic context compaction for batch processing.

        When compaction_control is provided, uses the Anthropic SDK's
        tool_runner with compaction to manage context window in long loops.
        When None, falls back to regular chat.
        """
        if not compaction_control:
            return await self.chat(
                messages=messages, system=system, task=task,
                max_tokens=max_tokens, temperature=temperature,
            )

        # Use compaction-enabled path via underlying claude client
        model_tier = TASK_MODELS.get(task, "standard")
        return await self._claude.chat_with_compaction(
            messages, system=system, model=model_tier,
            max_tokens=max_tokens, temperature=temperature,
            compaction_control=compaction_control,
        )
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_llm_router_compaction.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add requirements.txt services/ai/llm_router.py tests/test_llm_router_compaction.py
git commit -m "feat: add context compaction support to LLM router"
```

---

### Task 18: Add compaction to seed pipeline batch processing

**Files:**
- Modify: `services/ingestion/seed_chempoint.py`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_seed_from_industries_uses_compaction():
    """Batch ingestion should pass compaction_control when available."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    pipeline._llm_router = MagicMock()
    pipeline._llm_router.chat_with_compaction = AsyncMock(return_value='[{"name": "P1"}]')

    mock_scraper.scrape_industry_page = AsyncMock(return_value=[])

    stats = await pipeline.seed_from_industries(
        ["https://ex.com/ind1"],
        on_progress=lambda e: None,
        max_products=50,
    )

    # Pipeline should complete without error even with compaction support
    assert stats["errors"] == 0
```

**Step 2: Run test, then implement**

The compaction integration is opt-in — the pipeline constructor accepts an optional `llm_router` param. When present, batch loops can use `chat_with_compaction`. For MVP, this is a plumbing task: add the parameter passthrough.

In `services/ingestion/seed_chempoint.py`, update the constructor:

```python
    def __init__(self, scraper, doc_service, graph_service, db_manager, llm_router=None):
        self._scraper = scraper
        self._doc = doc_service
        self._graph = graph_service
        self._db = db_manager
        self._llm = llm_router
```

And update main.py wiring to pass `llm_router` to the pipeline.

**Step 3: Run tests**

Run: `pytest tests/test_seed_chempoint.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add services/ingestion/seed_chempoint.py main.py tests/test_seed_chempoint.py
git commit -m "feat: wire LLM router with compaction support into seed pipeline"
```

---

### Task 19: Add batch email processing with compaction to AutoResponseEngine

**Files:**
- Modify: `services/auto_response_engine.py`
- Test: `tests/test_auto_response_engine.py`

**Step 1: Write the failing test**

Add to `tests/test_auto_response_engine.py`:

```python
@pytest.mark.asyncio
async def test_batch_process_inbox(engine):
    """batch_process_inbox should process multiple emails and return aggregate stats."""
    emails = [
        {"id": "msg-1", "body": "Need TDS for product X",
         "classification": _make_classification(IntentType.REQUEST_TDS_SDS)},
        {"id": "msg-2", "body": "Quote for product Y",
         "classification": _make_classification(IntentType.REQUEST_QUOTE)},
    ]

    results = await engine.batch_process_inbox(emails)

    assert len(results) == 2
    assert all(r["response_text"] for r in results)
    assert results[0]["metadata"]["intents"] == ["request_tds_sds"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_auto_response_engine.py::test_batch_process_inbox -v`
Expected: FAIL — `batch_process_inbox` doesn't exist

**Step 3: Implement batch method**

Add to `AutoResponseEngine`:

```python
    async def batch_process_inbox(
        self,
        emails: list[dict],
        on_progress=None,
    ) -> list[dict]:
        """Process a batch of classified emails, generating drafts for each.

        Args:
            emails: List of dicts with keys: id, body, classification, customer_account (optional)
            on_progress: Optional callback for progress events

        Returns:
            List of draft results (same shape as generate_draft output)
        """
        _emit = on_progress or (lambda e: None)
        results = []

        for i, email in enumerate(emails):
            _emit({"stage": "processing", "current": i + 1,
                   "total": len(emails), "email_id": email.get("id")})
            try:
                draft = await self.generate_draft(
                    body=email["body"],
                    classification=email["classification"],
                    customer_account=email.get("customer_account"),
                )
                results.append(draft)
            except Exception as exc:
                logger.warning("Batch draft failed for %s: %s", email.get("id"), exc)
                results.append({
                    "response_text": "",
                    "attachments": [],
                    "confidence": 0.0,
                    "metadata": {"error": str(exc), "email_id": email.get("id")},
                })

        _emit({"stage": "done", "total_processed": len(results),
               "successful": sum(1 for r in results if r["response_text"])})
        return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_auto_response_engine.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add services/auto_response_engine.py tests/test_auto_response_engine.py
git commit -m "feat: add batch_process_inbox method to AutoResponseEngine"
```

---

## Slice F: Test Hardening (3 tasks)

### Task 20: WebSocket broadcast + streaming tests

**Files:**
- Modify: `tests/test_ingestion_ws.py`

**Step 1: Add WebSocket tests**

```python
@pytest.mark.asyncio
async def test_websocket_receives_events():
    """WebSocket client should receive broadcast events."""
    from routes.ingestion_ws import _job_events, _jobs, _broadcast
    import routes.ingestion_ws as mod

    app = _make_test_app()
    job_id = "ws-test"
    _jobs[job_id] = {"status": "running", "result": None}
    mod._job_events[job_id] = []

    from starlette.testclient import TestClient
    client = TestClient(app)

    with client.websocket_connect(f"/api/v1/ingestion/ws/{job_id}") as ws:
        # Broadcast an event
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_broadcast(job_id, {"stage": "processing", "product": "Test"}))
        data = ws.receive_json()
        assert data["stage"] == "processing"

    _jobs.clear()
    mod._job_events.clear()
```

**Step 2: Run and iterate until passing**

Run: `pytest tests/test_ingestion_ws.py -v`

**Step 3: Commit**

```bash
git add tests/test_ingestion_ws.py
git commit -m "test: add WebSocket broadcast and streaming tests"
```

---

### Task 21: Document service search + get_by_id tests

**Files:**
- Modify: `tests/test_document_service.py`

**Step 1: Add missing tests**

```python
@pytest.mark.asyncio
async def test_search_documents():
    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(
        return_value=[
            {"id": "d1", "product_id": "p1", "doc_type": "TDS",
             "file_name": "tds.pdf", "is_current": True, "created_at": "2026-01-01"},
        ])
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db_manager=mock_db)

    results = await svc.search_documents("tds", doc_type="TDS", limit=10)
    assert len(results) == 1
    assert results[0]["doc_type"] == "TDS"


@pytest.mark.asyncio
async def test_get_document_by_id_found():
    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
        return_value={"id": "d1", "product_id": "p1", "doc_type": "SDS",
                      "file_name": "sds.pdf"})
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db_manager=mock_db)

    doc = await svc.get_document_by_id("d1")
    assert doc is not None
    assert doc["id"] == "d1"


@pytest.mark.asyncio
async def test_get_document_by_id_not_found():
    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(return_value=None)
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db_manager=mock_db)

    doc = await svc.get_document_by_id("nonexistent")
    assert doc is None
```

**Step 2: Run tests**

Run: `pytest tests/test_document_service.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_document_service.py
git commit -m "test: add search_documents and get_document_by_id tests"
```

---

### Task 22: CSV import + graph viz filter tests

**Files:**
- Tests already created in Tasks 13 and 14

This task is to verify all new tests pass together and run the full suite.

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS, 490+ tests

**Step 2: Verify frontend builds**

Run: `npm run build`
Expected: BUILD SUCCESS

**Step 3: Final commit if any stragglers**

```bash
git add -A
git commit -m "test: final test hardening — all 490+ tests passing"
```

---

## Execution Summary

| Task | Slice | What | Est. Tests Added |
|------|-------|------|-----------------|
| 1 | A | `list_products` total count | +1 |
| 2 | A | Fix `get_product` PG lookup | +1 |
| 3 | A | Switch frontend search endpoint | 0 (build check) |
| 4 | B | Guard empty product names | +1 |
| 5 | B | `max_products` global cap | +1 |
| 6 | B | Cancel endpoint + flag | +2 |
| 7 | B | Fix batch error broadcast | +1 |
| 8 | B | Track upsert vs insert | +1 |
| 9 | B | Add LLM router task models | 0 |
| 10 | C | Strip markdown fences | +2 |
| 11 | C | Truncate old extraction methods | +1 |
| 12 | C | Add pdfplumber to requirements | 0 |
| 13 | C | CSV/Excel import service | +5 |
| 14 | D | Fix graph-viz backend | +1 |
| 15 | D | react-force-graph-2d rewrite | 0 (build check) |
| 16 | D | Cancel button frontend | 0 (build check) |
| 17 | E | Compaction in LLM router | +2 |
| 18 | E | Compaction in seed pipeline | +1 |
| 19 | E | Batch email processing | +1 |
| 20 | F | WebSocket broadcast tests | +2 |
| 21 | F | Doc service search tests | +3 |
| 22 | F | Full suite verification | 0 |
| **Total** | | **22 tasks** | **~26 new tests** |

**Expected final count:** 468 + 26 = **494 tests**
