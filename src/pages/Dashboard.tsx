import { useQuery } from "@tanstack/react-query";
import { api, type InboxStats, type DashboardMetrics } from "@/lib/api";
import { formatCurrency, formatNumber, cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Link } from "react-router-dom";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  Inbox, Clock, Users, Zap, TrendingUp, FileText, MessageSquare,
  Activity, ArrowRight,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const CHART_COLORS = ["#1e3a8a", "#0284c7", "#0d9488", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];
const PIE_COLORS = ["#1e3a8a", "#0284c7", "#0d9488", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];

interface KpiCardProps {
  label: string;
  value: string;
  subtext?: string;
  icon: LucideIcon;
  color: string;
  iconBg: string;
}

function KpiCard({ label, value, subtext, icon: Icon, color, iconBg }: KpiCardProps) {
  return (
    <div className={cn("rounded-xl border border-slate-200 border-l-4 bg-white p-5 shadow-sm", color)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
          {subtext && <p className="mt-1 text-xs text-slate-400">{subtext}</p>}
        </div>
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", iconBg)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
      {label && <p className="mb-1 text-xs font-medium text-slate-500">{label}</p>}
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-semibold text-slate-800">{formatNumber(entry.value)}</p>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["inbox-stats"],
    queryFn: api.getInboxStats,
    refetchInterval: 30_000,
  });

  const { data: metrics } = useQuery<DashboardMetrics>({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
    refetchInterval: 60_000,
  });

  // Derived data from inbox stats
  const totalMessages = stats?.total ?? 0;
  const byStatus = stats?.by_status ?? [];
  const byIntent = stats?.by_intent ?? [];

  const newCount = byStatus.find((s) => s.status === "new")?.count ?? 0;
  const classifiedCount = byStatus.find((s) => s.status === "classified")?.count ?? 0;
  const approvedCount = byStatus.find((s) => s.status === "approved")?.count ?? 0;
  const escalatedCount = byStatus.find((s) => s.status === "escalated")?.count ?? 0;

  // AI accuracy estimate (approved / (approved + escalated))
  const totalResolved = approvedCount + escalatedCount;
  const aiAccuracy = totalResolved > 0 ? Math.round((approvedCount / totalResolved) * 100) : 0;

  // Estimated hours saved (approx 5 min per auto-handled message)
  const hoursSaved = Math.round((approvedCount * 5) / 60);

  // Intent distribution for pie chart
  const intentPieData = byIntent.map((i) => ({
    name: formatIntentLabel(i.intent),
    value: i.count,
  }));

  // Status bar chart data
  const statusBarData = byStatus.map((s) => ({
    name: s.status,
    count: s.count,
  }));

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-montserrat text-2xl font-bold text-slate-900">
            {greeting}, {user?.name?.split(" ")[0] || "there"}
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
            {user?.org_name && (
              <span className="rounded-full bg-industrial-100 px-2.5 py-0.5 text-xs font-medium text-industrial-700">
                {user.org_name}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-green-500" />
          <span className="text-xs font-medium text-green-600">All Systems Operational</span>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Link to="/inbox" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-industrial-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-industrial-100 text-industrial-600 transition-colors group-hover:bg-industrial-600 group-hover:text-white">
            <Inbox className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Inbox</p>
            <p className="text-[11px] text-slate-400">{newCount} new messages</p>
          </div>
        </Link>
        <Link to="/knowledge-base" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-purple-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600 transition-colors group-hover:bg-purple-600 group-hover:text-white">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Knowledge Base</p>
            <p className="text-[11px] text-slate-400">Products & TDS/SDS</p>
          </div>
        </Link>
        <Link to="/orders" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-tech-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-tech-100 text-tech-600 transition-colors group-hover:bg-tech-600 group-hover:text-white">
            <TrendingUp className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Orders</p>
            <p className="text-[11px] text-slate-400">{metrics?.open_orders ?? 0} open</p>
          </div>
        </Link>
        <Link to="/chat" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-amber-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600 transition-colors group-hover:bg-amber-600 group-hover:text-white">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">AI Assistant</p>
            <p className="text-[11px] text-slate-400">Sourcing chat</p>
          </div>
        </Link>
      </div>

      {/* KPI Row 1: Operations Impact */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Messages Handled"
          value={formatNumber(totalMessages)}
          subtext={`${newCount} pending review`}
          icon={Inbox}
          color="border-l-industrial-600"
          iconBg="bg-industrial-100 text-industrial-600"
        />
        <KpiCard
          label="AI Accuracy"
          value={`${aiAccuracy}%`}
          subtext={`${approvedCount} approved, ${escalatedCount} escalated`}
          icon={Zap}
          color="border-l-tech-500"
          iconBg="bg-tech-100 text-tech-600"
        />
        <KpiCard
          label="Hours Saved"
          value={`${hoursSaved}h`}
          subtext={`~${Math.round(hoursSaved / 160 * 10) / 10} FTE equivalent`}
          icon={Clock}
          color="border-l-amber-500"
          iconBg="bg-amber-100 text-amber-600"
        />
        <KpiCard
          label="Auto-Approved"
          value={formatNumber(approvedCount)}
          subtext="AI drafts sent with human approval"
          icon={Users}
          color="border-l-green-500"
          iconBg="bg-green-100 text-green-600"
        />
      </div>

      {/* KPI Row 2: Pipeline stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {byStatus.map((s) => (
          <div key={s.status} className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <span className="text-xs font-medium capitalize text-slate-500">{s.status}</span>
            <p className="mt-1 text-2xl font-bold text-slate-800">{formatNumber(s.count)}</p>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Intent Distribution Pie */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
            Intent Distribution
          </h2>
          <div className="h-[300px]">
            {intentPieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={intentPieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={110}
                    paddingAngle={2}
                    strokeWidth={0}
                  >
                    {intentPieData.map((_e, idx) => (
                      <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No intent data yet
              </div>
            )}
          </div>
          {/* Legend */}
          <div className="mt-2 flex flex-wrap justify-center gap-3">
            {intentPieData.map((d, idx) => (
              <div key={d.name} className="flex items-center gap-1.5 text-xs text-slate-600">
                <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                {d.name} ({d.value})
              </div>
            ))}
          </div>
        </div>

        {/* Volume by Status Bar */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
            Messages by Status
          </h2>
          <div className="h-[300px]">
            {statusBarData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusBarData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e2e8f0" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={40}>
                    {statusBarData.map((_e, idx) => (
                      <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No message data yet
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom: Intent breakdown table */}
      {byIntent.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
              Intent Breakdown
            </h2>
            <Link
              to="/inbox"
              className="flex items-center gap-1 text-xs font-medium text-industrial-600 hover:underline"
            >
              View Inbox <ArrowRight size={12} />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80">
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Intent</th>
                  <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">Count</th>
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Distribution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {byIntent.map((i, idx) => (
                  <tr key={i.intent} className="transition-colors hover:bg-slate-50/60">
                    <td className="whitespace-nowrap px-5 py-3 font-medium text-slate-800">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }} />
                        {formatIntentLabel(i.intent)}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-right font-medium text-slate-900">
                      {formatNumber(i.count)}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${totalMessages > 0 ? Math.round((i.count / totalMessages) * 100) : 0}%`,
                              backgroundColor: PIE_COLORS[idx % PIE_COLORS.length],
                            }}
                          />
                        </div>
                        <span className="text-xs text-slate-400">
                          {totalMessages > 0 ? Math.round((i.count / totalMessages) * 100) : 0}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function formatIntentLabel(intent: string): string {
  return intent
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
