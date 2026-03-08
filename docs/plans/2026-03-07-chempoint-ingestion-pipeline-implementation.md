# Chempoint Ingestion Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a live demo pipeline that scrapes Chempoint, downloads TDS/SDS PDFs, extracts structured data with confidence scores via Claude, populates the Neo4j knowledge graph, and shows real-time progress + interactive graph visualization.

**Architecture:** Extend existing ChempointScraper, DocumentService, and TDSSDSGraphService with progress callbacks, confidence-scored extraction, WebSocket streaming, and Neovis.js visualization. Add a CLI script with `rich` progress bars.

**Tech Stack:** Python 3.14 / FastAPI / WebSocket, pdfplumber, Claude Sonnet (via LLMRouter), Neo4j 5.x, Neovis.js, React 18 / TypeScript / Tailwind, `rich` (CLI)

**Design Doc:** `docs/plans/2026-03-07-chempoint-ingestion-pipeline-design.md`

---

## Phase 1: Confidence-Scored PDF Extraction (Tasks 1–2)

### Task 1: Add Confidence Scores to DocumentService Extraction

**Files:**
- Modify: `services/document_service.py`
- Test: `tests/test_document_service.py`

**Step 1: Write the failing test**

Add to `tests/test_document_service.py`:

```python
@pytest.mark.asyncio
async def test_extract_tds_fields_with_confidence():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "appearance": {"value": "White powder", "confidence": 0.95},
            "density": {"value": "1.21 g/cm³", "confidence": 0.92},
            "flash_point": {"value": "N/A", "confidence": 0.88},
            "viscosity": {"value": "1200-4500 cP", "confidence": 0.91},
            "pH": {"value": "5.0-8.0", "confidence": 0.85},
            "boiling_point": {"value": "100°C", "confidence": 0.70},
            "melting_point": {"value": "65°C", "confidence": 0.75},
            "solubility": {"value": "Soluble in water", "confidence": 0.93},
            "shelf_life": {"value": "24 months", "confidence": 0.60},
            "storage_conditions": {"value": "Cool, dry place", "confidence": 0.90},
            "recommended_uses": {"value": ["Adhesives", "Coatings"], "confidence": 0.87},
        }
        fields = await svc.extract_tds_fields_with_confidence("sample tds text")
        assert fields["appearance"]["confidence"] == 0.95
        assert fields["density"]["value"] == "1.21 g/cm³"
        # Low confidence flagged
        assert fields["shelf_life"]["confidence"] < 0.7


@pytest.mark.asyncio
async def test_extract_sds_fields_with_confidence():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "ghs_classification": {"value": "Not classified", "confidence": 0.97},
            "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
            "un_number": {"value": "N/A", "confidence": 0.85},
            "hazard_statements": {"value": [], "confidence": 0.90},
            "precautionary_statements": {"value": ["P264"], "confidence": 0.82},
            "first_aid": {"value": "Move to fresh air", "confidence": 0.88},
            "ppe_requirements": {"value": "Safety glasses, gloves", "confidence": 0.91},
            "fire_fighting": {"value": "Use water spray", "confidence": 0.78},
            "environmental_hazards": {"value": "No known hazards", "confidence": 0.80},
            "transport_info": {"value": "Not regulated", "confidence": 0.93},
        }
        fields = await svc.extract_sds_fields_with_confidence("sample sds text")
        assert fields["cas_numbers"]["confidence"] == 0.99
        assert fields["ghs_classification"]["value"] == "Not classified"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_document_service.py::test_extract_tds_fields_with_confidence tests/test_document_service.py::test_extract_sds_fields_with_confidence -v`
Expected: FAIL — no method `extract_tds_fields_with_confidence`

**Step 3: Update DocumentService**

In `services/document_service.py`, add new prompts and methods. Replace the extraction prompts with confidence-scored versions:

```python
TDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Technical Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {"value": null, "confidence": 0.0}.

Fields to extract:
- appearance, color, odor, density, viscosity, pH, flash_point
- boiling_point, melting_point, solubility, molecular_weight
- shelf_life, storage_conditions, recommended_uses (list)

Return ONLY valid JSON object. No markdown.

Text:
{text}"""

SDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Safety Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {"value": null, "confidence": 0.0}.

Fields to extract:
- ghs_classification, hazard_statements (list), precautionary_statements (list)
- cas_numbers (list), un_number, dot_class
- first_aid, fire_fighting, ppe_requirements
- environmental_hazards, disposal_methods, transport_info

Return ONLY valid JSON object. No markdown.

Text:
{text}"""
```

Add methods to `DocumentService`:

```python
async def extract_tds_fields_with_confidence(self, text: str) -> dict:
    """Extract TDS fields with per-field confidence scores."""
    return await self._call_llm(TDS_CONFIDENCE_PROMPT.format(text=text[:8000]))

async def extract_sds_fields_with_confidence(self, text: str) -> dict:
    """Extract SDS fields with per-field confidence scores."""
    return await self._call_llm(SDS_CONFIDENCE_PROMPT.format(text=text[:8000]))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_document_service.py -v`
Expected: All PASSED

**Step 5: Run full suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -x -q`
Expected: All 458+ tests pass

**Step 6: Commit**

```bash
git add services/document_service.py tests/test_document_service.py
git commit -m "feat: add confidence-scored TDS/SDS extraction to DocumentService"
```

---

### Task 2: Update Seed Pipeline to Use Confidence Extraction and Emit Progress

**Files:**
- Modify: `services/ingestion/seed_chempoint.py`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

Add to `tests/test_seed_chempoint.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_with_progress_callback():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    progress_events = []

    def on_progress(event):
        progress_events.append(event)

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "POLYOX WSR-301", "manufacturer": "Dow",
        "cas_number": "25322-68-3", "product_line": "POLYOX",
        "industries": ["Adhesives"], "tds_url": "https://example.com/tds.pdf",
        "sds_url": "https://example.com/sds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake-pdf")

    mock_doc = MagicMock()
    mock_doc.store_document = AsyncMock(return_value={"id": "doc-1"})
    mock_doc.extract_text_from_pdf = AsyncMock(return_value="Appearance: White powder")
    mock_doc.extract_tds_fields_with_confidence = AsyncMock(return_value={
        "appearance": {"value": "White powder", "confidence": 0.95},
    })
    mock_doc.extract_sds_fields_with_confidence = AsyncMock(return_value={
        "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
    })

    mock_graph = MagicMock()
    mock_graph.create_tds = AsyncMock()
    mock_graph.create_sds = AsyncMock()
    mock_graph.link_product_to_industry = AsyncMock()
    mock_graph.link_product_to_product_line = AsyncMock()

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "prod-1", "sku": "POLYOX-WSR-301"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    pipeline = ChempointSeedPipeline(
        scraper=mock_scraper, doc_service=mock_doc,
        graph_service=mock_graph, db_manager=mock_db,
    )
    result = await pipeline.seed_from_url(
        "https://chempoint.com/products/polyox", on_progress=on_progress,
    )
    assert result["products_created"] >= 1
    assert len(progress_events) >= 3  # scraping, extracting, building_graph
    assert progress_events[0]["stage"] in ("scraping", "discovering")


@pytest.mark.asyncio
async def test_pipeline_stores_confidence_in_graph():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "TEST-PROD", "manufacturer": "TestMfr",
        "tds_url": "https://example.com/tds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake")

    mock_doc = MagicMock()
    mock_doc.store_document = AsyncMock(return_value={"id": "d1"})
    mock_doc.extract_text_from_pdf = AsyncMock(return_value="text")
    mock_doc.extract_tds_fields_with_confidence = AsyncMock(return_value={
        "appearance": {"value": "Clear liquid", "confidence": 0.92},
    })

    mock_graph = MagicMock()
    mock_graph.create_tds = AsyncMock()
    mock_graph.link_product_to_industry = AsyncMock()
    mock_graph.link_product_to_product_line = AsyncMock()

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "p1", "sku": "TEST-PROD"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    pipeline = ChempointSeedPipeline(
        scraper=mock_scraper, doc_service=mock_doc,
        graph_service=mock_graph, db_manager=mock_db,
    )
    await pipeline.seed_from_url("https://example.com/test")

    # Verify the graph got confidence-scored fields flattened
    call_args = mock_graph.create_tds.call_args
    fields = call_args[0][1]  # second positional arg
    assert "appearance" in fields
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_seed_chempoint.py::test_pipeline_with_progress_callback -v`
Expected: FAIL

**Step 3: Update ChempointSeedPipeline**

Modify `services/ingestion/seed_chempoint.py`:

1. Add `on_progress` callback parameter to `seed_from_url` and `seed_from_industry`
2. Call `on_progress({"stage": "...", "product": "...", "current": N, "total": M, "detail": "..."})` at each step
3. Use `extract_tds_fields_with_confidence` / `extract_sds_fields_with_confidence` instead of old methods
4. Flatten confidence fields for graph storage: `{k: v["value"] for k, v in fields.items()}` but also store raw confidence data in PG `documents.structured_data`
5. Add `seed_from_industries(industry_urls, on_progress)` batch method

```python
async def seed_from_url(self, url: str, on_progress=None) -> dict:
    """Scrape a Chempoint product page and populate the knowledge graph."""
    _emit = on_progress or (lambda e: None)
    _emit({"stage": "scraping", "detail": f"Fetching {url}"})

    products = await self._scraper.scrape_product_page(url)
    total = len(products)

    stats = {"products_created": 0, "tds_stored": 0, "sds_stored": 0,
             "industries_linked": 0, "errors": 0}

    for i, product_data in enumerate(products):
        name = product_data.get("name", "unknown")
        try:
            _emit({"stage": "processing", "product": name,
                   "current": i + 1, "total": total})
            await self._process_product(product_data, stats, _emit)
        except Exception as e:
            logger.error("Failed to process %s: %s", name, e)
            stats["errors"] += 1
            _emit({"stage": "error", "product": name, "detail": str(e)})

    _emit({"stage": "done", "detail": f"Completed: {stats}"})
    return stats

async def seed_from_industries(self, industry_urls: list[str],
                                on_progress=None) -> dict:
    """Batch scrape multiple industry pages."""
    _emit = on_progress or (lambda e: None)
    combined = {"products_created": 0, "tds_stored": 0,
                "sds_stored": 0, "industries_linked": 0, "errors": 0}

    for idx, url in enumerate(industry_urls):
        _emit({"stage": "discovering", "detail": f"Industry {idx+1}/{len(industry_urls)}: {url}"})
        sub = await self.seed_from_industry(url)
        for k in combined:
            combined[k] += sub.get(k, 0)

    return combined
```

Update `_process_document` to use confidence extraction:

```python
async def _process_document(self, product_id, sku, doc_url, doc_type, stats, _emit=None):
    _emit = _emit or (lambda e: None)
    try:
        _emit({"stage": "downloading_pdf", "product": sku, "detail": f"{doc_type} from {doc_url}"})
        file_bytes = await self._scraper.download_document(doc_url)
        file_name = doc_url.split("/")[-1] or f"{doc_type.lower()}.pdf"

        await self._doc.store_document(
            product_id=product_id, doc_type=doc_type,
            file_bytes=file_bytes, file_name=file_name, source_url=doc_url,
        )

        _emit({"stage": "extracting", "product": sku, "detail": f"OCR + Claude extraction for {doc_type}"})
        text = await self._doc.extract_text_from_pdf(file_bytes)

        if doc_type == "TDS":
            raw_fields = await self._doc.extract_tds_fields_with_confidence(text)
        else:
            raw_fields = await self._doc.extract_sds_fields_with_confidence(text)

        # Flatten for graph (store values only)
        flat_fields = {}
        for k, v in raw_fields.items():
            if isinstance(v, dict) and "value" in v:
                flat_fields[k] = v["value"]
            else:
                flat_fields[k] = v
        flat_fields["pdf_url"] = doc_url

        _emit({"stage": "building_graph", "product": sku,
               "detail": f"{doc_type}: {len(flat_fields)} fields extracted"})

        if doc_type == "TDS":
            await self._graph.create_tds(sku, flat_fields)
            stats["tds_stored"] += 1
        else:
            await self._graph.create_sds(sku, flat_fields)
            stats["sds_stored"] += 1

    except Exception as e:
        logger.warning("Failed %s from %s: %s", doc_type, doc_url, e)
        stats["errors"] = stats.get("errors", 0) + 1
```

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_seed_chempoint.py -v`
Expected: All PASSED

**Step 5: Run full suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -x -q`

**Step 6: Commit**

```bash
git add services/ingestion/seed_chempoint.py tests/test_seed_chempoint.py
git commit -m "feat: add progress callbacks and confidence-scored extraction to seed pipeline"
```

---

## Phase 2: WebSocket Progress Streaming (Tasks 3–4)

### Task 3: WebSocket Endpoint for Ingestion Progress

**Files:**
- Create: `routes/ingestion_ws.py`
- Modify: `main.py` (register WebSocket route)
- Test: `tests/test_ingestion_ws.py`

**Step 1: Write the failing test**

```python
# tests/test_ingestion_ws.py
"""Test WebSocket ingestion progress streaming."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app():
    from routes.ingestion_ws import router, set_ingestion_pipeline
    app = FastAPI()
    app.include_router(router)
    return app, set_ingestion_pipeline


def test_start_ingestion_returns_job_id():
    app, set_pipeline = _make_test_app()
    mock_pipeline = MagicMock()
    mock_pipeline.seed_from_url = AsyncMock(return_value={"products_created": 1})
    set_pipeline(mock_pipeline)

    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/start", json={"url": "https://chempoint.com/products/test"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "running"


def test_start_batch_ingestion():
    app, set_pipeline = _make_test_app()
    mock_pipeline = MagicMock()
    mock_pipeline.seed_from_industries = AsyncMock(return_value={"products_created": 5})
    set_pipeline(mock_pipeline)

    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/start-batch", json={
        "industry_urls": [
            "https://chempoint.com/industries/adhesives/all",
            "https://chempoint.com/industries/coatings/all",
        ],
        "max_products": 50,
    })
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_get_job_status():
    app, set_pipeline = _make_test_app()
    set_pipeline(MagicMock())

    client = TestClient(app)
    # Start a job first
    with patch("routes.ingestion_ws.asyncio") as mock_asyncio:
        mock_asyncio.create_task = MagicMock()
        resp = client.post("/api/v1/ingestion/start", json={"url": "https://example.com"})
        job_id = resp.json()["job_id"]

    resp2 = client.get(f"/api/v1/ingestion/jobs/{job_id}")
    assert resp2.status_code == 200
    assert resp2.json()["job_id"] == job_id
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_ingestion_ws.py -v`
Expected: FAIL — cannot import

**Step 3: Implement ingestion_ws.py**

Create `routes/ingestion_ws.py`:

```python
"""WebSocket-enabled ingestion endpoints with real-time progress."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])

_pipeline = None
_jobs: dict[str, dict] = {}
_job_events: dict[str, list[dict]] = {}
_job_subscribers: dict[str, list[WebSocket]] = {}


def set_ingestion_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


class StartIngestionRequest(BaseModel):
    url: str


class StartBatchRequest(BaseModel):
    industry_urls: list[str]
    max_products: int = 50


@router.post("/start", status_code=202)
async def start_ingestion(req: StartIngestionRequest):
    """Start single-URL ingestion. Returns job_id for WebSocket progress."""
    if not _pipeline:
        raise HTTPException(503, "Ingestion pipeline not configured")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "events": [], "result": None}
    _job_events[job_id] = []
    _job_subscribers[job_id] = []

    async def _run():
        try:
            result = await _pipeline.seed_from_url(
                req.url, on_progress=lambda e: _broadcast(job_id, e),
            )
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = result
            _broadcast(job_id, {"stage": "done", "result": result})
        except Exception as exc:
            logger.error("Ingestion job %s failed: %s", job_id, exc)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            _broadcast(job_id, {"stage": "error", "detail": str(exc)})

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "running"}


@router.post("/start-batch", status_code=202)
async def start_batch_ingestion(req: StartBatchRequest):
    """Start batch industry ingestion. Returns job_id."""
    if not _pipeline:
        raise HTTPException(503, "Ingestion pipeline not configured")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "events": [], "result": None}
    _job_events[job_id] = []
    _job_subscribers[job_id] = []

    async def _run():
        try:
            result = await _pipeline.seed_from_industries(
                req.industry_urls,
                on_progress=lambda e: _broadcast(job_id, e),
            )
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = result
            _broadcast(job_id, {"stage": "done", "result": result})
        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "running"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll job status (fallback if WebSocket not available)."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {**job, "events": _job_events.get(job_id, [])[-20:]}


@router.websocket("/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    """WebSocket for real-time ingestion progress."""
    await websocket.accept()

    if job_id not in _job_subscribers:
        _job_subscribers[job_id] = []
    _job_subscribers[job_id].append(websocket)

    # Send any missed events
    for event in _job_events.get(job_id, []):
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            # Keep alive, client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        _job_subscribers[job_id].remove(websocket)


def _broadcast(job_id: str, event: dict):
    """Store event and broadcast to all WebSocket subscribers."""
    if job_id in _job_events:
        _job_events[job_id].append(event)

    for ws in _job_subscribers.get(job_id, []):
        try:
            asyncio.create_task(ws.send_text(json.dumps(event)))
        except Exception:
            pass
```

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_ingestion_ws.py -v`
Expected: 3 PASSED

**Step 5: Wire into main.py**

In `main.py`, add after the existing router registrations:

```python
from routes.ingestion_ws import router as ingestion_ws_router, set_ingestion_pipeline
```

Add to lifespan after seed_chempoint pipeline is ready (~line 703):

```python
app.include_router(ingestion_ws_router)
set_ingestion_pipeline(seed_pipeline)
```

**Step 6: Run full suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -x -q`

**Step 7: Commit**

```bash
git add routes/ingestion_ws.py tests/test_ingestion_ws.py main.py
git commit -m "feat: add WebSocket ingestion endpoints with real-time progress streaming"
```

---

### Task 4: Graph Visualization Backend Endpoint

**Files:**
- Modify: `routes/knowledge_base.py`
- Test: `tests/test_knowledge_base_routes.py`

**Step 1: Write the failing test**

Add to `tests/test_knowledge_base_routes.py`:

```python
def test_graph_visualization_endpoint(client):
    """Test /graph-viz returns nodes and edges for Neovis.js."""
    resp = client.get("/api/v1/knowledge-base/graph-viz")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data


def test_graph_visualization_with_industry_filter(client):
    resp = client.get("/api/v1/knowledge-base/graph-viz?industry=Adhesives")
    assert resp.status_code == 200
```

Note: The test fixture `client` must have the knowledge base service mock returning graph data. Check the existing fixture in the test file and extend it to mock `get_graph_visualization`.

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_knowledge_base_routes.py::test_graph_visualization_endpoint -v`
Expected: FAIL — 404 no such route

**Step 3: Add graph-viz endpoint**

Add to `routes/knowledge_base.py`:

```python
@router.get("/graph-viz")
async def graph_visualization(
    industry: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return nodes and edges for frontend graph visualization."""
    svc = _get_svc()
    data = await svc.get_graph_visualization(
        industry=industry, manufacturer=manufacturer, limit=limit,
    )
    return data
```

Add to `services/knowledge_base_service.py` the `get_graph_visualization` method:

```python
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

    results = await self._neo4j.execute_read(cypher, params)

    nodes = {}
    edges = []

    for record in results:
        # Process nodes — each type gets a unique ID and color label
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

    # Build edges from relationships
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
```

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_knowledge_base_routes.py -v`

**Step 5: Commit**

```bash
git add routes/knowledge_base.py services/knowledge_base_service.py tests/test_knowledge_base_routes.py
git commit -m "feat: add graph visualization endpoint for Neovis.js"
```

---

## Phase 3: CLI Script (Task 5)

### Task 5: Rich CLI Script for Batch Seeding

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/seed_chempoint.py`

**Step 1: Install rich**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/pip install rich && echo "rich" >> requirements.txt`

**Step 2: Create the CLI script**

Create `scripts/__init__.py` (empty file).

Create `scripts/seed_chempoint.py`:

```python
"""CLI script to seed the knowledge graph from Chempoint.

Usage:
    python -m scripts.seed_chempoint --industries "Adhesives,Coatings,Pharma" --max-products 50
    python -m scripts.seed_chempoint --url "https://chempoint.com/products/polyox-wsr301"
"""
import argparse
import asyncio
import logging
import os
import sys

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text

console = Console()

# Chempoint industry page URLs
INDUSTRY_URLS = {
    "Adhesives": "https://www.chempoint.com/en-us/products/industry/adhesives-and-sealants",
    "Coatings": "https://www.chempoint.com/en-us/products/industry/paints-and-coatings",
    "Pharma": "https://www.chempoint.com/en-us/products/industry/pharmaceutical",
    "Personal Care": "https://www.chempoint.com/en-us/products/industry/personal-care",
    "Water Treatment": "https://www.chempoint.com/en-us/products/industry/water-treatment",
    "Food & Beverage": "https://www.chempoint.com/en-us/products/industry/food-and-beverage",
    "Plastics": "https://www.chempoint.com/en-us/products/industry/plastics-and-rubber",
    "Energy": "https://www.chempoint.com/en-us/products/industry/energy",
    "Agriculture": "https://www.chempoint.com/en-us/products/industry/agriculture",
    "Construction": "https://www.chempoint.com/en-us/products/industry/building-and-construction",
}


async def run_seed(args):
    """Run the seeding pipeline."""
    # Import after path setup
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from services.database_manager import DatabaseManager
    from services.graph.neo4j_client import Neo4jClient
    from services.ai.llm_router import LLMRouter
    from services.document_service import DocumentService
    from services.graph.tds_sds_service import TDSSDSGraphService
    from services.ingestion.chempoint_scraper import ChempointScraper
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    # Init services
    db = DatabaseManager(os.getenv("DATABASE_URL", "postgresql://chatbot:password@localhost:5432/chatbot"))
    await db.initialize()

    neo4j = Neo4jClient(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "changeme"),
    )
    await neo4j.verify_connectivity()

    llm = LLMRouter(api_key=os.getenv("ANTHROPIC_API_KEY"))
    doc_service = DocumentService(db, ai_service=llm)
    graph_service = TDSSDSGraphService(neo4j)

    scraper = ChempointScraper(
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
        llm_router=llm,
    )

    pipeline = ChempointSeedPipeline(
        scraper=scraper, doc_service=doc_service,
        graph_service=graph_service, db_manager=db,
    )

    # Progress display
    stats = {"products_created": 0, "tds_stored": 0, "sds_stored": 0,
             "industries_linked": 0, "errors": 0}
    current_product = ""
    current_stage = ""

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        if args.url:
            # Single URL mode
            task = progress.add_task("Ingesting product...", total=None)

            def on_progress(event):
                nonlocal current_product, current_stage
                current_stage = event.get("stage", "")
                current_product = event.get("product", "")
                detail = event.get("detail", "")
                progress.update(task, description=f"[{current_stage}] {current_product or detail}")

            result = await pipeline.seed_from_url(args.url, on_progress=on_progress)
            progress.update(task, completed=True)

        else:
            # Industry batch mode
            industries = [i.strip() for i in args.industries.split(",")]
            urls = []
            for ind in industries:
                if ind in INDUSTRY_URLS:
                    urls.append(INDUSTRY_URLS[ind])
                else:
                    console.print(f"[yellow]Unknown industry: {ind}. Skipping.[/yellow]")

            if not urls:
                console.print("[red]No valid industries found. Available:[/red]")
                for k in INDUSTRY_URLS:
                    console.print(f"  - {k}")
                return

            task = progress.add_task(f"Seeding {len(urls)} industries...", total=len(urls))

            def on_progress(event):
                stage = event.get("stage", "")
                product = event.get("product", "")
                detail = event.get("detail", "")
                if stage == "discovering":
                    progress.advance(task)
                progress.update(task, description=f"[{stage}] {product or detail}")

            result = await pipeline.seed_from_industries(urls, on_progress=on_progress)
            progress.update(task, completed=len(urls))

    # Summary
    console.print()
    summary = Table(title="Seed Pipeline Results", show_header=True)
    summary.add_column("Metric", style="bold")
    summary.add_column("Count", justify="right")
    for key, val in result.items():
        color = "green" if val > 0 else "dim"
        summary.add_row(key.replace("_", " ").title(), f"[{color}]{val}[/{color}]")
    console.print(Panel(summary))

    await db.close()
    await neo4j.close()


def main():
    parser = argparse.ArgumentParser(description="Seed knowledge graph from Chempoint")
    parser.add_argument("--url", help="Single product URL to ingest")
    parser.add_argument("--industries", default="Adhesives,Coatings,Pharma,Personal Care,Water Treatment",
                        help="Comma-separated industry names")
    parser.add_argument("--max-products", type=int, default=50, help="Max products per industry")
    args = parser.parse_args()
    asyncio.run(run_seed(args))


if __name__ == "__main__":
    main()
```

**Step 3: Test manually**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m scripts.seed_chempoint --url "https://www.chempoint.com/en-us/products/dow/polyox-water-soluble-resins" 2>&1`
Expected: Progress bars show, product gets ingested (requires FIRECRAWL_API_KEY and ANTHROPIC_API_KEY in env)

**Step 4: Commit**

```bash
git add scripts/ requirements.txt
git commit -m "feat: add rich CLI script for Chempoint batch seeding with progress bars"
```

---

## Phase 4: Frontend — Ingestion Panel + Graph Viz (Tasks 6–8)

### Task 6: Install Neovis.js and Add API Types

**Step 1: Install neovis.js**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm install neovis.js`

**Step 2: Add TypeScript types to api.ts**

Add to `src/lib/api.ts`, in the types section:

```typescript
export interface IngestionEvent {
  stage: string;
  product?: string;
  current?: number;
  total?: number;
  detail?: string;
  result?: Record<string, number>;
}

export interface IngestionJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  events: IngestionEvent[];
  result?: Record<string, number>;
  error?: string;
}

export interface GraphVizData {
  nodes: Array<{
    id: string;
    label: string;
    name: string;
    color: string;
    properties: Record<string, unknown>;
  }>;
  edges: Array<{
    source: string;
    target: string;
    relationship: string;
  }>;
}
```

Add to the `api` object:

```typescript
// Ingestion
startIngestion: (url: string) =>
  post<{ job_id: string; status: string }>("/ingestion/start", { url }),
startBatchIngestion: (industryUrls: string[], maxProducts = 50) =>
  post<{ job_id: string; status: string }>("/ingestion/start-batch", {
    industry_urls: industryUrls,
    max_products: maxProducts,
  }),
getIngestionJob: (jobId: string) => get<IngestionJob>(`/ingestion/jobs/${jobId}`),

// Graph Visualization
getGraphViz: (industry?: string, manufacturer?: string) => {
  const params = new URLSearchParams();
  if (industry) params.set("industry", industry);
  if (manufacturer) params.set("manufacturer", manufacturer);
  const qs = params.toString();
  return get<GraphVizData>(`/knowledge-base/graph-viz${qs ? `?${qs}` : ""}`);
},
```

**Step 3: Commit**

```bash
git add package.json package-lock.json src/lib/api.ts
git commit -m "feat: add neovis.js dependency and ingestion/graph-viz API types"
```

---

### Task 7: Ingestion Panel Component

**Files:**
- Create: `src/components/ingestion/IngestionPanel.tsx`

Create the live ingestion panel with progress bars:

```tsx
import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type IngestionEvent } from "@/lib/api";
import {
  Play, Loader2, CheckCircle, AlertCircle, Database,
  FileText, Download, Cpu, Globe
} from "lucide-react";

const INDUSTRY_OPTIONS = [
  "Adhesives", "Coatings", "Pharma", "Personal Care", "Water Treatment",
  "Food & Beverage", "Plastics", "Energy", "Agriculture", "Construction",
];

const INDUSTRY_URLS: Record<string, string> = {
  "Adhesives": "https://www.chempoint.com/en-us/products/industry/adhesives-and-sealants",
  "Coatings": "https://www.chempoint.com/en-us/products/industry/paints-and-coatings",
  "Pharma": "https://www.chempoint.com/en-us/products/industry/pharmaceutical",
  "Personal Care": "https://www.chempoint.com/en-us/products/industry/personal-care",
  "Water Treatment": "https://www.chempoint.com/en-us/products/industry/water-treatment",
  "Food & Beverage": "https://www.chempoint.com/en-us/products/industry/food-and-beverage",
  "Plastics": "https://www.chempoint.com/en-us/products/industry/plastics-and-rubber",
  "Energy": "https://www.chempoint.com/en-us/products/industry/energy",
  "Agriculture": "https://www.chempoint.com/en-us/products/industry/agriculture",
  "Construction": "https://www.chempoint.com/en-us/products/industry/building-and-construction",
};

const STAGE_ICONS: Record<string, typeof Play> = {
  discovering: Globe,
  scraping: Download,
  downloading_pdf: FileText,
  extracting: Cpu,
  building_graph: Database,
};

function StageIcon({ stage }: { stage: string }) {
  const Icon = STAGE_ICONS[stage] || Loader2;
  return <Icon size={14} className={stage === "done" ? "text-green-500" : "animate-pulse text-blue-500"} />;
}

export default function IngestionPanel() {
  const [mode, setMode] = useState<"single" | "batch">("batch");
  const [url, setUrl] = useState("");
  const [selectedIndustries, setSelectedIndustries] = useState<string[]>(["Adhesives", "Coatings"]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<IngestionEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Poll job status as fallback
  const { data: job } = useQuery({
    queryKey: ["ingestion-job", jobId],
    queryFn: () => api.getIngestionJob(jobId!),
    enabled: !!jobId && !wsConnected,
    refetchInterval: jobId ? 2000 : false,
  });

  // WebSocket connection
  useEffect(() => {
    if (!jobId) return;
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ingestion/ws/${jobId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data) as IngestionEvent;
      setEvents((prev) => [...prev, event]);
    };
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    return () => ws.close();
  }, [jobId]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const startSingle = useMutation({
    mutationFn: () => api.startIngestion(url),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setEvents([]);
    },
  });

  const startBatch = useMutation({
    mutationFn: () => {
      const urls = selectedIndustries
        .filter((i) => INDUSTRY_URLS[i])
        .map((i) => INDUSTRY_URLS[i]);
      return api.startBatchIngestion(urls);
    },
    onSuccess: (data) => {
      setJobId(data.job_id);
      setEvents([]);
    },
  });

  const isRunning = job?.status === "running" || startSingle.isPending || startBatch.isPending;
  const isDone = events.some((e) => e.stage === "done");
  const lastEvent = events[events.length - 1];
  const productCount = events.filter((e) => e.stage === "building_graph").length;
  const errorCount = events.filter((e) => e.stage === "error").length;

  const toggleIndustry = (ind: string) => {
    setSelectedIndustries((prev) =>
      prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind]
    );
  };

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-800">Data Ingestion</h3>
        <div className="flex gap-1 rounded-lg bg-slate-100 p-0.5">
          <button onClick={() => setMode("single")}
            className={`rounded-md px-3 py-1 text-xs font-medium ${mode === "single" ? "bg-white shadow-sm text-slate-800" : "text-slate-500"}`}>
            Single URL
          </button>
          <button onClick={() => setMode("batch")}
            className={`rounded-md px-3 py-1 text-xs font-medium ${mode === "batch" ? "bg-white shadow-sm text-slate-800" : "text-slate-500"}`}>
            Batch Industries
          </button>
        </div>
      </div>

      {mode === "single" ? (
        <div className="flex gap-2">
          <input value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="https://chempoint.com/products/..."
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none" />
          <button onClick={() => startSingle.mutate()} disabled={!url || isRunning}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Ingest
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {INDUSTRY_OPTIONS.map((ind) => (
              <button key={ind} onClick={() => toggleIndustry(ind)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  selectedIndustries.includes(ind)
                    ? "border-blue-300 bg-blue-50 text-blue-700"
                    : "border-slate-200 text-slate-500 hover:border-slate-300"
                }`}>
                {ind}
              </button>
            ))}
          </div>
          <button onClick={() => startBatch.mutate()}
            disabled={selectedIndustries.length === 0 || isRunning}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Seed {selectedIndustries.length} Industries
          </button>
        </div>
      )}

      {/* Progress Section */}
      {jobId && (
        <div className="space-y-3">
          {/* Stats Bar */}
          <div className="flex gap-4 text-sm">
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle size={14} /> {productCount} products
            </span>
            {errorCount > 0 && (
              <span className="flex items-center gap-1 text-red-500">
                <AlertCircle size={14} /> {errorCount} errors
              </span>
            )}
            <span className={`ml-auto text-xs ${wsConnected ? "text-green-500" : "text-slate-400"}`}>
              {wsConnected ? "Live" : "Polling"}
            </span>
          </div>

          {/* Current Stage */}
          {lastEvent && !isDone && (
            <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">
              <StageIcon stage={lastEvent.stage} />
              <span className="font-medium">{lastEvent.product || lastEvent.detail || lastEvent.stage}</span>
              {lastEvent.current && lastEvent.total && (
                <span className="ml-auto text-xs text-blue-400">
                  {lastEvent.current}/{lastEvent.total}
                </span>
              )}
            </div>
          )}

          {/* Progress Bar */}
          {lastEvent?.current && lastEvent?.total && (
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-blue-500 transition-all duration-300"
                style={{ width: `${(lastEvent.current / lastEvent.total) * 100}%` }} />
            </div>
          )}

          {/* Event Log */}
          <div ref={logRef}
            className="max-h-48 overflow-y-auto rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-600">
            {events.map((e, i) => (
              <div key={i} className="flex items-center gap-2 py-0.5">
                <StageIcon stage={e.stage} />
                <span className="text-slate-400">{e.stage}</span>
                <span>{e.product || e.detail || ""}</span>
              </div>
            ))}
          </div>

          {/* Done Summary */}
          {isDone && lastEvent?.result && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3">
              <p className="mb-2 text-sm font-semibold text-green-800">Ingestion Complete</p>
              <div className="grid grid-cols-4 gap-2 text-center text-xs">
                {Object.entries(lastEvent.result).map(([k, v]) => (
                  <div key={k}>
                    <p className="text-lg font-bold text-green-700">{v as number}</p>
                    <p className="text-green-600">{k.replace(/_/g, " ")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/ingestion/IngestionPanel.tsx
git commit -m "feat: add IngestionPanel component with live progress bars and WebSocket"
```

---

### Task 8: Graph Explorer Component + Updated KnowledgeBase Page

**Files:**
- Create: `src/components/graph/GraphExplorer.tsx`
- Modify: `src/pages/KnowledgeBase.tsx`

**Step 1: Create GraphExplorer.tsx**

```tsx
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type GraphVizData } from "@/lib/api";
import { Network, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

// Dynamic import since neovis.js needs DOM
let NeoVis: any = null;

export default function GraphExplorer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [industry, setIndustry] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<Record<string, unknown> | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["graph-viz", industry],
    queryFn: () => api.getGraphViz(industry || undefined),
  });

  useEffect(() => {
    if (!data || !containerRef.current) return;
    renderGraph(data);
  }, [data]);

  const renderGraph = (vizData: GraphVizData) => {
    const container = containerRef.current;
    if (!container) return;

    // Clear previous
    container.innerHTML = "";
    const canvas = document.createElement("canvas");
    canvas.width = container.clientWidth;
    canvas.height = 500;
    container.appendChild(canvas);

    // Draw with simple force-directed layout (canvas fallback)
    // For production, use neovis.js with Neo4j direct connection
    // For demo, render nodes and edges on canvas
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const nodes = vizData.nodes.map((n, i) => ({
      ...n,
      x: Math.cos((i / vizData.nodes.length) * Math.PI * 2) * 200 + canvas.width / 2,
      y: Math.sin((i / vizData.nodes.length) * Math.PI * 2) * 200 + canvas.height / 2,
      radius: n.label === "Product" ? 20 : 14,
    }));

    const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

    // Simple force simulation (5 iterations)
    for (let iter = 0; iter < 50; iter++) {
      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 2000 / (dist * dist);
          nodes[i].x -= (dx / dist) * force;
          nodes[i].y -= (dy / dist) * force;
          nodes[j].x += (dx / dist) * force;
          nodes[j].y += (dy / dist) * force;
        }
      }
      // Attraction (edges)
      for (const edge of vizData.edges) {
        const s = nodeMap[edge.source];
        const t = nodeMap[edge.target];
        if (!s || !t) continue;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const force = (dist - 120) * 0.01;
        s.x += (dx / dist) * force;
        s.y += (dy / dist) * force;
        t.x -= (dx / dist) * force;
        t.y -= (dy / dist) * force;
      }
      // Center gravity
      for (const n of nodes) {
        n.x += (canvas.width / 2 - n.x) * 0.01;
        n.y += (canvas.height / 2 - n.y) * 0.01;
      }
    }

    // Draw edges
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (const edge of vizData.edges) {
      const s = nodeMap[edge.source];
      const t = nodeMap[edge.target];
      if (!s || !t) continue;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();

      // Relationship label
      ctx.fillStyle = "#94a3b8";
      ctx.font = "9px sans-serif";
      ctx.fillText(edge.relationship, (s.x + t.x) / 2, (s.y + t.y) / 2 - 4);
    }

    // Draw nodes
    for (const node of nodes) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = "#1e293b";
      ctx.font = "bold 10px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(node.name.substring(0, 20), node.x, node.y + node.radius + 14);

      // Type badge
      ctx.fillStyle = node.color;
      ctx.font = "8px sans-serif";
      ctx.fillText(node.label, node.x, node.y + node.radius + 24);
    }

    // Click handler
    canvas.onclick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      for (const node of nodes) {
        const dx = mx - node.x;
        const dy = my - node.y;
        if (dx * dx + dy * dy < node.radius * node.radius) {
          setSelectedNode(node.properties);
          return;
        }
      }
      setSelectedNode(null);
    };
  };

  const INDUSTRIES = [
    "", "Adhesives", "Coatings", "Pharma", "Personal Care",
    "Water Treatment", "Plastics", "Energy",
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Network size={18} className="text-purple-600" />
          <h3 className="text-lg font-bold text-slate-800">Knowledge Graph Explorer</h3>
        </div>
        <select value={industry} onChange={(e) => setIndustry(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
          <option value="">All Industries</option>
          {INDUSTRIES.filter(Boolean).map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {[
          { label: "Product", color: "#1e3a8a" },
          { label: "TDS", color: "#7c3aed" },
          { label: "SDS", color: "#dc2626" },
          { label: "Industry", color: "#f59e0b" },
          { label: "ProductLine", color: "#0d9488" },
          { label: "Manufacturer", color: "#059669" },
        ].map(({ label, color }) => (
          <span key={label} className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </span>
        ))}
      </div>

      {/* Graph Canvas */}
      <div ref={containerRef}
        className="relative min-h-[500px] rounded-xl border border-slate-200 bg-slate-50" >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-purple-600" />
          </div>
        )}
        {!isLoading && (!data || data.nodes.length === 0) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
            <Network size={40} className="mb-3" />
            <p>No graph data yet. Run ingestion to populate.</p>
          </div>
        )}
      </div>

      {/* Selected Node Properties */}
      {selectedNode && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-700">Node Properties</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(selectedNode).map(([k, v]) => (
              <div key={k} className="rounded bg-slate-50 px-2 py-1">
                <span className="text-slate-400">{k}: </span>
                <span className="font-medium text-slate-700">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Update KnowledgeBase.tsx**

Replace `src/pages/KnowledgeBase.tsx` to add tabs for Products, Graph Explorer, and Ingestion:

Add imports at top:

```tsx
import IngestionPanel from "@/components/ingestion/IngestionPanel";
import GraphExplorer from "@/components/graph/GraphExplorer";
```

Add tab state and tab UI wrapping the existing search content and the two new panels. The page should have 3 tabs: "Products" (existing search), "Graph Explorer" (new), "Ingestion" (new).

**Step 3: Commit**

```bash
git add src/components/graph/GraphExplorer.tsx src/pages/KnowledgeBase.tsx
git commit -m "feat: add GraphExplorer with canvas visualization and tabbed KnowledgeBase page"
```

---

## Phase 5: Integration & Polish (Tasks 9–10)

### Task 9: Wire Ingestion Pipeline in main.py

**Files:**
- Modify: `main.py`

Add after seed_chempoint pipeline initialization (~line 703):

```python
from routes.ingestion_ws import router as ingestion_ws_router, set_ingestion_pipeline
app.include_router(ingestion_ws_router)
if seed_pipeline:
    set_ingestion_pipeline(seed_pipeline)
    logger.info("Ingestion WebSocket pipeline wired")
```

**Commit:**

```bash
git add main.py
git commit -m "feat: wire ingestion WebSocket pipeline into main.py lifespan"
```

---

### Task 10: Run Full Suite, Fix Regressions, Verify Demo Flow

**Step 1: Run all tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All 458+ tests pass

**Step 2: Build frontend**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npx vite build`
Expected: Build succeeds with no errors

**Step 3: Start server and smoke test**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m uvicorn main:app --port 8080`

Test endpoints:
- `curl http://localhost:8080/health`
- `curl http://localhost:8080/api/v1/knowledge-base/products`
- `curl http://localhost:8080/api/v1/knowledge-base/graph-viz`
- `curl -X POST http://localhost:8080/api/v1/ingestion/start -H "Content-Type: application/json" -d '{"url":"https://www.chempoint.com/en-us/products/dow/polyox-water-soluble-resins"}'`

**Step 4: Fix any regressions**

**Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify full suite and demo flow after ingestion pipeline integration"
```

---

## Execution Order & Dependencies

```
Phase 1: Task 1 → Task 2 (confidence extraction, then pipeline progress)
Phase 2: Task 3 → Task 4 (WebSocket, then graph viz endpoint)
Phase 3: Task 5 (CLI — independent, can run in parallel with Phase 2)
Phase 4: Task 6 → Task 7 → Task 8 (npm install, then components, then page update)
Phase 5: Task 9 → Task 10 (wire, then verify)
```

**Parallelizable:** Tasks 3+5 can run in parallel. Tasks 4+5 can run in parallel.

**Estimated total: 10 tasks across 5 phases.**
