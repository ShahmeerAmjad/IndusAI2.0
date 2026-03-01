import { useState } from "react";
import { Download, FileSpreadsheet, FileText, File } from "lucide-react";
import { toast } from "sonner";

type Format = "csv" | "xlsx" | "pdf";

interface Props {
  endpoint: string;
  label?: string;
  params?: Record<string, string>;
}

const FORMAT_ICONS: Record<Format, typeof Download> = {
  csv: FileText,
  xlsx: FileSpreadsheet,
  pdf: File,
};

export default function ReportDownloadButton({
  endpoint,
  label = "Download Report",
  params = {},
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState<Format | null>(null);

  async function handleDownload(format: Format) {
    setLoading(format);
    setIsOpen(false);

    try {
      const searchParams = new URLSearchParams({ format, ...params });
      const token = localStorage.getItem("indusai_access_token");
      const res = await fetch(`/api/v1/reports/${endpoint}?${searchParams}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!res.ok) throw new Error(`Download failed: ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${endpoint}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${format.toUpperCase()} downloaded`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
      >
        <Download className="h-3.5 w-3.5" />
        {label}
      </button>

      {isOpen && (
        <div className="absolute right-0 z-10 mt-1 w-36 rounded-md border border-slate-200 bg-white shadow-lg">
          {(["csv", "xlsx", "pdf"] as Format[]).map((fmt) => {
            const Icon = FORMAT_ICONS[fmt];
            return (
              <button
                key={fmt}
                onClick={() => handleDownload(fmt)}
                disabled={loading !== null}
                className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50 first:rounded-t-md last:rounded-b-md"
              >
                <Icon className="h-3.5 w-3.5" />
                {loading === fmt ? "Downloading..." : fmt.toUpperCase()}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
