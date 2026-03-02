import { useQuery } from "@tanstack/react-query";
import { api, DashboardMetrics } from "@/lib/api";
import { formatCurrency, formatNumber, statusColor, cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Area,
} from "recharts";
import {
  DollarSign,
  Package,
  ClipboardList,
  TrendingUp,
  AlertTriangle,
  FileText,
  CircleAlert,
  RotateCcw,
  Search,
  Plus,
  Upload as UploadIcon,
  Download,
  Activity,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface KpiCard {
  label: string;
  value: string;
  icon: LucideIcon;
  border: string;           // Tailwind border-l color class
  bg: string;               // Tailwind background tint class
  iconBg: string;           // icon circle background
  iconColor: string;        // icon stroke color
}

interface AlertCard {
  label: string;
  value: number;
  icon: LucideIcon;
  border: string;
  textColor: string;
}

interface TopProduct {
  sku: string;
  name: string;
  total_qty: number;
  total_revenue: number;
}

interface TopCustomer {
  name: string;
  company: string;
  total_revenue: number;
  order_count: number;
}

interface RecentOrder {
  order_number: string;
  status: string;
  total_amount: number;
  customer_name: string;
  order_date: string;
}

interface ProductChartItem {
  name: string;
  revenue: number;
}

interface CustomerPieItem {
  name: string;
  value: number;
  orders: number;
}

/* ------------------------------------------------------------------ */
/*  Palette                                                            */
/* ------------------------------------------------------------------ */

const CHART_COLORS = [
  "#1e3a8a", // industrial-800
  "#0284c7", // industrial-600
  "#0ea5e9", // industrial-500
  "#38bdf8", // industrial-400
  "#7dd3fc", // industrial-300
  "#0d9488", // tech-600
  "#14b8a6", // tech-500
  "#2dd4bf", // tech-400
];

const PIE_COLORS = ["#1e3a8a", "#0284c7", "#0d9488", "#f59e0b", "#ef4444"];

/* ------------------------------------------------------------------ */
/*  Custom Tooltip for Recharts                                        */
/* ------------------------------------------------------------------ */

interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; name: string; payload: Record<string, unknown> }>;
  label?: string;
  isCurrency?: boolean;
}

function ChartTooltip({ active, payload, label, isCurrency = true }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
      <p className="mb-1 text-xs font-medium text-slate-500">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-semibold text-slate-800">
          {isCurrency ? formatCurrency(entry.value) : formatNumber(entry.value)}
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sales Trend mini-chart (uses getSalesSummary)                      */
/* ------------------------------------------------------------------ */

function SalesTrendChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["salesSummary", "daily"],
    queryFn: () => api.getSalesSummary("daily"),
  });

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        Loading trend...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1e3a8a" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#1e3a8a" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 11, fill: "#64748b" }}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#64748b" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) =>
            v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`
          }
        />
        <Tooltip content={<ChartTooltip />} />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="none"
          fill="url(#revenueGradient)"
        />
        <Line
          type="monotone"
          dataKey="revenue"
          stroke="#1e3a8a"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "#1e3a8a" }}
          activeDot={{ r: 5, fill: "#0284c7" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Dashboard Component                                           */
/* ------------------------------------------------------------------ */

export default function Dashboard() {
  const { user } = useAuth();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const {
    data: metrics,
    isLoading,
    isError,
    error,
  } = useQuery<DashboardMetrics>({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
    refetchInterval: 60_000,
  });

  /* ---------- Loading & Error States ---------- */

  if (isLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <p className="text-lg text-slate-400">Loading...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <p className="text-lg text-red-500">
          {error instanceof Error ? error.message : "Failed to load dashboard"}
        </p>
      </div>
    );
  }

  if (!metrics) return null;

  /* ---------- Derived data ---------- */

  const kpiCards: KpiCard[] = [
    {
      label: "Revenue Today",
      value: formatCurrency(metrics.revenue_today),
      icon: DollarSign,
      border: "border-l-tech-500",
      bg: "bg-tech-50/60",
      iconBg: "bg-tech-100",
      iconColor: "text-tech-600",
    },
    {
      label: "Orders Today",
      value: formatNumber(metrics.orders_today),
      icon: Package,
      border: "border-l-industrial-600",
      bg: "bg-industrial-50/60",
      iconBg: "bg-industrial-100",
      iconColor: "text-industrial-600",
    },
    {
      label: "Open Orders",
      value: formatNumber(metrics.open_orders),
      icon: ClipboardList,
      border: "border-l-industrial-800",
      bg: "bg-industrial-50/40",
      iconBg: "bg-industrial-100",
      iconColor: "text-industrial-800",
    },
    {
      label: "Revenue This Month",
      value: formatCurrency(metrics.revenue_this_month),
      icon: TrendingUp,
      border: "border-l-tech-600",
      bg: "bg-tech-50/40",
      iconBg: "bg-tech-100",
      iconColor: "text-tech-600",
    },
  ];

  const alertCards: AlertCard[] = [
    {
      label: "Low Stock Items",
      value: metrics.low_stock_items,
      icon: AlertTriangle,
      border: "border-l-amber-500",
      textColor: "text-amber-600",
    },
    {
      label: "Pending Invoices",
      value: metrics.pending_invoices,
      icon: FileText,
      border: "border-l-industrial-400",
      textColor: "text-industrial-600",
    },
    {
      label: "Overdue Invoices",
      value: metrics.overdue_invoices,
      icon: CircleAlert,
      border: "border-l-red-500",
      textColor: "text-red-600",
    },
    {
      label: "Open RMAs",
      value: metrics.open_rmas,
      icon: RotateCcw,
      border: "border-l-amber-400",
      textColor: "text-amber-600",
    },
  ];

  const topProductsData: ProductChartItem[] = metrics.top_products
    .slice(0, 8)
    .map((p: TopProduct) => ({
      name: p.name.length > 28 ? `${p.name.slice(0, 26)}...` : p.name,
      revenue: p.total_revenue,
    }))
    .reverse(); // reverse so highest is at top in horizontal bar chart

  const topCustomersPieData: CustomerPieItem[] = metrics.top_customers
    .slice(0, 5)
    .map((c: TopCustomer) => ({
      name: c.company || c.name,
      value: c.total_revenue,
      orders: c.order_count,
    }));

  /* ---------- Render ---------- */

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
        <Link to="/chat" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-industrial-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-industrial-100 text-industrial-600 transition-colors group-hover:bg-industrial-600 group-hover:text-white">
            <Search className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Search Parts</p>
            <p className="text-[11px] text-slate-400">AI sourcing</p>
          </div>
        </Link>
        <Link to="/orders" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-tech-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-tech-100 text-tech-600 transition-colors group-hover:bg-tech-600 group-hover:text-white">
            <Plus className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Create Order</p>
            <p className="text-[11px] text-slate-400">New O2C order</p>
          </div>
        </Link>
        <Link to="/bulk-import" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-amber-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600 transition-colors group-hover:bg-amber-600 group-hover:text-white">
            <UploadIcon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Import Data</p>
            <p className="text-[11px] text-slate-400">CSV upload</p>
          </div>
        </Link>
        <Link to="/inventory" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-purple-300 hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600 transition-colors group-hover:bg-purple-600 group-hover:text-white">
            <Download className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Download Report</p>
            <p className="text-[11px] text-slate-400">Inventory export</p>
          </div>
        </Link>
      </div>

      {/* ---- Row 1: KPI Cards ---- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.map((card) => (
          <div
            key={card.label}
            className={cn(
              "relative overflow-hidden rounded-xl border border-slate-200 border-l-4 p-5 shadow-sm transition-shadow hover:shadow-md",
              card.border,
              card.bg,
            )}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {card.label}
                </p>
                <p className="mt-2 text-3xl font-bold text-slate-900">
                  {card.value}
                </p>
              </div>
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-lg",
                  card.iconBg,
                )}
              >
                <card.icon className={cn("h-5 w-5", card.iconColor)} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ---- Row 2: Alert / Metric Cards ---- */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {alertCards.map((card) => (
          <div
            key={card.label}
            className={cn(
              "rounded-lg border border-slate-200 border-l-4 bg-white px-4 py-3 shadow-sm",
              card.border,
            )}
          >
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.textColor)} />
              <span className="text-xs font-medium text-slate-500">
                {card.label}
              </span>
            </div>
            <p className={cn("mt-1 text-2xl font-bold", card.textColor)}>
              {formatNumber(card.value)}
            </p>
          </div>
        ))}
      </div>

      {/* ---- Row 3: Charts ---- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top Products Bar Chart */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
            Top Products by Revenue
          </h2>
          <div className="h-[320px]">
            {topProductsData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={topProductsData}
                  layout="vertical"
                  margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e2e8f0" }}
                    tickFormatter={(v: number) =>
                      v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`
                    }
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={140}
                    tick={{ fontSize: 11, fill: "#334155" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar
                    dataKey="revenue"
                    radius={[0, 4, 4, 0]}
                    barSize={22}
                  >
                    {topProductsData.map((_entry: ProductChartItem, idx: number) => (
                      <Cell
                        key={idx}
                        fill={CHART_COLORS[idx % CHART_COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                No product data available
              </div>
            )}
          </div>
        </div>

        {/* Sales Trend Line Chart */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
            Revenue Trend (Daily)
          </h2>
          <div className="h-[320px]">
            <SalesTrendChart />
          </div>
        </div>
      </div>

      {/* ---- Row 4: Recent Orders Table + Top Customers ---- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent Orders - spans 2 cols */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-2">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
              Recent Orders
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80">
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Order #
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Customer
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Status
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Amount
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {metrics.recent_orders.length > 0 ? (
                  metrics.recent_orders.map((order: RecentOrder) => (
                    <tr
                      key={order.order_number}
                      className="transition-colors hover:bg-slate-50/60"
                    >
                      <td className="whitespace-nowrap px-5 py-3 font-mono text-sm font-medium text-industrial-800">
                        {order.order_number}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-700">
                        {order.customer_name}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize",
                            statusColor(order.status),
                          )}
                        >
                          {order.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right font-medium text-slate-900">
                        {formatCurrency(order.total_amount)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-500">
                        {new Date(order.order_date).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-5 py-8 text-center text-slate-400"
                    >
                      No recent orders
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top Customers */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
              Top Customers by Revenue
            </h2>
          </div>

          {/* Pie Chart */}
          {topCustomersPieData.length > 0 && (
            <div className="flex justify-center px-4 pt-4">
              <div className="h-[180px] w-[180px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={topCustomersPieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={80}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {topCustomersPieData.map((_entry: CustomerPieItem, idx: number) => (
                        <Cell
                          key={idx}
                          fill={PIE_COLORS[idx % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      content={(props) => {
                        const { active, payload } = props as { active?: boolean; payload?: Array<{ payload: CustomerPieItem }> };
                        if (!active || !payload?.length) return null;
                        const d: CustomerPieItem = payload[0].payload;
                        return (
                          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
                            <p className="text-xs font-medium text-slate-500">
                              {d.name}
                            </p>
                            <p className="text-sm font-semibold text-slate-800">
                              {formatCurrency(d.value)}
                            </p>
                            <p className="text-xs text-slate-400">
                              {d.orders} orders
                            </p>
                          </div>
                        );
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Customer List */}
          <div className="divide-y divide-slate-100 px-5 pb-3">
            {metrics.top_customers.slice(0, 5).map((c: TopCustomer, idx: number) => (
              <div
                key={c.name + c.company}
                className="flex items-center gap-3 py-3"
              >
                {/* Rank badge */}
                <div
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                  style={{
                    backgroundColor:
                      PIE_COLORS[idx % PIE_COLORS.length],
                  }}
                >
                  {idx + 1}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">
                    {c.company || c.name}
                  </p>
                  <p className="text-xs text-slate-400">
                    {c.order_count} orders
                  </p>
                </div>

                <p className="flex-shrink-0 text-sm font-semibold text-slate-900">
                  {formatCurrency(c.total_revenue)}
                </p>
              </div>
            ))}

            {metrics.top_customers.length === 0 && (
              <p className="py-6 text-center text-sm text-slate-400">
                No customer data available
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
