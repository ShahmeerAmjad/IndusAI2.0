import { useState } from "react";
import { api, type SourcingResponse } from "@/lib/api";
import { Search, Package, Truck, DollarSign, AlertCircle, Loader2 } from "lucide-react";

export default function Sourcing() {
  const [query, setQuery] = useState("");
  const [qty, setQty] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SourcingResponse | null>(null);
  const [error, setError] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.searchSourcing(query, qty);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">AI Parts Sourcing</h1>
        <p className="text-sm text-slate-500 mt-1">
          Search for MRO parts using natural language. Powered by knowledge graph + AI.
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Try "SKF 6204-2RS bearing" or "25mm bore ball bearing" or "M8 bolt grade 8.8"'
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <input
          type="number"
          value={qty}
          onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
          min={1}
          className="w-20 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-center"
          title="Quantity"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
        </button>
      </form>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* AI Response */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-100 text-blue-600">
                <Package className="h-3.5 w-3.5" />
              </div>
              <span className="text-sm font-medium text-slate-900">AI Response</span>
              {result.intent && (
                <span className="ml-auto rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
                  {result.intent}
                </span>
              )}
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-700">
                {result.parts_found} parts found
              </span>
            </div>
            <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap">
              {result.response}
            </div>
          </div>

          {/* Sourcing Results Table */}
          {result.sourcing_results.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
                <h3 className="text-sm font-semibold text-slate-900">
                  Sourcing Options ({result.sourcing_results.length})
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500 uppercase">
                      <th className="px-4 py-3">Part</th>
                      <th className="px-4 py-3">Seller</th>
                      <th className="px-4 py-3 text-right">Unit Price</th>
                      <th className="px-4 py-3 text-right">Total</th>
                      <th className="px-4 py-3 text-right">In Stock</th>
                      <th className="px-4 py-3 text-right">Delivery</th>
                      <th className="px-4 py-3 text-right">Distance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.sourcing_results.map((sr, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-900">{sr.sku}</div>
                          <div className="text-xs text-slate-500">{sr.manufacturer}</div>
                        </td>
                        <td className="px-4 py-3 text-slate-700">{sr.seller_name}</td>
                        <td className="px-4 py-3 text-right font-medium">
                          <DollarSign className="inline h-3 w-3 text-slate-400" />
                          {sr.unit_price.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-slate-900">
                          ${sr.total_cost.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right">{sr.qty_available}</td>
                        <td className="px-4 py-3 text-right">
                          <Truck className="inline h-3 w-3 text-slate-400 mr-1" />
                          {sr.transit_days}d
                        </td>
                        <td className="px-4 py-3 text-right text-slate-500">
                          {sr.distance_km > 0 ? `${sr.distance_km.toFixed(0)} km` : "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
