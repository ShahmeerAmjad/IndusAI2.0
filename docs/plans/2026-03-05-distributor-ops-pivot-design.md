# IndusAI 3.0 — Distributor Ops Pivot: Design Doc

**Date:** 2026-03-05
**Status:** Approved
**Approach:** Bottom-Up (Backend → Frontend)
**Scope:** Chempoint KB pipeline + Inbox MVP + Dashboard pivot + Frontend reorg

## Problem

The app currently looks like a buyer-focused MRO ERP. After the supplier-sales pivot, it needs to be a **distributor operations tool** that reduces support team load. Three gaps:

1. **No way to trigger Chempoint scraping** — `chempoint_scraper.py` exists but has no route or UI
2. **No Inbox** — the core feature (inbound message triage with AI drafts) doesn't exist
3. **All frontend pages** still show buyer-focused messaging and KPIs

## Architecture

```
KNOWLEDGE BASE PIPELINE (Chempoint → Neo4j)
  Firecrawl crawl → ChempointProduct objects
  → Neo4j ingestion (Product, Manufacturer, ProductLine, Industry nodes)
  → TDS/SDS PDF download → Claude extraction → structured nodes
  → Voyage AI embeddings on Product nodes

INBOX PIPELINE (Inbound → AI Draft → Human Review)
  Inbound message (email/web/simulated)
  → Intent Classifier (9 intents, multi-intent, Claude Haiku)
  → Auto-Response Engine (queries Neo4j, inventory, pricing, order history)
  → AI draft + confidence score → status: draft_ready
  → Human review: approve / edit / escalate / feedback

FRONTEND
  Inbox (primary) → Dashboard (ops KPIs) → AI Assistant → Knowledge Base
  → Orders, Quotes, Inventory, Products (secondary)
```

## Data Layer

### New Tables

**inbound_messages** — channel, from/to, subject, body, intents JSONB, status (`new → classified → draft_ready → reviewed → sent → escalated`), ai_draft_response, ai_confidence, assigned_to, customer_account_id, thread_id

**customer_accounts** — name, email, phone, company, account_number, pricing_tier, payment_terms

**classification_feedback** — message_id FK, ai_intent, ai_confidence, human_intent, is_correct, corrected_by

**documents** — product_id FK, doc_type (TDS/SDS), file_path, extracted_text, structured_data JSONB, source_url, revision_date, is_current

No changes to existing tables.

## Knowledge Base Pipeline

### Chempoint Scraper → Neo4j Ingestion

Uses existing `chempoint_scraper.py` (Firecrawl BFS, 50 pages default).

For each `ChempointProduct`:
- Create/merge `(:Product)` node (sku, name, cas_number, description)
- Create/merge `(:Manufacturer)` → `MANUFACTURED_BY`
- Create/merge `(:ProductLine)` → `BELONGS_TO`
- Create/merge `(:Industry)` → `SERVES_INDUSTRY`
- If tds_url/sds_url present: download PDF → store in `documents` table → extract structured fields via Claude → create `(:TechnicalDataSheet)` / `(:SafetyDataSheet)` nodes
- Generate Voyage AI embedding → store on Product node

### API Routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/knowledge-base/crawl` | Trigger Chempoint crawl, returns job_id |
| GET | `/api/v1/knowledge-base/crawl/{job_id}` | Poll crawl status |
| GET | `/api/v1/knowledge-base/products` | Paginated product browse |
| GET | `/api/v1/knowledge-base/products/{id}` | Product detail + TDS/SDS |
| POST | `/api/v1/knowledge-base/documents/upload` | Manual TDS/SDS upload |

## Intent Classifier

Extends existing `services/intent_classifier.py` to 9 intents:

| Intent | Auto-Action |
|--------|-------------|
| PLACE_ORDER | Check inventory + pricing → draft order confirmation |
| REQUEST_QUOTE | Lookup customer tier → draft quote |
| REQUEST_TDS_SDS | Neo4j lookup → attach document |
| ORDER_STATUS | Look up order → return tracking |
| TECHNICAL_SUPPORT | GraphRAG query → draft answer |
| RETURN_COMPLAINT | Create RMA draft |
| REORDER | Find last order → check current stock/pricing |
| ACCOUNT_INQUIRY | Look up customer account |
| SAMPLE_REQUEST | Check sample policy → draft response |

Multi-intent per message. Returns `[{intent, confidence, text_span, entities}]`.
Uses Claude Haiku for speed. Few-shot examples from `classification_feedback`.

## Auto-Response Engine

New `services/auto_response_engine.py`:
- Takes classified inbound_message
- Per intent, queries relevant data source (Neo4j, PostgreSQL orders, inventory)
- Produces: ai_draft_response text, ai_confidence float, suggested_attachments list
- Updates message status: `classified → draft_ready`

## Inbox API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/inbox` | Paginated message list (filter: status, channel, intent, assigned_to) |
| GET | `/api/v1/inbox/{id}` | Message detail + AI draft + customer context |
| GET | `/api/v1/inbox/stats` | Aggregate stats for dashboard |
| POST | `/api/v1/inbox/{id}/approve` | Approve AI draft → status `sent` |
| POST | `/api/v1/inbox/{id}/edit` | Submit edited response → status `sent` |
| POST | `/api/v1/inbox/{id}/escalate` | Assign to specialist |
| POST | `/api/v1/inbox/{id}/feedback` | Log correction to classification_feedback |
| POST | `/api/v1/inbox/simulate` | Submit fake email → full pipeline → appears in inbox |

### Seed Data

25 realistic sample messages in debug mode:
- Mix of all 9 intents, various confidence levels
- Some multi-intent messages
- Pre-classified with AI drafts ready for review

## Frontend Changes

### Sidebar Reorg

Priority order:
1. Inbox (with unread badge) — PRIMARY
2. Dashboard (ops KPIs)
3. AI Assistant (chat)
4. Knowledge Base (new)
5. Orders, Quotes, Inventory, Products (secondary, collapsed section)

Footer: "AI-Powered Support Automation"
Remove: Procurement, Invoicing, Returns, Channels from nav

### Dashboard (Full Replace)

**4 KPI Cards:**
- Messages Handled Today
- Avg Response Time
- AI Accuracy Rate (% approved without edits)
- Hours Saved This Month

**Charts:**
- Intent Distribution (pie)
- Response Time Trend (line)
- Messages by Channel (bar)

**Recent Activity:** Latest inbox items with status badges

Data from `GET /api/v1/inbox/stats`.

### Inbox Page (New)

- Left panel: message list with intent badge, customer name, timestamp, status pill
- Right panel: message detail — original content, detected intents with confidence scores, AI draft (editable), approve/edit/escalate buttons
- Top bar: filters (status, channel, intent) + "Simulate Inbound" button
- Auto-refresh every 10s

### Knowledge Base Page (New)

- Search bar (product name, SKU, CAS number)
- Product cards with manufacturer, industries, TDS/SDS badges
- Product detail modal: specs, TDS/SDS structured data, download links
- Admin section: "Crawl Chempoint" button + status, manual PDF upload

### Chat Cleanup

- Remove qty picker, location selector from header
- Remove order buttons and comparison tables
- Keep as secondary "ask the AI" tool for support reps

## Build Order (Bottom-Up)

### Phase 1: Data Layer
- Create migration for 4 new tables
- Run on startup in debug mode

### Phase 2: Knowledge Base Backend
- Wire chempoint_scraper to routes
- Build Neo4j ingestion service
- TDS/SDS PDF download + Claude extraction
- Knowledge base browse/search API

### Phase 3: Inbox Backend
- Extend intent classifier to 9 intents + multi-intent
- Build auto-response engine
- Build inbox CRUD routes
- Build simulate endpoint
- Seed 25 sample messages

### Phase 4: Frontend Pivot
- Sidebar reorg + relabeling
- Dashboard full replace with ops KPIs
- Inbox page (new)
- Knowledge Base page (new)
- Chat cleanup (remove buyer patterns)

### Phase 5: Integration + Polish
- Wire frontend to real APIs
- End-to-end test: simulate → classify → draft → approve
- Verify Chempoint crawl → browse → chat can answer product questions

## Reuse

- `chempoint_scraper.py` — as-is for crawling
- `web_scraper.py` — Firecrawl integration
- `intent_classifier.py` — extend, don't replace
- `graphrag/` — powers AI assistant and auto-response
- `graph/neo4j_client.py` — node creation
- All platform services (orders, inventory, pricing) — used by auto-response engine
- `ai_service.py` — Claude calls for extraction + drafting

## Success Criteria

- Chempoint crawl seeds 50+ products with TDS/SDS data in Neo4j
- Inbox shows 25 seeded messages with AI drafts
- "Simulate Inbound" → message appears in inbox within 5 seconds with draft
- Dashboard shows ops KPIs computed from inbox data
- AI Assistant can answer "What's the flash point of X?" from TDS data
- Every page feels like a distributor ops tool, not a buyer ERP
