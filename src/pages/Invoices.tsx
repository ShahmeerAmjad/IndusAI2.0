import { useQuery } from "@tanstack/react-query";
import { api, Invoice } from "@/lib/api";
import { useState } from "react";
import { formatCurrency, statusColor, cn } from "@/lib/utils";
import ReportDownloadButton from "@/components/ReportDownloadButton";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

type Tab = "invoices" | "aging";
type StatusFilter = "all" | "draft" | "sent" | "paid" | "overdue" | "void";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "paid", label: "Paid" },
  { value: "overdue", label: "Overdue" },
  { value: "void", label: "Void" },
];

const AGING_COLORS: Record<string, string> = {
  current: "#22c55e",
  "1-30": "#eab308",
  "31-60": "#f97316",
  "61-90": "#ea580c",
  "90+": "#ef4444",
};

const AGING_LABELS: Record<string, string> = {
  current: "Current",
  "1-30": "1-30 Days",
  "31-60": "31-60 Days",
  "61-90": "61-90 Days",
  "90+": "90+ Days",
};

export default function Invoices() {
  const [tab, setTab] = useState<Tab>("invoices");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);

  const invoicesQuery = useQuery({
    queryKey: ["invoices", page, statusFilter],
    queryFn: () =>
      api.getInvoices(page, statusFilter === "all" ? "" : statusFilter),
    enabled: tab === "invoices",
  });

  const agingQuery = useQuery({
    queryKey: ["ar-aging"],
    queryFn: () => api.getARaging(),
    enabled: tab === "aging",
  });

  const agingBucketOrder = ["current", "1-30", "31-60", "61-90", "90+"];

  const chartData = agingQuery.data
    ? agingBucketOrder
        .filter((key) => agingQuery.data![key])
        .map((key) => ({
          bucket: AGING_LABELS[key] || key,
          balance: agingQuery.data![key].balance,
          color: AGING_COLORS[key] || "#6b7280",
        }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Invoicing &amp; Payments
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage invoices, track payments, and review accounts receivable aging.
          </p>
        </div>
        <ReportDownloadButton endpoint="invoices" label="Export Invoices" />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setTab("invoices")}
            className={cn(
              "whitespace-nowrap border-b-2 py-3 px-1 text-sm font-medium transition-colors",
              tab === "invoices"
                ? "border-industrial-600 text-industrial-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            )}
          >
            Invoices
          </button>
          <button
            onClick={() => setTab("aging")}
            className={cn(
              "whitespace-nowrap border-b-2 py-3 px-1 text-sm font-medium transition-colors",
              tab === "aging"
                ? "border-industrial-600 text-industrial-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            )}
          >
            AR Aging
          </button>
        </nav>
      </div>

      {/* Invoices Tab */}
      {tab === "invoices" && (
        <div className="space-y-4">
          {/* Status Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-700">Status:</span>
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setStatusFilter(opt.value);
                  setPage(1);
                }}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  statusFilter === opt.value
                    ? "bg-industrial-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Loading */}
          {invoicesQuery.isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-industrial-600 border-t-transparent" />
              <span className="ml-3 text-sm text-gray-500">
                Loading invoices...
              </span>
            </div>
          )}

          {/* Error */}
          {invoicesQuery.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
              <p className="text-sm text-red-700">
                Failed to load invoices:{" "}
                {invoicesQuery.error instanceof Error
                  ? invoicesQuery.error.message
                  : "Unknown error"}
              </p>
              <button
                onClick={() => invoicesQuery.refetch()}
                className="mt-2 text-sm font-medium text-red-700 underline hover:text-red-800"
              >
                Retry
              </button>
            </div>
          )}

          {/* Table */}
          {invoicesQuery.data && (
            <>
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr className="border-b bg-slate-50/80">
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Invoice #
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Customer
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Status
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Total
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Balance Due
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Invoice Date
                      </th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Due Date
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {invoicesQuery.data.items.map((inv: Invoice) => (
                      <tr
                        key={inv.id}
                        className="hover:bg-gray-50 transition-colors"
                      >
                        <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-industrial-600">
                          {inv.invoice_number}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                          {inv.customer_name || inv.customer_id}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm">
                          <span
                            className={cn(
                              "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
                              statusColor(inv.status)
                            )}
                          >
                            {inv.status.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                          {formatCurrency(inv.total_amount)}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                          {formatCurrency(inv.balance_due)}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                          {new Date(inv.invoice_date).toLocaleDateString()}
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                          {new Date(inv.due_date).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                    {invoicesQuery.data.items.length === 0 && (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-6 py-12 text-center text-sm text-gray-500"
                        >
                          No invoices found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {invoicesQuery.data.total_pages > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    Page {invoicesQuery.data.page} of{" "}
                    {invoicesQuery.data.total_pages} ({invoicesQuery.data.total}{" "}
                    total)
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() =>
                        setPage((p) =>
                          Math.min(invoicesQuery.data!.total_pages, p + 1)
                        )
                      }
                      disabled={page >= invoicesQuery.data.total_pages}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* AR Aging Tab */}
      {tab === "aging" && (
        <div className="space-y-6">
          {/* Loading */}
          {agingQuery.isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-industrial-600 border-t-transparent" />
              <span className="ml-3 text-sm text-gray-500">
                Loading AR aging data...
              </span>
            </div>
          )}

          {/* Error */}
          {agingQuery.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
              <p className="text-sm text-red-700">
                Failed to load AR aging:{" "}
                {agingQuery.error instanceof Error
                  ? agingQuery.error.message
                  : "Unknown error"}
              </p>
              <button
                onClick={() => agingQuery.refetch()}
                className="mt-2 text-sm font-medium text-red-700 underline hover:text-red-800"
              >
                Retry
              </button>
            </div>
          )}

          {agingQuery.data && (
            <>
              {/* Bar Chart */}
              <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="mb-4 text-lg font-semibold text-gray-900">
                  Accounts Receivable Aging
                </h2>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                    >
                      <XAxis
                        type="number"
                        tickFormatter={(v: number) =>
                          `$${(v / 1000).toFixed(0)}k`
                        }
                        fontSize={12}
                      />
                      <YAxis
                        type="category"
                        dataKey="bucket"
                        fontSize={12}
                        width={80}
                      />
                      <Tooltip
                        formatter={(value: number) => [
                          formatCurrency(value),
                          "Balance",
                        ]}
                        contentStyle={{
                          borderRadius: "8px",
                          border: "1px solid #e5e7eb",
                          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                        }}
                      />
                      <Bar dataKey="balance" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {agingBucketOrder.map((key) => {
                  const bucket = agingQuery.data![key];
                  if (!bucket) return null;
                  return (
                    <div
                      key={key}
                      className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block h-3 w-3 rounded-full"
                          style={{
                            backgroundColor:
                              AGING_COLORS[key] || "#6b7280",
                          }}
                        />
                        <h3 className="text-sm font-medium text-gray-500">
                          {AGING_LABELS[key] || key}
                        </h3>
                      </div>
                      <p className="mt-2 text-2xl font-bold text-gray-900">
                        {formatCurrency(bucket.balance)}
                      </p>
                      <p className="mt-1 text-sm text-gray-500">
                        {bucket.count} invoice{bucket.count !== 1 ? "s" : ""}
                      </p>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
