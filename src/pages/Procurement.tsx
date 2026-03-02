import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, PurchaseOrder, Supplier } from "@/lib/api";
import { useState } from "react";
import { formatCurrency, statusColor, cn } from "@/lib/utils";

type Tab = "purchase-orders" | "suppliers";

export default function Procurement() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>("purchase-orders");

  /* Queries */
  const posQuery = useQuery({
    queryKey: ["purchase-orders"],
    queryFn: () => api.getPurchaseOrders(),
  });

  const suppliersQuery = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api.getSuppliers(),
  });

  /* Auto-generate POs mutation */
  const autoGenMutation = useMutation({
    mutationFn: () => api.autoGeneratePOs(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });

  const purchaseOrders = posQuery.data?.items ?? [];
  const suppliers = suppliersQuery.data?.items ?? [];

  const isLoading =
    activeTab === "purchase-orders" ? posQuery.isLoading : suppliersQuery.isLoading;
  const isError =
    activeTab === "purchase-orders" ? posQuery.isError : suppliersQuery.isError;
  const error =
    activeTab === "purchase-orders" ? posQuery.error : suppliersQuery.error;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Procurement</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage purchase orders and suppliers
          </p>
        </div>

        {activeTab === "purchase-orders" && (
          <button
            disabled={autoGenMutation.isPending}
            onClick={() => autoGenMutation.mutate()}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors",
              autoGenMutation.isPending
                ? "cursor-not-allowed bg-gray-400"
                : "bg-gray-900 hover:bg-gray-800"
            )}
          >
            {autoGenMutation.isPending
              ? "Generating..."
              : "Auto-Generate POs"}
          </button>
        )}
      </div>

      {/* Auto-gen error */}
      {autoGenMutation.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            {autoGenMutation.error instanceof Error
              ? autoGenMutation.error.message
              : "Failed to auto-generate purchase orders."}
          </p>
        </div>
      )}

      {/* Auto-gen success */}
      {autoGenMutation.isSuccess && (
        <div className="rounded-lg border border-tech-200 bg-tech-50 p-4">
          <p className="text-sm text-tech-700">
            Purchase orders generated successfully.
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6" aria-label="Procurement tabs">
          {(
            [
              { key: "purchase-orders", label: "Purchase Orders" },
              { key: "suppliers", label: "Suppliers" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "whitespace-nowrap border-b-2 py-3 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
          <span className="ml-3 text-sm text-gray-500">Loading...</span>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Failed to load data
          </p>
          <p className="mt-1 text-sm text-red-600">
            {error instanceof Error
              ? error.message
              : "An unexpected error occurred."}
          </p>
        </div>
      )}

      {/* Purchase Orders tab */}
      {!isLoading && !isError && activeTab === "purchase-orders" && (
        <div className="overflow-x-auto overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-[600px] min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="border-b bg-slate-50/80">
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  PO #
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Supplier
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Status
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Total
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Order Date
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Expected Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {purchaseOrders.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-16 text-center text-sm text-gray-400"
                  >
                    No purchase orders found.
                  </td>
                </tr>
              ) : (
                purchaseOrders.map((po: PurchaseOrder) => (
                  <tr
                    key={po.id}
                    className="transition-colors hover:bg-gray-50"
                  >
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                      {po.po_number}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                      {po.supplier_name ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                          statusColor(po.status)
                        )}
                      >
                        {po.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                      {formatCurrency(po.total_amount)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {new Date(po.order_date).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {po.expected_date
                        ? new Date(po.expected_date).toLocaleDateString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Suppliers tab */}
      {!isLoading && !isError && activeTab === "suppliers" && (
        <div className="overflow-x-auto overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-[600px] min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="border-b bg-slate-50/80">
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Code
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Name
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Contact
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Email
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Payment Terms
                </th>
                <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Lead Time
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {suppliers.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-16 text-center text-sm text-gray-400"
                  >
                    No suppliers found.
                  </td>
                </tr>
              ) : (
                suppliers.map((supplier: Supplier) => (
                  <tr
                    key={supplier.id}
                    className="transition-colors hover:bg-gray-50"
                  >
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-mono font-medium text-gray-900">
                      {supplier.supplier_code}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {supplier.name}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                      {supplier.contact_name}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                      {supplier.email}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {supplier.payment_terms}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-500">
                      {supplier.lead_time_days} days
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
