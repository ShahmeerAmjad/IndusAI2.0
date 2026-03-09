import { X, ExternalLink } from "lucide-react";
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
