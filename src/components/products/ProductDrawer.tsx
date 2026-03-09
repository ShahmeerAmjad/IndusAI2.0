import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, FileText, Shield, Download, ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface ProductDrawerProps {
  sku: string;
  onClose: () => void;
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color = confidence >= 0.8
    ? "bg-green-100 text-green-700"
    : confidence >= 0.5
      ? "bg-yellow-100 text-yellow-700"
      : "bg-red-100 text-red-700";
  return (
    <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium", color)}>
      {Math.round(confidence * 100)}%
    </span>
  );
}

function FieldGroup({ title, fields, icon }: {
  title: string;
  fields: Record<string, unknown>;
  icon?: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const entries = Object.entries(fields).filter(([, v]) => {
    if (v == null) return false;
    if (typeof v === "object" && v !== null && "value" in v) return (v as { value: unknown }).value != null;
    return true;
  });

  if (entries.length === 0) return null;

  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-neutral-50 hover:bg-neutral-100 transition-colors text-left">
        {icon}
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-sm font-semibold text-neutral-700">{title}</span>
        <span className="text-xs text-neutral-400 ml-auto">{entries.length} fields</span>
      </button>
      {open && (
        <dl className="p-4 space-y-2 text-sm">
          {entries.map(([key, val]) => {
            let display: string;
            let confidence: number | null = null;

            if (typeof val === "object" && val !== null && "value" in val) {
              const typed = val as { value: unknown; confidence?: number };
              display = Array.isArray(typed.value)
                ? typed.value.join(", ")
                : String(typed.value ?? "\u2014");
              confidence = typed.confidence ?? null;
            } else if (Array.isArray(val)) {
              display = val.join(", ");
            } else {
              display = String(val);
            }

            return (
              <div key={key} className="flex items-start justify-between gap-3">
                <dt className="text-neutral-400 capitalize shrink-0">{key.replace(/_/g, " ")}</dt>
                <dd className="text-right font-medium text-neutral-700 flex items-center gap-2">
                  <span className="break-words max-w-[280px]">{display}</span>
                  {confidence !== null && <ConfidenceBadge confidence={confidence} />}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </div>
  );
}

const TDS_GROUPS: Record<string, string[]> = {
  "Physical Properties": [
    "appearance", "color", "odor", "form", "density", "specific_gravity",
    "bulk_density", "viscosity", "pH", "molecular_weight",
  ],
  "Thermal Properties": [
    "flash_point", "boiling_point", "melting_point", "glass_transition_temp",
    "vapor_pressure", "refractive_index",
  ],
  "Mechanical Properties": [
    "tensile_strength", "elongation", "hardness", "impact_strength",
    "adhesion_strength", "peel_strength", "shear_strength",
    "heat_deflection_temp", "thermal_conductivity",
  ],
  "Application": [
    "recommended_uses", "application_method", "application_temperature",
    "mix_ratio", "cure_time", "pot_life", "open_time", "set_time",
    "compatibility", "solubility", "particle_size",
  ],
  "Storage & Regulatory": [
    "shelf_life", "storage_conditions", "storage_temperature",
    "packaging", "regulatory_approvals", "product_name", "manufacturer",
    "product_line", "revision_date",
  ],
};

const SDS_GROUPS: Record<string, string[]> = {
  "Identification (Sec 1)": ["product_name", "supplier", "emergency_phone", "revision_date", "sds_number"],
  "Hazard Identification (Sec 2)": [
    "ghs_classification", "signal_word", "hazard_pictograms",
    "hazard_statements", "precautionary_statements",
  ],
  "Composition (Sec 3)": ["components", "cas_numbers"],
  "First Aid (Sec 4)": [
    "first_aid_inhalation", "first_aid_skin", "first_aid_eyes", "first_aid_ingestion",
  ],
  "PPE & Exposure (Sec 8)": [
    "exposure_limits", "respiratory_protection", "hand_protection",
    "eye_protection", "skin_protection",
  ],
  "Physical Properties (Sec 9)": [
    "appearance", "color", "odor", "pH", "density", "viscosity",
    "boiling_point", "flash_point", "vapor_pressure", "solubility",
  ],
  "Stability (Sec 10)": ["stability", "incompatible_materials", "decomposition_products"],
  "Toxicology (Sec 11)": [
    "ld50_oral", "lc50_inhalation", "skin_corrosion", "eye_damage",
    "carcinogenicity", "reproductive_toxicity", "mutagenicity",
  ],
  "Transport (Sec 14)": ["un_number", "shipping_name", "hazard_class", "packing_group"],
  "Regulatory (Sec 15)": ["sara_313", "california_prop_65", "cercla_rq"],
};

function groupFields(allFields: Record<string, unknown>, groups: Record<string, string[]>) {
  const grouped: Record<string, Record<string, unknown>> = {};
  const assigned = new Set<string>();

  for (const [groupName, keys] of Object.entries(groups)) {
    const g: Record<string, unknown> = {};
    for (const k of keys) {
      if (k in allFields) {
        g[k] = allFields[k];
        assigned.add(k);
      }
    }
    if (Object.keys(g).length > 0) {
      grouped[groupName] = g;
    }
  }

  const other: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(allFields)) {
    if (!assigned.has(k)) other[k] = v;
  }
  if (Object.keys(other).length > 0) {
    grouped["Other"] = other;
  }

  return grouped;
}

export default function ProductDrawer({ sku, onClose }: ProductDrawerProps) {
  const { data: product } = useQuery({
    queryKey: ["catalog-product-detail", sku],
    queryFn: () => api.searchProducts(sku, 1, 1),
  });

  const { data: extraction, isLoading } = useQuery({
    queryKey: ["product-extraction", sku],
    queryFn: () => api.getProductExtraction(sku),
  });

  const productInfo = product?.items?.[0];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-neutral-200 px-6 py-4">
          <div>
            <span className="font-mono text-xs bg-industrial-100 text-industrial-800 px-2 py-0.5 rounded">
              {sku}
            </span>
            <h2 className="text-lg font-semibold text-neutral-900 mt-1">
              {productInfo?.name || sku}
            </h2>
            {productInfo?.manufacturer && (
              <p className="text-sm text-neutral-500 mt-0.5">{productInfo.manufacturer}</p>
            )}
          </div>
          <button onClick={onClose}
            className="p-1.5 hover:bg-neutral-100 rounded-lg transition-colors">
            <X size={20} className="text-neutral-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-2 border-industrial-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : extraction ? (
            <>
              {/* TDS Section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-blue-600" />
                    <h3 className="font-semibold text-neutral-800">Technical Data Sheet</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {extraction.tds?.pdf_url && (
                      <a href={extraction.tds.pdf_url} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs bg-blue-50 text-blue-700 px-2.5 py-1 rounded-md hover:bg-blue-100">
                        <Download size={12} /> Download
                      </a>
                    )}
                    {extraction.tds?.source_url && (
                      <a href={extraction.tds.source_url} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs bg-neutral-50 text-neutral-600 px-2.5 py-1 rounded-md hover:bg-neutral-100">
                        <ExternalLink size={12} /> Chempoint
                      </a>
                    )}
                  </div>
                </div>
                {extraction.tds?.revision_date && (
                  <p className="text-xs text-neutral-400 mb-2">Revision: {extraction.tds.revision_date}</p>
                )}
                <div className="space-y-2">
                  {Object.entries(groupFields(extraction.tds?.fields ?? {}, TDS_GROUPS)).map(
                    ([groupName, fields]) => (
                      <FieldGroup key={groupName} title={groupName} fields={fields}
                        icon={<FileText size={12} className="text-blue-400" />} />
                    )
                  )}
                  {Object.keys(extraction.tds?.fields ?? {}).length === 0 && (
                    <p className="text-sm italic text-neutral-400">No TDS extraction data</p>
                  )}
                </div>
              </div>

              {/* SDS Section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Shield size={16} className="text-red-600" />
                    <h3 className="font-semibold text-neutral-800">Safety Data Sheet</h3>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {extraction.sds?.pdf_url && (
                      <a href={extraction.sds.pdf_url} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs bg-red-50 text-red-700 px-2.5 py-1 rounded-md hover:bg-red-100">
                        <Download size={12} /> Download
                      </a>
                    )}
                    {extraction.sds?.source_url && (
                      <a href={extraction.sds.source_url} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs bg-neutral-50 text-neutral-600 px-2.5 py-1 rounded-md hover:bg-neutral-100">
                        <ExternalLink size={12} /> Chempoint
                      </a>
                    )}
                  </div>
                </div>
                {extraction.sds?.revision_date && (
                  <p className="text-xs text-neutral-400 mb-2">Revision: {extraction.sds.revision_date}</p>
                )}
                {extraction.sds?.cas_numbers && extraction.sds.cas_numbers.length > 0 && (
                  <p className="text-xs text-neutral-500 mb-2">
                    CAS: {extraction.sds.cas_numbers.join(", ")}
                  </p>
                )}
                <div className="space-y-2">
                  {Object.entries(groupFields(extraction.sds?.fields ?? {}, SDS_GROUPS)).map(
                    ([groupName, fields]) => (
                      <FieldGroup key={groupName} title={groupName} fields={fields}
                        icon={<Shield size={12} className="text-red-400" />} />
                    )
                  )}
                  {Object.keys(extraction.sds?.fields ?? {}).length === 0 && (
                    <p className="text-sm italic text-neutral-400">No SDS extraction data</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-neutral-400">No extraction data available for this product.</p>
          )}
        </div>
      </div>
    </>
  );
}
