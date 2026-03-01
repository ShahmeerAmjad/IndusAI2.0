import type { SourcingResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ComparisonTableProps {
  results: SourcingResult[];
  qty: number;
}

export default function ComparisonTable({ results, qty }: ComparisonTableProps) {
  if (results.length < 2) return null;

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-slate-50 text-left text-slate-500">
            <th className="px-3 py-2.5 font-medium">Seller</th>
            <th className="px-3 py-2.5 font-medium">Unit Price</th>
            <th className="px-3 py-2.5 font-medium">Total ({qty} qty)</th>
            <th className="px-3 py-2.5 font-medium">Delivery</th>
            <th className="px-3 py-2.5 font-medium">Stock</th>
            <th className="px-3 py-2.5 font-medium">Distance</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const total = r.unit_price * qty + r.shipping_cost;
            return (
              <tr
                key={`${r.sku}-${r.seller_name}`}
                className={cn(
                  "border-b last:border-0",
                  i === 0 && "bg-industrial-50/50",
                )}
              >
                <td className="px-3 py-2 font-medium text-slate-900">
                  {i === 0 && (
                    <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-industrial-500" />
                  )}
                  {r.seller_name}
                </td>
                <td className="px-3 py-2 text-slate-700">
                  ${r.unit_price.toFixed(2)}
                </td>
                <td className="px-3 py-2 font-semibold text-slate-900">
                  ${total.toFixed(2)}
                </td>
                <td className="px-3 py-2 text-slate-700">
                  {r.transit_days}d
                </td>
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      "font-medium",
                      r.qty_available >= qty
                        ? "text-green-600"
                        : "text-amber-600",
                    )}
                  >
                    {r.qty_available}
                  </span>
                </td>
                <td className="px-3 py-2 text-slate-700">
                  {r.distance_km != null
                    ? `${Math.round(r.distance_km)} km`
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
