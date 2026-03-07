import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Inbox as InboxIcon, Mail, Filter, RefreshCw } from "lucide-react";
import { api, type InboxFilters, type InboxMessage } from "@/lib/api";
import IntentBadge from "@/components/inbox/IntentBadge";

const STATUS_OPTIONS = ["all", "new", "classified", "approved", "escalated", "sent"];
const CHANNEL_OPTIONS = ["all", "email", "web", "fax"];

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-700",
  classified: "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  escalated: "bg-red-100 text-red-700",
  sent: "bg-slate-100 text-slate-500",
};

function parseIntents(raw: string | null): Array<{ intent: string; confidence: number }> {
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export default function Inbox() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<InboxFilters>({ limit: 30 });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["inbox-messages", filters],
    queryFn: () => api.getInboxMessages(filters),
    refetchInterval: 10_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["inbox-stats"],
    queryFn: () => api.getInboxStats(),
    refetchInterval: 30_000,
  });

  const setFilter = (key: keyof InboxFilters, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === "all" ? undefined : value,
      offset: 0,
    }));
  };

  const messages = data?.messages ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-industrial-600 text-white">
            <InboxIcon size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-neutral-800">Inbox</h1>
            <p className="text-sm text-neutral-500">{total} messages</p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 disabled:opacity-50"
        >
          <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {stats.by_status.map((s) => (
            <button
              key={s.status}
              onClick={() => setFilter("status", s.status)}
              className={`rounded-lg border p-3 text-center transition hover:shadow-sm ${
                filters.status === s.status ? "border-industrial-400 bg-industrial-50" : "border-neutral-200"
              }`}
            >
              <div className="text-xl font-bold text-neutral-800">{s.count}</div>
              <div className="text-xs capitalize text-neutral-500">{s.status}</div>
            </button>
          ))}
          <button
            onClick={() => setFilter("status", "all")}
            className={`rounded-lg border p-3 text-center transition hover:shadow-sm ${
              !filters.status ? "border-industrial-400 bg-industrial-50" : "border-neutral-200"
            }`}
          >
            <div className="text-xl font-bold text-neutral-800">{stats.total}</div>
            <div className="text-xs text-neutral-500">All</div>
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter size={14} className="text-neutral-400" />
        <div className="flex gap-1 rounded-lg border border-neutral-200 p-0.5">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setFilter("status", s)}
              className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition ${
                (filters.status || "all") === s
                  ? "bg-industrial-600 text-white"
                  : "text-neutral-600 hover:bg-neutral-100"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded-lg border border-neutral-200 p-0.5">
          {CHANNEL_OPTIONS.map((c) => (
            <button
              key={c}
              onClick={() => setFilter("channel", c)}
              className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition ${
                (filters.channel || "all") === c
                  ? "bg-industrial-600 text-white"
                  : "text-neutral-600 hover:bg-neutral-100"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Message list */}
      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-industrial-600" />
        </div>
      ) : messages.length === 0 ? (
        <div className="flex h-40 flex-col items-center justify-center text-neutral-400">
          <Mail size={32} className="mb-2" />
          <p>No messages match your filters</p>
        </div>
      ) : (
        <div className="space-y-2">
          {messages.map((msg) => (
            <MessageRow key={msg.id} message={msg} onClick={() => navigate(`/inbox/${msg.id}`)} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > (filters.limit ?? 30) && (
        <div className="flex items-center justify-center gap-3">
          <button
            disabled={!filters.offset}
            onClick={() => setFilters((f) => ({ ...f, offset: Math.max(0, (f.offset ?? 0) - (f.limit ?? 30)) }))}
            className="rounded border px-3 py-1 text-sm disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-sm text-neutral-500">
            {(filters.offset ?? 0) + 1}–{Math.min((filters.offset ?? 0) + (filters.limit ?? 30), total)} of {total}
          </span>
          <button
            disabled={(filters.offset ?? 0) + (filters.limit ?? 30) >= total}
            onClick={() => setFilters((f) => ({ ...f, offset: (f.offset ?? 0) + (f.limit ?? 30) }))}
            className="rounded border px-3 py-1 text-sm disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function MessageRow({ message, onClick }: { message: InboxMessage; onClick: () => void }) {
  const intents = parseIntents(message.intents);
  const statusColor = STATUS_COLORS[message.status] || "bg-gray-100 text-gray-600";
  const time = new Date(message.created_at).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-lg border border-neutral-200 bg-white p-4 text-left transition hover:border-industrial-300 hover:shadow-sm"
    >
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-industrial-100 text-industrial-600">
        <Mail size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium text-neutral-800">{message.from_address}</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}>
            {message.status}
          </span>
        </div>
        <p className="truncate text-sm text-neutral-600">{message.subject || "(no subject)"}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {intents.map((i, idx) => (
            <IntentBadge key={idx} intent={i.intent} confidence={i.confidence} />
          ))}
        </div>
      </div>
      <div className="flex-shrink-0 text-right">
        <div className="text-xs text-neutral-400">{time}</div>
        {message.ai_confidence != null && (
          <div className="mt-1 text-xs text-neutral-400">
            AI: {Math.round(message.ai_confidence * 100)}%
          </div>
        )}
      </div>
    </button>
  );
}
