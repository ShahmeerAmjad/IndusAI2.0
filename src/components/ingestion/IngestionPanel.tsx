import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type IngestionEvent } from "@/lib/api";
import {
  Play, Loader2, CheckCircle, AlertCircle, Database,
  FileText, Download, Cpu, Globe
} from "lucide-react";

const INDUSTRY_OPTIONS = [
  "Adhesives", "Coatings", "Pharma", "Personal Care", "Water Treatment",
  "Food & Beverage", "Plastics", "Energy", "Agriculture", "Construction",
];

const INDUSTRY_URLS: Record<string, string> = {
  "Adhesives": "https://www.chempoint.com/en-us/products/industry/adhesives-and-sealants",
  "Coatings": "https://www.chempoint.com/en-us/products/industry/paints-and-coatings",
  "Pharma": "https://www.chempoint.com/en-us/products/industry/pharmaceutical",
  "Personal Care": "https://www.chempoint.com/en-us/products/industry/personal-care",
  "Water Treatment": "https://www.chempoint.com/en-us/products/industry/water-treatment",
  "Food & Beverage": "https://www.chempoint.com/en-us/products/industry/food-and-beverage",
  "Plastics": "https://www.chempoint.com/en-us/products/industry/plastics-and-rubber",
  "Energy": "https://www.chempoint.com/en-us/products/industry/energy",
  "Agriculture": "https://www.chempoint.com/en-us/products/industry/agriculture",
  "Construction": "https://www.chempoint.com/en-us/products/industry/building-and-construction",
};

const STAGE_ICONS: Record<string, typeof Play> = {
  discovering: Globe,
  scraping: Download,
  downloading_pdf: FileText,
  extracting: Cpu,
  building_graph: Database,
};

function StageIcon({ stage }: { stage: string }) {
  const Icon = STAGE_ICONS[stage] || Loader2;
  return <Icon size={14} className={stage === "done" ? "text-green-500" : "animate-pulse text-blue-500"} />;
}

export default function IngestionPanel() {
  const [mode, setMode] = useState<"single" | "batch">("batch");
  const [url, setUrl] = useState("");
  const [selectedIndustries, setSelectedIndustries] = useState<string[]>(["Adhesives", "Coatings"]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<IngestionEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const { data: job } = useQuery({
    queryKey: ["ingestion-job", jobId],
    queryFn: () => api.getIngestionJob(jobId!),
    enabled: !!jobId && !wsConnected,
    refetchInterval: jobId ? 2000 : false,
  });

  useEffect(() => {
    if (!jobId) return;
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ingestion/ws/${jobId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data) as IngestionEvent;
      setEvents((prev) => [...prev, event]);
    };
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    return () => ws.close();
  }, [jobId]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const startSingle = useMutation({
    mutationFn: () => api.startIngestion(url),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setEvents([]);
    },
  });

  const startBatch = useMutation({
    mutationFn: () => {
      const urls = selectedIndustries
        .filter((i) => INDUSTRY_URLS[i])
        .map((i) => INDUSTRY_URLS[i]);
      return api.startBatchIngestion(urls);
    },
    onSuccess: (data) => {
      setJobId(data.job_id);
      setEvents([]);
    },
  });

  const cancelJob = useMutation({
    mutationFn: () => jobId ? api.cancelIngestion(jobId) : Promise.reject("No job"),
    onSuccess: () => {
      setEvents(prev => [...prev, { stage: "cancelled", detail: "Cancelled by user" }]);
    },
  });

  const isRunning = job?.status === "running" || startSingle.isPending || startBatch.isPending;
  const isCancelled = events.some((e) => e.stage === "cancelled");
  const isDone = events.some((e) => e.stage === "done");
  const lastEvent = events[events.length - 1];
  const productCount = events.filter((e) => e.stage === "building_graph").length;
  const errorCount = events.filter((e) => e.stage === "error").length;

  const toggleIndustry = (ind: string) => {
    setSelectedIndustries((prev) =>
      prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind]
    );
  };

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-800">Data Ingestion</h3>
        <div className="flex gap-1 rounded-lg bg-slate-100 p-0.5">
          <button onClick={() => setMode("single")}
            className={`rounded-md px-3 py-1 text-xs font-medium ${mode === "single" ? "bg-white shadow-sm text-slate-800" : "text-slate-500"}`}>
            Single URL
          </button>
          <button onClick={() => setMode("batch")}
            className={`rounded-md px-3 py-1 text-xs font-medium ${mode === "batch" ? "bg-white shadow-sm text-slate-800" : "text-slate-500"}`}>
            Batch Industries
          </button>
        </div>
      </div>

      {mode === "single" ? (
        <div className="flex gap-2">
          <input value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="https://chempoint.com/products/..."
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none" />
          <button onClick={() => startSingle.mutate()} disabled={!url || isRunning}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Ingest
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {INDUSTRY_OPTIONS.map((ind) => (
              <button key={ind} onClick={() => toggleIndustry(ind)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  selectedIndustries.includes(ind)
                    ? "border-blue-300 bg-blue-50 text-blue-700"
                    : "border-slate-200 text-slate-500 hover:border-slate-300"
                }`}>
                {ind}
              </button>
            ))}
          </div>
          <button onClick={() => startBatch.mutate()}
            disabled={selectedIndustries.length === 0 || isRunning}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Seed {selectedIndustries.length} Industries
          </button>
        </div>
      )}

      {jobId && (
        <div className="space-y-3">
          <div className="flex gap-4 text-sm">
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle size={14} /> {productCount} products
            </span>
            {errorCount > 0 && (
              <span className="flex items-center gap-1 text-red-500">
                <AlertCircle size={14} /> {errorCount} errors
              </span>
            )}
            <span className={`ml-auto text-xs ${wsConnected ? "text-green-500" : "text-slate-400"}`}>
              {wsConnected ? "Live" : "Polling"}
            </span>
          </div>

          {lastEvent && !isDone && (
            <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">
              <StageIcon stage={lastEvent.stage} />
              <span className="font-medium">{lastEvent.product || lastEvent.detail || lastEvent.stage}</span>
              {lastEvent.current && lastEvent.total && (
                <span className="ml-auto text-xs text-blue-400">
                  {lastEvent.current}/{lastEvent.total}
                </span>
              )}
            </div>
          )}

          {lastEvent?.current && lastEvent?.total && (
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-blue-500 transition-all duration-300"
                style={{ width: `${(lastEvent.current / lastEvent.total) * 100}%` }} />
            </div>
          )}

          {jobId && !isDone && !isCancelled && (
            <button
              onClick={() => cancelJob.mutate()}
              className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200"
              disabled={cancelJob.isPending}
            >
              {cancelJob.isPending ? "Cancelling..." : "Cancel"}
            </button>
          )}

          <div ref={logRef}
            className="max-h-48 overflow-y-auto rounded-lg bg-slate-50 p-3 font-mono text-xs text-slate-600">
            {events.map((e, i) => (
              <div key={i} className="flex items-center gap-2 py-0.5">
                <StageIcon stage={e.stage} />
                <span className="text-slate-400">{e.stage}</span>
                <span>{e.product || e.detail || ""}</span>
              </div>
            ))}
          </div>

          {isDone && lastEvent?.result && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3">
              <p className="mb-2 text-sm font-semibold text-green-800">Ingestion Complete</p>
              <div className="grid grid-cols-4 gap-2 text-center text-xs">
                {Object.entries(lastEvent.result).map(([k, v]) => (
                  <div key={k}>
                    <p className="text-lg font-bold text-green-700">{v as number}</p>
                    <p className="text-green-600">{k.replace(/_/g, " ")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
