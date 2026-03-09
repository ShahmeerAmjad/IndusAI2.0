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
  useLayoutForceAtlas2({
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
        onHoverNode({
          id: node,
          x: event.x,
          y: event.y,
        });
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
  }, [registerEvents, onSelectNode, onHoverNode]);

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
        } else {
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
  const sigmaRef = useRef<any>(null);

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

  // Camera controls — access sigma via ref
  const getSigma = useCallback(() => sigmaRef.current, []);

  const handleZoomIn = useCallback(() => {
    getSigma()?.getCamera()?.animatedZoom({ duration: 300 });
  }, [getSigma]);
  const handleZoomOut = useCallback(() => {
    getSigma()?.getCamera()?.animatedUnzoom({ duration: 300 });
  }, [getSigma]);
  const handleFitToScreen = useCallback(() => {
    getSigma()?.getCamera()?.animatedReset({ duration: 300 });
  }, [getSigma]);

  // Search select => zoom to node
  const handleSearchSelect = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
    const s = getSigma();
    if (s) {
      const nodePos = s.getNodeDisplayData(nodeId);
      if (nodePos) {
        s.getCamera().animate(
          { x: nodePos.x, y: nodePos.y, ratio: 0.15 },
          { duration: 500 },
        );
      }
    }
  }, [getSigma]);

  // Navigate to node from panel
  const handleNavigate = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
    const s = getSigma();
    if (s) {
      const nodePos = s.getNodeDisplayData(nodeId);
      if (nodePos) {
        s.getCamera().animate(
          { x: nodePos.x, y: nodePos.y, ratio: 0.15 },
          { duration: 500 },
        );
      }
    }
  }, [getSigma]);

  // Restart layout
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
    defaultEdgeType: "arrow" as const,
    edgeLabelFont: "Inter, system-ui, sans-serif",
    stagePadding: 30,
  };

  return (
    <div className="relative overflow-hidden rounded-xl" style={{ height }}>
      <SigmaContainer
        ref={sigmaRef}
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
