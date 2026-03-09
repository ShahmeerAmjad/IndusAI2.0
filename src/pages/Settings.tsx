import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type KeysResponse, type KeysUpdateRequest } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Key, Eye, EyeOff, Save, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

interface KeyCardProps {
  label: string;
  envName: string;
  description: string;
  configured: boolean;
  preview: string;
  fieldKey: keyof KeysUpdateRequest;
  onSave: (key: keyof KeysUpdateRequest, value: string) => void;
  isSaving: boolean;
  savingField: keyof KeysUpdateRequest | null;
  saveResult: { field: keyof KeysUpdateRequest; success: boolean; message: string } | null;
}

function KeyCard({
  label,
  envName,
  description,
  configured,
  preview,
  fieldKey,
  onSave,
  isSaving,
  savingField,
  saveResult,
}: KeyCardProps) {
  const [value, setValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const isThisSaving = isSaving && savingField === fieldKey;
  const thisResult = saveResult?.field === fieldKey ? saveResult : null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
            <Key className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{label}</h3>
            <p className="mt-0.5 text-xs text-slate-500">{description}</p>
            <p className="mt-1 font-mono text-[11px] text-slate-400">{envName}</p>
          </div>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
            configured
              ? "bg-green-50 text-green-700"
              : "bg-amber-50 text-amber-700"
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              configured ? "bg-green-500" : "bg-amber-500"
            )}
          />
          {configured ? "Configured" : "Not Set"}
        </span>
      </div>

      {configured && preview && (
        <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2">
          <p className="font-mono text-xs text-slate-500">{preview}</p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type={showValue ? "text" : "password"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={configured ? "Enter new key to update" : "Enter API key"}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 pr-10 font-mono text-sm text-slate-800 placeholder:text-slate-400 focus:border-industrial-400 focus:outline-none focus:ring-2 focus:ring-industrial-100"
          />
          <button
            type="button"
            onClick={() => setShowValue(!showValue)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <button
          onClick={() => {
            if (value.trim()) {
              onSave(fieldKey, value.trim());
              setValue("");
              setShowValue(false);
            }
          }}
          disabled={!value.trim() || isThisSaving}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            value.trim() && !isThisSaving
              ? "bg-industrial-600 text-white hover:bg-industrial-700"
              : "bg-slate-100 text-slate-400 cursor-not-allowed"
          )}
        >
          {isThisSaving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save
        </button>
      </div>

      {thisResult && (
        <div
          className={cn(
            "mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium",
            thisResult.success
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700"
          )}
        >
          {thisResult.success ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : (
            <AlertCircle className="h-3.5 w-3.5" />
          )}
          {thisResult.message}
        </div>
      )}
    </div>
  );
}

const KEY_CONFIG: Array<{
  label: string;
  envName: string;
  description: string;
  fieldKey: keyof KeysUpdateRequest;
}> = [
  {
    label: "Anthropic API Key",
    envName: "ANTHROPIC_API_KEY",
    description: "Required — powers all AI features (classification, drafts, extraction)",
    fieldKey: "anthropic_api_key",
  },
  {
    label: "Firecrawl API Key",
    envName: "FIRECRAWL_API_KEY",
    description: "Optional — high-quality web scraping with JS rendering",
    fieldKey: "firecrawl_api_key",
  },
  {
    label: "Voyage API Key",
    envName: "VOYAGE_API_KEY",
    description: "Optional — required for vector search & graph sync",
    fieldKey: "voyage_api_key",
  },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const [savingField, setSavingField] = useState<keyof KeysUpdateRequest | null>(null);
  const [saveResult, setSaveResult] = useState<{
    field: keyof KeysUpdateRequest;
    success: boolean;
    message: string;
  } | null>(null);

  const { data, isLoading } = useQuery<KeysResponse>({
    queryKey: ["settings-keys"],
    queryFn: api.getKeys,
  });

  const mutation = useMutation({
    mutationFn: api.updateKeys,
    onSuccess: (result, variables) => {
      const field = Object.keys(variables)[0] as keyof KeysUpdateRequest;
      setSaveResult({ field, success: true, message: result.message || "Key updated successfully" });
      queryClient.invalidateQueries({ queryKey: ["settings-keys"] });
      setTimeout(() => setSaveResult(null), 4000);
    },
    onError: (error: Error, variables) => {
      const field = Object.keys(variables)[0] as keyof KeysUpdateRequest;
      setSaveResult({ field, success: false, message: error.message || "Failed to update key" });
      setTimeout(() => setSaveResult(null), 4000);
    },
    onSettled: () => {
      setSavingField(null);
    },
  });

  const handleSave = (field: keyof KeysUpdateRequest, value: string) => {
    setSavingField(field);
    setSaveResult(null);
    mutation.mutate({ [field]: value });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-montserrat text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">Manage API keys and configuration</p>
      </div>

      {/* API Keys Section */}
      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-700">
          API Keys
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="space-y-4">
            {KEY_CONFIG.map((config) => {
              const keyData = data?.keys?.[config.fieldKey];
              return (
                <KeyCard
                  key={config.fieldKey}
                  label={config.label}
                  envName={config.envName}
                  description={config.description}
                  configured={keyData?.configured ?? false}
                  preview={keyData?.preview ?? ""}
                  fieldKey={config.fieldKey}
                  onSave={handleSave}
                  isSaving={mutation.isPending}
                  savingField={savingField}
                  saveResult={saveResult}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
