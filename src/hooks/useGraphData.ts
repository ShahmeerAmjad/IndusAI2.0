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
