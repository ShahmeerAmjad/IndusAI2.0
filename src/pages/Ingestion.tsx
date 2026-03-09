import IngestionPanel from "@/components/ingestion/IngestionPanel";

export default function Ingestion() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Data Ingestion</h1>
        <p className="text-sm text-slate-500 mt-1">
          Scrape Chempoint catalog to populate the knowledge graph
        </p>
      </div>
      <IngestionPanel />
    </div>
  );
}
