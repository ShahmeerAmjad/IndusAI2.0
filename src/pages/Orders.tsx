import { useQuery } from "@tanstack/react-query";
import { api, Order } from "@/lib/api";
import { useState } from "react";
import { formatCurrency, statusColor, cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import ReportDownloadButton from "@/components/ReportDownloadButton";

const STATUSES = [
  "All",
  "Draft",
  "Submitted",
  "Confirmed",
  "Shipped",
  "Delivered",
  "Cancelled",
] as const;

export default function Orders() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["orders", page, statusFilter],
    queryFn: () => api.getOrders(page, statusFilter),
  });

  const orders = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Orders</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage and track customer orders
          </p>
        </div>
        <ReportDownloadButton endpoint="orders" label="Export Orders" />
      </div>

      {/* Status filter buttons */}
      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => {
          const value = s === "All" ? "" : s.toLowerCase();
          const isActive = statusFilter === value;
          return (
            <button
              key={s}
              onClick={() => {
                setStatusFilter(value);
                setPage(1);
              }}
              className={cn(
                "rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-gray-900 text-white shadow-sm"
                  : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              )}
            >
              {s}
            </button>
          );
        })}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
          <span className="ml-3 text-sm text-gray-500">Loading orders...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Failed to load orders
          </p>
          <p className="mt-1 text-sm text-red-600">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </p>
        </div>
      )}

      {/* Table */}
      {!isLoading && !isError && (
        <>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Order #
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Customer
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Total Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Date
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {orders.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-16 text-center text-sm text-gray-400"
                    >
                      No orders found.
                    </td>
                  </tr>
                ) : (
                  orders.map((order: Order) => (
                    <tr
                      key={order.id}
                      onClick={() => navigate(`/orders/${order.id}`)}
                      className="cursor-pointer transition-colors hover:bg-gray-50"
                    >
                      <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                        {order.order_number}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                        {order.customer_name ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                            statusColor(order.status)
                          )}
                        >
                          {order.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                        {formatCurrency(order.total_amount)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                        {new Date(order.order_date).toLocaleDateString()}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/orders/${order.id}`);
                          }}
                          className="rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-300 transition-colors hover:bg-gray-50"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Page {data?.page ?? 1} of {totalPages}
              {data?.total != null && (
                <span className="ml-1">({data.total} total orders)</span>
              )}
            </p>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className={cn(
                  "rounded-md px-4 py-2 text-sm font-medium transition-colors",
                  page <= 1
                    ? "cursor-not-allowed bg-gray-100 text-gray-400"
                    : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                )}
              >
                Previous
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className={cn(
                  "rounded-md px-4 py-2 text-sm font-medium transition-colors",
                  page >= totalPages
                    ? "cursor-not-allowed bg-gray-100 text-gray-400"
                    : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                )}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
