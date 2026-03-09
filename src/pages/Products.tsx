import { useQuery } from "@tanstack/react-query";
import { api, CatalogProduct } from "@/lib/api";
import { useState, useMemo, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  Search, ChevronDown, ChevronRight, Check, Minus,
  FileText, Shield, Download, ExternalLink, X,
} from "lucide-react";
import ProductDrawer from "@/components/products/ProductDrawer";

type DocFilter = "all" | "has_tds" | "has_sds" | "missing_tds" | "missing_sds";

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function Products() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [page, setPage] = useState(1);
  const [manufacturer, setManufacturer] = useState("");
  const [industry, setIndustry] = useState("");
  const [docFilter, setDocFilter] = useState<DocFilter>("all");
  const [expandedSku, setExpandedSku] = useState<string | null>(null);
  const [drawerSku, setDrawerSku] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Reset to page 1 when search changes
  const prevSearch = useRef(debouncedSearch);
  useEffect(() => {
    if (prevSearch.current !== debouncedSearch) {
      setPage(1);
      prevSearch.current = debouncedSearch;
    }
  }, [debouncedSearch]);

  // Derive has_tds / has_sds from docFilter
  const filterParams = useMemo(() => {
    const p: { has_tds?: boolean; has_sds?: boolean } = {};
    if (docFilter === "has_tds") p.has_tds = true;
    if (docFilter === "has_sds") p.has_sds = true;
    if (docFilter === "missing_tds") p.has_tds = false;
    if (docFilter === "missing_sds") p.has_sds = false;
    return p;
  }, [docFilter]);

  const { data, isLoading } = useQuery({
    queryKey: ["catalog-products", page, debouncedSearch, manufacturer, industry, docFilter],
    queryFn: () =>
      api.getCatalogProducts({
        page, pageSize: 25, search: debouncedSearch || undefined,
        manufacturer: manufacturer || undefined,
        industry: industry || undefined,
        ...filterParams,
      }),
  });

  const { data: filters } = useQuery({
    queryKey: ["catalog-filters"],
    queryFn: () => api.getCatalogFilters(),
  });

  const hasActiveFilters = !!debouncedSearch || !!manufacturer || !!industry || docFilter !== "all";

  const products = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 25));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-montserrat font-bold text-neutral-900">Product Catalog</h1>
        <p className="text-neutral-500 text-sm mt-1">
          {total.toLocaleString()} products — Parts, Manufacturers, TDS & SDS Documents
        </p>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[300px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
          <input
            ref={searchRef}
            type="text" value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, SKU, manufacturer, description..."
            className="w-full pl-10 pr-9 py-2 border border-neutral-300 rounded-lg text-sm
                       focus:outline-none focus:ring-2 focus:ring-industrial-600 bg-white"
          />
          {search && (
            <button onClick={() => { setSearch(""); searchRef.current?.focus(); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600">
              <X size={14} />
            </button>
          )}
        </div>

        <select value={manufacturer} onChange={(e) => { setManufacturer(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[160px]">
          <option value="">All Manufacturers</option>
          {(filters?.manufacturers ?? []).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>

        <select value={industry} onChange={(e) => { setIndustry(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[140px]">
          <option value="">All Industries</option>
          {(filters?.industries ?? []).map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>

        <select value={docFilter} onChange={(e) => { setDocFilter(e.target.value as DocFilter); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[140px]">
          <option value="all">All Docs</option>
          <option value="has_tds">Has TDS</option>
          <option value="has_sds">Has SDS</option>
          <option value="missing_tds">Missing TDS</option>
          <option value="missing_sds">Missing SDS</option>
        </select>

        {hasActiveFilters && (
          <button onClick={() => { setSearch(""); setManufacturer(""); setIndustry(""); setDocFilter("all"); setPage(1); }}
            className="px-3 py-2 border border-neutral-300 text-neutral-600 text-sm rounded-lg hover:bg-neutral-50">
            Clear All
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 bg-neutral-50 rounded-lg border border-dashed border-neutral-300">
          <p className="text-neutral-500 text-sm">No products found.</p>
        </div>
      ) : (
        <div className="border border-neutral-200 rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-200">
                <th className="w-8 px-3 py-3"></th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">SKU</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Name</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Manufacturer</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">TDS</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">SDS</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Industries</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <ProductRow
                  key={product.sku}
                  product={product}
                  isExpanded={expandedSku === product.sku}
                  onToggle={() => setExpandedSku(expandedSku === product.sku ? null : product.sku)}
                  onViewDetails={() => setDrawerSku(product.sku)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <p className="text-sm text-neutral-500">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
              className={cn("px-4 py-2 text-sm font-medium rounded-lg border",
                page <= 1 ? "border-neutral-200 text-neutral-300 cursor-not-allowed" : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}>Previous</button>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className={cn("px-4 py-2 text-sm font-medium rounded-lg border",
                page >= totalPages ? "border-neutral-200 text-neutral-300 cursor-not-allowed" : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}>Next</button>
          </div>
        </div>
      )}

      {/* Drawer */}
      {drawerSku && (
        <ProductDrawer sku={drawerSku} onClose={() => setDrawerSku(null)} />
      )}
    </div>
  );
}

/* ---- Expandable Row Sub-component ---- */

function ProductRow({ product, isExpanded, onToggle, onViewDetails }: {
  product: CatalogProduct;
  isExpanded: boolean;
  onToggle: () => void;
  onViewDetails: () => void;
}) {
  return (
    <>
      <tr onClick={onToggle}
        className={cn(
          "border-b border-neutral-100 cursor-pointer hover:bg-neutral-50 transition-colors",
          isExpanded && "bg-industrial-50"
        )}>
        <td className="px-3 py-3 text-neutral-400">
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs bg-industrial-100 text-industrial-800 px-2 py-0.5 rounded">
            {product.sku}
          </span>
        </td>
        <td className="px-4 py-3 font-medium text-neutral-900 max-w-[300px] truncate">{product.name}</td>
        <td className="px-4 py-3 text-neutral-600">{product.manufacturer || "\u2014"}</td>
        <td className="px-4 py-3 text-center">
          {product.has_tds
            ? <Check size={16} className="inline text-blue-600" />
            : <Minus size={16} className="inline text-neutral-300" />}
        </td>
        <td className="px-4 py-3 text-center">
          {product.has_sds
            ? <Check size={16} className="inline text-red-600" />
            : <Minus size={16} className="inline text-neutral-300" />}
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {(product.industries || []).slice(0, 3).map((ind) => (
              <span key={ind} className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                {ind}
              </span>
            ))}
            {(product.industries || []).length > 3 && (
              <span className="text-xs text-neutral-400">+{product.industries.length - 3}</span>
            )}
          </div>
        </td>
      </tr>

      {isExpanded && (
        <tr>
          <td colSpan={7} className="bg-neutral-50 border-b border-neutral-200 px-8 py-4">
            <ExpandedProductDetail sku={product.sku} onViewDetails={onViewDetails} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ---- Expanded Accordion Content ---- */

function ExpandedProductDetail({ sku, onViewDetails }: { sku: string; onViewDetails: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["product-extraction", sku],
    queryFn: () => api.getProductExtraction(sku),
  });

  if (isLoading) {
    return <div className="text-sm text-neutral-400 py-2">Loading extraction data...</div>;
  }

  if (!data) {
    return <div className="text-sm text-neutral-400 py-2">No extraction data available.</div>;
  }

  const tdsFields = data.tds?.fields ?? {};
  const sdsFields = data.sds?.fields ?? {};

  return (
    <div className="space-y-3">
      <div className="grid gap-4 md:grid-cols-2">
        {/* TDS Summary */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-blue-600" />
              <span className="text-sm font-semibold text-neutral-700">TDS Fields</span>
            </div>
            <div className="flex items-center gap-1.5">
              {data.tds?.pdf_url && (
                <a href={data.tds.pdf_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                  <Download size={12} /> Download
                </a>
              )}
              {data.tds?.source_url && (
                <a href={data.tds.source_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
                  <ExternalLink size={12} /> Chempoint
                </a>
              )}
            </div>
          </div>
          <div className="p-3">
            {Object.keys(tdsFields).length > 0 ? (
              <dl className="space-y-1.5 text-sm">
                {Object.entries(tdsFields).slice(0, 8).map(([key, val]) => {
                  const display = typeof val === "object" && val !== null && "value" in val
                    ? String((val as { value: unknown }).value ?? "\u2014")
                    : String(val ?? "\u2014");
                  if (display === "\u2014" || display === "null") return null;
                  return (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-neutral-400 capitalize">{key.replace(/_/g, " ")}</dt>
                      <dd className="text-right font-medium text-neutral-700 truncate max-w-[200px]">{display}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : (
              <p className="text-sm italic text-neutral-400">No TDS data extracted</p>
            )}
          </div>
        </div>

        {/* SDS Summary */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-red-600" />
              <span className="text-sm font-semibold text-neutral-700">SDS Fields</span>
            </div>
            <div className="flex items-center gap-1.5">
              {data.sds?.pdf_url && (
                <a href={data.sds.pdf_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                  <Download size={12} /> Download
                </a>
              )}
              {data.sds?.source_url && (
                <a href={data.sds.source_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-red-600 hover:underline">
                  <ExternalLink size={12} /> Chempoint
                </a>
              )}
            </div>
          </div>
          <div className="p-3">
            {Object.keys(sdsFields).length > 0 ? (
              <dl className="space-y-1.5 text-sm">
                {Object.entries(sdsFields).slice(0, 8).map(([key, val]) => {
                  const display = typeof val === "object" && val !== null && "value" in val
                    ? String((val as { value: unknown }).value ?? "\u2014")
                    : String(val ?? "\u2014");
                  if (display === "\u2014" || display === "null") return null;
                  return (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-neutral-400 capitalize">{key.replace(/_/g, " ")}</dt>
                      <dd className="text-right font-medium text-neutral-700 truncate max-w-[200px]">{display}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : (
              <p className="text-sm italic text-neutral-400">No SDS data extracted</p>
            )}
          </div>
        </div>
      </div>

      <button onClick={onViewDetails}
        className="flex items-center gap-1.5 text-sm text-industrial-600 hover:text-industrial-800 font-medium">
        <ExternalLink size={14} /> View Full Details
      </button>
    </div>
  );
}
