import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Database,
  GitBranch,
  RefreshCw,
  ShieldCheck,
  Clock,
  ShoppingCart,
  AlertTriangle,
} from "lucide-react";

interface GraphStats {
  nodes: Record<string, number>;
  edges: Record<string, number>;
  error?: string;
}

interface SellerFreshness {
  total_listings: number;
  stale_listings: number;
  fresh_listings: number;
  sellers: Array<{
    name: string;
    listings: number;
    stale_count: number;
    last_verified: string | null;
  }>;
}

interface SourcingQuery {
  id: string;
  query: string;
  intent: string | null;
  parts_found: number;
  user_email: string | null;
  org_name: string | null;
  created_at: string | null;
}

interface ReliabilityData {
  average_reliability: number;
  distribution: Array<{ bucket: string; count: number; avg_score: number }>;
}

interface SourcingOrder {
  id: string;
  seller_name: string;
  sku: string;
  qty: number;
  unit_price: number;
  total: number;
  status: string;
  user_email: string | null;
  org_name: string | null;
  created_at: string | null;
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "slate",
}: {
  icon: typeof Database;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  const colors: Record<string, string> = {
    slate: "bg-slate-100 text-slate-600",
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    amber: "bg-amber-100 text-amber-600",
    red: "bg-red-100 text-red-600",
  };
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg",
            colors[color] || colors.slate,
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs text-slate-500">{label}</p>
          <p className="text-lg font-bold text-slate-900">{value}</p>
          {sub && <p className="text-[10px] text-slate-400">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

export default function AdminDebug() {
  const { data: graphStats, isLoading: graphLoading } = useQuery<GraphStats>({
    queryKey: ["admin", "graph-stats"],
    queryFn: () => api.adminGraphStats(),
  });

  const { data: freshness, isLoading: freshnessLoading } =
    useQuery<SellerFreshness>({
      queryKey: ["admin", "freshness"],
      queryFn: () => api.adminSellerFreshness(),
    });

  const { data: reliability } = useQuery<ReliabilityData>({
    queryKey: ["admin", "reliability"],
    queryFn: () => api.adminReliabilityScores(),
  });

  const { data: recentQueries } = useQuery<SourcingQuery[]>({
    queryKey: ["admin", "recent-sourcing"],
    queryFn: () => api.adminRecentSourcing(),
  });

  const { data: recentOrders } = useQuery<SourcingOrder[]>({
    queryKey: ["admin", "recent-orders"],
    queryFn: () => api.adminRecentOrders(),
  });

  const totalNodes = graphStats
    ? Object.values(graphStats.nodes).reduce((a, b) => a + b, 0)
    : 0;
  const totalEdges = graphStats
    ? Object.values(graphStats.edges).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          icon={Database}
          label="Graph Nodes"
          value={graphLoading ? "..." : totalNodes}
          sub={
            graphStats
              ? Object.entries(graphStats.nodes)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ")
              : undefined
          }
          color="blue"
        />
        <StatCard
          icon={GitBranch}
          label="Graph Edges"
          value={graphLoading ? "..." : totalEdges}
          sub={
            graphStats
              ? Object.entries(graphStats.edges)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(", ")
              : undefined
          }
          color="green"
        />
        <StatCard
          icon={RefreshCw}
          label="Fresh Listings"
          value={freshnessLoading ? "..." : freshness?.fresh_listings ?? 0}
          sub={`${freshness?.stale_listings ?? 0} stale of ${freshness?.total_listings ?? 0}`}
          color={
            freshness && freshness.stale_listings > freshness.fresh_listings
              ? "red"
              : "green"
          }
        />
        <StatCard
          icon={ShieldCheck}
          label="Avg Reliability"
          value={reliability?.average_reliability ?? "—"}
          sub="across all listings"
          color="amber"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Graph nodes breakdown */}
        {graphStats && !graphStats.error && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Graph Node Types
            </h3>
            <div className="space-y-2">
              {Object.entries(graphStats.nodes)
                .sort((a, b) => b[1] - a[1])
                .map(([label, count]) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="text-xs text-slate-600">{label}</span>
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-industrial-500"
                          style={{
                            width: `${Math.min(100, (count / totalNodes) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="w-10 text-right text-xs font-medium text-slate-900">
                        {count}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Reliability distribution */}
        {reliability && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Reliability Score Distribution
            </h3>
            <div className="space-y-3">
              {reliability.distribution.map((d) => (
                <div key={d.bucket} className="flex items-center justify-between">
                  <span className="text-xs text-slate-600">{d.bucket}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-900">
                      {d.count} listings
                    </span>
                    <span className="text-[10px] text-slate-400">
                      avg {d.avg_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Seller Freshness */}
        {freshness && freshness.sellers.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-900">
              Seller Listing Freshness
            </h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2 font-medium">Seller</th>
                  <th className="pb-2 font-medium">Listings</th>
                  <th className="pb-2 font-medium">Stale</th>
                  <th className="pb-2 font-medium">Last Verified</th>
                </tr>
              </thead>
              <tbody>
                {freshness.sellers.map((s) => (
                  <tr key={s.name} className="border-b last:border-0">
                    <td className="py-2 font-medium text-slate-900">{s.name}</td>
                    <td className="py-2 text-slate-700">{s.listings}</td>
                    <td className="py-2">
                      <span
                        className={cn(
                          "font-medium",
                          s.stale_count > 0 ? "text-amber-600" : "text-green-600",
                        )}
                      >
                        {s.stale_count}
                      </span>
                    </td>
                    <td className="py-2 text-slate-500">
                      {s.last_verified
                        ? new Date(s.last_verified).toLocaleDateString()
                        : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Recent sourcing queries */}
        {recentQueries && recentQueries.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Clock className="h-4 w-4 text-slate-400" />
              Recent Sourcing Queries
            </h3>
            <div className="max-h-64 overflow-y-auto space-y-2">
              {recentQueries.slice(0, 20).map((q) => (
                <div
                  key={q.id}
                  className="flex items-start justify-between rounded-lg bg-slate-50 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-900">
                      {q.query}
                    </p>
                    <p className="text-[10px] text-slate-400">
                      {q.intent || "unknown"} — {q.parts_found} parts
                      {q.user_email && ` — ${q.user_email}`}
                    </p>
                  </div>
                  <span className="shrink-0 text-[10px] text-slate-400">
                    {q.created_at
                      ? new Date(q.created_at).toLocaleTimeString()
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recent orders */}
      {recentOrders && recentOrders.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
            <ShoppingCart className="h-4 w-4 text-slate-400" />
            Recent Sourcing Orders
          </h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="pb-2 font-medium">SKU</th>
                <th className="pb-2 font-medium">Seller</th>
                <th className="pb-2 font-medium">Qty</th>
                <th className="pb-2 font-medium">Total</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">User</th>
                <th className="pb-2 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentOrders.slice(0, 20).map((o) => (
                <tr key={o.id} className="border-b last:border-0">
                  <td className="py-2 font-medium text-slate-900">{o.sku}</td>
                  <td className="py-2 text-slate-700">{o.seller_name}</td>
                  <td className="py-2 text-slate-700">{o.qty}</td>
                  <td className="py-2 font-medium text-slate-900">
                    ${o.total.toFixed(2)}
                  </td>
                  <td className="py-2">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-medium",
                        o.status === "confirmed"
                          ? "bg-green-100 text-green-700"
                          : "bg-slate-100 text-slate-600",
                      )}
                    >
                      {o.status}
                    </span>
                  </td>
                  <td className="py-2 text-slate-500">{o.user_email || "—"}</td>
                  <td className="py-2 text-slate-500">
                    {o.created_at
                      ? new Date(o.created_at).toLocaleTimeString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!graphStats && !freshness && !recentQueries && (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <AlertTriangle className="mb-3 h-10 w-10" />
          <p className="text-sm">No debug data available yet.</p>
          <p className="text-xs">Services may still be initializing.</p>
        </div>
      )}
    </div>
  );
}
