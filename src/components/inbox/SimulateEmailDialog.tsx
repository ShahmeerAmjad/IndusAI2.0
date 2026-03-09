import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, Send, RotateCcw, ChevronDown } from "lucide-react";
import { api, type SimulateMessageRequest, type SimulateMessageResponse } from "@/lib/api";
import IntentBadge from "@/components/inbox/IntentBadge";

const PRESET_TEMPLATES: Array<{ label: string; group: string; data: SimulateMessageRequest }> = [
  {
    group: "Place Order",
    label: "PO submission — epoxy resin",
    data: {
      from_address: "purchasing@acmemfg.com",
      subject: "PO #7890 — 2,000 kg Epoxy Resin ER-500",
      body: "Please find attached PO #7890 for 2,000 kg of Epoxy Resin ER-500 at $12.50/kg. Ship to our Houston warehouse. Payment terms NET30.",
      channel: "email",
    },
  },
  {
    group: "Place Order",
    label: "Urgent order — solvent drums",
    data: {
      from_address: "ops@westcoastchem.com",
      subject: "Urgent order — 10 drums MEK",
      body: "We need 10 drums of MEK shipped ASAP to our San Jose plant. Please confirm availability and send a proforma invoice.",
      channel: "email",
    },
  },
  {
    group: "Order Status",
    label: "Delayed delivery inquiry",
    data: {
      from_address: "logistics@pacificcoatings.com",
      subject: "Where is PO-6621?",
      body: "Our PO-6621 was due last Friday and we still haven't received it. Can you provide a tracking update? Our production schedule depends on this.",
      channel: "email",
    },
  },
  {
    group: "Technical Support",
    label: "Resin compatibility question",
    data: {
      from_address: "r.gomez@advancedcomposites.com",
      subject: "Compatibility of ER-300 with carbon fiber layup",
      body: "We're switching from ER-500 to ER-300 for cost reasons. Will ER-300 maintain adequate adhesion on carbon fiber prepreg at 180°C cure? Any data on interlaminar shear strength?",
      channel: "email",
    },
  },
  {
    group: "Return / Complaint",
    label: "Out-of-spec product",
    data: {
      from_address: "qc@precisionplastics.com",
      subject: "Batch #BX-4410 out of spec",
      body: "Our QC tests show batch BX-4410 of POLYOX WSR-301 has viscosity at 6,200 cps — well above the 5,500 cps max on the TDS. We need a replacement batch or credit. CoA attached.",
      channel: "email",
    },
  },
  {
    group: "Reorder",
    label: "Monthly restock",
    data: {
      from_address: "orders@reliablesupply.com",
      subject: "March restock — same as February",
      body: "Hi, please repeat our February order: 500 kg ER-500, 200 kg HD-100, and 50 L SC-050. Same ship-to address. Thanks!",
      channel: "email",
    },
  },
  {
    group: "Account Inquiry",
    label: "Tax certificate update",
    data: {
      from_address: "accounting@greenchemsolutions.com",
      subject: "Updated tax exemption certificate",
      body: "Attached is our renewed tax exemption certificate valid through 2027. Please update our account records. Also, can you confirm our current payment terms?",
      channel: "email",
    },
  },
  {
    group: "Sample Request",
    label: "Sample for new formulation",
    data: {
      from_address: "formulation@novacoatings.com",
      subject: "Sample request — waterborne polyurethane",
      body: "We're developing a new low-VOC coating line. Can you send 1 kg samples of your top 2 waterborne polyurethane dispersions? Need them for lab trials next week.",
      channel: "web",
    },
  },
  {
    group: "Request Quote",
    label: "Bulk silicone quote",
    data: {
      from_address: "procurement@industrialtechcorp.com",
      subject: "RFQ — 5,000 kg silicone fluid",
      body: "Please quote 5,000 kg of 100 cSt silicone fluid, delivered to our Memphis TN plant. We need pricing for both drum and tote packaging options.",
      channel: "email",
    },
  },
  {
    group: "Request TDS/SDS",
    label: "SDS for compliance audit",
    data: {
      from_address: "safety@coastalchemicals.com",
      subject: "SDS needed — all products on our blanket PO",
      body: "Our EHS team needs current SDS documents for all products on blanket PO BPO-2024-15. Can you send a bulk download or link?",
      channel: "email",
    },
  },
  {
    group: "Multi-Intent",
    label: "Quote + TDS + sample",
    data: {
      from_address: "eng@newstartmaterials.com",
      subject: "New project — need pricing, docs, and samples",
      body: "We're kicking off a new adhesive project. Could you:\n1. Quote 500 kg of ER-500 epoxy resin\n2. Send the TDS and SDS for ER-500\n3. Ship a 1 kg sample so we can run lab tests before committing\nTimeline is tight — appreciate a fast turnaround.",
      channel: "email",
    },
  },
];

// Group presets for the dropdown
const PRESET_GROUPS = [...new Set(PRESET_TEMPLATES.map((t) => t.group))];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function SimulateEmailDialog({ open, onOpenChange }: Props) {
  const queryClient = useQueryClient();

  const [form, setForm] = useState<SimulateMessageRequest>({
    from_address: "",
    subject: "",
    body: "",
    channel: "email",
  });
  const [result, setResult] = useState<SimulateMessageResponse | null>(null);

  const mutation = useMutation({
    mutationFn: api.simulateMessage,
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["inbox-messages"] });
      queryClient.invalidateQueries({ queryKey: ["inbox-stats"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.body.trim()) return;
    mutation.mutate({
      ...form,
      from_address: form.from_address || undefined,
      subject: form.subject || undefined,
    });
  };

  const loadPreset = (preset: (typeof PRESET_TEMPLATES)[number]) => {
    setForm(preset.data);
    setResult(null);
    mutation.reset();
  };

  const resetForm = () => {
    setForm({ from_address: "", subject: "", body: "", channel: "email" });
    setResult(null);
    mutation.reset();
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-neutral-200 bg-white shadow-xl focus:outline-none">
          <div className="flex items-center justify-between border-b border-neutral-100 px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-neutral-800">
              Simulate Inbound Email
            </Dialog.Title>
            <Dialog.Close className="rounded-md p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600">
              <X size={18} />
            </Dialog.Close>
          </div>

          <div className="max-h-[70vh] overflow-y-auto px-6 py-4">
            {!result ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Preset selector */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-neutral-500">
                    Load Preset
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none rounded-lg border border-neutral-200 bg-white px-3 py-2 pr-8 text-sm text-neutral-700 focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
                      value=""
                      onChange={(e) => {
                        const idx = parseInt(e.target.value, 10);
                        if (!isNaN(idx)) loadPreset(PRESET_TEMPLATES[idx]);
                      }}
                    >
                      <option value="">Select a template...</option>
                      {PRESET_GROUPS.map((group) => (
                        <optgroup key={group} label={group}>
                          {PRESET_TEMPLATES.map((t, i) =>
                            t.group === group ? (
                              <option key={i} value={i}>
                                {t.label}
                              </option>
                            ) : null,
                          )}
                        </optgroup>
                      ))}
                    </select>
                    <ChevronDown
                      size={14}
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400"
                    />
                  </div>
                </div>

                {/* From */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-neutral-500">
                    From Address
                  </label>
                  <input
                    type="text"
                    placeholder="demo@customer.com"
                    value={form.from_address}
                    onChange={(e) => setForm((f) => ({ ...f, from_address: e.target.value }))}
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
                  />
                </div>

                {/* Subject */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-neutral-500">
                    Subject
                  </label>
                  <input
                    type="text"
                    placeholder="Customer inquiry"
                    value={form.subject}
                    onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
                  />
                </div>

                {/* Body */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-neutral-500">
                    Email Body <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    required
                    rows={5}
                    placeholder="Type the email body here..."
                    value={form.body}
                    onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
                  />
                </div>

                {/* Channel */}
                <div>
                  <label className="mb-1 block text-xs font-medium text-neutral-500">
                    Channel
                  </label>
                  <div className="flex gap-2">
                    {["email", "web"].map((ch) => (
                      <button
                        key={ch}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, channel: ch }))}
                        className={`rounded-lg border px-4 py-1.5 text-sm font-medium capitalize transition ${
                          form.channel === ch
                            ? "border-industrial-400 bg-industrial-50 text-industrial-700"
                            : "border-neutral-200 text-neutral-500 hover:bg-neutral-50"
                        }`}
                      >
                        {ch}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Error */}
                {mutation.isError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {(mutation.error as Error).message || "Failed to simulate message"}
                  </div>
                )}

                {/* Submit */}
                <button
                  type="submit"
                  disabled={mutation.isPending || !form.body.trim()}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-industrial-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-industrial-700 disabled:opacity-50"
                >
                  {mutation.isPending ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Classifying...
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      Simulate &amp; Classify
                    </>
                  )}
                </button>
              </form>
            ) : (
              /* Result panel */
              <div className="space-y-4">
                <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
                  <div className="text-sm font-medium text-green-800">Message processed</div>
                  <div className="mt-0.5 text-xs text-green-600">
                    Status: <span className="font-medium capitalize">{result.status}</span>
                  </div>
                </div>

                {/* Detected Intents */}
                <div>
                  <div className="mb-2 text-xs font-medium text-neutral-500">Detected Intents</div>
                  {result.intents.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {result.intents.map((intent, i) => (
                        <IntentBadge
                          key={i}
                          intent={intent.intent}
                          confidence={intent.confidence}
                          size="md"
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-neutral-400">No intents detected</p>
                  )}
                </div>

                {/* AI Confidence */}
                {result.ai_confidence != null && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-neutral-500">
                      AI Confidence
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-neutral-100">
                        <div
                          className="h-2 rounded-full bg-industrial-500"
                          style={{ width: `${Math.round(result.ai_confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-neutral-700">
                        {Math.round(result.ai_confidence * 100)}%
                      </span>
                    </div>
                  </div>
                )}

                {/* AI Draft preview */}
                {result.ai_draft && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-neutral-500">AI Draft</div>
                    <div className="max-h-40 overflow-y-auto rounded-lg border border-neutral-100 bg-neutral-50 p-3 text-sm text-neutral-600 whitespace-pre-wrap">
                      {result.ai_draft}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={resetForm}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50"
                  >
                    <RotateCcw size={14} />
                    Send Another
                  </button>
                  {result.message_id && (
                    <button
                      onClick={() => {
                        onOpenChange(false);
                        window.location.href = `/inbox/${result.message_id}`;
                      }}
                      className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-industrial-600 px-4 py-2 text-sm font-medium text-white hover:bg-industrial-700"
                    >
                      View Message
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
