import { useState, useRef } from "react";
import { Upload, FileText, Download, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

interface ImportError {
  row: number;
  field: string;
  error: string;
}

interface ImportResult {
  success: number;
  errors: ImportError[];
  total: number;
  dry_run: boolean;
}

type EntityType = "products" | "inventory";

export default function BulkImport() {
  const [entityType, setEntityType] = useState<EntityType>("products");
  const [dryRun, setDryRun] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    if (!file) return;
    setIsLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = localStorage.getItem("indusai_access_token");
      const res = await fetch(
        `/api/v1/bulk/${entityType}?dry_run=${dryRun}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        },
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${res.status}`);
      }

      const data: ImportResult = await res.json();
      setResult(data);

      if (data.errors.length === 0) {
        toast.success(
          dryRun
            ? `Dry run: ${data.success} records validated`
            : `${data.success} records imported`,
        );
      } else {
        toast.warning(`${data.success} succeeded, ${data.errors.length} errors`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function downloadTemplate() {
    const token = localStorage.getItem("indusai_access_token");
    const res = await fetch(`/api/v1/bulk/templates/${entityType}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${entityType}_template.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.name.endsWith(".csv")) {
      setFile(droppedFile);
      setResult(null);
    } else {
      toast.error("Only CSV files are accepted");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bulk Import</h1>
          <p className="text-sm text-gray-500">
            Upload CSV files to import products or inventory
          </p>
        </div>
        <button
          onClick={downloadTemplate}
          className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          <Download className="h-4 w-4" />
          Download {entityType} template
        </button>
      </div>

      {/* Entity type selector */}
      <div className="flex gap-3">
        {(["products", "inventory"] as EntityType[]).map((type) => (
          <button
            key={type}
            onClick={() => {
              setEntityType(type);
              setResult(null);
              setFile(null);
            }}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              entityType === type
                ? "bg-industrial-600 text-white"
                : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50"
            }`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-10 transition-colors hover:border-industrial-400 hover:bg-slate-100"
      >
        <Upload className="h-10 w-10 text-slate-400 mb-3" />
        <p className="text-sm font-medium text-slate-700">
          {file ? file.name : "Drop a CSV file here or click to browse"}
        </p>
        <p className="mt-1 text-xs text-slate-400">Max 5MB, CSV format only</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) {
              setFile(f);
              setResult(null);
            }
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="mt-3 rounded-md bg-white border border-slate-300 px-4 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          Browse files
        </button>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="rounded border-slate-300"
          />
          <span className="text-slate-700">Dry run (validate only)</span>
        </label>

        <button
          onClick={handleUpload}
          disabled={!file || isLoading}
          className="flex items-center gap-2 rounded-md bg-industrial-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-industrial-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              {dryRun ? "Validate" : "Import"}
            </>
          )}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-3 mb-4">
            {result.errors.length === 0 ? (
              <CheckCircle2 className="h-6 w-6 text-green-500" />
            ) : result.success > 0 ? (
              <AlertTriangle className="h-6 w-6 text-amber-500" />
            ) : (
              <XCircle className="h-6 w-6 text-red-500" />
            )}
            <div>
              <p className="text-sm font-semibold text-slate-900">
                {result.dry_run ? "Validation" : "Import"} Results
              </p>
              <p className="text-xs text-slate-500">
                {result.success} of {result.total} records{" "}
                {result.dry_run ? "validated" : "imported"} successfully
              </p>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-slate-700 mb-2">
                Errors ({result.errors.length})
              </p>
              <div className="max-h-60 overflow-y-auto rounded-md border border-slate-200">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-slate-600">Row</th>
                      <th className="px-3 py-2 text-left text-slate-600">Field</th>
                      <th className="px-3 py-2 text-left text-slate-600">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((err, i) => (
                      <tr key={i} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-slate-700">{err.row}</td>
                        <td className="px-3 py-2 font-mono text-slate-600">{err.field}</td>
                        <td className="px-3 py-2 text-red-600">{err.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
