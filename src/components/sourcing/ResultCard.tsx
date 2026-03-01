import { Package, Truck, MapPin, Building2, ShoppingCart, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SourcingResult } from "@/lib/api";

interface ResultCardProps {
  result: SourcingResult;
  qty: number;
  rank: number;
  onOrder: (result: SourcingResult) => void;
  onRequestQuote: (result: SourcingResult) => void;
  orderLoading?: boolean;
}

export default function ResultCard({
  result,
  qty,
  rank,
  onOrder,
  onRequestQuote,
  orderLoading,
}: ResultCardProps) {
  const totalCost = result.unit_price * qty + result.shipping_cost;
  const inStock = result.qty_available >= qty;

  return (
    <div
      className={cn(
        "rounded-xl border bg-white p-4 shadow-sm transition-shadow hover:shadow-md",
        rank === 1
          ? "border-industrial-300 ring-1 ring-industrial-200"
          : "border-gray-200",
      )}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {rank === 1 && (
              <span className="shrink-0 rounded-full bg-industrial-100 px-2 py-0.5 text-[10px] font-bold text-industrial-700 uppercase tracking-wide">
                Best Match
              </span>
            )}
            <h3 className="truncate text-sm font-semibold text-slate-900">
              {result.name}
            </h3>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            SKU: {result.sku}
            {result.manufacturer && ` | ${result.manufacturer}`}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-lg font-bold text-slate-900">
            ${result.unit_price.toFixed(2)}
          </p>
          <p className="text-[10px] text-slate-400">per unit</p>
        </div>
      </div>

      {/* Seller + meta row */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Building2 className="h-3.5 w-3.5 text-slate-400" />
          <span className="truncate">{result.seller_name}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Truck className="h-3.5 w-3.5 text-slate-400" />
          <span>{result.transit_days}d delivery</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Package className="h-3.5 w-3.5 text-slate-400" />
          <span className={inStock ? "text-green-600" : "text-amber-600"}>
            {inStock ? `${result.qty_available} avail` : "Low stock"}
          </span>
        </div>
        {result.distance_km != null && (
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <MapPin className="h-3.5 w-3.5 text-slate-400" />
            <span>{Math.round(result.distance_km)} km</span>
          </div>
        )}
      </div>

      {/* Cost summary */}
      <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
        <div className="text-xs text-slate-500">
          {qty} x ${result.unit_price.toFixed(2)} + ${result.shipping_cost.toFixed(2)} shipping
        </div>
        <div className="text-sm font-bold text-slate-900">
          ${totalCost.toFixed(2)}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onOrder(result)}
          disabled={orderLoading || !inStock}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-industrial-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-industrial-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ShoppingCart className="h-3.5 w-3.5" />
          Order Now
        </button>
        <button
          onClick={() => onRequestQuote(result)}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <FileText className="h-3.5 w-3.5" />
          Request Quote
        </button>
      </div>
    </div>
  );
}
