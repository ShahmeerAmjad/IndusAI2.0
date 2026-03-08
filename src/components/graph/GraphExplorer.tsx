import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "@/lib/api";
import { Search } from "lucide-react";

const NODE_COLORS: Record<string, string> = {
  Product: "#1e3a8a",
  Manufacturer: "#059669",
  ProductLine: "#0d9488",
  Industry: "#f59e0b",
  TDS: "#7c3aed",
  SDS: "#dc2626",
};

const NODE_SIZES: Record<string, number> = {
  Product: 8,
  Manufacturer: 6,
  ProductLine: 6,
  Industry: 6,
  TDS: 4,
  SDS: 4,
};

type GraphNode = {
  id: string;
  label: string;
  name: string;
  color: string;
  properties: Record<string, unknown>;
};
type GraphEdge = { source: string; target: string; relationship: string };

export default function GraphExplorer() {
  const [industry, setIndustry] = useState<string>("");
  const [manufacturer, setManufacturer] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [depth, setDepth] = useState<"products" | "products+docs" | "full">("full");
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: vizData, isLoading } = useQuery({
    queryKey: ["graph-viz", industry, manufacturer],
    queryFn: () => api.getGraphViz(industry || undefined, manufacturer || undefined),
  });

  const { data: industries } = useQuery({
    queryKey: ["industries"],
    queryFn: () => api.getIndustries(),
  });

  // Filter nodes by depth
  const filteredData = useCallback(() => {
    if (!vizData) return { nodes: [], links: [] };
    let nodes = vizData.nodes as GraphNode[];
    let edges = vizData.edges as GraphEdge[];

    if (depth === "products") {
      nodes = nodes.filter((n) => n.label === "Product");
      const nodeIds = new Set(nodes.map((n) => n.id));
      edges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    } else if (depth === "products+docs") {
      nodes = nodes.filter((n) => ["Product", "TDS", "SDS"].includes(n.label));
      const nodeIds = new Set(nodes.map((n) => n.id));
      edges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    }

    return {
      nodes,
      links: edges.map((e) => ({ source: e.source, target: e.target, label: e.relationship })),
    };
  }, [vizData, depth]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as GraphNode);
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 500);
      graphRef.current.zoom(3, 500);
    }
  }, []);

  const handleNodeDoubleClick = useCallback((node: any) => {
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 300);
      graphRef.current.zoom(5, 300);
    }
  }, []);

  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height: Math.max(height, 400) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const graphData = filteredData();

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select value={industry} onChange={(e) => setIndustry(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Industries</option>
          {(industries || []).map((ind: string) => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
        <select value={depth} onChange={(e) => setDepth(e.target.value as any)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="full">Full Graph</option>
          <option value="products+docs">Products + Documents</option>
          <option value="products">Products Only</option>
        </select>
        <span className="text-xs text-gray-500">
          {graphData.nodes.length} nodes &middot; {graphData.links.length} edges
        </span>
      </div>

      {/* Graph */}
      <div ref={containerRef} className="border rounded-lg bg-gray-50 relative" style={{ height: 500 }}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-gray-400">Loading graph...</div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            nodeLabel={(node: any) => `${node.label}: ${node.name}`}
            nodeColor={(node: any) => NODE_COLORS[node.label] || "#666"}
            nodeVal={(node: any) => NODE_SIZES[node.label] || 4}
            linkLabel={(link: any) => link.label}
            linkColor={() => "#d1d5db"}
            linkDirectionalArrowLength={3}
            onNodeClick={handleNodeClick}
            onNodeDblClick={handleNodeDoubleClick}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              if (globalScale < 1.5) return; // Hide labels when zoomed out
              const label = node.name?.substring(0, 25) || "";
              const fontSize = 10 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "#374151";
              ctx.fillText(label, node.x, node.y + 10 / globalScale);
            }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {Object.entries(NODE_COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Selected node panel */}
      {selectedNode && (
        <div className="border rounded-lg p-4 bg-white shadow-sm">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-medium px-2 py-0.5 rounded"
                style={{ backgroundColor: NODE_COLORS[selectedNode.label] + "20",
                         color: NODE_COLORS[selectedNode.label] }}>
                {selectedNode.label}
              </span>
              <h3 className="font-semibold mt-1">{selectedNode.name}</h3>
            </div>
            <button onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600 text-sm">&times;</button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-1 text-sm">
            {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
              <div key={k}>
                <span className="text-gray-500">{k}:</span>{" "}
                <span>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
