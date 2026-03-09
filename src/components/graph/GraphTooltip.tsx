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
