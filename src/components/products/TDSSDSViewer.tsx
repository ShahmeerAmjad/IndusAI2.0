import { FileText, Shield, Download, ExternalLink } from "lucide-react";

interface TDSSDSViewerProps {
  tds?: Record<string, string | number | null>;
  sds?: Record<string, string | number | string[] | null>;
  tdsUrl?: string;
  sdsUrl?: string;
  tdsSourceUrl?: string;
  sdsSourceUrl?: string;
}

const TDS_FIELDS = [
  { key: "appearance", label: "Appearance" },
  { key: "density", label: "Density" },
  { key: "viscosity", label: "Viscosity" },
  { key: "flash_point", label: "Flash Point" },
  { key: "pH", label: "pH" },
  { key: "melting_point", label: "Melting Point" },
  { key: "boiling_point", label: "Boiling Point" },
  { key: "solubility", label: "Solubility" },
  { key: "storage_conditions", label: "Storage" },
  { key: "molecular_weight", label: "Molecular Weight" },
];

const SDS_FIELDS = [
  { key: "ghs_classification", label: "GHS Classification" },
  { key: "cas_numbers", label: "CAS Numbers" },
  { key: "un_number", label: "UN Number" },
  { key: "hazard_statements", label: "Hazard Statements" },
  { key: "ppe_requirements", label: "PPE Requirements" },
  { key: "first_aid", label: "First Aid" },
  { key: "storage_requirements", label: "Storage" },
];

function renderValue(val: unknown): string {
  if (val == null) return "-";
  if (Array.isArray(val)) return val.join(", ");
  return String(val);
}

export default function TDSSDSViewer({ tds, sds, tdsUrl, sdsUrl, tdsSourceUrl, sdsSourceUrl }: TDSSDSViewerProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* TDS card */}
      <div className="rounded-lg border border-neutral-200 bg-white">
        <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-blue-600" />
            <h4 className="text-sm font-semibold text-neutral-700">Technical Data Sheet</h4>
          </div>
          <div className="flex items-center gap-1.5">
            {tdsUrl && (
              <a href={tdsUrl} target="_blank" rel="noreferrer"
                 className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                <Download size={12} /> Download
              </a>
            )}
            {tdsSourceUrl && (
              <a href={tdsSourceUrl} target="_blank" rel="noreferrer"
                 className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
                <ExternalLink size={12} /> Chempoint
              </a>
            )}
          </div>
        </div>
        <div className="p-4">
          {tds && Object.keys(tds).length > 0 ? (
            <dl className="space-y-2 text-sm">
              {TDS_FIELDS.map((f) =>
                tds[f.key] != null ? (
                  <div key={f.key} className="flex justify-between gap-4">
                    <dt className="text-neutral-400">{f.label}</dt>
                    <dd className="text-right font-medium text-neutral-700">{renderValue(tds[f.key])}</dd>
                  </div>
                ) : null
              )}
            </dl>
          ) : (
            <p className="text-sm italic text-neutral-400">No TDS data available</p>
          )}
        </div>
      </div>

      {/* SDS card */}
      <div className="rounded-lg border border-neutral-200 bg-white">
        <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-3">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-red-600" />
            <h4 className="text-sm font-semibold text-neutral-700">Safety Data Sheet</h4>
          </div>
          <div className="flex items-center gap-1.5">
            {sdsUrl && (
              <a href={sdsUrl} target="_blank" rel="noreferrer"
                 className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                <Download size={12} /> Download
              </a>
            )}
            {sdsSourceUrl && (
              <a href={sdsSourceUrl} target="_blank" rel="noreferrer"
                 className="flex items-center gap-1 text-xs text-red-600 hover:underline">
                <ExternalLink size={12} /> Chempoint
              </a>
            )}
          </div>
        </div>
        <div className="p-4">
          {sds && Object.keys(sds).length > 0 ? (
            <dl className="space-y-2 text-sm">
              {SDS_FIELDS.map((f) =>
                sds[f.key] != null ? (
                  <div key={f.key} className="flex justify-between gap-4">
                    <dt className="text-neutral-400">{f.label}</dt>
                    <dd className="text-right font-medium text-neutral-700">{renderValue(sds[f.key])}</dd>
                  </div>
                ) : null
              )}
            </dl>
          ) : (
            <p className="text-sm italic text-neutral-400">No SDS data available</p>
          )}
        </div>
      </div>
    </div>
  );
}
