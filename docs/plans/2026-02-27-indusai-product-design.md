# IndusAI Product Design — AI-Powered MRO Sourcing Platform

**Date**: 2026-02-27
**Status**: Approved
**Approach**: B — AI-First Sourcing Layer

---

## 1. Product Identity

**IndusAI** — AI-powered MRO parts sourcing platform for procurement teams.

**One-liner**: "Tell us what you need. We find the best part, price, and supplier — instantly."

**Target buyer**: Manufacturing plants, facilities teams, procurement departments — anyone who BUYS MRO parts and wants to find the best part, price, and delivery speed across multiple suppliers.

**Deployment**: SaaS, multi-tenant.

**Differentiator**: Other procurement tools are catalogs you search manually. IndusAI *understands* MRO parts — it knows cross-references, specs, compatibility, and alternatives. It optimizes for price, delivery time, and buyer location simultaneously. It's like having a veteran parts expert available 24/7.

**Moat**: The knowledge graph. Every query makes it smarter. Cross-references, specs, compatibility data, and pricing intelligence compound over time. Competitors have catalogs. We have understanding.

---

## 2. Architecture

```
BUYER LAYER
  ┌──────────────┐  ┌──────────────┐  ┌───────────┐
  │ AI Chat UI   │  │ Catalog UI   │  │ Orders UI │
  │ (primary)    │  │ (fallback)   │  │ (tracking)│
  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘
         │                 │                │
API GATEWAY
  Auth (JWT+OAuth) │ Rate Limit │ Tenant Isolation
         │
INTELLIGENCE LAYER
  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐
  │ GraphRAG    │  │ Location     │  │ Price       │
  │ Query Engine│  │ Optimizer    │  │ Comparator  │
  │ (exists)    │  │ (NEW)        │  │ (NEW)       │
  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘
         │                │                  │
DATA LAYER
  ┌──────────┐  ┌───────────┐  ┌──────────────────┐
  │ Neo4j    │  │ PostgreSQL│  │ Redis            │
  │ Parts    │  │ Users     │  │ Sessions, cache  │
  │ Graph    │  │ Orders    │  │ geo lookups      │
  │ Specs    │  │ Sellers   │  │                  │
  │ X-refs   │  │ Locations │  │                  │
  └──────────┘  └───────────┘  └──────────────────┘
         │
SUPPLY INGESTION
  ┌──────────┐  ┌───────────┐  ┌──────────────────┐
  │ Web      │  │ CSV/PDF   │  │ Seller Portal    │
  │ Scraper  │  │ Importer  │  │ (self-serve)     │
  │ (NEW)    │  │ (exists)  │  │ (post-MVP)       │
  └──────────┘  └───────────┘  └──────────────────┘
```

### Key design decisions

- **Prices in PostgreSQL** (seller_listings) — change frequently, need fast updates
- **Part knowledge in Neo4j** (specs, cross-refs, compatibility) — relational, stable
- **Query engine joins both at runtime** — graph for intelligence, SQL for commerce
- **Reliability scores on all data** — drives ranking silently, never shown to buyers

---

## 3. Data Model — New Entities

### PostgreSQL (transactional)

```sql
-- Auth & multi-tenancy
users              (id, email, password_hash, name, org_id, role, created_at)
organizations      (id, name, plan, primary_location_id, created_at)

-- Locations (buyer plants + seller warehouses)
locations          (id, org_id, label, address, city, state, zip, country, lat, lng)

-- Seller/supply side
seller_profiles    (id, org_id, name, website, catalog_source, last_scraped_at)
seller_warehouses  (id, seller_id, location_id, ships_to_regions[])
seller_listings    (id, seller_id, sku, part_sku, price, currency,
                    qty_available, warehouse_id, lead_time_days,
                    reliability, source_type, last_verified_at, stale_after,
                    updated_at)

-- Sourcing & RFQ
sourcing_requests  (id, buyer_org_id, query_text, intent, results_json,
                    location_id, created_at)
rfq_requests       (id, buyer_org_id, part_description, qty, urgency,
                    target_price, status, created_at)
rfq_responses      (id, rfq_id, seller_id, price, lead_time, expires_at)
```

### Neo4j (knowledge graph) — new nodes/edges

```
(:Seller {code, name, website, regions[]})
(:Warehouse {code, name, lat, lng, seller_code})
(:Seller)-[:SUPPLIES]->(:Part) {price, qty, lead_time_days}
(:Warehouse)-[:STOCKS]->(:Part) {qty, bin_location}
```

### Reliability metadata on all graph data

```
(:Part)-[:HAS_PRICE {value, currency, seller, reliability, source,
                     last_verified_at, stale_after}]->
(:Part)-[:HAS_SPEC {name, value, reliability, source, last_verified_at}]->
```

---

## 4. Living Knowledge Base & Data Freshness

### Three-tier knowledge sourcing

| Tier | Source | Reliability | Refresh |
|------|--------|-------------|---------|
| Tier 1: Verified | Seller self-uploaded, direct API feeds | 9-10 | Real-time / daily |
| Tier 2: Scraped | Public distributor sites (Grainger, McMaster, MSC) | 6-8 | Weekly crawl + staleness check |
| Tier 3: Reference | Manufacturer spec sheets, industry databases | 4-6 | Monthly, cross-validated |

### Reliability scoring

- **Source type**: manufacturer datasheet = 10, API feed = 9, scrape = 7, forum = 4
- **Age decay**: price from 30 days ago drops 2 points
- **Cross-validation**: same spec confirmed by 3+ sources = boost
- **Historical accuracy**: if past scrapes were correct, trust increases

### Staleness engine

- **Daily**: Flag prices older than 7 days as "stale" → re-scrape those listings
- **Weekly**: Full crawl of all Tier 2 sources → diff and update
- **Monthly**: Crawl Tier 3 reference sources → cross-validate specs
- **On-query**: Stale data ranks lower. Data >30 days stale on price excluded entirely.

### Auto-enrichment targets

- Spec sheets → structured specs (bore, OD, load rating, temp range)
- Cross-reference tables → manufacturer equivalence maps
- Application notes → environment suitability (food-grade, high-temp, etc.)
- Compliance data → RoHS, REACH, country of origin
- Discontinuation notices → replacement part mapping

---

## 5. Ranking & Buyer Experience

### Composite ranking (buyer never sees scores)

```
composite_score = (reliability x 0.3) + (price_rank x 0.35)
                + (delivery_speed x 0.25) + (proximity x 0.1)
```

- Stale data ranks lower automatically
- Really stale data (>30 days on price) excluded entirely
- Buyer sees confident, clean results — no hedging

### Admin/testing debug view

Toggle via `?debug=true` or admin dashboard:
- Reliability score per result
- Last verified timestamp
- Source type
- Staleness warnings
- Composite score breakdown

---

## 6. Core User Flows

### Flow 1: Buyer Sign-up & Onboarding

```
Sign up (email/password or Google OAuth)
  → Create organization
  → Add primary location (address → geocode to lat/lng)
  → Optional: "What do you typically buy?" (seeds preferences)
  → Land on AI chat interface
```

### Flow 2: AI Sourcing Query (core loop)

```
Buyer: "I need 100 units of 6204-2RS or equivalent, sealed,
        for a food processing plant"

Stage 1 — Intent + Entity extraction
  part_lookup, 6204-2RS, qty=100, environment=food-grade

Stage 2 — Graph Resolution
  finds 6204-2RS (SKF), 6204DDU (NSK), FAG-6204-2RSR

Stage 3 — Cross-ref expansion
  all 3 equivalent, check food-grade seal options

Stage 4 — Seller matching + Location optimization (NEW)
  • Query seller_listings for all 3 SKUs
  • Filter: qty_available >= 100
  • Geocode: buyer location → seller warehouse distances
  • Calculate: unit_price + estimated_shipping + lead_time
  • Rank by composite_score (reliability, price, speed, proximity)

Stage 5 — LLM Response
  Presents top 3 options with price, delivery, distance
  Includes cross-reference intelligence and domain advice
  Offers: "Request quote" or "Order now"
```

### Flow 3: Quote Request (RFQ)

```
Buyer: "Get me a quote from Grainger"
  → Creates rfq_request
  → On-platform seller: notification sent
  → Off-platform seller: RFQ email draft generated
  → Buyer tracks in dashboard
```

### Flow 4: Order Placement

```
Buyer: "Order 100 units of the NSK from MSC"
  → Creates order linked to seller_listing + warehouse
  → Tracks: placed → confirmed → shipped → delivered
  → Status updates via chat or email
```

### Flow 5: Catalog Ingestion (supply side)

```
Option A — Scrape: crawl distributor URL
  → Parser → Normalizer → Resolver (dedup) → Graph Builder
  → seller_listings populated with prices/qty/reliability

Option B — Upload: seller uploads CSV/PDF
  → Same pipeline, tagged with seller_id

Option C — API feed: real-time sync (post-MVP)
```

---

## 7. MVP Scope

### Build now (MVP)

| # | Feature | Status |
|---|---------|--------|
| 1 | Auth system — signup, login, JWT refresh, Google OAuth | New |
| 2 | Org & location — create org, add locations with geocoding | New |
| 3 | Seller & warehouse data model | New |
| 4 | Web scraper — crawl distributor sites into ingestion pipeline | Extends existing pipeline |
| 5 | Reliability scoring engine — score, decay, staleness | New |
| 6 | Location optimizer — geocode, distance, shipping estimates | New |
| 7 | Price comparator — normalize across sellers, composite ranking | New |
| 8 | Enhanced GraphRAG Stage 4 — sellers, location, pricing in context | Extends existing engine |
| 9 | AI Chat UI redesign — sourcing-focused with result cards | Redesign existing |
| 10 | Order placement from chat — "order this" creates order | Extends existing |
| 11 | RFQ flow — request quote, track responses | New |
| 12 | Freshness scheduler — daily/weekly re-scrape stale data | New |
| 13 | Admin debug view — reliability scores, scrape status | New |

### Post-MVP

| Feature | Why later |
|---------|-----------|
| Seller self-serve portal | Need buyers first |
| Real-time API feeds | Requires seller partnerships |
| Approval workflows (PO > $X needs manager) | Enterprise feature |
| ERP connectors (NetSuite, SAP) | Customer-specific |
| Mobile app | Web-first |
| Bulk / recurring orders | Power user feature |
| Supplier scorecarding | Need order history first |
| Demand forecasting | Need usage data first |

---

## 8. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.12+, FastAPI | Existing |
| Frontend | React 18, TypeScript, Vite | Existing, redesign chat UI |
| Knowledge Graph | Neo4j 5.x | Existing |
| Database | PostgreSQL 16 | Existing |
| Cache | Redis 7 | Existing |
| LLM | Claude (Haiku/Sonnet/Opus) | Existing |
| Embeddings | Voyage AI (voyage-3-large) | Existing |
| Auth | bcrypt + JWT + Google OAuth | New |
| Geocoding | OpenStreetMap Nominatim (free) or Google Maps | New |
| Web Scraping | httpx + BeautifulSoup + LLM extraction | Extends existing |
| Scheduling | APScheduler or Celery Beat | New |
