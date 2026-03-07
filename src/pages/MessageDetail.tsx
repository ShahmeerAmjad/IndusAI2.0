import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle, AlertTriangle, RefreshCw, Send, UserPlus, Paperclip } from "lucide-react";
import { toast } from "sonner";
import { api, type InboxMessage } from "@/lib/api";
import IntentBadge from "@/components/inbox/IntentBadge";
import AIDraftEditor from "@/components/inbox/AIDraftEditor";

function parseIntents(raw: string | null): Array<{ intent: string; confidence: number; text_span?: string }> {
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

export default function MessageDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: message, isLoading } = useQuery({
    queryKey: ["inbox-message", id],
    queryFn: () => api.getInboxMessage(id!),
    enabled: !!id,
  });

  const approveMut = useMutation({
    mutationFn: () => api.approveMessage(id!),
    onSuccess: () => { toast.success("Message approved"); qc.invalidateQueries({ queryKey: ["inbox-message", id] }); },
  });

  const escalateMut = useMutation({
    mutationFn: () => api.escalateMessage(id!),
    onSuccess: () => { toast.success("Message escalated"); qc.invalidateQueries({ queryKey: ["inbox-message", id] }); },
  });

  const classifyMut = useMutation({
    mutationFn: () => api.classifyMessage(id!),
    onSuccess: () => { toast.success("Re-classified"); qc.invalidateQueries({ queryKey: ["inbox-message", id] }); },
  });

  const draftMut = useMutation({
    mutationFn: (text: string) => api.updateDraft(id!, text),
    onSuccess: () => { toast.success("Draft updated"); qc.invalidateQueries({ queryKey: ["inbox-message", id] }); },
  });

  if (isLoading) {
    return (
      <div className="flex h-60 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-industrial-600" />
      </div>
    );
  }

  if (!message) {
    return <div className="p-8 text-center text-neutral-400">Message not found</div>;
  }

  const intents = parseIntents(message.intents);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/inbox")}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 text-neutral-500 hover:bg-neutral-50"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-neutral-800">{message.subject || "(no subject)"}</h1>
          <p className="text-sm text-neutral-500">
            From <span className="font-medium text-neutral-700">{message.from_address}</span>
            {" "}&middot;{" "}
            {new Date(message.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={message.status} />
      </div>

      {/* Action bar */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => approveMut.mutate()}
          disabled={approveMut.isPending || message.status === "approved"}
          className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          <Send size={14} /> Approve & Send
        </button>
        <button
          onClick={() => escalateMut.mutate()}
          disabled={escalateMut.isPending || message.status === "escalated"}
          className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
        >
          <UserPlus size={14} /> Escalate
        </button>
        <button
          onClick={() => classifyMut.mutate()}
          disabled={classifyMut.isPending}
          className="flex items-center gap-2 rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 disabled:opacity-50"
        >
          <RefreshCw size={14} className={classifyMut.isPending ? "animate-spin" : ""} /> Re-classify
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content (2/3) */}
        <div className="space-y-6 lg:col-span-2">
          {/* Original email */}
          <div className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-neutral-700">Original Message</h3>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-600">
              {message.body || "(empty body)"}
            </div>
          </div>

          {/* AI Draft */}
          <AIDraftEditor
            draft={message.ai_draft_response || ""}
            onSave={(text) => draftMut.mutate(text)}
            disabled={message.status === "approved" || message.status === "sent"}
          />
        </div>

        {/* Sidebar (1/3) */}
        <div className="space-y-5">
          {/* Detected intents */}
          <div className="rounded-lg border border-neutral-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-neutral-700">Detected Intents</h3>
            {intents.length === 0 ? (
              <p className="text-sm text-neutral-400 italic">No intents detected</p>
            ) : (
              <div className="space-y-3">
                {intents.map((i, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <IntentBadge intent={i.intent} size="md" />
                      <span className="text-xs text-neutral-400">{Math.round(i.confidence * 100)}%</span>
                    </div>
                    {/* Confidence bar */}
                    <div className="h-1.5 overflow-hidden rounded-full bg-neutral-100">
                      <div
                        className="h-full rounded-full bg-industrial-500 transition-all"
                        style={{ width: `${Math.round(i.confidence * 100)}%` }}
                      />
                    </div>
                    {i.text_span && (
                      <p className="text-xs text-neutral-400 italic">"{i.text_span}"</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Confidence */}
          {message.ai_confidence != null && (
            <div className="rounded-lg border border-neutral-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-semibold text-neutral-700">AI Confidence</h3>
              <div className="flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-neutral-100">
                  <div
                    className={`h-full rounded-full transition-all ${
                      message.ai_confidence >= 0.7 ? "bg-green-500" :
                      message.ai_confidence >= 0.4 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${Math.round(message.ai_confidence * 100)}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-neutral-700">
                  {Math.round(message.ai_confidence * 100)}%
                </span>
              </div>
            </div>
          )}

          {/* Message metadata */}
          <div className="rounded-lg border border-neutral-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-neutral-700">Details</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-neutral-400">Channel</dt>
                <dd className="font-medium capitalize text-neutral-700">{message.channel}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-neutral-400">Status</dt>
                <dd className="font-medium capitalize text-neutral-700">{message.status}</dd>
              </div>
              {message.assigned_to && (
                <div className="flex justify-between">
                  <dt className="text-neutral-400">Assigned to</dt>
                  <dd className="font-medium text-neutral-700">{message.assigned_to}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-neutral-400">Received</dt>
                <dd className="font-medium text-neutral-700">
                  {new Date(message.created_at).toLocaleDateString()}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const configs: Record<string, { icon: typeof CheckCircle; color: string }> = {
    new: { icon: AlertTriangle, color: "bg-blue-100 text-blue-700" },
    classified: { icon: RefreshCw, color: "bg-amber-100 text-amber-700" },
    approved: { icon: CheckCircle, color: "bg-green-100 text-green-700" },
    escalated: { icon: UserPlus, color: "bg-red-100 text-red-700" },
    sent: { icon: Send, color: "bg-slate-100 text-slate-600" },
  };
  const cfg = configs[status] || configs.new;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${cfg.color}`}>
      <Icon size={14} /> {status}
    </span>
  );
}
