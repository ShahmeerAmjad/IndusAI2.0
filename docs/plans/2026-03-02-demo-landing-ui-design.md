# IndusAI Demo & UI Enhancement Design

**Date:** 2026-03-02
**Goal:** Prepare for co-founder live demo — showcase what's built, make the product feel premium, and prove execution quality.

---

## 1. Landing Page (New — Public)

**Route:** `/` (no auth required). Dashboard moves to `/dashboard`.

### 1.1 Navigation Bar
- Logo + "IndusAI" branding (left)
- Anchor links: Features, Tech Stack, Stats (center)
- Login / Sign Up buttons (right)

### 1.2 Hero Section
- Full-width dark gradient background (`slate-900 → industrial-900`)
- Headline: **"The Operating System for MRO Distribution"**
- Subheadline: "AI-powered sourcing, order-to-cash, and supply chain intelligence — built for industrial distributors"
- Two CTAs: "Get Started" (solid `industrial-600`) + "Explore Features" (white outline, scrolls to #features)

### 1.3 Stats Bar
Horizontal strip with key metrics:
- "100+ API Endpoints"
- "227 Tests Passing"
- "5-Stage AI Pipeline"
- "16 App Pages"
- "Full O2C + P2P"

### 1.4 Feature Cards (`#features`)
2×4 grid of cards, each with: colored icon, title, 2-3 line description, "Live" badge.

| Card | Icon | Description |
|------|------|-------------|
| AI Sourcing Engine | Search | Natural language part search, 5-stage GraphRAG pipeline, ranked by price/delivery/proximity |
| Knowledge Graph | Database | Neo4j-powered part intelligence, cross-references, specs, compatibility mapping |
| Order-to-Cash | ShoppingCart | Products, inventory, orders, quotes, invoicing, payments, RMA |
| Procure-to-Pay | Truck | Suppliers, purchase orders, goods receipts, auto-PO generation |
| Intelligence Layer | Brain | Reliability scoring, price comparison, location optimization, freshness scheduling |
| Reports & Bulk Ops | FileText | CSV/Excel/PDF reports, bulk import with validation, template downloads |
| Omnichannel | MessageSquare | Web, WhatsApp, email, SMS with escalation management |
| Multi-Tenant Auth | Shield | JWT with refresh rotation, org-scoped, role-based access |

### 1.5 Tech Stack Strip
Horizontal logo/icon display: React, FastAPI, Neo4j, PostgreSQL, Redis, Claude AI, Voyage AI

### 1.6 Footer
"IndusAI v3.0 — Built for Industrial Distribution" + copyright

---

## 2. Dashboard Upgrade (`/dashboard`)

### 2.1 Welcome Header
- "Good [morning/afternoon], [Name]" with current date
- Org name badge
- System health indicator (green/amber/red dot) from `/health/detailed`

### 2.2 KPI Cards (4-col grid)
- Keep: Revenue Today, Orders Today, Open Orders, Revenue This Month
- Add: subtle trend indicators (up/down arrows with % change)
- Unify colors to `industrial-*` palette (drop raw emerald/blue/indigo)

### 2.3 Alert Cards
- Keep 4 alerts (Low Stock, Pending Invoices, Overdue, Open RMAs)
- Red border-left for critical (overdue), amber for warnings (low stock)
- More compact layout

### 2.4 Quick Actions Bar (New)
Row of 4 action buttons between KPIs and charts:
- "Search Parts" → `/chat`
- "Create Order" → `/orders`
- "Import Data" → `/bulk-import`
- "Download Report" → opens report modal

### 2.5 Charts
- Consistent `industrial-*` / `tech-*` color scheme
- Proper chart titles and axis labels
- Revenue trend: add subtle area fill under line
- Bar chart: gradient blue/teal fills

### 2.6 Recent Table + Pie
- Tighter table rows, industrial palette for pie chart colors

---

## 3. AI Sourcing Chat — Premium Upgrade (`/chat`)

### 3.1 Welcome State
When no messages:
- Centered IndusAI logo
- "What part are you looking for?"
- 4-6 suggested query pills (e.g., "Find SKF 6205-2RS bearings", "Compare hydraulic filters")

### 3.2 Message Bubbles
- User: `industrial-600` blue, slight shadow
- Assistant: white with subtle border + shadow (not flat gray)
- Smooth fade-in animation on new messages

### 3.3 Streaming Text Effect
- Assistant responses appear word-by-word (typewriter animation)
- Gives "AI thinking in real-time" feel

### 3.4 AI "Thinking" Stages
During search, show staged progress:
1. "Analyzing your query..." (brain icon)
2. "Searching knowledge graph..." (database icon)
3. "Matching sellers..." (building icon)
4. "Ranking results..." (chart icon)

Each stage animates in sequence over 1-2 seconds.

### 3.5 Dark Mode Toggle
- Chat-only dark theme (not app-wide)
- Dark background with glowing blue accents for AI responses
- Result cards pop against dark background

### 3.6 Side Panel — Order & Query History
Right-side collapsible panel (slide-in/out):
- **Recent Orders**: last 5 orders with status pills, clickable
- **Past Queries**: recent searches, click to re-run
- Toggle via panel icon in chat header
- Auto-hides on screens < 1024px

### 3.7 Rich Result Cards
- Reliability score as visual gauge (arc/ring)
- Award badges: "Best Price" / "Fastest Delivery" / "Closest" on qualifying results
- Expandable section showing cross-references and alternative parts
- Rank #1 card gets gradient header bar
- Better visual separation between price/delivery/stock
- Stock indicator: green filled bar for in-stock, amber for low

### 3.8 Comparison Table
- Auto-expand when 2+ results (no toggle needed)
- Smooth animation on expand
- Column sorting support

### 3.9 Order Confirmation
- Checkmark animation
- Order details card with ID and summary (not just a green box)

### 3.10 Input Area
- Subtle inner glow on focus
- Cmd+Enter to send (in addition to Enter)

### 3.11 Typing Indicator
- "IndusAI is searching..." with animated search icon (replaces bouncing dots)

---

## 4. Cross-Page Consistency

### 4.1 Color Unification
Replace all raw `blue-*`, `gray-*`, `emerald-*` with defined `industrial-*`, `tech-*`, `neutral-*` palette across all 16 pages.

### 4.2 Header Page Titles
Fix `PAGE_TITLES` map to include all routes: `/sourcing`, `/bulk-import`, `/products/:id`, `/orders/:id`.

### 4.3 Remove Duplicate Sourcing Page
Delete `Sourcing.tsx` — Chat.tsx is the single AI sourcing surface. Remove route and sidebar entry.

### 4.4 Sidebar Branding
- Update from "MRO Platform v3.0" to "IndusAI" with proper logo
- Update footer text from "Agentic Back-Office OS" to match landing page branding

### 4.5 Table Consistency
Standardize across all pages:
- Same dark header row style
- Same hover states (subtle row highlight)
- Same pagination component

### 4.6 Card Consistency
Standardize border-radius, shadow, padding, and hover effects across all pages.

---

## 5. Responsive Polish

### 5.1 Sidebar Collapse
- `< 1024px`: Icons-only mode (40px wide) with tooltip labels on hover
- `< 768px`: Slide-out hamburger menu

### 5.2 Dashboard Grid
- Desktop: 4-col KPIs, 2-col charts
- Tablet: 2-col KPIs, 1-col charts
- Mobile: 1-col everything

### 5.3 Chat Responsive
- Full-height on all screen sizes
- Side panel auto-hides on < 1024px, toggle button visible
- Result cards stack vertically on mobile

### 5.4 Tables
- Horizontal scroll wrapper on mobile
- Priority columns (name, status, amount) pinned; secondary columns scroll

---

## Files Affected

### New Files
- `src/pages/Landing.tsx` — Public landing page

### Modified Files
- `src/App.tsx` — Route changes (/ → Landing, /dashboard → Dashboard)
- `src/pages/Dashboard.tsx` — Welcome header, quick actions, color polish, trends
- `src/pages/Chat.tsx` — Premium overhaul (streaming, dark mode, stages, side panel)
- `src/components/sourcing/ResultCard.tsx` — Rich cards (gauge, badges, expandable)
- `src/components/sourcing/ComparisonTable.tsx` — Auto-expand, sorting
- `src/components/layout/Sidebar.tsx` — Branding, responsive collapse
- `src/components/layout/Header.tsx` — Fix page titles
- `src/components/layout/AppLayout.tsx` — Responsive sidebar support
- `src/index.css` — Dark mode chat styles, new animations
- `tailwind.config.ts` — Any new utility classes needed
- All page files — Color palette unification

### Deleted Files
- `src/pages/Sourcing.tsx` — Redundant with Chat.tsx
