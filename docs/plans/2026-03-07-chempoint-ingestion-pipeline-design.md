# Live Chempoint Ingestion Pipeline with Knowledge Graph Visualization

**Date:** 2026-03-07
**Status:** Approved
**Goal:** Build a live demo pipeline that scrapes Chempoint, downloads TDS/SDS PDFs, extracts structured data via Claude OCR, and populates the Neo4j knowledge graph — with real-time visual progress and graph visualization.

## Architecture

```
TRIGGER (CLI or Admin UI button)
    │
CHEMPOINT SCRAPER (Firecrawl API)
    ├── Crawl industry pages → extract product URLs
    ├── Crawl product pages → extract metadata (name, CAS#, manufacturer, industries)
    └── Download TDS/SDS PDF links
    │
PDF EXTRACTION PIPELINE (Claude Vision/pdfplumber)
    ├── Extract text from PDF
    ├── Call Claude to parse structured fields + confidence scores
    └── Store in PostgreSQL `documents` table
    │
KNOWLEDGE GRAPH BUILDER (Neo4j)
    ├── Create/merge Product, Manufacturer, ProductLine, Industry nodes
    ├── Create TDS/SDS nodes with extracted properties
    ├── Link relationships (HAS_TDS, HAS_SDS, SERVES_INDUSTRY, MANUFACTURED_BY)
    └── Generate Voyage AI embeddings
    │
REAL-TIME PROGRESS (WebSocket)
    └── Push updates to frontend: { phase, product_name, progress%, status }
```

## Components

### 1. Backend: Ingestion Pipeline with Progress Events

- `POST /api/v1/admin/seed-chempoint` — starts pipeline, returns job ID
- `POST /api/v1/admin/ingest-product` — single product URL, live ingestion
- `WebSocket /ws/ingestion/{job_id}` — streams progress events to frontend
- Progress stages: `discovering` → `scraping` → `downloading_pdf` → `extracting` → `building_graph` → `done`
- Each event includes: stage, product name, current/total count, extracted field preview

### 2. PDF Extraction with Confidence Scores

- pdfplumber for text extraction (fast, free)
- Claude Sonnet for structured field parsing with confidence per field
- Full TDS fields: appearance, density, flash_point, viscosity, pH, boiling_point, melting_point, solubility, shelf_life, storage_conditions, recommended_uses
- Full SDS fields: ghs_classification, hazard_statements, precautionary_statements, cas_numbers, un_number, first_aid, ppe_requirements, fire_fighting, environmental_hazards, transport_info
- Each field returns `{value, confidence: 0.0-1.0}`
- Low confidence (<0.7) flagged in UI with amber indicator

### 3. Frontend: Knowledge Base Ingestion Panel

- "Seed from Chempoint" button with industry selector (choose which industries to scrape)
- Live progress dashboard showing:
  - Overall progress bar (X of Y products)
  - Current product being processed with stage indicator
  - Rolling log of completed products with field counts
  - Error/skip count
- Single product URL input for live demo ingestion
- After completion: auto-refresh Knowledge Base product list

### 4. Frontend: Neo4j Graph Visualization (Neovis.js)

- New tab/section in Knowledge Base page: "Graph Explorer"
- Renders interactive 2D graph from Neo4j
- Node types color-coded: Products (blue), Manufacturers (green), Industries (orange), TDS (purple), SDS (red)
- Click node to see properties panel
- Zoom/pan, relationship labels on edges
- Pre-built Cypher queries: "Show all products for [Industry]", "Show product + TDS/SDS + Manufacturer"
- Backend endpoint: `GET /api/v1/graph/visualize?query=...` returns nodes + edges JSON

### 5. CLI Script

- `python -m scripts.seed_chempoint --industries "Adhesives,Coatings,Pharma" --max-products 50`
- Rich terminal output with progress bars (using `rich` library)
- Outputs summary: products created, documents extracted, graph nodes built

## Data Flow Example (Single Product)

```
1. Scrape chempoint.com/products/polyox-wsr-301
   → {name: "POLYOX WSR-301", manufacturer: "Dow", CAS: "25322-68-3",
      industries: ["Adhesives", "Pharma"], tds_url: "...", sds_url: "..."}

2. Download TDS PDF → pdfplumber → raw text
   → Claude: "Extract TDS fields with confidence"
   → {appearance: {value: "White powder", confidence: 0.95},
      density: {value: "1.21 g/cm³", confidence: 0.92},
      flash_point: {value: "N/A", confidence: 0.88}, ...}

3. Download SDS PDF → same pipeline
   → {ghs_classification: {value: "Not classified", confidence: 0.97},
      cas_numbers: {value: ["25322-68-3"], confidence: 0.99}, ...}

4. Neo4j: MERGE (p:Product {sku: "POLYOX-WSR-301"})
          MERGE (m:Manufacturer {name: "Dow"})
          MERGE (p)-[:MANUFACTURED_BY]->(m)
          MERGE (tds:TechnicalDataSheet {...})
          MERGE (p)-[:HAS_TDS]->(tds)
          ... (Industry links, SDS, ProductLine)

5. WebSocket event → frontend updates progress bar
```

## Existing Code to Extend

| Module | What exists | What to add |
|--------|-------------|-------------|
| `services/ingestion/chempoint_scraper.py` | Scrape product/industry pages via Firecrawl + LLM extraction | Progress callback, batch crawl orchestration |
| `services/ingestion/seed_chempoint.py` | End-to-end pipeline (scrape → extract → graph) | WebSocket progress events, confidence scores |
| `services/document_service.py` | Store docs, extract TDS/SDS fields via Claude | Confidence scores per field, pdfplumber integration |
| `services/graph/tds_sds_service.py` | Create TDS/SDS/Industry nodes in Neo4j | Bulk operations, visualization query endpoint |
| `routes/knowledge_base.py` | Product search, doc upload, crawl trigger | WebSocket progress, graph viz endpoint |
| `src/pages/KnowledgeBase.tsx` | Product list, search, filters | Ingestion panel, progress bars, Neovis.js graph |

## Dependencies to Add

- `pdfplumber` — PDF text extraction (Python)
- `rich` — CLI progress bars (Python)
- `neovis.js` — Neo4j graph visualization (npm)
- `websockets` already available via FastAPI

## Demo Script

**Pre-demo:** Run CLI to seed ~50 products across 5 industries (~10 min)

**Live demo:**
1. Open Knowledge Base — show 50+ products already loaded
2. Click "Graph Explorer" — show the knowledge graph with interconnected nodes
3. Click a product — show extracted TDS/SDS fields with confidence scores
4. Paste a new product URL → click "Ingest" → watch live progress
5. Graph auto-updates with new node appearing
6. Switch to Inbox — show how AI drafts reference this knowledge graph data

## Success Criteria

- [ ] 50+ real products scraped from Chempoint with TDS/SDS data
- [ ] Live progress visible in both CLI and web UI
- [ ] Extracted fields show confidence scores, low-confidence flagged
- [ ] Neo4j graph renders interactively with color-coded nodes
- [ ] Single-product live ingestion completes in <30 seconds
- [ ] Knowledge Base page shows all ingested products with search/filter
