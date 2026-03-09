# IndusAI — Landing Page Demo Showcase Design

**Date:** 2026-03-09
**Status:** Approved
**Purpose:** Co-founder demo — showcase what's built, live stats, architecture, ROI, and knowledge graph capabilities

---

## Overview

Add scrollable demo showcase sections to the existing Landing page (`/`). All stats are fetched live from the running API. The knowledge graph section includes a live force-graph visualization and search. Feature cards deep-link into the running app for live walkthroughs.

## Audience

Business partner / co-founder. Tone: technical credibility — prove depth and quality of what's actually built.

## Sections

### 1. Hero / Vision
- Headline: **"Supplier Sales & Support Automation"**
- Subline: "AI that triages, classifies, and drafts responses to millions of inbound emails — so your team handles exceptions, not routine."
- Dark gradient background, consistent with existing Landing style

### 2. The Problem
- Visual "before" card with pain stats:
  - 2M+ emails/year
  - 8 people across 12 inboxes
  - 2.5 hour average response time
  - ~$640K/year in labor cost
  - Error-prone manual triage
- Red/amber color scheme to convey pain

### 3. How It Works (Architecture Flow)
- Horizontal flow diagram rendered as styled cards (not an image):
  - **Inbound Channels** (Email, Web Chat, Fax)
  - → **Unified Router** (normalize → InboundMessage)
  - → **Multi-Intent Classifier** (9 intents, entity extraction)
  - → **Auto-Response Engine** (Knowledge Graph + TDS/SDS + Inventory + Pricing)
  - → **Human Review Queue** (approve / edit / escalate)
  - → **Send**
- Each node: icon + label + short description
- "No auto-send" safety badge on the human review step
- Connecting arrows/lines between nodes

### 4. What's Built (Live Stats Grid)
- Grid of stat cards, each fetched from running API on component mount
- Cards:
  - **API Endpoints** — count from `/health/detailed` or known count
  - **Tests Passing** — current count (458+)
  - **Products in DB** — `GET /api/products` total count
  - **Messages in Inbox** — `GET /api/inbox/messages` count
  - **Intents Supported** — 9 (from classifier config)
  - **Knowledge Graph Nodes** — from Neo4j stats endpoint
  - **TDS/SDS Documents** — from document service count
  - **Customer Accounts** — from accounts endpoint
- Each card: colored icon, animated count-up number, label
- Green pulse dot + "Live" badge to indicate real-time data

### 5. Knowledge Graph & Search
- **Live graph visualization** using existing `react-force-graph-2d`:
  - Render a subgraph (product → TDS → manufacturer → industry)
  - Nodes colored by type, edges labeled by relationship
  - Interactive: drag, zoom, hover for details
- **Live search bar**:
  - Type product name or CAS number
  - Results fetched from knowledge graph API
  - Show matching products with linked TDS/SDS
- **Explanatory text**: "Structured graph, not chunked documents. Property lookups, not semantic guessing."
- **Stats**: node count, relationship count, fetched live from Neo4j

### 6. Live Features (Jump-In Cards)
- Clickable cards that deep-link into running app pages:
  - **Inbox** → `/inbox` — "See 15 classified messages with AI-drafted responses"
  - **Knowledge Base** → `/knowledge-base` — "Browse products, TDS/SDS documents"
  - **Dashboard** → `/dashboard` — "ROI metrics and operational KPIs"
  - **AI Chat** → `/chat` — "Natural language product search"
  - **Products** → `/products` — "Full product catalog with graph data"
- Each card: icon, title, 1-line description, "Open Live →" button
- Cards arranged in a responsive grid

### 7. ROI / Cost Savings
- Before/After comparison:
  | Metric | Before | After IndusAI |
  |--------|--------|---------------|
  | Response time | 2.5 hours | ~3 minutes |
  | Support reps needed | 8 | 3 |
  | Annual labor cost | $640K | ~$240K |
  | Error rate | High (manual) | Near-zero (AI + human review) |
- Large savings callout: **"$400K/year saved"**
- Green/positive color scheme

### 8. Tech Stack
- Horizontal strip with logos/icons:
  - React, FastAPI, Neo4j, PostgreSQL, Redis, Claude AI, Voyage AI
- "Built with" label
- Subtle, clean presentation

### 9. What's Next (Roadmap)
- Timeline or checklist of upcoming features:
  - WhatsApp & Fax channels
  - ERP adapter integrations (SAP, Oracle)
  - Auto-training from human feedback loop
  - Multi-tenant deployment
  - Advanced analytics & reporting
- "Coming Soon" badges on each item

## Technical Approach

- **Frontend only** — all sections added to `Landing.tsx` or split into sub-components in `src/components/demo/`
- **Live stats** — `fetch()` calls on mount to existing API endpoints (no new backend routes)
- **Knowledge graph** — reuse existing `react-force-graph-2d` dependency and graph API endpoints
- **Animated count-up** — lightweight CSS animation or small custom hook (no new dependency)
- **No auth** — demo sections visible without login
- **Responsive** — works on laptop screen for presentation, but not mobile-optimized

## What's NOT Included

- No new backend routes or services
- No video/media embeds
- No contact forms or lead capture
- No auth wall on demo sections
- No new npm dependencies (reuse existing)
