# Knowledge Graph Visualization — Sigma.js Refactor Design

**Date:** 2026-03-09
**Status:** Approved
**Inspiration:** GitNexus (Sigma.js + Graphology + ForceAtlas2)

## Overview

Replace `react-force-graph-2d` (Canvas) with **Sigma.js + Graphology** (WebGL) for the knowledge graph visualization. Add dark/light mode toggle, search-driven highlighting, clickable legend filters, hover tooltips, click detail panel, and a full-screen `/graph` route.

## Architecture

### Component Hierarchy

```
src/components/graph/
├── SigmaGraph.tsx          # Core graph — wraps @react-sigma/core
├── GraphControls.tsx        # Zoom, fit, layout toggle, dark/light switch
├── GraphLegend.tsx          # Clickable legend — toggles node types on/off
├── GraphSearch.tsx          # Search bar — highlights matching nodes
├── GraphNodePanel.tsx       # Slide-out detail panel on node click
├── GraphTooltip.tsx         # Hover tooltip (name + type)
└── useGraphData.ts          # Hook — fetches from API, builds graphology instance

src/pages/
├── GraphFullScreen.tsx      # Full-screen /graph route
└── KnowledgeBase.tsx        # Existing page — embedded SigmaGraph in tab
```

### Key Libraries
- `graphology` — graph data structure
- `@react-sigma/core` — React wrapper for Sigma.js
- `graphology-layout-forceatlas2` — ForceAtlas2 in Web Worker
- **Remove:** `react-force-graph-2d`, `neovis.js`

### Data Flow
```
API (/api/v1/knowledge-base/graph-viz)
  → useGraphData hook
    → graphology.Graph instance (nodes + edges)
      → ForceAtlas2 layout (Web Worker)
        → Sigma.js WebGL renderer
          → GraphControls / GraphLegend / GraphSearch overlay
```

## Visual Design

### Dark Mode (Default for full-screen)
- Background: `#0f172a` (slate-900)
- Nodes: bright colors with subtle glow effect (Sigma.js node halo program)
- Edges: `rgba(148, 163, 184, 0.15)` (faint slate)
- Labels: white, shown above a zoom threshold
- Selected node: pulsing ring + brighter color

### Light Mode (Default for embedded)
- Background: `#f8fafc` (slate-50)
- Nodes: solid colors (same palette, slightly muted)
- Edges: `#e2e8f0` (slate-200)
- Labels: `#334155` (slate-700)
- Selected node: darker ring

### Node Color Palette (shared)
| Type | Color | Size |
|------|-------|------|
| Product | `#3b82f6` (blue-500) | 10 |
| Manufacturer | `#10b981` (emerald-500) | 8 |
| ProductLine | `#14b8a6` (teal-500) | 7 |
| Industry | `#f59e0b` (amber-500) | 8 |
| TDS | `#8b5cf6` (violet-500) | 5 |
| SDS | `#ef4444` (red-500) | 5 |

### Hover State
- Node enlarges 1.5x
- Tooltip appears: type badge + name
- Connected edges brighten, non-connected nodes fade to 20% opacity

### Click State
- Node gets a highlight ring
- Neighbor nodes stay bright, everything else fades
- Side panel slides in from right with properties, related nodes, TDS/SDS links

### ForceAtlas2 Layout
- `gravity: 1`, `scalingRatio: 2`, `slowDown: 5`
- Runs in Web Worker, auto-stops after convergence
- Products cluster naturally around their Manufacturer nodes

## Interactions & Features

### Search Bar (top-left overlay)
- As you type, matching nodes highlight (name/SKU/CAS# match)
- Non-matching nodes fade to 20% opacity
- Press Enter or click a result to zoom-to-fit the matched node
- Clear search restores full graph

### Legend (bottom-left overlay)
- Color dots with labels for each node type
- Click a type to toggle visibility (hidden nodes + their edges disappear)
- Dimmed dot = hidden type
- "Show All" / "Hide All" shortcuts

### Controls (bottom-right overlay)
- Zoom in / Zoom out / Fit-to-screen buttons
- Dark/light toggle (sun/moon icon)
- "Restart Layout" button (re-runs ForceAtlas2)

### Node Detail Panel (right side, 320px)
- Slides in on click
- Header: type badge + node name
- Body sections vary by type:
  - **Product:** SKU, CAS#, description, manufacturer link, industry tags, TDS/SDS download links
  - **Manufacturer:** name, product count, list of products (clickable → navigates graph)
  - **Industry:** name, product count
  - **TDS/SDS:** revision date, key fields, link to parent product
- Clicking a related node in the panel navigates the graph to that node

### Full-Screen Page (`/graph`)
- No sidebar, graph fills viewport
- Floating overlays for search, legend, controls
- Back button → returns to previous page
- Default: dark mode

### Embedded in Knowledge Base
- Same `SigmaGraph` component, constrained to tab height (~500px)
- Default: light mode (matches page)
- Industry/manufacturer dropdowns remain above the graph
- Depth filter removed (legend toggles replace it)

## Migration

1. Install `graphology`, `@react-sigma/core`, `graphology-layout-forceatlas2`
2. Remove `react-force-graph-2d` and `neovis.js`
3. Build `SigmaGraph` core + overlay components
4. Replace `GraphExplorer.tsx` internals
5. Update `KnowledgeGraphDemo.tsx` on Landing page
6. Add `/graph` full-screen route + Sidebar link

## Testing
- Visual smoke tests — dark/light, hover, click, search, legend toggles
- Unit tests for `useGraphData` hook — data transformation
- Existing KB route tests remain valid (no API changes)

## No Backend Changes
- Existing `/api/v1/knowledge-base/graph-viz` endpoint unchanged
- `useGraphData` transforms `{nodes, edges}` → `graphology.Graph`
