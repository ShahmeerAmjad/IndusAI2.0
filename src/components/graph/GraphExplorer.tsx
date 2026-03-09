import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import SigmaGraph from "./SigmaGraph";

export default function GraphExplorer() {
  const [industry, setIndustry] = useState<string>("");
  const [manufacturer, setManufacturer] = useState<string>("");

  const { data: filters } = useQuery({
    queryKey: ["catalog-filters"],
    queryFn: () => api.getCatalogFilters(),
  });

  return (
    <div className="space-y-4">
      {/* Filter dropdowns */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All Industries</option>
          {(filters?.industries || []).map((ind) => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
        <select
          value={manufacturer}
          onChange={(e) => setManufacturer(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All Manufacturers</option>
          {(filters?.manufacturers || []).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* Graph */}
      <SigmaGraph
        industry={industry || undefined}
        manufacturer={manufacturer || undefined}
        defaultDarkMode={false}
        height="500px"
      />
    </div>
  );
}
