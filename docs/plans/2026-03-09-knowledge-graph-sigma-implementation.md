# Knowledge Graph Sigma.js Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace react-force-graph-2d with Sigma.js + Graphology (WebGL) for a dramatically better knowledge graph visualization with dark/light mode, search highlighting, clickable legend, hover tooltips, click detail panel, and full-screen `/graph` route.

**Architecture:** Shared `SigmaGraph` core component used in both full-screen page and embedded Knowledge Base tab. `useGraphData` hook fetches from existing API and builds a graphology Graph instance. ForceAtlas2 runs in a Web Worker for layout. Sigma.js nodeReducer/edgeReducer handle hover/search/filter state.

**Tech Stack:** `graphology`, `@react-sigma/core`, `@react-sigma/layout-forceatlas2`, `graphology-layout-forceatlas2`, `sigma`

---

### Task 1: Install Dependencies

**Files:**
- Modify: `package.json`

**Step 1: Install new graph libraries**

Run:
```bash
npm install graphology @react-sigma/core @react-sigma/layout-core @react-sigma/layout-forceatlas2 graphology-layout-forceatlas2 graphology-types sigma
```

**Step 2: Remove old graph libraries**

Run:
```bash
npm uninstall react-force-graph-2d neovis.js
```

**Step 3: Verify build**

Run: `npm run build`
Expected: Build succeeds (will have import errors in GraphExplorer/KnowledgeGraphDemo — that's expected, we'll fix those next)

**Step 4: Commit**

```bash
git add package.json package-lock.json
git commit -m "feat: swap graph deps — add sigma.js/graphology, remove react-force-graph-2d/neovis"
```

---

### Task 2: Create useGraphData Hook

**Files:**
- Create: `src/hooks/useGraphData.ts`

**Step 1: Write the hook**

```typescript
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Graph from "graphology";
import { api } from "@/lib/api";

export const NODE_COLORS: Record<string, string> = {
  Product: "#3b82f6",
  Manufacturer: "#10b981",
  ProductLine: "#14b8a6",
  Industry: "#f59e0b",
  TDS: "#8b5cf6",
  SDS: "#ef4444",
};

export const NODE_SIZES: Record<string, number> = {
  Product: 10,
  Manufacturer: 8,
  ProductLine: 7,
  Industry: 8,
  TDS: 5,
  SDS: 5,
};

export type NodeType = keyof typeof NODE_COLORS;

export function useGraphData(industry?: string, manufacturer?: string) {
  const { data: vizData, isLoading, error } = useQuery({
    queryKey: ["graph-viz", industry, manufacturer],
    queryFn: () => api.getGraphViz(industry || undefined, manufacturer || undefined),
  });

  const graph = useMemo(() => {
    if (!vizData) return null;

    const g = new Graph({ multi: true, type: "directed" });

    for (const node of vizData.nodes) {
      if (!g.hasNode(node.id)) {
        g.addNode(node.id, {
          label: node.name || node.id,
          size: NODE_SIZES[node.label] || 5,
          color: NODE_COLORS[node.label] || "#6b7280",
          nodeType: node.label,
          x: Math.random() * 100,
          y: Math.random() * 100,
          ...node.properties,
        });
      }
    }

    for (const edge of vizData.edges) {
      if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
        g.addEdge(edge.source, edge.target, {
          label: edge.relationship,
          size: 1,
        });
      }
    }

    return g;
  }, [vizData]);

  return { graph, isLoading, error };
}
```

**Step 2: Verify no type errors**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors in useGraphData.ts

**Step 3: Commit**

```bash
git add src/hooks/useGraphData.ts
git commit -m "feat: add useGraphData hook — transforms API data into graphology Graph"
```

---

### Task 3: Create GraphTooltip Component

**Files:**
- Create: `src/components/graph/GraphTooltip.tsx`

**Step 1: Write the tooltip component**

```tsx
import { NODE_COLORS } from "@/hooks/useGraphData";

interface GraphTooltipProps {
  nodeType: string;
  name: string;
  position: { x: number; y: number };
}

export default function GraphTooltip({ nodeType, name, position }: GraphTooltipProps) {
  const color = NODE_COLORS[nodeType] || "#6b7280";

  return (
    <div
      className="pointer-events-none absolute z-50 flex items-center gap-2 rounded-lg border border-white/10 bg-slate-900/90 px-3 py-1.5 text-sm text-white shadow-xl backdrop-blur-sm"
      style={{
        left: position.x + 12,
        top: position.y - 8,
      }}
    >
      <span
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-medium">{name}</span>
      <span className="text-xs text-slate-400">{nodeType}</span>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/graph/GraphTooltip.tsx
git commit -m "feat: add GraphTooltip — hover tooltip for graph nodes"
```

---

### Task 4: Create GraphNodePanel Component

**Files:**
- Create: `src/components/graph/GraphNodePanel.tsx`

**Step 1: Write the node detail panel**

```tsx
import { X, ExternalLink, FileText, Shield } from "lucide-react";
import { NODE_COLORS } from "@/hooks/useGraphData";

interface GraphNodePanelProps {
  nodeId: string;
  nodeType: string;
  name: string;
  properties: Record<string, unknown>;
  neighbors: Array<{ id: string; name: string; nodeType: string; relationship: string }>;
  darkMode: boolean;
  onClose: () => void;
  onNavigate: (nodeId: string) => void;
}

export default function GraphNodePanel({
  nodeType,
  name,
  properties,
  neighbors,
  darkMode,
  onClose,
  onNavigate,
}: GraphNodePanelProps) {
  const color = NODE_COLORS[nodeType] || "#6b7280";

  const bg = darkMode ? "bg-slate-900/95 border-slate-700" : "bg-white border-slate-200";
  const textPrimary = darkMode ? "text-white" : "text-slate-900";
  const textSecondary = darkMode ? "text-slate-400" : "text-slate-500";
  const divider = darkMode ? "border-slate-700" : "border-slate-200";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-50";

  // Group neighbors by relationship
  const grouped = neighbors.reduce<Record<string, typeof neighbors>>((acc, n) => {
    (acc[n.relationship] ||= []).push(n);
    return acc;
  }, {});

  return (
    <div
      className={`absolute right-0 top-0 z-40 h-full w-80 overflow-y-auto border-l shadow-2xl backdrop-blur-sm ${bg}`}
    >
      {/* Header */}
      <div className={`sticky top-0 z-10 border-b p-4 ${bg} ${divider}`}>
        <div className="flex items-start justify-between">
          <div>
            <span
              className="inline-block rounded-full px-2 py-0.5 text-xs font-medium text-white"
              style={{ backgroundColor: color }}
            >
              {nodeType}
            </span>
            <h3 className={`mt-1 text-lg font-semibold ${textPrimary}`}>{name}</h3>
          </div>
          <button
            onClick={onClose}
            className={`rounded-lg p-1 ${textSecondary} ${hoverBg}`}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Properties */}
      <div className={`border-b p-4 ${divider}`}>
        <h4 className={`mb-2 text-xs font-semibold uppercase tracking-wider ${textSecondary}`}>
          Properties
        </h4>
        <div className="space-y-1.5">
          {Object.entries(properties)
            .filter(([k]) => !["x", "y", "size", "color", "nodeType", "label"].includes(k))
            .map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className={textSecondary}>{key}</span>
                <span className={`max-w-[60%] truncate text-right ${textPrimary}`}>
                  {String(value ?? "—")}
                </span>
              </div>
            ))}
        </div>
      </div>

      {/* Related Nodes */}
      {Object.keys(grouped).length > 0 && (
        <div className="p-4">
          <h4 className={`mb-2 text-xs font-semibold uppercase tracking-wider ${textSecondary}`}>
            Relationships
          </h4>
          {Object.entries(grouped).map(([rel, nodes]) => (
            <div key={rel} className="mb-3">
              <p className={`mb-1 text-xs font-medium ${textSecondary}`}>{rel}</p>
              <div className="space-y-1">
                {nodes.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => onNavigate(n.id)}
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${textPrimary} ${hoverBg} transition`}
                  >
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: NODE_COLORS[n.nodeType] || "#6b7280" }}
                    />
                    <span className="flex-1 truncate">{n.name}</span>
                    <ExternalLink size={12} className={textSecondary} />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/graph/GraphNodePanel.tsx
git commit -m "feat: add GraphNodePanel — slide-out detail panel for clicked nodes"
```

---

### Task 5: Create GraphLegend Component

**Files:**
- Create: `src/components/graph/GraphLegend.tsx`

**Step 1: Write the legend with toggle functionality**

```tsx
import { Eye, EyeOff } from "lucide-react";
import { NODE_COLORS, type NodeType } from "@/hooks/useGraphData";

interface GraphLegendProps {
  hiddenTypes: Set<string>;
  onToggleType: (type: string) => void;
  onShowAll: () => void;
  onHideAll: () => void;
  darkMode: boolean;
}

const NODE_TYPE_LABELS: Record<string, string> = {
  Product: "Products",
  Manufacturer: "Manufacturers",
  ProductLine: "Product Lines",
  Industry: "Industries",
  TDS: "Tech Data Sheets",
  SDS: "Safety Data Sheets",
};

export default function GraphLegend({
  hiddenTypes,
  onToggleType,
  onShowAll,
  onHideAll,
  darkMode,
}: GraphLegendProps) {
  const bg = darkMode
    ? "bg-slate-900/80 border-slate-700"
    : "bg-white/90 border-slate-200";
  const text = darkMode ? "text-slate-300" : "text-slate-600";
  const textMuted = darkMode ? "text-slate-500" : "text-slate-400";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-100";

  return (
    <div
      className={`absolute bottom-4 left-4 z-30 rounded-xl border p-3 shadow-lg backdrop-blur-sm ${bg}`}
    >
      <div className="mb-2 flex items-center justify-between gap-4">
        <span className={`text-xs font-semibold uppercase tracking-wider ${textMuted}`}>
          Node Types
        </span>
        <div className="flex gap-1">
          <button
            onClick={onShowAll}
            className={`rounded px-1.5 py-0.5 text-[10px] ${text} ${hoverBg}`}
            title="Show all"
          >
            <Eye size={12} />
          </button>
          <button
            onClick={onHideAll}
            className={`rounded px-1.5 py-0.5 text-[10px] ${text} ${hoverBg}`}
            title="Hide all"
          >
            <EyeOff size={12} />
          </button>
        </div>
      </div>
      <div className="space-y-1">
        {Object.entries(NODE_COLORS).map(([type, color]) => {
          const hidden = hiddenTypes.has(type);
          return (
            <button
              key={type}
              onClick={() => onToggleType(type)}
              className={`flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-xs transition ${hoverBg} ${
                hidden ? textMuted : text
              }`}
            >
              <span
                className="inline-block h-3 w-3 rounded-full transition-opacity"
                style={{
                  backgroundColor: color,
                  opacity: hidden ? 0.25 : 1,
                }}
              />
              <span className={hidden ? "line-through" : ""}>
                {NODE_TYPE_LABELS[type] || type}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/graph/GraphLegend.tsx
git commit -m "feat: add GraphLegend — clickable type toggles with show/hide all"
```

---

### Task 6: Create GraphSearch Component

**Files:**
- Create: `src/components/graph/GraphSearch.tsx`

**Step 1: Write the search overlay**

```tsx
import { useState, useCallback, useRef, useEffect } from "react";
import { Search, X } from "lucide-react";
import { NODE_COLORS } from "@/hooks/useGraphData";

interface SearchResult {
  id: string;
  name: string;
  nodeType: string;
}

interface GraphSearchProps {
  results: SearchResult[];
  onSearch: (query: string) => void;
  onSelect: (nodeId: string) => void;
  onClear: () => void;
  darkMode: boolean;
}

export default function GraphSearch({
  results,
  onSearch,
  onSelect,
  onClear,
  darkMode,
}: GraphSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const bg = darkMode
    ? "bg-slate-900/80 border-slate-700"
    : "bg-white/90 border-slate-200";
  const text = darkMode ? "text-white" : "text-slate-900";
  const textMuted = darkMode ? "text-slate-400" : "text-slate-500";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-100";

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value);
      onSearch(value);
      setOpen(value.length > 0);
    },
    [onSearch],
  );

  const handleClear = useCallback(() => {
    setQuery("");
    onSearch("");
    onClear();
    setOpen(false);
    inputRef.current?.focus();
  }, [onSearch, onClear]);

  const handleSelect = useCallback(
    (nodeId: string) => {
      onSelect(nodeId);
      setOpen(false);
    },
    [onSelect],
  );

  return (
    <div className={`absolute left-4 top-4 z-30 w-72 rounded-xl border shadow-lg backdrop-blur-sm ${bg}`}>
      <div className="relative">
        <Search size={14} className={`absolute left-3 top-1/2 -translate-y-1/2 ${textMuted}`} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Search nodes..."
          className={`w-full rounded-xl bg-transparent py-2.5 pl-9 pr-8 text-sm focus:outline-none ${text}`}
        />
        {query && (
          <button
            onClick={handleClear}
            className={`absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 ${textMuted} ${hoverBg}`}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className={`max-h-60 overflow-y-auto border-t p-1 ${darkMode ? "border-slate-700" : "border-slate-200"}`}>
          {results.slice(0, 20).map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm ${text} ${hoverBg} transition`}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: NODE_COLORS[r.nodeType] || "#6b7280" }}
              />
              <span className="flex-1 truncate">{r.name}</span>
              <span className={`text-xs ${textMuted}`}>{r.nodeType}</span>
            </button>
          ))}
        </div>
      )}

      {open && query.length > 0 && results.length === 0 && (
        <div className={`border-t p-3 text-center text-xs ${textMuted} ${darkMode ? "border-slate-700" : "border-slate-200"}`}>
          No matching nodes
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/graph/GraphSearch.tsx
git commit -m "feat: add GraphSearch — overlay search bar with result dropdown"
```

---

### Task 7: Create GraphControls Component

**Files:**
- Create: `src/components/graph/GraphControls.tsx`

**Step 1: Write the controls overlay**

```tsx
import { ZoomIn, ZoomOut, Maximize2, Sun, Moon, RotateCcw } from "lucide-react";

interface GraphControlsProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitToScreen: () => void;
  onRestartLayout: () => void;
}

export default function GraphControls({
  darkMode,
  onToggleDarkMode,
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  onRestartLayout,
}: GraphControlsProps) {
  const bg = darkMode
    ? "bg-slate-900/80 border-slate-700"
    : "bg-white/90 border-slate-200";
  const text = darkMode ? "text-slate-300" : "text-slate-600";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-100";

  const buttons = [
    { icon: ZoomIn, label: "Zoom in", onClick: onZoomIn },
    { icon: ZoomOut, label: "Zoom out", onClick: onZoomOut },
    { icon: Maximize2, label: "Fit to screen", onClick: onFitToScreen },
    { icon: RotateCcw, label: "Restart layout", onClick: onRestartLayout },
    {
      icon: darkMode ? Sun : Moon,
      label: darkMode ? "Light mode" : "Dark mode",
      onClick: onToggleDarkMode,
    },
  ];

  return (
    <div
      className={`absolute bottom-4 right-4 z-30 flex flex-col gap-1 rounded-xl border p-1.5 shadow-lg backdrop-blur-sm ${bg}`}
    >
      {buttons.map(({ icon: Icon, label, onClick }) => (
        <button
          key={label}
          onClick={onClick}
          title={label}
          className={`rounded-lg p-2 transition ${text} ${hoverBg}`}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/graph/GraphControls.tsx
git commit -m "feat: add GraphControls — zoom, fit, dark mode toggle, restart layout"
```

---

### Task 8: Create SigmaGraph Core Component

**Files:**
- Create: `src/components/graph/SigmaGraph.tsx`

This is the main component that ties everything together.

**Step 1: Write the SigmaGraph component**

```tsx
import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import Graph from "graphology";
import {
  SigmaContainer,
  useLoadGraph,
  useRegisterEvents,
  useSigma,
} from "@react-sigma/core";
import { useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import "@react-sigma/core/lib/style.css";

import { useGraphData, NODE_COLORS } from "@/hooks/useGraphData";
import GraphTooltip from "./GraphTooltip";
import GraphNodePanel from "./GraphNodePanel";
import GraphLegend from "./GraphLegend";
import GraphSearch from "./GraphSearch";
import GraphControls from "./GraphControls";

interface SigmaGraphProps {
  industry?: string;
  manufacturer?: string;
  defaultDarkMode?: boolean;
  height?: string;
}

/* ---- Inner component: has access to sigma context ---- */
function GraphEvents({
  graph,
  darkMode,
  hiddenTypes,
  searchQuery,
  selectedNode,
  onSelectNode,
  onHoverNode,
}: {
  graph: Graph;
  darkMode: boolean;
  hiddenTypes: Set<string>;
  searchQuery: string;
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
  onHoverNode: (info: { id: string; x: number; y: number } | null) => void;
}) {
  const sigma = useSigma();
  const loadGraph = useLoadGraph();
  const registerEvents = useRegisterEvents();

  // Load graph
  useEffect(() => {
    loadGraph(graph);
  }, [graph, loadGraph]);

  // ForceAtlas2 layout
  const { start: startLayout, stop: stopLayout, isRunning } = useLayoutForceAtlas2({
    settings: {
      gravity: 1,
      scalingRatio: 2,
      slowDown: 5,
      barnesHutOptimize: true,
    },
    autoRunFor: 3000,
  });

  // Register events
  useEffect(() => {
    registerEvents({
      enterNode: ({ node, event }) => {
        const pos = sigma.viewportToFramedGraph({ x: event.x, y: event.y });
        const display = sigma.getNodeDisplayData(node);
        if (display) {
          onHoverNode({
            id: node,
            x: event.x,
            y: event.y,
          });
        }
      },
      leaveNode: () => {
        onHoverNode(null);
      },
      clickNode: ({ node }) => {
        onSelectNode(node);
      },
      clickStage: () => {
        onSelectNode(null);
      },
    });
  }, [registerEvents, sigma, onSelectNode, onHoverNode]);

  // Node/edge reducers for highlighting
  useEffect(() => {
    const lcQuery = searchQuery.toLowerCase();

    sigma.setSetting("nodeReducer", (node, data) => {
      const res = { ...data };
      const nodeType = graph.getNodeAttribute(node, "nodeType") as string;

      // Hidden types
      if (hiddenTypes.has(nodeType)) {
        res.hidden = true;
        return res;
      }

      // Search highlighting
      if (lcQuery) {
        const label = (data.label || "").toLowerCase();
        if (!label.includes(lcQuery)) {
          res.color = darkMode ? "rgba(100,116,139,0.15)" : "rgba(148,163,184,0.2)";
          res.label = "";
        } else {
          res.highlighted = true;
          res.forceLabel = true;
        }
      }

      // Hover/selection highlighting
      if (selectedNode) {
        if (node === selectedNode) {
          res.highlighted = true;
          res.forceLabel = true;
        } else if (graph.hasNode(selectedNode) && graph.areNeighbors(node, selectedNode)) {
          res.forceLabel = true;
        } else if (node !== selectedNode) {
          res.color = darkMode ? "rgba(100,116,139,0.15)" : "rgba(148,163,184,0.2)";
          res.label = "";
        }
      }

      return res;
    });

    sigma.setSetting("edgeReducer", (edge, data) => {
      const res = { ...data };

      if (selectedNode) {
        const src = graph.source(edge);
        const tgt = graph.target(edge);
        if (src !== selectedNode && tgt !== selectedNode) {
          res.hidden = true;
        } else {
          res.color = darkMode ? "rgba(148,163,184,0.6)" : "rgba(100,116,139,0.5)";
          res.size = 2;
        }
      }

      // Hide edges for hidden types
      const srcType = graph.getNodeAttribute(graph.source(edge), "nodeType") as string;
      const tgtType = graph.getNodeAttribute(graph.target(edge), "nodeType") as string;
      if (hiddenTypes.has(srcType) || hiddenTypes.has(tgtType)) {
        res.hidden = true;
      }

      return res;
    });

    sigma.refresh({ skipIndexation: true });
  }, [sigma, graph, darkMode, hiddenTypes, searchQuery, selectedNode]);

  return null;
}

/* ---- Main SigmaGraph component ---- */
export default function SigmaGraph({
  industry,
  manufacturer,
  defaultDarkMode = false,
  height = "500px",
}: SigmaGraphProps) {
  const { graph, isLoading } = useGraphData(industry, manufacturer);
  const [darkMode, setDarkMode] = useState(defaultDarkMode);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<{
    id: string;
    x: number;
    y: number;
  } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const sigmaContainerRef = useRef<any>(null);

  // Search results
  const searchResults = useMemo(() => {
    if (!graph || !searchQuery) return [];
    const lc = searchQuery.toLowerCase();
    const results: Array<{ id: string; name: string; nodeType: string }> = [];
    graph.forEachNode((node, attrs) => {
      if ((attrs.label || "").toLowerCase().includes(lc)) {
        results.push({ id: node, name: attrs.label as string, nodeType: attrs.nodeType as string });
      }
    });
    return results;
  }, [graph, searchQuery]);

  // Hovered node tooltip data
  const tooltipData = useMemo(() => {
    if (!hoveredNode || !graph) return null;
    const attrs = graph.getNodeAttributes(hoveredNode.id);
    return {
      nodeType: attrs.nodeType as string,
      name: attrs.label as string,
      position: { x: hoveredNode.x, y: hoveredNode.y },
    };
  }, [hoveredNode, graph]);

  // Selected node panel data
  const panelData = useMemo(() => {
    if (!selectedNode || !graph || !graph.hasNode(selectedNode)) return null;
    const attrs = graph.getNodeAttributes(selectedNode);
    const neighbors: Array<{
      id: string;
      name: string;
      nodeType: string;
      relationship: string;
    }> = [];
    graph.forEachEdge(selectedNode, (edge, edgeAttrs, source, target) => {
      const neighborId = source === selectedNode ? target : source;
      const neighborAttrs = graph.getNodeAttributes(neighborId);
      neighbors.push({
        id: neighborId,
        name: neighborAttrs.label as string,
        nodeType: neighborAttrs.nodeType as string,
        relationship: edgeAttrs.label as string,
      });
    });
    return { attrs, neighbors };
  }, [selectedNode, graph]);

  // Legend callbacks
  const handleToggleType = useCallback((type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const handleShowAll = useCallback(() => setHiddenTypes(new Set()), []);
  const handleHideAll = useCallback(
    () => setHiddenTypes(new Set(Object.keys(NODE_COLORS))),
    [],
  );

  // Controls callbacks
  const handleZoomIn = useCallback(() => {
    sigmaContainerRef.current?.getCamera?.()?.animatedZoom({ duration: 300 });
  }, []);
  const handleZoomOut = useCallback(() => {
    sigmaContainerRef.current?.getCamera?.()?.animatedUnzoom({ duration: 300 });
  }, []);
  const handleFitToScreen = useCallback(() => {
    sigmaContainerRef.current?.getCamera?.()?.animatedReset({ duration: 300 });
  }, []);

  // Search select => zoom to node
  const handleSearchSelect = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
    const sigma = sigmaContainerRef.current;
    if (sigma) {
      const nodePos = sigma.getNodeDisplayData?.(nodeId);
      if (nodePos) {
        sigma.getCamera?.()?.animate(
          { x: nodePos.x, y: nodePos.y, ratio: 0.15 },
          { duration: 500 },
        );
      }
    }
  }, []);

  // Navigate to node from panel
  const handleNavigate = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
    const sigma = sigmaContainerRef.current;
    if (sigma) {
      const nodePos = sigma.getNodeDisplayData?.(nodeId);
      if (nodePos) {
        sigma.getCamera?.()?.animate(
          { x: nodePos.x, y: nodePos.y, ratio: 0.15 },
          { duration: 500 },
        );
      }
    }
  }, []);

  // Restart layout placeholder (handled inside GraphEvents)
  const [layoutKey, setLayoutKey] = useState(0);
  const handleRestartLayout = useCallback(() => {
    setLayoutKey((k) => k + 1);
  }, []);

  if (isLoading || !graph) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl ${
          darkMode ? "bg-slate-900" : "bg-slate-50"
        }`}
        style={{ height }}
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-300 border-t-blue-500" />
      </div>
    );
  }

  const sigmaSettings = {
    allowInvalidContainer: true,
    renderLabels: true,
    labelRenderedSizeThreshold: 8,
    labelColor: { color: darkMode ? "#e2e8f0" : "#334155" },
    labelFont: "Inter, system-ui, sans-serif",
    labelSize: 12,
    defaultEdgeColor: darkMode ? "rgba(148,163,184,0.15)" : "#e2e8f0",
    defaultEdgeType: "arrow",
    edgeLabelFont: "Inter, system-ui, sans-serif",
    stagePadding: 30,
  };

  return (
    <div className="relative overflow-hidden rounded-xl" style={{ height }}>
      <SigmaContainer
        ref={sigmaContainerRef}
        graph={Graph}
        settings={sigmaSettings}
        className="!absolute inset-0"
        style={{
          height: "100%",
          width: "100%",
          backgroundColor: darkMode ? "#0f172a" : "#f8fafc",
        }}
      >
        <GraphEvents
          key={layoutKey}
          graph={graph}
          darkMode={darkMode}
          hiddenTypes={hiddenTypes}
          searchQuery={searchQuery}
          selectedNode={selectedNode}
          onSelectNode={setSelectedNode}
          onHoverNode={setHoveredNode}
        />
      </SigmaContainer>

      {/* Overlays */}
      <GraphSearch
        results={searchResults}
        onSearch={setSearchQuery}
        onSelect={handleSearchSelect}
        onClear={() => setSearchQuery("")}
        darkMode={darkMode}
      />

      <GraphLegend
        hiddenTypes={hiddenTypes}
        onToggleType={handleToggleType}
        onShowAll={handleShowAll}
        onHideAll={handleHideAll}
        darkMode={darkMode}
      />

      <GraphControls
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode((d) => !d)}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFitToScreen={handleFitToScreen}
        onRestartLayout={handleRestartLayout}
      />

      {/* Tooltip */}
      {tooltipData && (
        <GraphTooltip
          nodeType={tooltipData.nodeType}
          name={tooltipData.name}
          position={tooltipData.position}
        />
      )}

      {/* Node detail panel */}
      {panelData && selectedNode && (
        <GraphNodePanel
          nodeId={selectedNode}
          nodeType={panelData.attrs.nodeType as string}
          name={panelData.attrs.label as string}
          properties={panelData.attrs as Record<string, unknown>}
          neighbors={panelData.neighbors}
          darkMode={darkMode}
          onClose={() => setSelectedNode(null)}
          onNavigate={handleNavigate}
        />
      )}

      {/* Node/edge count */}
      <div
        className={`absolute right-4 top-4 z-30 rounded-lg px-3 py-1.5 text-xs backdrop-blur-sm ${
          darkMode
            ? "bg-slate-900/80 text-slate-400"
            : "bg-white/90 text-slate-500"
        }`}
      >
        {graph.order} nodes · {graph.size} edges
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -40`
Expected: No errors in graph components

**Step 3: Commit**

```bash
git add src/components/graph/SigmaGraph.tsx
git commit -m "feat: add SigmaGraph — core Sigma.js component with all overlays"
```

---

### Task 9: Replace GraphExplorer with SigmaGraph

**Files:**
- Modify: `src/components/graph/GraphExplorer.tsx`

**Step 1: Rewrite GraphExplorer to wrap SigmaGraph**

Replace the entire file contents with:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import SigmaGraph from "./SigmaGraph";

export default function GraphExplorer() {
  const [industry, setIndustry] = useState<string>("");
  const [manufacturer, setManufacturer] = useState<string>("");

  const { data: filters } = useQuery({
    queryKey: ["catalog-filters"],
    queryFn: () => api.getCatalogFilters(),
  });

  return (
    <div className="space-y-4">
      {/* Filter dropdowns */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All Industries</option>
          {(filters?.industries || []).map((ind) => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
        <select
          value={manufacturer}
          onChange={(e) => setManufacturer(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All Manufacturers</option>
          {(filters?.manufacturers || []).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* Graph */}
      <SigmaGraph
        industry={industry || undefined}
        manufacturer={manufacturer || undefined}
        defaultDarkMode={false}
        height="500px"
      />
    </div>
  );
}
```

**Step 2: Verify build**

Run: `npm run build 2>&1 | tail -20`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/components/graph/GraphExplorer.tsx
git commit -m "refactor: replace GraphExplorer internals with SigmaGraph wrapper"
```

---

### Task 10: Update KnowledgeGraphDemo on Landing Page

**Files:**
- Modify: `src/components/demo/KnowledgeGraphDemo.tsx`

**Step 1: Rewrite to use SigmaGraph**

Replace the entire file contents with:

```tsx
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Database, GitBranch } from "lucide-react";
import { api } from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";
import { NODE_COLORS } from "@/hooks/useGraphData";
import SigmaGraph from "@/components/graph/SigmaGraph";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

export default function KnowledgeGraphDemo() {
  const { data: graphStats } = useQuery({
    queryKey: ["demo-graph-stats"],
    queryFn: () => api.getGraphStats(),
  });

  const totalNodes = graphStats
    ? Object.values(graphStats.nodes).reduce((a, b) => a + b, 0)
    : 0;
  const totalEdges = graphStats
    ? Object.values(graphStats.edges).reduce((a, b) => a + b, 0)
    : 0;

  const nodeCount = useCountUp(totalNodes);
  const edgeCount = useCountUp(totalEdges);

  return (
    <section className="bg-white py-20">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-purple-100 px-4 py-1.5 text-sm font-medium text-purple-700">
            Knowledge Graph
          </span>
          <h2 className="text-3xl font-bold text-slate-900">
            Structured Intelligence, Not Chunked Documents
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            Product specs, TDS/SDS data, manufacturers, and cross-references stored as a
            connected graph in Neo4j. Property lookups, not semantic guessing.
          </p>
        </motion.div>

        {/* Stats bar */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-8 flex flex-wrap items-center justify-center gap-8"
        >
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-purple-600" />
            <span className="text-2xl font-bold text-slate-900">{nodeCount}</span>
            <span className="text-sm text-slate-500">Nodes</span>
            <span className="ml-1 flex items-center gap-1 text-[10px] text-emerald-600">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-purple-600" />
            <span className="text-2xl font-bold text-slate-900">{edgeCount}</span>
            <span className="text-sm text-slate-500">Relationships</span>
          </div>
          <div className="flex flex-wrap gap-3">
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 text-xs text-slate-500">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {type}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Graph */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={fadeIn}
        >
          <SigmaGraph defaultDarkMode={true} height="450px" />
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Verify build**

Run: `npm run build 2>&1 | tail -10`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/components/demo/KnowledgeGraphDemo.tsx
git commit -m "refactor: update KnowledgeGraphDemo to use SigmaGraph with dark mode"
```

---

### Task 11: Create Full-Screen Graph Page

**Files:**
- Create: `src/pages/GraphFullScreen.tsx`
- Modify: `src/App.tsx`
- Modify: `src/components/layout/Sidebar.tsx`

**Step 1: Create the full-screen page**

```tsx
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import SigmaGraph from "@/components/graph/SigmaGraph";

export default function GraphFullScreen() {
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 z-50 bg-slate-900">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="absolute left-4 top-4 z-50 flex items-center gap-2 rounded-xl bg-slate-900/80 border border-slate-700 px-4 py-2 text-sm text-slate-300 shadow-lg backdrop-blur-sm hover:bg-slate-800 transition"
      >
        <ArrowLeft size={16} />
        Back
      </button>

      <SigmaGraph defaultDarkMode={true} height="100vh" />
    </div>
  );
}
```

**Step 2: Add route to App.tsx**

In `src/App.tsx`, add the lazy import alongside the other lazy imports:

```tsx
const GraphFullScreen = lazy(() => import("@/pages/GraphFullScreen"));
```

Add the route inside the `<Route element={<RequireAuth />}>` block, BEFORE the `<Route element={<AppLayout />}>` (so it renders without the sidebar):

```tsx
<Route path="/graph" element={<Suspense fallback={<FullPageLoader />}><GraphFullScreen /></Suspense>} />
```

**Step 3: Add Sidebar link**

In `src/components/layout/Sidebar.tsx`, add `Share2` to the lucide-react imports:

```tsx
import { ..., Share2 } from "lucide-react";
```

Add to the "Products" section items array, after the Knowledge Base entry:

```tsx
{ to: "/graph", label: "Graph Explorer", icon: Share2 },
```

**Step 4: Verify build**

Run: `npm run build 2>&1 | tail -10`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add src/pages/GraphFullScreen.tsx src/App.tsx src/components/layout/Sidebar.tsx
git commit -m "feat: add full-screen /graph route with dark mode, sidebar link"
```

---

### Task 12: Clean Up and Final Verification

**Files:**
- Verify all changes

**Step 1: Full build test**

Run: `npm run build`
Expected: Build succeeds with no errors

**Step 2: Check for leftover react-force-graph-2d imports**

Run: `grep -r "react-force-graph-2d\|neovis" src/ --include="*.tsx" --include="*.ts"`
Expected: No results (all old imports removed)

**Step 3: Run existing frontend tests**

Run: `npm run test 2>&1 | tail -20`
Expected: All tests pass

**Step 4: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore: clean up old graph imports, verify build"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Install deps | package.json |
| 2 | useGraphData hook | src/hooks/useGraphData.ts |
| 3 | GraphTooltip | src/components/graph/GraphTooltip.tsx |
| 4 | GraphNodePanel | src/components/graph/GraphNodePanel.tsx |
| 5 | GraphLegend | src/components/graph/GraphLegend.tsx |
| 6 | GraphSearch | src/components/graph/GraphSearch.tsx |
| 7 | GraphControls | src/components/graph/GraphControls.tsx |
| 8 | SigmaGraph core | src/components/graph/SigmaGraph.tsx |
| 9 | Replace GraphExplorer | src/components/graph/GraphExplorer.tsx |
| 10 | Update KnowledgeGraphDemo | src/components/demo/KnowledgeGraphDemo.tsx |
| 11 | Full-screen page + route + sidebar | src/pages/GraphFullScreen.tsx, App.tsx, Sidebar.tsx |
| 12 | Clean up + verify | All |
