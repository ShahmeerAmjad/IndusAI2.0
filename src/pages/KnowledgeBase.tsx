import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, BookOpen, FileText, Shield, ChevronDown, ChevronUp } from "lucide-react";
import { api, type GraphPart, type DocumentMeta } from "@/lib/api";
import TDSSDSViewer from "@/components/products/TDSSDSViewer";

export default function KnowledgeBase() {
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { data: searchResults, isLoading } = useQuery({
    queryKey: ["kb-search", searchTerm],
    queryFn: () => api.searchGraph(searchTerm, 30),
    enabled: searchTerm.length >= 2,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchTerm(query.trim());
  };

  const results = searchResults?.results ?? [];

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
          <p className="text-sm text-neutral-500">{results.length} results</p>
          {results.map((r) => (
            <ProductCard key={r.node.sku} part={r.node} score={r.score} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProductCard({ part, score }: { part: GraphPart; score: number }) {
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
            <span>&middot;</span>
            <span>Score: {score.toFixed(2)}</span>
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

          {/* TDS/SDS viewer placeholder (no graph TDS/SDS data in search results) */}
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
