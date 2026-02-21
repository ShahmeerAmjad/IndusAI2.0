import { useQuery } from "@tanstack/react-query";
import { api, Product } from "@/lib/api";
import { useState } from "react";
import { formatCurrency, cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

export default function Products() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Reset to page 1 when search changes
  const [appliedSearch, setAppliedSearch] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["products", page, appliedSearch],
    queryFn: () => api.getProducts(page, appliedSearch),
  });

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setAppliedSearch(search);
    setPage(1);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-500 font-inter text-sm">Loading products...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md text-center">
          <h3 className="text-red-800 font-semibold text-lg mb-2">Failed to load products</h3>
          <p className="text-red-600 text-sm">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </p>
        </div>
      </div>
    );
  }

  const products = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-montserrat font-bold text-neutral-900">Product Catalog</h1>
        <p className="text-neutral-500 text-sm mt-1">
          Browse and search MRO products ({total.toLocaleString()} items)
        </p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearchSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by SKU, name, or manufacturer..."
            className="w-full pl-10 pr-4 py-2.5 border border-neutral-300 rounded-lg text-sm
                       focus:outline-none focus:ring-2 focus:ring-industrial-600 focus:border-transparent
                       placeholder:text-neutral-400 bg-white"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 bg-industrial-800 text-white text-sm font-medium rounded-lg
                     hover:bg-industrial-900 transition-colors"
        >
          Search
        </button>
        {appliedSearch && (
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setAppliedSearch("");
              setPage(1);
            }}
            className="px-4 py-2.5 border border-neutral-300 text-neutral-600 text-sm font-medium
                       rounded-lg hover:bg-neutral-50 transition-colors"
          >
            Clear
          </button>
        )}
      </form>

      {/* Product Grid */}
      {products.length === 0 ? (
        <div className="text-center py-16 bg-neutral-50 rounded-lg border border-dashed border-neutral-300">
          <p className="text-neutral-500 text-sm">No products found matching your search.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product: Product) => (
            <div
              key={product.id}
              onClick={() => navigate(`/products/${product.id}`)}
              className="bg-white border border-neutral-200 rounded-lg p-5 cursor-pointer
                         hover:border-industrial-400 hover:shadow-md transition-all group"
            >
              {/* SKU Badge */}
              <div className="flex items-center justify-between mb-3">
                <span className="inline-block bg-industrial-100 text-industrial-800 text-xs font-semibold px-2.5 py-1 rounded-md font-mono">
                  {product.sku}
                </span>
                <svg
                  className="h-4 w-4 text-neutral-300 group-hover:text-industrial-600 transition-colors"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>

              {/* Product Name */}
              <h3 className="font-semibold text-neutral-900 text-sm leading-snug mb-2 group-hover:text-industrial-800 transition-colors">
                {product.name}
              </h3>

              {/* Details */}
              <div className="space-y-1.5 text-xs text-neutral-500">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-neutral-600 w-24 shrink-0">Manufacturer</span>
                  <span className="truncate">{product.manufacturer}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-neutral-600 w-24 shrink-0">Category</span>
                  <span className="truncate">{product.category}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-neutral-600 w-24 shrink-0">UOM</span>
                  <span>{product.uom}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-neutral-600 w-24 shrink-0">Lead Time</span>
                  <span>
                    {product.lead_time_days} {product.lead_time_days === 1 ? "day" : "days"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-neutral-500">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
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
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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
