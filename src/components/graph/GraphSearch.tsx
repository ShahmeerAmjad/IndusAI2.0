import { useState, useCallback, useRef } from "react";
import { Search, X } from "lucide-react";
import { NODE_COLORS } from "@/hooks/useGraphData";

interface SearchResult {
  id: string;
  name: string;
  nodeType: string;
}

interface GraphSearchProps {
  results: SearchResult[];
  onSearch: (query: string) => void;
  onSelect: (nodeId: string) => void;
  onClear: () => void;
  darkMode: boolean;
}

export default function GraphSearch({
  results,
  onSearch,
  onSelect,
  onClear,
  darkMode,
}: GraphSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const bg = darkMode
    ? "bg-slate-900/80 border-slate-700"
    : "bg-white/90 border-slate-200";
  const text = darkMode ? "text-white" : "text-slate-900";
  const textMuted = darkMode ? "text-slate-400" : "text-slate-500";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-100";

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value);
      onSearch(value);
      setOpen(value.length > 0);
    },
    [onSearch],
  );

  const handleClear = useCallback(() => {
    setQuery("");
    onSearch("");
    onClear();
    setOpen(false);
    inputRef.current?.focus();
  }, [onSearch, onClear]);

  const handleSelect = useCallback(
    (nodeId: string) => {
      onSelect(nodeId);
      setOpen(false);
    },
    [onSelect],
  );

  return (
    <div className={`absolute left-4 top-4 z-30 w-72 rounded-xl border shadow-lg backdrop-blur-sm ${bg}`}>
      <div className="relative">
        <Search size={14} className={`absolute left-3 top-1/2 -translate-y-1/2 ${textMuted}`} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Search nodes..."
          className={`w-full rounded-xl bg-transparent py-2.5 pl-9 pr-8 text-sm focus:outline-none ${text}`}
        />
        {query && (
          <button
            onClick={handleClear}
            className={`absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 ${textMuted} ${hoverBg}`}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className={`max-h-60 overflow-y-auto border-t p-1 ${darkMode ? "border-slate-700" : "border-slate-200"}`}>
          {results.slice(0, 20).map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm ${text} ${hoverBg} transition`}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: NODE_COLORS[r.nodeType] || "#6b7280" }}
              />
              <span className="flex-1 truncate">{r.name}</span>
              <span className={`text-xs ${textMuted}`}>{r.nodeType}</span>
            </button>
          ))}
        </div>
      )}

      {open && query.length > 0 && results.length === 0 && (
        <div className={`border-t p-3 text-center text-xs ${textMuted} ${darkMode ? "border-slate-700" : "border-slate-200"}`}>
          No matching nodes
        </div>
      )}
    </div>
  );
}
