import { Eye, EyeOff } from "lucide-react";
import { NODE_COLORS } from "@/hooks/useGraphData";

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
