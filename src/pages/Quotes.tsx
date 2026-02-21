import { useQuery } from "@tanstack/react-query";
import { api, Quote } from "@/lib/api";
import { formatCurrency, statusColor, cn } from "@/lib/utils";

export default function Quotes() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["quotes"],
    queryFn: () => api.getQuotes(),
  });

  const quotes = data?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Quotes</h1>
        <p className="mt-1 text-sm text-gray-500">
          View and manage customer quotes
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
          <span className="ml-3 text-sm text-gray-500">Loading quotes...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Failed to load quotes
          </p>
          <p className="mt-1 text-sm text-red-600">
            {error instanceof Error
              ? error.message
              : "An unexpected error occurred."}
          </p>
        </div>
      )}

      {/* Table */}
      {!isLoading && !isError && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Quote #
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
                  Valid Until
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Created At
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {quotes.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-16 text-center text-sm text-gray-400"
                  >
                    No quotes found.
                  </td>
                </tr>
              ) : (
                quotes.map((quote: Quote) => (
                  <tr
                    key={quote.id}
                    className="transition-colors hover:bg-gray-50"
                  >
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                      {quote.quote_number}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                      {quote.customer_name ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                          statusColor(quote.status)
                        )}
                      >
                        {quote.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                      {formatCurrency(quote.total_amount)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {quote.valid_until
                        ? new Date(quote.valid_until).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {new Date(quote.created_at).toLocaleDateString()}
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
