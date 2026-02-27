# IndusAI 3.0 — Knowledge Graph-Powered MRO Intelligence Platform

**Date:** 2026-02-23
**Status:** Approved
**Authors:** Shahmeer + Claude

---

## 1. Vision

IndusAI 3.0 merges v1's AI depth (vector search, part parsing, multi-LLM) with v2's operational breadth (O2C, P2P, invoicing, RMA, workflows) and adds a **Neo4j knowledge graph** as the core intelligence layer. The knowledge graph transforms a commodity chatbot into an MRO reasoning engine that gets smarter with every interaction.

**Target:** Tiered B2B SaaS — SMBs for fast sales cycles, architected for enterprise scale.

---

## 2. Why Knowledge Graph Over RAG Alone

Traditional RAG (chunk → embed → retrieve) fails for MRO because:

1. **Cross-references are relational, not semantic.** Embeddings cannot reliably map SKF 6205-2RS → NSK 6205DDU. A graph edge does this deterministically.
2. **Spec matching requires precision, not similarity.** A 25mm bore bearing cannot substitute for 25.4mm. Graph queries enforce exact constraints.
3. **Multi-hop reasoning is structurally impossible.** "Replace all bearings in motor X" requires: motor → BOM → bearings → alternatives → inventory → pricing. RAG retrieves flat chunks; graphs traverse chains.
4. **Large catalogs degrade RAG precision.** At 100K+ SKUs, "almost right" results overwhelm correct ones. Graphs maintain precision at any scale.

**Benchmark evidence:** GraphRAG outperforms vector RAG 3.4x overall on enterprise queries (FalkorDB/Diffbot benchmark). Accuracy drops to ~0% for multi-entity queries without graph support.

---

## 3. Knowledge Graph Ontology

### Node Types

| Node | Key Properties | Purpose |
|------|---------------|---------|
| `Part` | sku, name, description, UOM, weight, hazmat | Core product entity |
| `Manufacturer` | name, country, website | Brand/OEM tracking |
| `Category` | name, parent | Hierarchical taxonomy |
| `Specification` | name, data_type | Spec definition (bore_diameter, load_rating, etc.) |
| `Warehouse` | code, name, location | Stock locations |
| `Supplier` | code, name, rating | Vendor master |
| `Customer` | id, name, company, segment | Customer intelligence |
| `Assembly` | name, description, model | Composed unit (motor, pump, etc.) |

### Edge Types

| Edge | From → To | Properties | Purpose |
|------|-----------|------------|---------|
| `EQUIVALENT_TO` | Part → Part | confidence, source, verified | Cross-manufacturer equivalencies |
| `REPLACES` | Part → Part | effective_date | Supersession tracking |
| `REPLACED_BY` | Part → Part | effective_date | Reverse supersession |
| `COMPATIBLE_WITH` | Part → Part | context (housing, shaft, seal) | Fitment/compatibility |
| `ALTERNATIVE_TO` | Part → Part | spec_match_pct, price_diff | Near-equivalent options |
| `COMPONENT_OF` | Part → Assembly | position, quantity | BOM relationships |
| `BELONGS_TO` | Part → Category | — | Taxonomy classification |
| `SUBCATEGORY_OF` | Category → Category | — | Category hierarchy |
| `MANUFACTURED_BY` | Part → Manufacturer | — | Brand association |
| `HAS_SPEC` | Part → Specification | value, unit | Dimensional/performance specs |
| `SUPPLIES` | Supplier → Part | price, MOQ, lead_time | Procurement intelligence |
| `STOCKED_IN` | Part → Warehouse | qty_on_hand, bin_location | Inventory (eventual consistency) |
| `PURCHASED` | Customer → Part | frequency, last_date | Purchase history |
| `PREFERS_BRAND` | Customer → Manufacturer | — | Brand preferences |

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  React Frontend (v2 enhanced)               │
│  Dashboard │ Products │ Orders │ Inventory │ Chat │ Graph   │
│  + Graph Explorer │ Catalog Import │ Cross-Ref Manager      │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Query Router / Orchestrator              │   │
│  │  Intent Classifier → Entity Extractor → Part Parser  │   │
│  └──────────┬──────────────┬──────────────┬────────────┘   │
│             │              │              │                  │
│  ┌──────────▼───┐  ┌──────▼──────┐  ┌───▼────────────┐   │
│  │ GraphRAG     │  │ Vector      │  │ Relational     │   │
│  │ Engine       │  │ Search      │  │ Query          │   │
│  │ (Neo4j)      │  │ (Neo4j vec) │  │ (PostgreSQL)   │   │
│  └──────────────┘  └─────────────┘  └────────────────┘   │
│         │                 │              │                  │
│  ┌──────▼─────────────────▼──────────────▼──────────┐      │
│  │           Context Merger + Result Ranker          │      │
│  └──────────────────────┬───────────────────────────┘      │
│                         │                                   │
│  ┌──────────────────────▼───────────────────────────┐      │
│  │  LLM Layer (Claude + circuit breaker)              │      │
│  │  Opus │ Sonnet │ Haiku  +  Voyage AI (embeddings) │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  ┌──────────────────┐  ┌─────────────────────────────┐    │
│  │ Platform Services │  │ Catalog Ingestion Pipeline  │    │
│  │ (v2: O2C, P2P,   │  │ Parse → Normalize → Resolve │    │
│  │  Invoice, RMA,    │  │ → Graph Build → Embed       │    │
│  │  Workflow, Price)  │  │                             │    │
│  └──────────────────┘  └─────────────────────────────┘    │
└────────┬──────────────────┬──────────────────┬─────────────┘
         │                  │                  │
    ┌────▼────┐       ┌────▼────┐        ┌────▼────┐
    │  Neo4j  │       │Postgres │        │  Redis  │
    │  Graph  │       │ + pgvec │        │  Cache  │
    │         │       │         │        │         │
    │ Parts   │       │ Orders  │        │ Sessions│
    │ Specs   │       │ Invoices│        │ Rate    │
    │ X-refs  │       │ Invent. │        │ Limits  │
    │ Compat  │       │ Pricing │        │         │
    │ Vectors │       │ Custmrs │        │         │
    └─────────┘       └─────────┘        └─────────┘
```

### Data Ownership

| Data Domain | Owner | Rationale |
|-------------|-------|-----------|
| Part ontology, specs, cross-refs, compatibility, taxonomy | **Neo4j** | Relationship-native, graph traversal |
| Product embeddings (1536-dim vectors) | **Neo4j native vector index** | Co-located with graph for hybrid retrieval |
| Inventory levels, warehouse stock | **PostgreSQL** | Transactional, frequent ACID updates |
| Orders, invoices, payments, RMA, workflows | **PostgreSQL** | Transactional lifecycle management |
| Pricing (lists, tiers, contracts) | **PostgreSQL** | Complex joins, transactional |
| Customer accounts, credit | **PostgreSQL** | Relational data |
| Conversation history | **PostgreSQL** | Append-only, simple queries |

### Sync Strategy

- **Inventory → Graph:** Event-driven (inventory change → publish → update graph property). Eventual consistency < 30s acceptable for chat queries.
- **Parts → PostgreSQL:** Neo4j is source of truth for product intelligence. PostgreSQL mirrors a simplified product table for order/invoice joins.
- **Pricing → Graph:** PostgreSQL is source of truth. Graph stores price ranges for approximate filtering; exact pricing always from PostgreSQL.

---

## 5. GraphRAG Query Pipeline

### 5-Stage Query Flow

**Stage 1: Intent + Entity Extraction**
```
Input: "Do you have an NSK equivalent of SKF 6205-2RS that handles 200°C?"

→ Intent: PART_LOOKUP (confidence: 0.92)
→ Entities: {
    part_number: "6205-2RS",
    manufacturer: "SKF",
    target_manufacturer: "NSK",
    spec_constraint: {max_temperature: 200, unit: "°C"}
  }
```

**Stage 2: Graph Resolution (Neo4j Cypher)**
```cypher
MATCH (p:Part {sku: "6205-2RS"})-[:MANUFACTURED_BY]->(m:Manufacturer {name: "SKF"})
MATCH (p)-[:EQUIVALENT_TO]-(eq:Part)-[:MANUFACTURED_BY]->(m2:Manufacturer {name: "NSK"})
MATCH (eq)-[:HAS_SPEC]->(s:Specification {name: "max_temperature"})
WHERE s.value >= 200
RETURN eq, s
```

**Stage 3: Vector Fallback** (if graph returns no results)
- Embed the query as a vector
- Search Neo4j vector index for similar parts
- Filter through graph spec constraints
- Useful for natural language queries without specific part numbers

**Stage 4: Context Assembly**
Merge results from all three sources:
- Graph matches (with relationship paths for explainability)
- Vector matches (with similarity scores)
- PostgreSQL data (inventory, exact pricing)

**Stage 5: LLM Response Generation**
Claude generates a natural language response with:
- Direct answer to the query
- Specification comparison
- Inventory availability + pricing
- Suggested next actions

### Multi-Hop Reasoning

```
"Replace all bearings in motor EM3558T"

Hop 1: MATCH (a:Assembly {model: "EM3558T"})-[:CONTAINS]->(p:Part:Bearing) → 2 bearings
Hop 2: For each bearing → MATCH (p)-[:EQUIVALENT_TO|ALTERNATIVE_TO]-(alt:Part) → alternatives
Hop 3: For each alternative → check inventory + pricing via PostgreSQL
Hop 4: MATCH (p)-[:COMPATIBLE_WITH]->(acc:Part) → seals, retaining rings, lubricant
Result: Complete replacement kit with pricing
```

---

## 6. Catalog Ingestion Pipeline

```
Sources: CSV/Excel │ PDF Catalogs │ Supplier APIs │ Web Scraping
                    ▼
Stage 1: Parse & Extract
  • PDF → pdfplumber/docling (table-aware extraction)
  • CSV → pandas normalization
  • HTML → BeautifulSoup + LLM extraction (from v1)
                    ▼
Stage 2: LLM-Powered Normalization
  • Part number parsing (v1's bearing/fastener/belt parsers)
  • Spec extraction & unit standardization
  • Category classification into taxonomy
  • Manufacturer identification
                    ▼
Stage 3: Entity Resolution & Deduplication
  • Fuzzy + exact match against existing graph nodes
  • Duplicate detection (same part, different descriptions)
  • Cross-reference resolution (A = B from different manufacturer)
  • Confidence scoring on matches
  • Human-in-the-loop queue for low-confidence matches
                    ▼
Stage 4: Graph Construction
  • Create/update Part, Manufacturer, Category, Spec nodes
  • Create edges (EQUIVALENT_TO, HAS_SPEC, BELONGS_TO, etc.)
  • Generate vector embeddings for new/updated parts
  • Sync simplified product data to PostgreSQL
```

---

## 7. Claude LLM Layer + Voyage AI Embeddings

### Model Routing

```python
class LLMRouter:
    claude_models: {
        "fast": "claude-haiku-4-5",        # Intent classification, entity extraction
        "standard": "claude-sonnet-4-6",   # Response generation, catalog normalization
        "heavy": "claude-opus-4-6",        # Complex reasoning, graph construction
    }

    task_routing: {
        "intent_classification": "fast",        # Haiku
        "entity_extraction": "fast",            # Haiku
        "response_generation": "standard",      # Sonnet
        "catalog_normalization": "standard",    # Sonnet
        "graph_construction": "standard",       # Sonnet
        "complex_reasoning": "heavy",           # Opus
    }

    embedding_provider: VoyageEmbeddingClient   # voyage-3-large
```

### Resilience

- Circuit breaker on Claude API (from v2, threshold: 5 failures, timeout: 60s)
- Retry with exponential backoff (3 attempts, 1s base)
- Model-tier fallback: if Opus unavailable, fall back to Sonnet
- Voyage AI for all embeddings (voyage-3-large, 1024 dims)

---

## 8. Frontend Additions

Beyond v2's existing 12 pages, add:

| Page | Purpose |
|------|---------|
| **Graph Explorer** | Force-directed visualization of part relationships. Click a part → see equivalents, compatibility, specs in graph layout. |
| **Catalog Import** | Drag-and-drop CSV/PDF. Progress bar for parse → normalize → resolve → build stages. Review queue for low-confidence matches. |
| **Cross-Reference Manager** | Table view of all cross-references. Validate, edit, merge. Confidence indicators. |
| **Enhanced Search** | Show reasoning path ("Found via: SKF 6205 → EQUIVALENT_TO → NSK 6205DDU → HAS_SPEC → temp: 220°C"). |
| **Part Intelligence Card** | Enhanced product detail: graph context, alternatives, compatible parts, assembly membership, purchase history. |

---

## 9. Merging v1 and v2

### From v1 (IndusAI-main) — Bring Back:
- Part number parsers (bearing, fastener, V-belt) → feed into graph construction
- LLM client patterns → adapted for Claude-only router
- Embedding service → generates vectors for Neo4j vector index
- Semantic/hybrid search logic → adapted for Neo4j vector search
- Catalog scraper service → feeds ingestion pipeline
- PDF quote generation → keep for quoting workflow
- Entity extraction patterns → enhanced with graph-based resolution

### From v2 (IndusAI2.0) — Keep:
- Full platform services (Order, Invoice, Procurement, RMA, Workflow, Pricing, Analytics)
- React frontend (all 12 pages + new graph pages)
- PostgreSQL schema for transactional data
- Docker + CI/CD setup
- Circuit breaker pattern
- Rate limiting, JWT auth, security headers

### New for v3:
- Neo4j knowledge graph + ontology
- GraphRAG query pipeline (5-stage)
- Catalog ingestion pipeline (4-stage)
- Context merger + result ranker
- Graph Explorer UI
- Event-driven sync (Neo4j ↔ PostgreSQL)

---

## 10. Competitive Positioning

| Capability | Grainger | Verusen | Generic RAG Bot | **IndusAI 3.0** |
|-----------|----------|---------|----------------|----------------|
| Product search | Keyword | N/A | Vector similarity | **Graph + Vector + Spec** |
| Cross-references | Manual tables | ML matching | Embedding similarity | **Graph traversal (deterministic)** |
| Multi-hop reasoning | None | None | None | **Native graph chains** |
| Spec precision | Filter-based | N/A | "Similar" results | **Exact constraint matching** |
| Conversational AI | None | None | Basic chatbot | **Claude-powered, graph-aware** |
| BOM intelligence | None | Basic | None | **Assembly graph resolution** |
| Self-improving data | No | Yes (ML) | No | **Graph + validated interactions** |
| Platform operations | E-commerce | Procurement | None | **Full O2C + P2P + Invoicing** |
| Catalog ingestion | Manual | CSV/API | PDF chunking | **Multi-format + LLM normalization** |

### The Moat

The knowledge graph is the defensible moat. Every cross-reference validated by a customer interaction, every catalog ingested, every spec relationship confirmed — the graph grows smarter. A competitor starting from scratch cannot replicate years of accumulated relationship data. This is the same flywheel that made Verusen's "Material Graph" (41M SKUs) their core asset.

---

## 11. Implementation Phases

### Phase 1: Foundation (Weeks 1-4)
- Neo4j setup + ontology creation
- Catalog ingestion pipeline (CSV → graph)
- Basic GraphRAG query (single-hop: part lookup + cross-refs)
- Claude LLM router + Voyage AI embeddings
- Merge v1 part parsers into codebase

### Phase 2: Intelligence (Weeks 5-8)
- Multi-hop reasoning pipeline
- Vector embeddings in Neo4j + hybrid search
- Context merger + result ranker
- Enhanced chat with graph-powered responses
- Neo4j ↔ PostgreSQL sync service

### Phase 3: Platform Integration (Weeks 9-12)
- Graph Explorer UI
- Catalog Import UI with review queue
- Cross-Reference Manager
- Enhanced Search with reasoning display
- Part Intelligence Cards

### Phase 4: Polish & Pitch (Weeks 13-16)
- Demo dataset (realistic MRO catalog, 10K+ SKUs)
- Performance optimization (query caching, graph indexes)
- Security hardening
- Documentation + pitch deck materials
- End-to-end testing
