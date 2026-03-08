import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type GraphVizData } from "@/lib/api";
import { Network } from "lucide-react";

export default function GraphExplorer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [industry, setIndustry] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<Record<string, unknown> | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["graph-viz", industry],
    queryFn: () => api.getGraphViz(industry || undefined),
  });

  useEffect(() => {
    if (!data || !containerRef.current) return;
    renderGraph(data);
  }, [data]);

  const renderGraph = (vizData: GraphVizData) => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = "";
    const canvas = document.createElement("canvas");
    canvas.width = container.clientWidth;
    canvas.height = 500;
    container.appendChild(canvas);

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const nodes = vizData.nodes.map((n, i) => ({
      ...n,
      x: Math.cos((i / vizData.nodes.length) * Math.PI * 2) * 200 + canvas.width / 2,
      y: Math.sin((i / vizData.nodes.length) * Math.PI * 2) * 200 + canvas.height / 2,
      radius: n.label === "Product" ? 20 : 14,
    }));

    const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

    // Simple force simulation
    for (let iter = 0; iter < 50; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 2000 / (dist * dist);
          nodes[i].x -= (dx / dist) * force;
          nodes[i].y -= (dy / dist) * force;
          nodes[j].x += (dx / dist) * force;
          nodes[j].y += (dy / dist) * force;
        }
      }
      for (const edge of vizData.edges) {
        const s = nodeMap[edge.source];
        const t = nodeMap[edge.target];
        if (!s || !t) continue;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const force = (dist - 120) * 0.01;
        s.x += (dx / dist) * force;
        s.y += (dy / dist) * force;
        t.x -= (dx / dist) * force;
        t.y -= (dy / dist) * force;
      }
      for (const n of nodes) {
        n.x += (canvas.width / 2 - n.x) * 0.01;
        n.y += (canvas.height / 2 - n.y) * 0.01;
      }
    }

    // Draw edges
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    for (const edge of vizData.edges) {
      const s = nodeMap[edge.source];
      const t = nodeMap[edge.target];
      if (!s || !t) continue;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      ctx.fillStyle = "#94a3b8";
      ctx.font = "9px sans-serif";
      ctx.fillText(edge.relationship, (s.x + t.x) / 2, (s.y + t.y) / 2 - 4);
    }

    // Draw nodes
    for (const node of nodes) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#1e293b";
      ctx.font = "bold 10px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(node.name.substring(0, 20), node.x, node.y + node.radius + 14);
      ctx.fillStyle = node.color;
      ctx.font = "8px sans-serif";
      ctx.fillText(node.label, node.x, node.y + node.radius + 24);
    }

    canvas.onclick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      for (const node of nodes) {
        const dx = mx - node.x;
        const dy = my - node.y;
        if (dx * dx + dy * dy < node.radius * node.radius) {
          setSelectedNode(node.properties);
          return;
        }
      }
      setSelectedNode(null);
    };
  };

  const INDUSTRIES = [
    "", "Adhesives", "Coatings", "Pharma", "Personal Care",
    "Water Treatment", "Plastics", "Energy",
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Network size={18} className="text-purple-600" />
          <h3 className="text-lg font-bold text-slate-800">Knowledge Graph Explorer</h3>
        </div>
        <select value={industry} onChange={(e) => setIndustry(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
          <option value="">All Industries</option>
          {INDUSTRIES.filter(Boolean).map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-3 text-xs">
        {[
          { label: "Product", color: "#1e3a8a" },
          { label: "TDS", color: "#7c3aed" },
          { label: "SDS", color: "#dc2626" },
          { label: "Industry", color: "#f59e0b" },
          { label: "ProductLine", color: "#0d9488" },
          { label: "Manufacturer", color: "#059669" },
        ].map(({ label, color }) => (
          <span key={label} className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
            {label}
          </span>
        ))}
      </div>

      <div ref={containerRef}
        className="relative min-h-[500px] rounded-xl border border-slate-200 bg-slate-50">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-purple-600" />
          </div>
        )}
        {!isLoading && (!data || data.nodes.length === 0) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
            <Network size={40} className="mb-3" />
            <p>No graph data yet. Run ingestion to populate.</p>
          </div>
        )}
      </div>

      {selectedNode && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-700">Node Properties</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(selectedNode).map(([k, v]) => (
              <div key={k} className="rounded bg-slate-50 px-2 py-1">
                <span className="text-slate-400">{k}: </span>
                <span className="font-medium text-slate-700">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
