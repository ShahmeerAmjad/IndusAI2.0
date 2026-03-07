const INTENT_CONFIG: Record<string, { label: string; color: string }> = {
  request_quote: { label: "Quote", color: "bg-blue-100 text-blue-800" },
  request_tds_sds: { label: "TDS/SDS", color: "bg-purple-100 text-purple-800" },
  place_order: { label: "Order", color: "bg-green-100 text-green-800" },
  order_status: { label: "Status", color: "bg-amber-100 text-amber-800" },
  technical_support: { label: "Technical", color: "bg-cyan-100 text-cyan-800" },
  return_complaint: { label: "Return", color: "bg-red-100 text-red-800" },
  reorder: { label: "Reorder", color: "bg-emerald-100 text-emerald-800" },
  account_inquiry: { label: "Account", color: "bg-slate-100 text-slate-800" },
  sample_request: { label: "Sample", color: "bg-orange-100 text-orange-800" },
};

interface IntentBadgeProps {
  intent: string;
  confidence?: number;
  size?: "sm" | "md";
}

export default function IntentBadge({ intent, confidence, size = "sm" }: IntentBadgeProps) {
  const config = INTENT_CONFIG[intent] || { label: intent, color: "bg-gray-100 text-gray-700" };
  const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-2.5 py-1";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium ${config.color} ${sizeClass}`}>
      {config.label}
      {confidence != null && (
        <span className="opacity-60">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
}
