import { useQuery } from "@tanstack/react-query";
import { api, InventoryItem, ReorderAlert } from "@/lib/api";
import { formatNumber, cn } from "@/lib/utils";
import { useState } from "react";
import ReportDownloadButton from "@/components/ReportDownloadButton";

type Tab = "stock" | "reorder";

export default function Inventory() {
  const [activeTab, setActiveTab] = useState<Tab>("stock");
  const [stockPage, setStockPage] = useState(1);

  const {
    data: stockData,
    isLoading: stockLoading,
    isError: stockError,
    error: stockErr,
  } = useQuery({
    queryKey: ["inventory", stockPage],
    queryFn: () => api.getInventory(stockPage),
  });

  const {
    data: alerts,
    isLoading: alertsLoading,
    isError: alertsError,
    error: alertsErr,
  } = useQuery({
    queryKey: ["reorder-alerts"],
    queryFn: () => api.getReorderAlerts(),
    enabled: activeTab === "reorder",
  });

  const tabs: Array<{ key: Tab; label: string; count?: number }> = [
    { key: "stock", label: "Stock Levels" },
    { key: "reorder", label: "Reorder Alerts", count: alerts?.length },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-montserrat font-bold text-neutral-900">
            Inventory Management
          </h1>
          <p className="text-neutral-500 text-sm mt-1">
            Monitor stock levels and reorder alerts across warehouses
          </p>
        </div>
        <ReportDownloadButton endpoint="inventory" label="Export Inventory" />
      </div>

      {/* Tab Buttons */}
      <div className="flex gap-1 bg-neutral-100 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-md transition-colors",
              activeTab === tab.key
                ? "bg-white text-industrial-800 shadow-sm"
                : "text-neutral-500 hover:text-neutral-700"
            )}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="ml-2 inline-flex items-center justify-center bg-red-100 text-red-700 text-xs font-semibold rounded-full px-2 py-0.5 min-w-[1.25rem]">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Stock Levels Tab */}
      {activeTab === "stock" && (
        <StockLevelsTab
          data={stockData}
          isLoading={stockLoading}
          isError={stockError}
          error={stockErr}
          page={stockPage}
          onPageChange={setStockPage}
        />
      )}

      {/* Reorder Alerts Tab */}
      {activeTab === "reorder" && (
        <ReorderAlertsTab
          data={alerts}
          isLoading={alertsLoading}
          isError={alertsError}
          error={alertsErr}
        />
      )}
    </div>
  );
}

/* ---------- Stock Levels Tab ---------- */

interface StockLevelsTabProps {
  data:
    | {
        items: InventoryItem[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
      }
    | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  page: number;
  onPageChange: (page: number) => void;
}

function StockLevelsTab({ data, isLoading, isError, error, page, onPageChange }: StockLevelsTabProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 text-sm">Loading inventory...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <h3 className="text-red-800 font-semibold text-lg mb-2">Failed to load inventory</h3>
        <p className="text-red-600 text-sm">
          {error instanceof Error ? error.message : "An unexpected error occurred."}
        </p>
      </div>
    );
  }

  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;

  if (items.length === 0) {
    return (
      <div className="text-center py-16 bg-neutral-50 rounded-lg border border-dashed border-neutral-300">
        <p className="text-neutral-500 text-sm">No inventory records found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border border-neutral-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-200">
                <th className="text-left py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  SKU
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Product
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Warehouse
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  On Hand
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Reserved
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Available
                </th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Reorder Pt
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Bin Location
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item: InventoryItem, idx: number) => {
                const isLow = item.quantity_available <= item.reorder_point;
                return (
                  <tr
                    key={item.id}
                    className={cn(
                      "border-b border-neutral-100 transition-colors",
                      isLow
                        ? "bg-red-50 hover:bg-red-100"
                        : idx % 2 === 0
                          ? "bg-white hover:bg-neutral-50"
                          : "bg-neutral-50/50 hover:bg-neutral-50"
                    )}
                  >
                    <td className="py-2.5 px-4 font-mono text-xs text-industrial-800 font-semibold">
                      {item.sku}
                    </td>
                    <td className="py-2.5 px-4 text-neutral-700 font-medium max-w-[200px] truncate">
                      {item.product_name}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="inline-block bg-neutral-100 text-neutral-600 text-xs font-medium px-2 py-0.5 rounded">
                        {item.warehouse_code}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-right text-neutral-700 tabular-nums">
                      {formatNumber(item.quantity_on_hand)}
                    </td>
                    <td className="py-2.5 px-4 text-right text-neutral-500 tabular-nums">
                      {formatNumber(item.quantity_reserved)}
                    </td>
                    <td
                      className={cn(
                        "py-2.5 px-4 text-right font-semibold tabular-nums",
                        isLow ? "text-red-700" : "text-neutral-700"
                      )}
                    >
                      {formatNumber(item.quantity_available)}
                    </td>
                    <td className="py-2.5 px-4 text-right text-neutral-500 tabular-nums">
                      {formatNumber(item.reorder_point)}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs text-neutral-500">
                      {item.bin_location || "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-neutral-500">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page <= 1}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-lg border transition-colors",
                page <= 1
                  ? "border-neutral-200 text-neutral-300 cursor-not-allowed bg-neutral-50"
                  : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-lg border transition-colors",
                page >= totalPages
                  ? "border-neutral-200 text-neutral-300 cursor-not-allowed bg-neutral-50"
                  : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Reorder Alerts Tab ---------- */

interface ReorderAlertsTabProps {
  data: ReorderAlert[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}

function ReorderAlertsTab({ data, isLoading, isError, error }: ReorderAlertsTabProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 text-sm">Loading reorder alerts...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <h3 className="text-red-800 font-semibold text-lg mb-2">Failed to load reorder alerts</h3>
        <p className="text-red-600 text-sm">
          {error instanceof Error ? error.message : "An unexpected error occurred."}
        </p>
      </div>
    );
  }

  const alerts = data ?? [];

  if (alerts.length === 0) {
    return (
      <div className="text-center py-16 bg-green-50 rounded-lg border border-dashed border-green-300">
        <svg
          className="h-10 w-10 text-green-400 mx-auto mb-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-green-700 font-medium text-sm">All stock levels are above reorder points.</p>
        <p className="text-green-600 text-xs mt-1">No reorder alerts at this time.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-500">
        {alerts.length} {alerts.length === 1 ? "item needs" : "items need"} reordering
      </p>

      <div className="grid gap-3">
        {alerts.map((alert: ReorderAlert) => (
          <div
            key={`${alert.product_id}-${alert.warehouse_code}`}
            className="bg-white border border-red-200 rounded-lg p-5 hover:shadow-sm transition-shadow"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              {/* Left: Product Info */}
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="inline-block bg-industrial-100 text-industrial-800 text-xs font-semibold px-2.5 py-0.5 rounded-md font-mono">
                    {alert.sku}
                  </span>
                  <span className="inline-block bg-neutral-100 text-neutral-600 text-xs font-medium px-2 py-0.5 rounded">
                    {alert.warehouse_code}
                  </span>
                </div>
                <h3 className="font-medium text-neutral-900 text-sm">{alert.product_name}</h3>
              </div>

              {/* Right: Quantities */}
              <div className="flex flex-wrap gap-4 text-xs">
                <div className="text-center">
                  <p className="text-neutral-400 uppercase tracking-wide font-medium">Available</p>
                  <p className="text-lg font-semibold text-red-600 tabular-nums">
                    {formatNumber(alert.quantity_available)}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-neutral-400 uppercase tracking-wide font-medium">Reorder Pt</p>
                  <p className="text-lg font-semibold text-neutral-700 tabular-nums">
                    {formatNumber(alert.reorder_point)}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-neutral-400 uppercase tracking-wide font-medium">Reorder Qty</p>
                  <p className="text-lg font-semibold text-industrial-800 tabular-nums">
                    {formatNumber(alert.reorder_qty)}
                  </p>
                </div>
              </div>
            </div>

            {/* Supplier Info */}
            {(alert.preferred_supplier || alert.supplier_price !== undefined) && (
              <div className="mt-3 pt-3 border-t border-neutral-100 flex flex-wrap items-center gap-4 text-xs text-neutral-500">
                {alert.preferred_supplier && (
                  <span>
                    Preferred Supplier:{" "}
                    <span className="font-medium text-neutral-700">{alert.preferred_supplier}</span>
                  </span>
                )}
                {alert.supplier_price !== undefined && alert.supplier_price !== null && (
                  <span>
                    Unit Price:{" "}
                    <span className="font-medium text-neutral-700">
                      ${alert.supplier_price.toFixed(2)}
                    </span>
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
