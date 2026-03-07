# IndusAI 3.0 — Supplier Sales & Support Automation Design

**Date:** 2026-03-05
**Status:** Approved
**Approach:** Omnichannel Inbox First (Approach A)

## Problem Statement

Industrial parts suppliers/distributors receive millions of inbound emails per year across multiple inboxes (12+ mailboxes). Teams of 8+ people manually triage orders, quote requests, TDS/SDS document requests, and support questions. This is slow (2.5hr average response time), expensive (~$640K/yr in labor), and error-prone.

**Target customers:** Industrial parts suppliers and chemical distributors (companies like Chempoint, which distributes for 50+ manufacturers like Dow, BASF, 3M).

**Value proposition:** Reduce TAT from hours to minutes. Cut operational headcount from 8 to 3 reps. AI handles routine requests (quotes, TDS/SDS, order status), humans handle exceptions.

## Architecture Overview

```
INBOUND CHANNELS
  Email (IMAP/Webhook) ──┐
  Web Chat (WebSocket) ──┤
  Fax (Cloud → PDF → OCR)┘
          │
  UNIFIED MESSAGE ROUTER
  (normalize → InboundMessage)
          │
  INTENT CLASSIFIER (9 intents, multi-intent per message)
  + Entity Extraction (products, quantities, PO#, CAS#)
  + Trainable via human feedback loop
          │
  AUTO-RESPONSE ENGINE
  (Knowledge Graph + TDS/SDS + Inventory + Pricing + Order History)
  → Drafts response + attachments
  → ALL drafts go to human review (no auto-send)
          │
  HUMAN REVIEW QUEUE (Inbox UI)
  → Approve / Edit / Send
  → Escalate to specialist
  → Create order / quote
          │
  DATA LAYER
  PostgreSQL (messages, orders, accounts)
  Neo4j (products, TDS/SDS, specs, relationships)
  Redis (sessions, cache)
  File Storage (TDS/SDS PDFs)
```

### Key Design Decisions

1. **No auto-send** — All AI drafts require human approval. Safety-first for industrial/chemical products.
2. **Multi-intent classification** — Real emails contain multiple requests. Each intent becomes a separate work item.
3. **Knowledge graph over RAG** — TDS/SDS fields are extracted into structured Neo4j nodes, not chunked text. "What's the flash point?" is a property lookup, not semantic search.
4. **Trainable classifier** — Human corrections build a training dataset. Classifier improves over time.
5. **ERP simplified for MVP** — CSV/Excel import for product/inventory data. ERP adapters are future state.
6. **Chempoint as reference model** — Scrape their public catalog to seed the product DB and taxonomy. Not the customer.

## Knowledge Graph Design

### Node Types

```
(:Industry {name, description})
(:Manufacturer {name, website, country, logo_url})
(:ProductLine {name, description})
(:Product {
    sku, name, description, cas_number,
    chemical_formula, physical_form,
    packaging_options[], grade,
    min_order_qty, lead_time_days
})
(:TechnicalDataSheet {
    appearance, color, odor, density, viscosity,
    pH, flash_point, boiling_point, melting_point,
    solubility, shelf_life, recommended_uses[],
    storage_conditions, pdf_url, revision_date
})
(:SafetyDataSheet {
    ghs_classification, hazard_statements[],
    precautionary_statements[], cas_numbers[],
    un_number, dot_class, first_aid,
    fire_fighting, ppe_requirements,
    environmental_hazards, disposal,
    transport_info, revision_date, pdf_url
})
(:Application {name, description})
(:Specification {name})
(:Distributor {name, website})
(:Warehouse {code, name, lat, lng, region})
(:PricePoint {
    unit_price, currency, price_per_unit,
    uom, min_qty, max_qty,
    effective_date, expiration_date, pricing_tier
})
(:CustomerAccount {name, email, company, account_number, pricing_tier})
```

### Relationships

```
(:Product)-[:HAS_TDS]->(:TechnicalDataSheet)
(:Product)-[:HAS_SDS]->(:SafetyDataSheet)
(:Product)-[:MANUFACTURED_BY]->(:Manufacturer)
(:Product)-[:BELONGS_TO]->(:ProductLine)
(:Product)-[:SERVES_INDUSTRY]->(:Industry)
(:Product)-[:USED_FOR]->(:Application)
(:Product)-[:EQUIVALENT_TO]->(:Product)
(:Product)-[:ALTERNATIVE_TO]->(:Product)
(:Product)-[:HAS_SPEC {name, value, unit}]->(:Specification)
(:Product)-[:DISTRIBUTED_BY {price, moq, lead_time}]->(:Distributor)
(:Product)-[:PRICED_AT]->(:PricePoint)
(:Product)-[:STOCKED_AT {qty_on_hand, qty_reserved, reorder_point}]->(:Warehouse)
(:Manufacturer)-[:PRODUCES]->(:ProductLine)
(:ProductLine)-[:CONTAINS]->(:Product)
(:Warehouse)-[:OWNED_BY]->(:Distributor)
(:CustomerAccount)-[:HAS_CONTRACT_PRICE {contract_price, volume_discount, valid_until}]->(:Product)
(:Industry)-[:HAS_APPLICATION]->(:Application)
```

### Chempoint-Inspired Taxonomy

**18 Industries:** Adhesives, Agriculture, Building & Construction, Care Chemicals, Coatings, Elastomers, Energy, Facility Infrastructure, Food & Beverage, Inks, Lubricants, MRO, Metal Processing, Personal Care, Pharma, Plastics, Transportation, Water Treatment

**50+ Manufacturers:** Dow, BASF, 3M, Chemours, DuPont, Eastman, Henkel, Huntsman, LANXESS, Momentive, etc.

**190+ Product Lines** across manufacturers

## New PostgreSQL Tables

### Document Storage
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id),
    doc_type VARCHAR(10) NOT NULL,       -- 'TDS' or 'SDS'
    file_path TEXT NOT NULL,
    file_name TEXT,
    file_size_bytes INTEGER,
    mime_type VARCHAR(50),
    extracted_text TEXT,
    structured_data JSONB,               -- parsed fields from LLM/OCR
    source_url TEXT,
    revision_date DATE,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Inbound Messages
```sql
CREATE TABLE inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL,        -- 'email', 'web', 'fax'
    from_address TEXT NOT NULL,
    to_address TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    raw_payload JSONB,
    attachments JSONB,                   -- [{name, path, mime_type, size}]
    intents JSONB,                       -- [{intent, confidence, text_span, entities}]
    status VARCHAR(20) DEFAULT 'new',    -- new, classified, draft_ready, reviewed, sent, escalated
    assigned_to UUID,
    ai_draft_response TEXT,
    ai_confidence FLOAT,
    conversation_id UUID,
    customer_account_id UUID,
    thread_id TEXT,                       -- email thread grouping
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Customer Accounts
```sql
CREATE TABLE customer_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    fax_number TEXT,
    company TEXT,
    account_number TEXT,
    erp_customer_id TEXT,
    pricing_tier VARCHAR(20),
    payment_terms VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Classification Feedback (Trainable Classifier)
```sql
CREATE TABLE classification_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES inbound_messages(id),
    ai_intent VARCHAR(30),
    ai_confidence FLOAT,
    human_intent VARCHAR(30),
    text_excerpt TEXT,
    is_correct BOOLEAN,
    corrected_by UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### ERP Connections (Future)
```sql
CREATE TABLE erp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    erp_type VARCHAR(30) NOT NULL,
    connection_config JSONB,
    sync_schedule VARCHAR(20),
    last_sync_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);
```

## Intent Classification

### 9 Intent Types

| Intent | Example | Auto-Action |
|--------|---------|-------------|
| PLACE_ORDER | "Need 500kg Polyox WSR-301" | Check inventory, draft order confirmation |
| REQUEST_QUOTE | "Can you quote me on..." | Look up pricing tier, generate quote PDF |
| REQUEST_TDS_SDS | "Send me the SDS for..." | Fetch from knowledge graph, attach PDF |
| ORDER_STATUS | "Where is PO-12345?" | Look up order, return tracking info |
| TECHNICAL_SUPPORT | "What viscosity grade for..." | Query knowledge graph, draft technical answer |
| RETURN_COMPLAINT | "Product arrived damaged" | Create RMA draft, draft apology + instructions |
| REORDER | "Same as last order" | Find last order, check current pricing/stock |
| ACCOUNT_INQUIRY | "What's my credit limit?" | Look up customer account, return info |
| SAMPLE_REQUEST | "Can I get a sample of..." | Check sample policy, draft response |

### Multi-Intent Handling

Real emails often contain multiple requests:
> "Hi, can you send me the SDS for Polyox WSR-301? Also, I need a quote for 500kg. And what's the status of PO-12345?"

The classifier outputs **multiple IntentResults** per message, each with its own confidence, text span, and entities. The AI drafts a single response covering all intents.

### Trainable Feedback Loop

```
Phase 1: Pattern matching + Claude LLM (zero-shot)
Phase 2: Human corrections → classification_feedback table → training dataset
Phase 3: Few-shot examples from corrections improve classifier
```

## Email Ingestion Pipeline

```
Email arrives (IMAP poll every 30s OR webhook)
    ↓
EMAIL PARSER SERVICE
  1. Parse headers (from, to, subject, date, In-Reply-To)
  2. Extract body (HTML → text)
  3. Download attachments
  4. Thread detection (In-Reply-To → conversation_id)
  5. Customer account lookup (from_address → customer_accounts)
  6. Store in inbound_messages (status='new')
    ↓
ATTACHMENT PROCESSOR
  .pdf → Claude Vision / pdfplumber → extract PO line items
  .xlsx/.csv → parse structured order data
  .tiff/.jpg (fax) → OCR → text → same pipeline
    ↓
INTENT CLASSIFIER (multi-intent)
  → Updates inbound_messages.intents JSONB
  → Status changes to 'classified'
    ↓
AUTO-RESPONSE ENGINE
  → Queries knowledge graph for product info, TDS/SDS
  → Looks up customer pricing tier
  → Checks inventory availability
  → Generates draft response + attachments
  → Status changes to 'draft_ready'
    ↓
HUMAN REVIEW QUEUE
  → Rep reviews, edits, approves
  → Status changes to 'sent'
  → If AI was wrong: correction logged to classification_feedback
```

## Fax Handling

- Cloud fax service (eFax API / Twilio Fax) receives inbound fax as PDF
- PDF → OCR (Claude Vision) → extracted text
- Same intent classification pipeline as email
- Stored as channel='fax' in inbound_messages

## Data Import (MVP, replaces ERP)

```python
class DataSourceAdapter(ABC):
    async def import_products(self, file) -> list[Product]
    async def import_inventory(self, file) -> list[StockLevel]
    async def import_customers(self, file) -> list[CustomerAccount]

class CSVImportAdapter(DataSourceAdapter): ...
class ExcelImportAdapter(DataSourceAdapter): ...
```

Future: SAP, NetSuite, Dynamics 365, Oracle adapters.

## Frontend Screens

### 1. Omnichannel Inbox (Primary)
- Left panel: filters (channel, status, intent, assigned)
- Center: message list with intent badges, timestamps, customer name
- Right panel: AI draft response, confidence score, related documents
- Actions: Approve, Edit, Escalate, Dismiss

### 2. Message Detail View
- Original email/message content
- Detected intents with confidence scores and entity extraction
- AI draft response (editable)
- Attached documents (Quote PDF, TDS/SDS PDFs)
- Customer context (account info, order history, pricing tier)
- Action buttons: Approve & Send, Edit Draft, Escalate, Dismiss

### 3. Product Knowledge Base
- Search by product name, SKU, CAS number, industry, manufacturer
- Product detail: specs from TDS, safety info from SDS, pricing, inventory
- Filter by industry, manufacturer, in-stock status
- Download TDS/SDS PDFs

### 4. Operations Impact Dashboard (ROI-Focused)
- Messages handled (total, by channel, by intent)
- Average response time (TAT reduction)
- Hours saved this month (~FTE equivalent)
- AI accuracy rate (% approved without edits)
- Orders auto-generated (count + revenue)
- TDS/SDS sent automatically
- Cost savings projection
- Intent distribution chart
- Response time trend

### 5. Existing Screens (reused from v2)
- Orders, Quotes, Customers, Inventory — already built
- Settings — add email inbox config, fax config, team management

## Chempoint Scraper (Seed Data)

Use Firecrawl to scrape Chempoint's public catalog:
1. Crawl /products, /industries, /manufacturers pages
2. Extract product names, descriptions, categories, manufacturers
3. Download TDS/SDS PDFs from product pages
4. OCR/extract structured fields from PDFs using Claude
5. Build Neo4j knowledge graph from extracted data
6. Generate embeddings for vector search fallback

## Reuse from Existing Code

### From v2 (current codebase):
- FastAPI app structure, auth, middleware (main.py)
- Intent classifier (services/intent_classifier.py) — extend to 9 intents
- Conversation service (services/conversation_service.py)
- AI service with circuit breaker (services/ai_service.py)
- GraphRAG query engine (services/graphrag/)
- Neo4j client and graph service (services/graph/)
- Ingestion pipeline (services/ingestion/)
- Web scraper with Firecrawl (services/ingestion/web_scraper.py)
- Report service for PDF generation (services/report_service.py)
- Bulk import service (services/bulk_import_service.py)
- All platform services (orders, quotes, inventory, pricing, etc.)
- Frontend: Dashboard, Orders, Quotes, Inventory, Products pages
- 227 existing tests

### From v1 (B2B-Omnichannel-Skynet):
- Channel abstraction pattern (app/services/channels/base.py)
- Scraper service with LLM extraction (app/services/scraper_service.py)
- PDF extraction pipeline (pdfplumber + LLM chunks)
- CSV extraction with flexible header detection
- Quote service with tiered pricing (app/services/quote_service.py)
- SQLAlchemy ORM models for conversations + messages (app/models/database/)
- Communication manager with WhatsApp retry logic

## Success Metrics

| Metric | Before IndusAI | After IndusAI | Target |
|--------|---------------|---------------|--------|
| Avg response time | 2.5 hours | < 5 minutes | 97% reduction |
| Staff needed | 8 people | 3 people | 62% reduction |
| Annual labor cost | ~$640K | ~$240K | $400K savings |
| TDS/SDS requests handled/day | ~50 manual | ~200 automated | 4x throughput |
| Quote generation time | 30-60 min | < 2 min | 95% faster |
| Error rate (wrong doc sent) | ~5% | < 1% | 80% reduction |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14 / FastAPI |
| Frontend | React 18, TypeScript, Tailwind, shadcn/ui |
| Databases | PostgreSQL 16, Neo4j 5.x, Redis 7 |
| AI/ML | Claude (Haiku/Sonnet/Opus), Voyage AI embeddings |
| Scraping | Firecrawl API |
| Email | IMAP (imaplib/aioimaplib) |
| Fax | Cloud fax API (future) |
| File Storage | Local disk (MVP), S3 (production) |
| Infrastructure | Docker Compose |
