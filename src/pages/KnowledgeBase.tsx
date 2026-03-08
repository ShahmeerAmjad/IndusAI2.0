import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, BookOpen, FileText, Shield, ChevronDown, ChevronUp, Network, Download } from "lucide-react";
import { api, type GraphPart, type DocumentMeta } from "@/lib/api";
import TDSSDSViewer from "@/components/products/TDSSDSViewer";
import IngestionPanel from "@/components/ingestion/IngestionPanel";
import GraphExplorer from "@/components/graph/GraphExplorer";

const TABS = [
  { key: "products", label: "Products", icon: BookOpen },
  { key: "graph", label: "Graph Explorer", icon: Network },
  { key: "ingestion", label: "Ingestion", icon: Download },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function KnowledgeBase() {
  const [tab, setTab] = useState<TabKey>("products");
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { data: searchData, isLoading } = useQuery({
    queryKey: ["kb-products", searchTerm],
    queryFn: () => api.searchProducts(searchTerm),
    enabled: searchTerm.length >= 2,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchTerm(query.trim());
  };

  const results = searchData?.items ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-600 text-white">
          <BookOpen size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-neutral-800">Knowledge Base</h1>
          <p className="text-sm text-neutral-500">Search products, TDS/SDS documents, and technical data</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-neutral-100 p-1">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === key
                ? "bg-white text-neutral-800 shadow-sm"
                : "text-neutral-500 hover:text-neutral-700"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Products Tab */}
      {tab === "products" && (
        <>
          {/* Search bar */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by product name, SKU, CAS number..."
                className="w-full rounded-lg border border-neutral-300 py-2.5 pl-10 pr-4 text-sm focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-industrial-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-industrial-700"
            >
              Search
            </button>
          </form>

          {/* Results */}
          {!searchTerm ? (
            <div className="flex h-48 flex-col items-center justify-center text-neutral-400">
              <BookOpen size={36} className="mb-3" />
              <p>Enter a search term to find products and documents</p>
            </div>
          ) : isLoading ? (
            <div className="flex h-32 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-industrial-600" />
            </div>
          ) : results.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center text-neutral-400">
              <p>No products found for "{searchTerm}"</p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-neutral-500">
                {searchData?.total ?? results.length} results
              </p>
              {results.map((p) => (
                <ProductCard key={p.sku} part={p} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Graph Explorer Tab */}
      {tab === "graph" && <GraphExplorer />}

      {/* Ingestion Tab */}
      {tab === "ingestion" && <IngestionPanel />}
    </div>
  );
}

function ProductCard({ part }: { part: GraphPart }) {
  const [expanded, setExpanded] = useState(false);

  const { data: docs } = useQuery({
    queryKey: ["kb-docs", part.sku],
    queryFn: () => api.getDocumentsForProduct(part.sku),
    enabled: expanded,
  });

  const hasTDS = docs?.some((d) => d.doc_type === "TDS");
  const hasSDS = docs?.some((d) => d.doc_type === "SDS");

  return (
    <div className="rounded-lg border border-neutral-200 bg-white transition hover:border-neutral-300">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-4 p-4 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-neutral-800">{part.name || part.sku}</span>
            <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs font-mono text-neutral-500">
              {part.sku}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
            {part.manufacturer && <span>{part.manufacturer}</span>}
            {part.category && (
              <>
                <span>&middot;</span>
                <span>{part.category}</span>
              </>
            )}
          </div>
          {part.description && (
            <p className="mt-1 line-clamp-2 text-sm text-neutral-500">{part.description}</p>
          )}
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <FileText size={14} className={hasTDS ? "text-blue-500" : "text-neutral-300"} title="TDS" />
          <Shield size={14} className={hasSDS ? "text-red-500" : "text-neutral-300"} title="SDS" />
          {expanded ? <ChevronUp size={16} className="text-neutral-400" /> : <ChevronDown size={16} className="text-neutral-400" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-neutral-100 p-4">
          {/* Specs */}
          {part.specs && part.specs.length > 0 && (
            <div className="mb-4">
              <h4 className="mb-2 text-xs font-semibold uppercase text-neutral-400">Specifications</h4>
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                {part.specs.map((s, i) => (
                  <div key={i} className="rounded bg-neutral-50 px-2 py-1">
                    <span className="text-neutral-400">{s.name}: </span>
                    <span className="font-medium text-neutral-700">
                      {s.value}{s.unit ? ` ${s.unit}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <TDSSDSViewer />

          {/* Documents */}
          {docs && docs.length > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-xs font-semibold uppercase text-neutral-400">Documents</h4>
              <div className="flex flex-wrap gap-2">
                {docs.map((d) => (
                  <a
                    key={d.id}
                    href={`/api/v1/documents/${d.id}/download`}
                    className="flex items-center gap-1.5 rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium text-industrial-600 hover:bg-industrial-50"
                  >
                    {d.doc_type === "TDS" ? <FileText size={12} /> : <Shield size={12} />}
                    {d.file_name}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
