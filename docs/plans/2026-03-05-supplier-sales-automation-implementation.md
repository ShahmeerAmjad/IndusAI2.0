# Supplier Sales & Support Automation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform IndusAI from a buyer-focused sourcing tool into a supplier sales & support automation platform that ingests TDS/SDS documents, classifies inbound email/web/fax messages by intent, and drafts AI responses for human review.

**Architecture:** Extend the existing FastAPI + Neo4j + PostgreSQL + React stack. Add new tables for inbound messages, documents, and customer accounts. Expand the Neo4j knowledge graph with TDS/SDS nodes, Industry/Manufacturer/ProductLine taxonomy. Build an email ingestion pipeline, multi-intent classifier, auto-response engine, and omnichannel inbox UI.

**Tech Stack:** Python 3.14 / FastAPI, React 18 / TypeScript / Tailwind / shadcn/ui, PostgreSQL 16, Neo4j 5.x, Redis 7, Claude (Haiku/Sonnet/Opus), Voyage AI embeddings, Firecrawl API, aioimaplib (email)

**Design Doc:** `docs/plans/2026-03-05-supplier-sales-automation-design.md`

---

## Phase 1: Data Foundation (Tasks 1–5)

### Task 1: Extend PostgreSQL Schema — New Tables

**Files:**
- Modify: `services/platform/schema.py` (append after line 547)
- Test: `tests/test_new_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_new_schema.py
"""Test that new supplier-sales tables exist after schema creation."""
import pytest
from unittest.mock import AsyncMock, MagicMock

REQUIRED_TABLES = [
    "documents",
    "inbound_messages",
    "customer_accounts",
    "classification_feedback",
    "erp_connections",
]

@pytest.mark.asyncio
async def test_new_tables_sql_contains_required_tables():
    """Verify the schema SQL string defines all required tables."""
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    for table in REQUIRED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SUPPLIER_SALES_SCHEMA, \
            f"Missing table: {table}"

@pytest.mark.asyncio
async def test_documents_table_has_tds_sds_fields():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "doc_type" in SUPPLIER_SALES_SCHEMA
    assert "extracted_text" in SUPPLIER_SALES_SCHEMA
    assert "structured_data" in SUPPLIER_SALES_SCHEMA
    assert "revision_date" in SUPPLIER_SALES_SCHEMA

@pytest.mark.asyncio
async def test_inbound_messages_has_multi_intent():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "intents JSONB" in SUPPLIER_SALES_SCHEMA
    assert "ai_draft_response" in SUPPLIER_SALES_SCHEMA
    assert "thread_id" in SUPPLIER_SALES_SCHEMA

@pytest.mark.asyncio
async def test_classification_feedback_table():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "ai_intent" in SUPPLIER_SALES_SCHEMA
    assert "human_intent" in SUPPLIER_SALES_SCHEMA
    assert "is_correct" in SUPPLIER_SALES_SCHEMA
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_new_schema.py -v`
Expected: FAIL with "cannot import name 'SUPPLIER_SALES_SCHEMA'"

**Step 3: Write the schema SQL**

Add to `services/platform/schema.py` — append a new `SUPPLIER_SALES_SCHEMA` string after the existing `PLATFORM_SCHEMA` and `PLATFORM_INDEXES` strings. Contains CREATE TABLE statements for: `documents`, `inbound_messages`, `customer_accounts`, `classification_feedback`, `erp_connections`. Also add `SUPPLIER_SALES_INDEXES` for common queries. See design doc for exact DDL.

**Step 4: Run test to verify it passes**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_new_schema.py -v`
Expected: 4 PASSED

**Step 5: Wire schema creation into main.py lifespan**

In `main.py`, find the `_init_database` function where `PLATFORM_SCHEMA` is executed. Add execution of `SUPPLIER_SALES_SCHEMA` and `SUPPLIER_SALES_INDEXES` after it.

**Step 6: Run full test suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -x -q`
Expected: All 227+ tests pass

**Step 7: Commit**

```bash
git add services/platform/schema.py tests/test_new_schema.py main.py
git commit -m "feat: add PostgreSQL tables for documents, inbound messages, customer accounts, classification feedback"
```

---

### Task 2: Extend Neo4j Knowledge Graph Schema — TDS/SDS Nodes

**Files:**
- Modify: `services/graph/schema.py`
- Test: `tests/test_graph_schema_tds_sds.py`

**Step 1: Write the failing test**

```python
# tests/test_graph_schema_tds_sds.py
"""Test that Neo4j schema includes TDS/SDS node types and industry taxonomy."""
import pytest

def test_tds_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    tds_constraints = [c for c in CONSTRAINTS if "TechnicalDataSheet" in c]
    assert len(tds_constraints) >= 1, "Missing TDS uniqueness constraint"

def test_sds_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    sds_constraints = [c for c in CONSTRAINTS if "SafetyDataSheet" in c]
    assert len(sds_constraints) >= 1, "Missing SDS uniqueness constraint"

def test_industry_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    industry_constraints = [c for c in CONSTRAINTS if "Industry" in c]
    assert len(industry_constraints) >= 1, "Missing Industry constraint"

def test_product_line_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    pl_constraints = [c for c in CONSTRAINTS if "ProductLine" in c]
    assert len(pl_constraints) >= 1, "Missing ProductLine constraint"

def test_industry_taxonomy_has_18_industries():
    from services.graph.schema import INDUSTRY_TAXONOMY
    assert len(INDUSTRY_TAXONOMY) >= 18, f"Expected 18+ industries, got {len(INDUSTRY_TAXONOMY)}"

def test_industry_taxonomy_includes_key_industries():
    from services.graph.schema import INDUSTRY_TAXONOMY
    required = ["Adhesives", "Coatings", "Pharma", "Metal Processing", "Water Treatment"]
    for industry in required:
        assert industry in INDUSTRY_TAXONOMY, f"Missing industry: {industry}"

def test_fulltext_index_includes_cas():
    from services.graph.schema import FULLTEXT_INDEXES
    combined = " ".join(FULLTEXT_INDEXES)
    assert "cas_number" in combined or "Product" in combined
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_graph_schema_tds_sds.py -v`
Expected: FAIL — no TDS/SDS constraints, no INDUSTRY_TAXONOMY

**Step 3: Extend schema.py**

Add to `services/graph/schema.py`:
- New CONSTRAINTS for: TechnicalDataSheet (unique on product_sku+revision_date), SafetyDataSheet (unique on product_sku+revision_date), Industry (unique name), ProductLine (unique name), Distributor (unique name), PricePoint, CustomerAccount
- New INDEXES for: Industry.name, ProductLine.name, TechnicalDataSheet properties, SafetyDataSheet.cas_numbers
- New FULLTEXT_INDEXES entry that includes cas_number
- New `INDUSTRY_TAXONOMY` dict with 18 industries and their applications (similar pattern to existing CATEGORY_TAXONOMY)

**Step 4: Run test to verify it passes**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_graph_schema_tds_sds.py -v`
Expected: 7 PASSED

**Step 5: Run full test suite**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

**Step 6: Commit**

```bash
git add services/graph/schema.py tests/test_graph_schema_tds_sds.py
git commit -m "feat: extend Neo4j schema with TDS/SDS nodes, Industry taxonomy, PricePoint and CustomerAccount"
```

---

### Task 3: Expand IntentType Enum — 9 Supplier-Sales Intents

**Files:**
- Modify: `services/ai/models.py:24-32`
- Modify: `services/intent_classifier.py:18-37` (update mappings)
- Test: `tests/test_intent_types.py`

**Step 1: Write the failing test**

```python
# tests/test_intent_types.py
"""Test that IntentType enum has all 9 supplier-sales intents."""
import pytest

def test_intent_type_has_9_intents():
    from services.ai.models import IntentType
    expected = [
        "place_order", "request_quote", "request_tds_sds",
        "order_status", "technical_support", "return_complaint",
        "reorder", "account_inquiry", "sample_request",
    ]
    actual = [i.value for i in IntentType]
    for e in expected:
        assert e in actual, f"Missing intent: {e}"

def test_multi_intent_result_model():
    from services.ai.models import MultiIntentResult, IntentResult, IntentType
    result = MultiIntentResult(intents=[
        IntentResult(intent=IntentType.REQUEST_QUOTE, confidence=0.95, text_span="quote for 500kg"),
        IntentResult(intent=IntentType.REQUEST_TDS_SDS, confidence=0.98, text_span="send me the SDS"),
    ])
    assert len(result.intents) == 2

def test_entity_result_has_cas_and_po():
    from services.ai.models import EntityResult
    er = EntityResult(
        part_numbers=["WSR-301"],
        cas_numbers=["25322-68-3"],
        po_numbers=["PO-12345"],
        quantities={"WSR-301": 500},
    )
    assert er.cas_numbers == ["25322-68-3"]
    assert er.po_numbers == ["PO-12345"]
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_intent_types.py -v`
Expected: FAIL — missing intents, missing MultiIntentResult

**Step 3: Update models.py**

Replace IntentType enum in `services/ai/models.py:24-32` with 9 new intents. Add `MultiIntentResult` model. Add `text_span` field to `IntentResult`. Add `cas_numbers` and `po_numbers` fields to `EntityResult`.

**Step 4: Update intent_classifier.py mappings**

Update `INTENT_TO_MESSAGE_TYPE` and `_MESSAGE_TYPE_TO_INTENT` dicts in `services/intent_classifier.py:18-37` to map the new intent types. Add new regex patterns for the new intents (REORDER, SAMPLE_REQUEST, REQUEST_TDS_SDS, etc.).

**Step 5: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_intent_types.py tests/ -x -q`
Expected: All pass (new + existing)

**Step 6: Commit**

```bash
git add services/ai/models.py services/intent_classifier.py tests/test_intent_types.py
git commit -m "feat: expand IntentType to 9 supplier-sales intents, add MultiIntentResult model"
```

---

### Task 4: Document Service — TDS/SDS Storage & Extraction

**Files:**
- Create: `services/document_service.py`
- Test: `tests/test_document_service.py`

**Step 1: Write the failing test**

```python
# tests/test_document_service.py
"""Test TDS/SDS document storage, OCR extraction, and structured field parsing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_store_document():
    from services.document_service import DocumentService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "doc-1", "doc_type": "TDS", "file_path": "/docs/tds.pdf"})
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)
    result = await svc.store_document(
        product_id="prod-1",
        doc_type="TDS",
        file_bytes=b"fake-pdf",
        file_name="tds.pdf",
    )
    assert result["doc_type"] == "TDS"

@pytest.mark.asyncio
async def test_extract_tds_fields():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    # Simulate LLM extraction from PDF text
    sample_text = """
    Product: Polyox WSR-301
    Appearance: White powder
    Density: 1.21 g/cm³
    Flash Point: N/A
    pH (2% solution): 5.0-8.0
    Viscosity: 1200-4500 cP
    Storage: Cool, dry place
    """
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "appearance": "White powder",
            "density": "1.21 g/cm³",
            "flash_point": "N/A",
            "pH": "5.0-8.0",
            "viscosity": "1200-4500 cP",
            "storage_conditions": "Cool, dry place",
        }
        fields = await svc.extract_tds_fields(sample_text)
        assert fields["appearance"] == "White powder"
        assert fields["density"] == "1.21 g/cm³"

@pytest.mark.asyncio
async def test_extract_sds_fields():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    sample_text = """
    GHS Classification: Not classified
    CAS Number: 25322-68-3
    UN Number: N/A
    First Aid - Inhalation: Move to fresh air
    PPE: Safety glasses, gloves
    """
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "ghs_classification": "Not classified",
            "cas_numbers": ["25322-68-3"],
            "un_number": "N/A",
            "first_aid": "Inhalation: Move to fresh air",
            "ppe_requirements": "Safety glasses, gloves",
        }
        fields = await svc.extract_sds_fields(sample_text)
        assert fields["cas_numbers"] == ["25322-68-3"]

@pytest.mark.asyncio
async def test_get_documents_for_product():
    from services.document_service import DocumentService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetch=AsyncMock(return_value=[
            {"id": "d1", "doc_type": "TDS", "file_name": "tds.pdf", "is_current": True},
            {"id": "d2", "doc_type": "SDS", "file_name": "sds.pdf", "is_current": True},
        ])
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)
    docs = await svc.get_documents_for_product("prod-1")
    assert len(docs) == 2
    assert docs[0]["doc_type"] == "TDS"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_document_service.py -v`
Expected: FAIL — cannot import DocumentService

**Step 3: Implement DocumentService**

Create `services/document_service.py` with:
- `store_document(product_id, doc_type, file_bytes, file_name)` — saves file to disk, inserts into `documents` table
- `extract_tds_fields(text)` — calls Claude to parse TDS text into structured fields
- `extract_sds_fields(text)` — calls Claude to parse SDS text into structured fields (GHS, CAS, hazards)
- `get_documents_for_product(product_id)` — returns current TDS/SDS for a product
- `extract_text_from_pdf(file_bytes)` — uses pdfplumber to get text from PDF
- `_call_llm(prompt)` — wrapper for AI service calls
- File storage path: `data/documents/{product_id}/{doc_type}_{filename}`

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_document_service.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add services/document_service.py tests/test_document_service.py
git commit -m "feat: add DocumentService for TDS/SDS storage and LLM-based field extraction"
```

---

### Task 5: Customer Account Service

**Files:**
- Create: `services/customer_account_service.py`
- Test: `tests/test_customer_account_service.py`

**Step 1: Write the failing test**

```python
# tests/test_customer_account_service.py
"""Test customer account CRUD and email-based lookup."""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_create_customer_account():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={
            "id": "ca-1", "name": "John Doe", "email": "john@acme.com",
            "company": "Acme Corp", "pricing_tier": "premium"
        })
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.create_account({
        "name": "John Doe", "email": "john@acme.com",
        "company": "Acme Corp", "pricing_tier": "premium"
    })
    assert result["company"] == "Acme Corp"

@pytest.mark.asyncio
async def test_lookup_by_email():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={
            "id": "ca-1", "name": "John Doe", "email": "john@acme.com",
            "company": "Acme Corp", "pricing_tier": "premium"
        })
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.lookup_by_email("john@acme.com")
    assert result["name"] == "John Doe"

@pytest.mark.asyncio
async def test_lookup_by_email_returns_none():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value=None)
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.lookup_by_email("unknown@example.com")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_customer_account_service.py -v`
Expected: FAIL

**Step 3: Implement CustomerAccountService**

Create `services/customer_account_service.py` with:
- `create_account(data)` — INSERT into customer_accounts
- `get_account(account_id)` — SELECT by id
- `lookup_by_email(email)` — SELECT by email (used by email ingestion to find existing customer)
- `update_account(account_id, data)` — UPDATE
- `list_accounts(limit, offset)` — paginated list

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_customer_account_service.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add services/customer_account_service.py tests/test_customer_account_service.py
git commit -m "feat: add CustomerAccountService with email-based lookup"
```

---

## Phase 2: Chempoint Scraper & Knowledge Graph Population (Tasks 6–8)

### Task 6: Chempoint Catalog Scraper

**Files:**
- Create: `services/ingestion/chempoint_scraper.py`
- Test: `tests/test_chempoint_scraper.py`

**Step 1: Write the failing test**

```python
# tests/test_chempoint_scraper.py
"""Test Chempoint catalog scraping and product extraction."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_scrape_product_page():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    mock_html = """
    <div class="product-detail">
        <h1>POLYOX™ WSR-301</h1>
        <span class="manufacturer">Dow</span>
        <span class="cas">25322-68-3</span>
        <p>Water-soluble resin for adhesives and coatings</p>
        <a href="/docs/tds-polyox-wsr301.pdf">Technical Data Sheet</a>
        <a href="/docs/sds-polyox-wsr301.pdf">Safety Data Sheet</a>
    </div>
    """
    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_html
        with patch.object(scraper, '_extract_with_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [{
                "name": "POLYOX WSR-301",
                "manufacturer": "Dow",
                "cas_number": "25322-68-3",
                "description": "Water-soluble resin for adhesives and coatings",
                "tds_url": "/docs/tds-polyox-wsr301.pdf",
                "sds_url": "/docs/sds-polyox-wsr301.pdf",
                "industries": ["Adhesives", "Coatings"],
                "product_line": "POLYOX Water-Soluble Resins",
            }]
            products = await scraper.scrape_product_page("https://chempoint.com/products/polyox-wsr301")
            assert len(products) == 1
            assert products[0]["cas_number"] == "25322-68-3"

@pytest.mark.asyncio
async def test_scrape_industry_page():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "<html>mock</html>"
        with patch.object(scraper, '_extract_with_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [
                {"name": "POLYOX WSR-301", "manufacturer": "Dow"},
                {"name": "METHOCEL K4M", "manufacturer": "Dow"},
            ]
            products = await scraper.scrape_industry_page("https://chempoint.com/industries/adhesives/all")
            assert len(products) == 2

@pytest.mark.asyncio
async def test_download_tds_sds_pdf():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch.object(scraper, '_download_file', new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = b"fake-pdf-bytes"
        result = await scraper.download_document("https://chempoint.com/docs/tds.pdf")
        assert result == b"fake-pdf-bytes"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_chempoint_scraper.py -v`
Expected: FAIL

**Step 3: Implement ChempointScraper**

Create `services/ingestion/chempoint_scraper.py` with:
- `scrape_product_page(url)` — scrape single product page, extract structured data via LLM
- `scrape_industry_page(url)` — scrape industry listing page for product list
- `scrape_manufacturer_page(url)` — scrape manufacturer page for their product lines
- `download_document(url)` — download TDS/SDS PDF bytes
- `crawl_full_catalog(base_url, max_pages)` — orchestrate full catalog crawl
- LLM extraction prompt tuned for Chempoint's page structure (product name, manufacturer, CAS#, industries, TDS/SDS links)
- Uses Firecrawl API (reuse pattern from existing `web_scraper.py`)

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_chempoint_scraper.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add services/ingestion/chempoint_scraper.py tests/test_chempoint_scraper.py
git commit -m "feat: add Chempoint catalog scraper with Firecrawl + LLM extraction"
```

---

### Task 7: Knowledge Graph Builder — TDS/SDS + Industry Nodes

**Files:**
- Modify: `services/ingestion/graph_builder.py` (extend with TDS/SDS node creation)
- Create: `services/graph/tds_sds_service.py`
- Test: `tests/test_tds_sds_graph.py`

**Step 1: Write the failing test**

```python
# tests/test_tds_sds_graph.py
"""Test creating TDS/SDS nodes and Industry relationships in Neo4j."""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_create_tds_node():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "tds-1"}])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.create_tds("SKU-001", {
        "appearance": "White powder",
        "density": "1.21 g/cm³",
        "flash_point": "N/A",
        "viscosity": "1200-4500 cP",
        "pdf_url": "/docs/tds.pdf",
        "revision_date": "2025-11-01",
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_sds_node():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "sds-1"}])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.create_sds("SKU-001", {
        "ghs_classification": "Not classified",
        "cas_numbers": ["25322-68-3"],
        "hazard_statements": [],
        "pdf_url": "/docs/sds.pdf",
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_industry_and_link_product():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{}])
    svc = TDSSDSGraphService(neo4j)
    await svc.link_product_to_industry("SKU-001", "Adhesives")
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_price_point():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{}])
    svc = TDSSDSGraphService(neo4j)
    await svc.set_price("SKU-001", {
        "unit_price": 42.50,
        "currency": "USD",
        "uom": "kg",
        "min_qty": 25,
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_query_tds_property():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[{
        "flash_point": "N/A",
        "viscosity": "1200-4500 cP",
    }])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.get_tds_properties("SKU-001")
    assert result["flash_point"] == "N/A"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_tds_sds_graph.py -v`
Expected: FAIL

**Step 3: Implement TDSSDSGraphService**

Create `services/graph/tds_sds_service.py` with Cypher queries for:
- `create_tds(product_sku, fields)` — MERGE TechnicalDataSheet node, CREATE [:HAS_TDS] relationship
- `create_sds(product_sku, fields)` — MERGE SafetyDataSheet node, CREATE [:HAS_SDS] relationship
- `link_product_to_industry(product_sku, industry_name)` — MERGE Industry, CREATE [:SERVES_INDUSTRY]
- `link_product_to_product_line(product_sku, line_name, manufacturer)` — MERGE ProductLine, CREATE [:BELONGS_TO], [:CONTAINS]
- `set_price(product_sku, price_data)` — MERGE PricePoint, CREATE [:PRICED_AT]
- `set_inventory(product_sku, warehouse_code, stock_data)` — MERGE relationship [:STOCKED_AT]
- `get_tds_properties(product_sku)` — MATCH and return TDS fields
- `get_sds_properties(product_sku)` — MATCH and return SDS fields
- `find_products_by_industry(industry_name)` — traverse Industry → Product

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_tds_sds_graph.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add services/graph/tds_sds_service.py tests/test_tds_sds_graph.py
git commit -m "feat: add TDSSDSGraphService for knowledge graph TDS/SDS nodes, Industry links, pricing"
```

---

### Task 8: Seed Data Pipeline — Chempoint → Knowledge Graph

**Files:**
- Create: `services/ingestion/seed_chempoint.py`
- Test: `tests/test_seed_chempoint.py`

**Step 1: Write the failing test**

```python
# tests/test_seed_chempoint.py
"""Test the end-to-end pipeline: scrape → extract → build graph nodes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_seed_pipeline_creates_product_and_tds():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "POLYOX WSR-301",
        "manufacturer": "Dow",
        "cas_number": "25322-68-3",
        "product_line": "POLYOX Water-Soluble Resins",
        "industries": ["Adhesives", "Pharma"],
        "tds_url": "https://chempoint.com/docs/tds.pdf",
        "sds_url": "https://chempoint.com/docs/sds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake-pdf")

    mock_doc_service = MagicMock()
    mock_doc_service.store_document = AsyncMock(return_value={"id": "doc-1"})
    mock_doc_service.extract_text_from_pdf = AsyncMock(return_value="Appearance: White powder")
    mock_doc_service.extract_tds_fields = AsyncMock(return_value={"appearance": "White powder"})
    mock_doc_service.extract_sds_fields = AsyncMock(return_value={"cas_numbers": ["25322-68-3"]})

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
        scraper=mock_scraper,
        doc_service=mock_doc_service,
        graph_service=mock_graph,
        db_manager=mock_db,
    )
    result = await pipeline.seed_from_url("https://chempoint.com/products/polyox-wsr301")
    assert result["products_created"] >= 1
    mock_graph.create_tds.assert_called_once()
    mock_graph.create_sds.assert_called_once()
    assert mock_graph.link_product_to_industry.call_count == 2  # Adhesives + Pharma
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_seed_chempoint.py -v`
Expected: FAIL

**Step 3: Implement ChempointSeedPipeline**

Create `services/ingestion/seed_chempoint.py` that orchestrates:
1. Scrape product page → get product data + TDS/SDS URLs
2. Download TDS/SDS PDFs → store via DocumentService
3. Extract text from PDFs → extract structured fields via LLM
4. Create/update product in PostgreSQL
5. Create TDS/SDS nodes in Neo4j
6. Link product to industries, manufacturer, product line
7. Generate embeddings via Voyage AI
8. Return summary (products_created, documents_stored, etc.)

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_seed_chempoint.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add services/ingestion/seed_chempoint.py tests/test_seed_chempoint.py
git commit -m "feat: add ChempointSeedPipeline for end-to-end catalog scrape → knowledge graph population"
```

---

## Phase 3: Email Ingestion & Multi-Intent Classification (Tasks 9–12)

### Task 9: Email Parser Service

**Files:**
- Create: `services/email/email_parser.py`
- Test: `tests/test_email_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_email_parser.py
"""Test email parsing: headers, body extraction, thread detection, attachment handling."""
import pytest
from email.message import EmailMessage

def _make_email(from_addr="john@acme.com", subject="Need a quote", body="Quote for 500kg Polyox",
                in_reply_to=None, attachments=None):
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = "sales@supplier.com"
    msg["Subject"] = subject
    msg["Date"] = "Wed, 05 Mar 2026 10:30:00 -0500"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    if attachments:
        for name, content, mime in attachments:
            maintype, subtype = mime.split("/")
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=name)
    return msg

def test_parse_basic_email():
    from services.email.email_parser import EmailParser
    parser = EmailParser()
    msg = _make_email()
    result = parser.parse(msg)
    assert result["from_address"] == "john@acme.com"
    assert result["subject"] == "Need a quote"
    assert "500kg Polyox" in result["body"]
    assert result["channel"] == "email"

def test_parse_thread_detection():
    from services.email.email_parser import EmailParser
    parser = EmailParser()
    msg = _make_email(in_reply_to="<msg-123@acme.com>")
    result = parser.parse(msg)
    assert result["thread_id"] == "<msg-123@acme.com>"

def test_parse_html_email():
    from services.email.email_parser import EmailParser
    parser = EmailParser()
    msg = EmailMessage()
    msg["From"] = "john@acme.com"
    msg["To"] = "sales@supplier.com"
    msg["Subject"] = "Order"
    msg.set_content("plaintext fallback")
    msg.add_alternative("<html><body><p>Need <b>500kg</b> Polyox</p></body></html>", subtype="html")
    result = parser.parse(msg)
    assert "500kg" in result["body"]

def test_parse_attachment():
    from services.email.email_parser import EmailParser
    parser = EmailParser()
    msg = _make_email(attachments=[
        ("PO-2024.xlsx", b"fake-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ])
    result = parser.parse(msg)
    assert len(result["attachments"]) == 1
    assert result["attachments"][0]["name"] == "PO-2024.xlsx"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_email_parser.py -v`
Expected: FAIL

**Step 3: Implement EmailParser**

Create `services/email/email_parser.py` with:
- `parse(email_message)` — returns dict with from_address, to_address, subject, body (HTML→text via BeautifulSoup), thread_id (from In-Reply-To), attachments list, raw_payload, channel="email"
- `_extract_body(msg)` — prefers plain text, falls back to HTML→text conversion
- `_extract_attachments(msg)` — returns list of {name, content_bytes, mime_type, size}
- Create `services/email/__init__.py`

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_email_parser.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add services/email/ tests/test_email_parser.py
git commit -m "feat: add EmailParser for header extraction, HTML→text, thread detection, attachments"
```

---

### Task 10: IMAP Email Ingestion Service

**Files:**
- Create: `services/email/email_ingestion.py`
- Test: `tests/test_email_ingestion.py`

**Step 1: Write the failing test**

```python
# tests/test_email_ingestion.py
"""Test IMAP email polling and message storage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_process_new_email_stores_in_db():
    from services.email.email_ingestion import EmailIngestionService

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "msg-1", "status": "new"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_account_svc = MagicMock()
    mock_account_svc.lookup_by_email = AsyncMock(return_value={"id": "ca-1", "company": "Acme"})

    svc = EmailIngestionService(
        db_manager=mock_db,
        customer_account_service=mock_account_svc,
    )

    parsed_email = {
        "from_address": "john@acme.com",
        "to_address": "sales@supplier.com",
        "subject": "Need quote",
        "body": "Quote for 500kg Polyox",
        "channel": "email",
        "thread_id": None,
        "attachments": [],
        "raw_payload": {},
    }

    result = await svc.ingest_parsed_email(parsed_email)
    assert result["status"] == "new"

@pytest.mark.asyncio
async def test_process_email_links_customer_account():
    from services.email.email_ingestion import EmailIngestionService

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "msg-1", "customer_account_id": "ca-1"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_account_svc = MagicMock()
    mock_account_svc.lookup_by_email = AsyncMock(return_value={"id": "ca-1"})

    svc = EmailIngestionService(db_manager=mock_db, customer_account_service=mock_account_svc)

    result = await svc.ingest_parsed_email({
        "from_address": "john@acme.com", "to_address": "sales@test.com",
        "subject": "test", "body": "test body", "channel": "email",
        "thread_id": None, "attachments": [], "raw_payload": {},
    })
    assert result["customer_account_id"] == "ca-1"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_email_ingestion.py -v`
Expected: FAIL

**Step 3: Implement EmailIngestionService**

Create `services/email/email_ingestion.py` with:
- `ingest_parsed_email(parsed)` — stores in inbound_messages table, looks up customer account, links thread_id
- `poll_imap(host, port, user, password, folder)` — connects via IMAP, fetches unread emails, calls parse + ingest for each
- `save_attachments(message_id, attachments)` — saves attachment files to disk, updates attachments JSONB

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_email_ingestion.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add services/email/email_ingestion.py tests/test_email_ingestion.py
git commit -m "feat: add EmailIngestionService for IMAP polling and message storage"
```

---

### Task 11: Multi-Intent Classifier

**Files:**
- Create: `services/multi_intent_classifier.py`
- Test: `tests/test_multi_intent_classifier.py`

**Step 1: Write the failing test**

```python
# tests/test_multi_intent_classifier.py
"""Test multi-intent classification from email bodies."""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_single_intent_email():
    from services.multi_intent_classifier import MultiIntentClassifier
    from services.ai.models import IntentType

    classifier = MultiIntentClassifier(llm_router=None)
    result = classifier.classify_patterns("Need a quote for 500kg Polyox WSR-301")
    assert any(r.intent == IntentType.REQUEST_QUOTE for r in result.intents)

@pytest.mark.asyncio
async def test_multi_intent_email():
    from services.multi_intent_classifier import MultiIntentClassifier
    from services.ai.models import IntentType

    classifier = MultiIntentClassifier(llm_router=None)
    text = (
        "Hi, can you send me the SDS for Polyox WSR-301? "
        "Also, I need a quote for 500kg. "
        "And what's the status of PO-12345?"
    )
    result = classifier.classify_patterns(text)
    intent_types = {r.intent for r in result.intents}
    assert IntentType.REQUEST_TDS_SDS in intent_types
    assert IntentType.REQUEST_QUOTE in intent_types
    assert IntentType.ORDER_STATUS in intent_types

@pytest.mark.asyncio
async def test_reorder_intent():
    from services.multi_intent_classifier import MultiIntentClassifier
    from services.ai.models import IntentType

    classifier = MultiIntentClassifier(llm_router=None)
    result = classifier.classify_patterns("Same as last order please, PO-11234")
    assert any(r.intent == IntentType.REORDER for r in result.intents)

@pytest.mark.asyncio
async def test_sample_request_intent():
    from services.multi_intent_classifier import MultiIntentClassifier
    from services.ai.models import IntentType

    classifier = MultiIntentClassifier(llm_router=None)
    result = classifier.classify_patterns("Can I get a sample of METHOCEL K4M?")
    assert any(r.intent == IntentType.SAMPLE_REQUEST for r in result.intents)

@pytest.mark.asyncio
async def test_entity_extraction():
    from services.multi_intent_classifier import MultiIntentClassifier

    classifier = MultiIntentClassifier(llm_router=None)
    result = classifier.classify_patterns("Quote for 500kg Polyox WSR-301, CAS 25322-68-3, for PO-12345")
    assert "WSR-301" in str(result.entities.part_numbers) or "Polyox" in str(result.entities.part_numbers)

@pytest.mark.asyncio
async def test_llm_fallback_for_ambiguous():
    from services.multi_intent_classifier import MultiIntentClassifier
    from services.ai.models import IntentType, MultiIntentResult, IntentResult, EntityResult

    mock_llm = MagicMock()
    mock_llm.classify_multi_intent = AsyncMock(return_value=MultiIntentResult(
        intents=[IntentResult(intent=IntentType.TECHNICAL_SUPPORT, confidence=0.85, text_span="what viscosity")],
        entities=EntityResult(),
    ))
    classifier = MultiIntentClassifier(llm_router=mock_llm)
    # Ambiguous text that patterns can't classify well
    result = await classifier.classify("What viscosity grade works best for 3000 RPM applications?")
    assert any(r.intent == IntentType.TECHNICAL_SUPPORT for r in result.intents)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_multi_intent_classifier.py -v`
Expected: FAIL

**Step 3: Implement MultiIntentClassifier**

Create `services/multi_intent_classifier.py` with:
- `classify_patterns(text)` → `MultiIntentResult` — pattern-based, can detect multiple intents per message
- `classify(text)` → `MultiIntentResult` — patterns first, falls back to LLM for low-confidence
- Pattern groups for all 9 intents (extend existing patterns from intent_classifier.py)
- Entity extraction: regex for PO numbers, CAS numbers, product names, quantities
- Each intent result includes `text_span` showing which part of the email triggered it
- Deduplication: if same intent detected twice, keep highest confidence

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_multi_intent_classifier.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add services/multi_intent_classifier.py tests/test_multi_intent_classifier.py
git commit -m "feat: add MultiIntentClassifier with 9 intents, multi-intent per message, entity extraction"
```

---

### Task 12: Auto-Response Engine

**Files:**
- Create: `services/auto_response_engine.py`
- Test: `tests/test_auto_response_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_auto_response_engine.py
"""Test AI draft response generation per intent type."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ai.models import IntentType, IntentResult, MultiIntentResult, EntityResult

@pytest.mark.asyncio
async def test_draft_tds_sds_response():
    from services.auto_response_engine import AutoResponseEngine

    mock_graph = MagicMock()
    mock_graph.get_tds_properties = AsyncMock(return_value={"flash_point": "N/A", "pdf_url": "/docs/tds.pdf"})
    mock_graph.get_sds_properties = AsyncMock(return_value={"cas_numbers": ["25322-68-3"], "pdf_url": "/docs/sds.pdf"})

    mock_ai = MagicMock()
    mock_ai.generate = AsyncMock(return_value="Please find attached the TDS and SDS for Polyox WSR-301.")

    engine = AutoResponseEngine(graph_service=mock_graph, ai_service=mock_ai, db_manager=MagicMock())

    intents = MultiIntentResult(
        intents=[IntentResult(intent=IntentType.REQUEST_TDS_SDS, confidence=0.98, text_span="send me the SDS")],
        entities=EntityResult(part_numbers=["WSR-301"]),
    )

    draft = await engine.generate_draft(
        body="Please send me the SDS for Polyox WSR-301",
        intents=intents,
        customer_account={"name": "John", "company": "Acme"},
    )
    assert draft["response_text"] is not None
    assert len(draft["attachments"]) >= 1  # TDS or SDS PDF

@pytest.mark.asyncio
async def test_draft_quote_response():
    from services.auto_response_engine import AutoResponseEngine

    mock_graph = MagicMock()
    mock_graph.get_product_pricing = AsyncMock(return_value={"unit_price": 42.50, "uom": "kg"})
    mock_graph.get_product_inventory = AsyncMock(return_value={"qty_on_hand": 2400})

    mock_ai = MagicMock()
    mock_ai.generate = AsyncMock(return_value="Quote for 500kg Polyox at $42.50/kg = $21,250.")

    engine = AutoResponseEngine(graph_service=mock_graph, ai_service=mock_ai, db_manager=MagicMock())

    intents = MultiIntentResult(
        intents=[IntentResult(intent=IntentType.REQUEST_QUOTE, confidence=0.95, text_span="quote for 500kg")],
        entities=EntityResult(part_numbers=["WSR-301"], quantities={"WSR-301": 500}),
    )

    draft = await engine.generate_draft(
        body="I need a quote for 500kg Polyox WSR-301",
        intents=intents,
        customer_account={"name": "John", "pricing_tier": "premium"},
    )
    assert draft["response_text"] is not None
    assert draft["confidence"] > 0.5

@pytest.mark.asyncio
async def test_multi_intent_combined_response():
    from services.auto_response_engine import AutoResponseEngine

    mock_graph = MagicMock()
    mock_graph.get_tds_properties = AsyncMock(return_value={"pdf_url": "/docs/tds.pdf"})
    mock_graph.get_sds_properties = AsyncMock(return_value={"pdf_url": "/docs/sds.pdf"})
    mock_graph.get_product_pricing = AsyncMock(return_value={"unit_price": 42.50})
    mock_graph.get_product_inventory = AsyncMock(return_value={"qty_on_hand": 2400})

    mock_ai = MagicMock()
    mock_ai.generate = AsyncMock(return_value="Here's your quote and SDS attached.")

    engine = AutoResponseEngine(graph_service=mock_graph, ai_service=mock_ai, db_manager=MagicMock())

    intents = MultiIntentResult(
        intents=[
            IntentResult(intent=IntentType.REQUEST_QUOTE, confidence=0.95, text_span="quote"),
            IntentResult(intent=IntentType.REQUEST_TDS_SDS, confidence=0.98, text_span="SDS"),
        ],
        entities=EntityResult(part_numbers=["WSR-301"], quantities={"WSR-301": 500}),
    )

    draft = await engine.generate_draft(
        body="Quote for 500kg and send me the SDS",
        intents=intents,
        customer_account={"name": "John"},
    )
    assert draft["response_text"] is not None
    assert len(draft["attachments"]) >= 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_auto_response_engine.py -v`
Expected: FAIL

**Step 3: Implement AutoResponseEngine**

Create `services/auto_response_engine.py` with:
- `generate_draft(body, intents, customer_account)` → `{response_text, attachments, confidence}`
- Intent handlers: one method per intent type
  - `_handle_request_tds_sds()` — fetch TDS/SDS from graph, attach PDFs
  - `_handle_request_quote()` — look up pricing, check inventory, generate quote
  - `_handle_place_order()` — check inventory, draft order confirmation
  - `_handle_order_status()` — look up order by PO number
  - `_handle_reorder()` — find last order, check current stock/pricing
  - `_handle_technical_support()` — query knowledge graph for technical data
  - `_handle_return_complaint()` — draft RMA initiation
  - `_handle_account_inquiry()` — return account details
  - `_handle_sample_request()` — draft sample response
- For multi-intent: collect context from all handlers, then call Claude to draft a single cohesive response
- Confidence = average of individual intent confidences × product-found factor

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_auto_response_engine.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add services/auto_response_engine.py tests/test_auto_response_engine.py
git commit -m "feat: add AutoResponseEngine with per-intent handlers and multi-intent draft generation"
```

---

## Phase 4: API Routes (Tasks 13–15)

### Task 13: Inbound Messages API Routes

**Files:**
- Create: `routes/inbox.py`
- Test: `tests/test_inbox_routes.py`

**Step 1: Write the failing test**

```python
# tests/test_inbox_routes.py
"""Test inbox API routes: list, get, update status, approve/send."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Reuse the app setup pattern from existing route tests
def _make_test_app():
    from fastapi import FastAPI
    from routes.inbox import router, set_inbox_services
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/inbox")
    return app, set_inbox_services

@pytest.fixture
def client():
    app, set_services = _make_test_app()
    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetch=AsyncMock(return_value=[
            {"id": "msg-1", "from_address": "john@acme.com", "subject": "Quote", "status": "new",
             "intents": '[{"intent": "request_quote", "confidence": 0.95}]',
             "channel": "email", "created_at": "2026-03-05T10:30:00"},
        ]),
        fetchrow=AsyncMock(return_value={
            "id": "msg-1", "from_address": "john@acme.com", "subject": "Quote",
            "body": "Need quote for Polyox", "status": "new",
            "intents": '[{"intent": "request_quote"}]',
            "ai_draft_response": "Here is your quote...",
            "channel": "email", "created_at": "2026-03-05T10:30:00",
        }),
        fetchval=AsyncMock(return_value=1),
        execute=AsyncMock(),
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    set_services(db_manager=mock_db, classifier=MagicMock(), response_engine=MagicMock())
    return TestClient(app)

def test_list_messages(client):
    resp = client.get("/api/v1/inbox/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["messages"]) >= 1

def test_get_message_detail(client):
    resp = client.get("/api/v1/inbox/messages/msg-1")
    assert resp.status_code == 200
    assert resp.json()["from_address"] == "john@acme.com"

def test_approve_message(client):
    resp = client.patch("/api/v1/inbox/messages/msg-1/approve")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_inbox_routes.py -v`
Expected: FAIL

**Step 3: Implement inbox routes**

Create `routes/inbox.py` with:
- `GET /messages` — list inbound messages with filters (status, channel, intent, assigned_to), pagination
- `GET /messages/{id}` — get message detail with AI draft, intents, customer context
- `PATCH /messages/{id}/classify` — trigger re-classification
- `PATCH /messages/{id}/approve` — mark as approved, update status to 'sent'
- `PATCH /messages/{id}/escalate` — assign to human, update status to 'escalated'
- `PATCH /messages/{id}/draft` — update AI draft text (human edits)
- `POST /messages/{id}/feedback` — log classification correction to classification_feedback
- `GET /messages/stats` — dashboard stats (count by status, by intent, avg response time)
- Wire into main.py router registration

**Step 4: Run tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_inbox_routes.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add routes/inbox.py tests/test_inbox_routes.py main.py
git commit -m "feat: add inbox API routes for message list, detail, approve, escalate, feedback"
```

---

### Task 14: Document & Product Knowledge API Routes

**Files:**
- Create: `routes/documents.py`
- Modify: `routes/platform.py` (add product knowledge endpoints)
- Test: `tests/test_document_routes.py`

**Step 1: Write the failing test**

```python
# tests/test_document_routes.py
"""Test document upload, download, and product knowledge routes."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

def _make_test_app():
    from fastapi import FastAPI
    from routes.documents import router, set_document_services
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents")
    return app, set_document_services

@pytest.fixture
def client():
    app, set_services = _make_test_app()
    mock_doc_svc = MagicMock()
    mock_doc_svc.get_documents_for_product = AsyncMock(return_value=[
        {"id": "d1", "doc_type": "TDS", "file_name": "tds.pdf", "is_current": True},
        {"id": "d2", "doc_type": "SDS", "file_name": "sds.pdf", "is_current": True},
    ])
    mock_doc_svc.store_document = AsyncMock(return_value={"id": "d3", "doc_type": "TDS"})
    set_services(document_service=mock_doc_svc)
    return TestClient(app)

def test_list_documents_for_product(client):
    resp = client.get("/api/v1/documents/product/prod-1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

def test_upload_document(client):
    resp = client.post(
        "/api/v1/documents/upload",
        data={"product_id": "prod-1", "doc_type": "TDS"},
        files={"file": ("tds.pdf", b"fake-pdf", "application/pdf")},
    )
    assert resp.status_code == 201
```

**Step 2–5: Standard TDD cycle**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/test_document_routes.py -v`

Implement `routes/documents.py` with:
- `GET /product/{product_id}` — list TDS/SDS for product
- `POST /upload` — upload TDS/SDS PDF, triggers extraction pipeline
- `GET /{doc_id}/download` — download PDF file
- `GET /search` — search documents by keyword, product name, CAS number
- Wire into main.py

**Step 6: Commit**

```bash
git add routes/documents.py tests/test_document_routes.py main.py
git commit -m "feat: add document API routes for TDS/SDS upload, download, search"
```

---

### Task 15: Customer Account API Routes

**Files:**
- Create: `routes/customer_accounts.py`
- Test: `tests/test_customer_account_routes.py`

Standard CRUD routes for customer accounts:
- `GET /customer-accounts` — list with search/filter
- `POST /customer-accounts` — create
- `GET /customer-accounts/{id}` — detail with order history
- `PATCH /customer-accounts/{id}` — update
- `GET /customer-accounts/lookup?email=` — lookup by email

Follow same TDD pattern as Tasks 13–14.

**Commit:**
```bash
git add routes/customer_accounts.py tests/test_customer_account_routes.py main.py
git commit -m "feat: add customer account API routes with email lookup"
```

---

## Phase 5: Frontend — Omnichannel Inbox UI (Tasks 16–20)

### Task 16: Inbox Page — Message List

**Files:**
- Create: `src/pages/Inbox.tsx`
- Modify: `src/lib/api.ts` (add inbox API methods)
- Modify: `src/App.tsx` (add route)

Build the primary inbox page with:
- Left sidebar: filter panel (channel checkboxes, status radio, intent checkboxes, assigned filter)
- Center: message list with cards showing from, subject, intent badges (color-coded), timestamp, status badge
- Use TanStack React Query for data fetching
- Paginated with infinite scroll or page numbers
- Sort by newest first
- Real-time polling every 10s via React Query `refetchInterval`

**API methods to add to `src/lib/api.ts`:**
```typescript
getInboxMessages(filters?: InboxFilters): Promise<InboxListResponse>
getInboxMessage(id: string): Promise<InboxMessage>
approveMessage(id: string): Promise<void>
escalateMessage(id: string): Promise<void>
updateDraft(id: string, draft: string): Promise<void>
submitFeedback(id: string, feedback: ClassificationFeedback): Promise<void>
getInboxStats(): Promise<InboxStats>
```

**Commit:**
```bash
git add src/pages/Inbox.tsx src/lib/api.ts src/App.tsx
git commit -m "feat: add Inbox page with message list, filters, intent badges"
```

---

### Task 17: Message Detail View

**Files:**
- Create: `src/pages/MessageDetail.tsx`
- Create: `src/components/inbox/IntentBadge.tsx`
- Create: `src/components/inbox/AIDraftEditor.tsx`

Build the message detail view with:
- Header: from, subject, timestamp, customer account link
- Original message content (full email body)
- Detected intents section: list of intent badges with confidence bars and text spans
- AI Draft Response: editable textarea with the AI-generated draft
- Attachments: list of TDS/SDS PDFs with download links
- Customer context sidebar: account info, recent orders, pricing tier
- Action bar: Approve & Send, Edit Draft, Escalate, Dismiss buttons
- Classification feedback: if human corrects intent, show dropdown to select correct intent

**Commit:**
```bash
git add src/pages/MessageDetail.tsx src/components/inbox/
git commit -m "feat: add MessageDetail page with AI draft editor, intent badges, customer context"
```

---

### Task 18: Product Knowledge Base Page

**Files:**
- Create: `src/pages/KnowledgeBase.tsx`
- Create: `src/components/products/TDSSDSViewer.tsx`

Build the product knowledge base page with:
- Search bar: search by product name, SKU, CAS number
- Filter sidebar: industry (18 checkboxes), manufacturer dropdown, in-stock toggle
- Product cards: name, manufacturer, CAS, industries served, TDS/SDS availability icons
- Product detail (expandable or separate page):
  - Key properties from TDS (appearance, density, flash point, viscosity, pH)
  - Safety info from SDS (GHS classification, hazard statements, PPE)
  - Pricing: list price, tiers
  - Inventory: stock by warehouse
  - Documents: TDS/SDS with View/Download buttons
- TDSSDSViewer component: renders extracted fields in a clean card layout

**Commit:**
```bash
git add src/pages/KnowledgeBase.tsx src/components/products/
git commit -m "feat: add KnowledgeBase page with product search, TDS/SDS viewer, industry filters"
```

---

### Task 19: Operations Impact Dashboard

**Files:**
- Modify: `src/pages/Dashboard.tsx` (overhaul for ROI metrics)

Replace the existing buyer-focused dashboard with the ROI-focused operations dashboard:
- Top row KPI cards: Messages Handled, Avg Response Time (+ % improvement), Hours Saved (~FTE), AI Accuracy Rate
- Second row: Orders Auto-Generated (count + $), TDS/SDS Sent Automatically
- Charts (Recharts):
  - Intent distribution pie chart
  - Response time trend line chart (showing improvement over time)
  - Volume by channel bar chart (email vs web vs fax)
- Bottom section: Cost savings projection table
- All data from `GET /api/v1/inbox/messages/stats` endpoint

**Commit:**
```bash
git add src/pages/Dashboard.tsx
git commit -m "feat: overhaul Dashboard to ROI-focused operations impact metrics"
```

---

### Task 20: Navigation & Layout Updates

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`
- Modify: `src/App.tsx`

Update navigation sidebar for supplier-sales focus:
- Primary: Inbox (with unread count badge), Dashboard
- Products: Knowledge Base, Documents
- Operations: Orders, Quotes, Customers, Inventory
- Settings: Email Config, Team, Admin Debug

Remove or deprioritize buyer-focused items (Sourcing Chat, RFQ, Procurement).

**Commit:**
```bash
git add src/components/layout/Sidebar.tsx src/App.tsx
git commit -m "feat: update navigation for supplier-sales focus with Inbox as primary"
```

---

## Phase 6: Integration & Pipeline Wiring (Tasks 21–23)

### Task 21: Wire Email Pipeline End-to-End

**Files:**
- Modify: `main.py` (add email ingestion service initialization, background polling task)

Wire in main.py lifespan:
1. Initialize EmailParser, EmailIngestionService, MultiIntentClassifier, AutoResponseEngine
2. Start background IMAP polling task (APScheduler, every 30 seconds)
3. Pipeline: poll → parse → ingest → classify → generate draft → store
4. Add email config to Settings class (IMAP host, port, user, password, folder)

**Commit:**
```bash
git add main.py
git commit -m "feat: wire email ingestion pipeline end-to-end with IMAP background polling"
```

---

### Task 22: Wire Document Service & Graph Service

**Files:**
- Modify: `main.py` (initialize DocumentService, TDSSDSGraphService)

Wire:
1. DocumentService initialized with db_manager
2. TDSSDSGraphService initialized with neo4j_client
3. Document routes wired with set_document_services()
4. Seed data pipeline available as admin endpoint (POST /api/v1/admin/seed-chempoint)

**Commit:**
```bash
git add main.py
git commit -m "feat: wire DocumentService and TDSSDSGraphService into app lifespan"
```

---

### Task 23: Classification Feedback Loop

**Files:**
- Create: `services/classification_feedback_service.py`
- Test: `tests/test_classification_feedback.py`

Implement:
- `log_feedback(message_id, ai_intent, human_intent, is_correct)` — INSERT into classification_feedback
- `get_few_shot_examples(intent_type, limit=5)` — SELECT recent correct examples for few-shot prompting
- `get_accuracy_stats()` — compute overall and per-intent accuracy rates
- Wire into MultiIntentClassifier: before LLM call, prepend few-shot examples from feedback

**Commit:**
```bash
git add services/classification_feedback_service.py tests/test_classification_feedback.py
git commit -m "feat: add classification feedback service for trainable intent classifier"
```

---

## Phase 7: Testing & Polish (Tasks 24–25)

### Task 24: Integration Tests

**Files:**
- Create: `tests/test_email_pipeline_integration.py`

Test the full pipeline end-to-end with mocks:
1. Raw email string → EmailParser → parsed dict
2. Parsed dict → EmailIngestionService → stored in DB
3. Stored message → MultiIntentClassifier → intents detected
4. Intents → AutoResponseEngine → draft generated
5. Verify draft references correct TDS/SDS documents

### Task 25: Run Full Test Suite & Fix Regressions

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && .venv/bin/python -m pytest tests/ -v --tb=short`

Fix any regressions in existing 227 tests caused by:
- IntentType enum changes (Task 3) — update test fixtures
- Schema changes (Task 1) — ensure backward compatibility
- Model changes — update imports

**Final commit:**
```bash
git add -A
git commit -m "test: add integration tests and fix regressions from supplier-sales pivot"
```

---

## Execution Order & Dependencies

```
Phase 1 (Data): Tasks 1→2→3→4→5 (sequential, each builds on previous)
Phase 2 (Scraper): Tasks 6→7→8 (sequential, scraper feeds graph builder)
Phase 3 (Email): Tasks 9→10→11→12 (sequential, parser→ingestion→classifier→response)
Phase 4 (API): Tasks 13,14,15 (parallel — independent route files)
Phase 5 (Frontend): Tasks 16→17, 18, 19, 20 (16→17 sequential, rest parallel)
Phase 6 (Wiring): Tasks 21→22→23 (sequential)
Phase 7 (Testing): Tasks 24→25 (sequential)
```

**Estimated total: 25 tasks across 7 phases.**
