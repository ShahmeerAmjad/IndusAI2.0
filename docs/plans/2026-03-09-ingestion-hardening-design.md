# Ingestion Pipeline Hardening & Scale — Design

**Date:** 2026-03-09
**Status:** Approved
**Goal:** Fix all demo blockers and bugs, scale to 250+ real Chempoint products, replace canvas graph with react-force-graph-2d, add CSV/Excel import, make scraper generic for any distributor site.

## Architecture

```
INGESTION SOURCES
├── Web Scraper (Firecrawl/generic) ─── Chempoint + any distributor site
├── CSV/Excel Import ───────────────── Bulk upload from customer ERP exports
└── (Future) REST API ─────────────── Direct ERP integration
         │
    EXTRACTION LAYER
    ├── Product metadata (name, manufacturer, CAS#, industry, product line)
    ├── PDF detection (download vs request-only)
    ├── PDF download + pdfplumber + Claude confidence extraction
    └── Markdown stripping, text truncation safety
         │
    KNOWLEDGE GRAPH (Neo4j)
    ├── Part, Manufacturer, ProductLine, Industry, TDS, SDS nodes
    ├── Cross-relationships (SERVES_INDUSTRY, MANUFACTURED_BY, etc.)
    └── Source tracking (which ingestion source added each node)
         │
    FRONTEND
    ├── Products tab (search from KB, not legacy graph)
    ├── Graph Explorer (react-force-graph-2d, scales to 1000+ nodes)
    ├── Ingestion tab (web scrape + CSV/Excel upload + progress)
    └── Cancel/status controls
```

## 1. Generic Scraper Architecture

Replace the hardcoded `ChempointScraper` with a two-layer design:

**Layer 1: Site Navigator** — handles crawling patterns (pagination, hierarchy traversal)
**Layer 2: Claude Extractor** — takes raw HTML and extracts structured data (works on any site)

```
GenericProductScraper
├── navigate(url, strategy="auto")
│   ├── Firecrawl scrapes the page → gets markdown/HTML
│   ├── Claude classifies page type: "industry_list", "product_list",
│   │   "product_detail", "manufacturer_list"
│   ├── Claude extracts: links to follow, pagination next URLs, product data
│   └── Recursively follows links based on page type
│
├── extract_product(html) → {name, manufacturer, description, cas_number,
│                             product_line, industries, tds_url, sds_url,
│                             tds_downloadable: bool, sds_downloadable: bool}
│   └── Claude Haiku — single prompt, works on any distributor site's HTML
│
├── download_pdf(url) → bytes  (only if downloadable=true)
│
└── Chempoint convenience layer (optional)
    ├── Known industry URLs as presets
    ├── Known manufacturer index URL
    └── Pagination pattern hint (speeds up navigation)
```

### TDS/SDS Detection

Chempoint has two patterns:
- **Direct download** (download icon + PDF link) — 3M, etc. → `tds_downloadable: true`
- **Request form** (request icon + contact form) — Aculon, etc. → `tds_downloadable: false`, `tds_url: null`

Products with request-only TDS/SDS still get created in the graph — just without document nodes until PDFs are uploaded via CSV/Excel.

### Pagination

Claude detects pagination from HTML (sees "1, 2, Next >" pattern), returns `next_page_url` alongside extracted products. Scraper follows until no more pages or `max_products` cap hit.

### Cost Control

- `max_products` enforced globally across all industries
- `max_pages_per_industry` to cap deep crawls
- Haiku for all navigation/extraction (~$0.001/page), Sonnet only for PDF field parsing (~$0.005/PDF)
- **Context compaction** on extraction loop (see §5 below) — prevents linear token growth across 250+ products
- Estimated total for 250+ products: **~$3** (down from ~$5 with compaction savings)

### Chempoint Crawl Strategy

Two entry points matching Chempoint's browse UI:
1. **By Industry**: Industries index → Industry page → Product list (paginated) → Product detail
2. **By Manufacturer**: Manufacturer index → Manufacturer page → Product Lines → Products

Both produce the same product dicts fed into the same pipeline.

## 2. CSV/Excel Import

### Expected Columns (flexible — Claude maps non-standard headers)

| Required | Optional |
|----------|----------|
| `name` or `product_name` | `cas_number` |
| `manufacturer` | `product_line` |
| | `industry` (comma-separated) |
| | `description` |
| | `tds_url` (direct PDF link) |
| | `sds_url` (direct PDF link) |
| | `tds_file` (filename matching uploaded PDF) |
| | `sds_file` (filename matching uploaded PDF) |

### Flow

1. User uploads CSV/Excel file via the Ingestion tab (new "Import" mode)
2. Backend parses the file, Claude Haiku maps non-standard column names
3. Dry-run preview: shows first 5 rows mapped, user confirms
4. Import runs: creates products in PG + Neo4j, downloads any TDS/SDS from provided URLs
5. Progress via same WebSocket system as web scraping
6. Optional: user uploads ZIP of TDS/SDS PDFs alongside — filenames matched to columns

### Integration

Reuses `ChempointSeedPipeline._process_product` and `_process_document` — the import just produces the same product dict that the scraper produces. One pipeline, multiple input sources.

## 3. Graph Visualization (react-force-graph-2d)

Replace custom canvas renderer with `react-force-graph-2d`.

### Node Types & Styling

| Type | Color | Size | Notes |
|------|-------|------|-------|
| Product | Blue (#1e3a8a) | Large | Main entities |
| Manufacturer | Green (#059669) | Medium | Clustered by products |
| ProductLine | Teal (#0d9488) | Medium | Grouped under manufacturers |
| Industry | Orange (#f59e0b) | Medium | Hub nodes connecting many products |
| TDS | Purple (#7c3aed) | Small | Leaf nodes off products |
| SDS | Red (#dc2626) | Small | Leaf nodes off products |

### Interactions

- Hover: tooltip with node name + type
- Click: properties panel (works on both circle and label — fixes hitbox bug)
- Zoom/pan: built into library
- Double-click: focus on node and its neighbors

### Scaling to 1000+ Nodes

- Industry/Manufacturer filter dropdowns (all industries included)
- "Depth" control: products only, products + docs, or full graph
- Node size by connection count
- Auto-hide labels at dense zoom levels
- Container resize handled automatically by the library

### Data Source

Same `/graph-viz` API endpoint with fixes: results materialized as list, all industries in dropdown.

## 4. Bug Fixes & Hardening

### LLM Safety
- Strip markdown fences from `_call_llm` responses before `json.loads`
- Truncate text to 8000 chars in old `extract_tds/sds_fields` methods

### Pipeline Robustness
- Guard empty product names (`_make_sku("")`) — skip with error event
- Broadcast error event on batch job failure (match single-job behavior)
- Enforce `max_products` as global cap across all industries
- Add cancel endpoint + cancellation flag checked between products
- Wire `set_ingestion_pipeline` only when `ChempointScraper` available
- Track upsert vs insert — "products_created" vs "products_updated"

### Search & Products
- Switch frontend from `/graph/parts/search/fulltext` to `/knowledge-base/products?search=...`
- Add `total` count to `KnowledgeBaseService.list_products`
- Fix `get_product` PG document lookup (wrong key)

### Document Upload
- Make `upload_document` route actually call `DocumentService.store_document`

### Graph Viz Backend
- Materialize Neo4j results as list before double-iteration
- All industries in filter dropdown

### Test Coverage (new tests)
- WebSocket endpoint (`ws/{job_id}`) + broadcast behavior
- `seed_from_industries` batch orchestration
- `search_documents` and `get_document_by_id`
- CSV/Excel import parsing + column mapping
- Generic scraper page classification
- Cancel job flow
- Graph viz manufacturer filter

## 5. Context Compaction (Cost & Performance Optimization)

Based on [Anthropic's automatic context compaction cookbook](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction). Core insight: long-running agentic loops that process items sequentially accumulate context linearly — compaction resets this with a summary, achieving **~58% token reduction**.

### Where It Applies

#### A. Ingestion Pipeline — Generic Scraper Extraction Loop (Slice B)

The scraper processes 250+ products sequentially. Each product involves:
1. Firecrawl page fetch → Claude page classification
2. Claude product extraction (name, manufacturer, CAS#, etc.)
3. PDF download → Claude TDS/SDS field extraction with confidence scores

Without compaction, product 250 carries the full context of products 1–249. Products are independent — no reason to keep earlier extraction results in context.

```python
# In GenericProductScraper or seed pipeline batch processing
compaction_control={
    "enabled": True,
    "context_token_threshold": 5000,   # Products are independent, compact early
    "model": "claude-haiku-4-5",       # Cheap summarization
    "summary_prompt": """Summarize ingestion progress:
1. Products processed (count, last few names)
2. Success/failure counts
3. Current industry being scraped
4. Any patterns or errors to carry forward
Wrap in <summary></summary> tags."""
}
```

**What summaries preserve:** product count, error patterns, current industry, pipeline state.
**What's safe to drop:** individual product HTML, extraction JSON, PDF text — all already persisted to PG/Neo4j.

#### B. Batch TDS/SDS Extraction (Slice C)

When processing multiple PDFs (from CSV/Excel import or scraper batch), each PDF extraction is independent. The confidence-scored extraction (`extract_tds_fields_with_confidence`, `extract_sds_fields_with_confidence`) can use compaction when called in a batch loop.

```python
# In DocumentService batch extraction or CSV import pipeline
compaction_control={
    "enabled": True,
    "context_token_threshold": 10000,  # PDFs are larger, slightly higher threshold
    "model": "claude-haiku-4-5",
    "summary_prompt": """Summarize document extraction progress:
1. Documents processed (count, types)
2. Fields extracted successfully vs failed
3. Average confidence scores
4. Any extraction issues to watch for
Wrap in <summary></summary> tags."""
}
```

#### C. Email Batch Processing — Auto-Response Engine

The `AutoResponseEngine` processes emails from the inbox queue. In production, this runs against 2M emails/year (Chempoint's stated volume). When processing a batch of emails sequentially (e.g., overnight queue drain or bulk re-classification), each email's classification + context gathering + draft generation accumulates in context.

**Current flow per email:**
1. Multi-intent classification (Claude call)
2. Per-intent context gathering (graph/DB lookups)
3. LLM draft generation (Claude call with full context block)

**With compaction:**

```python
# In a new batch_process_inbox() method on AutoResponseEngine
compaction_control={
    "enabled": True,
    "context_token_threshold": 8000,   # Emails vary in size, moderate threshold
    "model": "claude-haiku-4-5",
    "summary_prompt": """Summarize email processing progress:
1. Emails processed (count, by intent type)
2. Drafts generated vs failed
3. Average confidence scores
4. Common intent patterns seen
5. Any customer accounts with multiple emails
Wrap in <summary></summary> tags."""
}
```

**What summaries preserve:** email counts, intent distribution, confidence trends, error patterns.
**What's safe to drop:** individual email bodies, classification details, draft text — all persisted to PG inbox table.

### Implementation Approach

Use `client.beta.messages.tool_runner()` with `compaction_control` param (requires `anthropic` SDK >= 0.74.1). For our existing code that uses `llm_router.chat()`, add a `compaction_control` passthrough parameter:

```python
# services/ai/llm_router.py — add compaction support
async def chat_with_compaction(self, messages, system, task, max_tokens,
                                compaction_control=None, **kwargs):
    """Chat with automatic context compaction for batch processing."""
    if compaction_control:
        runner = self._client.beta.messages.tool_runner(
            model=self._resolve_model(task),
            max_tokens=max_tokens,
            messages=messages,
            compaction_control=compaction_control,
        )
        results = []
        for message in runner:
            results.append(message)
        return results[-1]  # Return final response
    else:
        return await self.chat(messages=messages, system=system,
                               task=task, max_tokens=max_tokens, **kwargs)
```

### Expected Impact

| Workflow | Without Compaction | With Compaction | Savings |
|----------|-------------------|-----------------|---------|
| 250 products scraped | ~$5.00 | ~$3.00 | ~40% |
| 100 TDS/SDS PDFs | ~$0.50 | ~$0.25 | ~50% |
| 500 emails batch | ~$2.50 | ~$1.00 | ~60% |

### SDK Requirement

```
anthropic>=0.74.1  # Required for compaction_control parameter
```

Add to `requirements.txt`. Current SDK version needs verification.

## 6. Slice Organization

| Slice | What | Files |
|-------|------|-------|
| **A: Search & Products** | Fix wrong endpoint, add total count, fix PG lookup | Frontend + KB service |
| **B: Ingestion Pipeline** | Generic scraper, cancel, max_products, broadcast fix, SKU guard, wiring, **compaction on extraction loop** | Scraper + pipeline + routes + main.py + llm_router |
| **C: Document Service** | Markdown stripping, truncation, upload route, CSV/Excel import, **compaction on batch PDF extraction** | Document service + routes + new import service |
| **D: Graph Visualization** | react-force-graph-2d, all interactions, filter fixes | Frontend components |
| **E: Test Hardening** | All identified test gaps | Test files |
| **F: Email Batch Processing** | **Compaction on batch email processing**, `batch_process_inbox()` method on AutoResponseEngine | Auto-response engine + llm_router |

## 7. Success Criteria

- [ ] 250+ real Chempoint products in Neo4j across 5+ industries
- [ ] Graph explorer renders 1000+ nodes smoothly with zoom/pan/click
- [ ] Products tab search returns Chempoint products (not legacy MRO)
- [ ] CSV/Excel upload creates products + downloads linked TDS/SDS PDFs
- [ ] TDS/SDS direct downloads extracted with confidence scores
- [ ] Request-only TDS/SDS gracefully skipped (product still created)
- [ ] Cancel button stops running ingestion jobs
- [ ] All identified bugs fixed
- [ ] Context compaction enabled on ingestion, PDF extraction, and email batch loops
- [ ] `anthropic` SDK >= 0.74.1 in requirements.txt
- [ ] Batch email processing method with compaction on AutoResponseEngine
- [ ] 490+ tests passing (current 468 + ~25 new)
- [ ] Frontend builds cleanly
