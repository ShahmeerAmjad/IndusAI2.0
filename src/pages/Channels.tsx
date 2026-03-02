import { useQuery } from "@tanstack/react-query";
import { api, ChannelMessage, EscalationTicket } from "@/lib/api";
import { useState } from "react";
import { statusColor, cn, formatNumber } from "@/lib/utils";
import {
  MessageSquare,
  Mail,
  Phone,
  Printer,
  Globe,
  AlertTriangle,
  Clock,
  TrendingUp,
  ArrowUpRight,
  Inbox,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Tab = "overview" | "conversations" | "escalations";

const CHANNEL_META: Record<string, { label: string; icon: LucideIcon; color: string; bg: string }> = {
  whatsapp: { label: "WhatsApp", icon: MessageSquare, color: "text-green-600", bg: "bg-green-100" },
  email:    { label: "Email",    icon: Mail,          color: "text-blue-600",  bg: "bg-blue-100" },
  sms:      { label: "SMS",      icon: Phone,         color: "text-violet-600", bg: "bg-violet-100" },
  fax:      { label: "Fax",      icon: Printer,       color: "text-amber-600", bg: "bg-amber-100" },
  web:      { label: "Web Chat", icon: Globe,         color: "text-slate-600", bg: "bg-slate-100" },
};

const CHANNEL_FILTERS = [
  { key: "", label: "All Channels" },
  { key: "whatsapp", label: "WhatsApp" },
  { key: "email", label: "Email" },
  { key: "sms", label: "SMS" },
  { key: "web", label: "Web Chat" },
] as const;

const ESCALATION_STATUSES = [
  { key: "", label: "All" },
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In Progress" },
  { key: "resolved", label: "Resolved" },
  { key: "closed", label: "Closed" },
] as const;

function priorityColor(priority: string) {
  const map: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-slate-100 text-slate-600",
  };
  return map[priority] || "bg-gray-100 text-gray-600";
}

function ChannelIcon({ channel, className }: { channel: string; className?: string }) {
  const meta = CHANNEL_META[channel];
  if (!meta) return <Globe className={className} />;
  const Icon = meta.icon;
  return <Icon className={className} />;
}

export default function Channels() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [msgPage, setMsgPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState("");
  const [escPage, setEscPage] = useState(1);
  const [escStatus, setEscStatus] = useState("");

  const statsQuery = useQuery({
    queryKey: ["channel-stats"],
    queryFn: api.getChannelStats,
    refetchInterval: 30_000,
  });

  const messagesQuery = useQuery({
    queryKey: ["channel-messages", msgPage, channelFilter],
    queryFn: () => api.getChannelMessages(msgPage, channelFilter),
    enabled: activeTab === "conversations" || activeTab === "overview",
  });

  const escalationsQuery = useQuery({
    queryKey: ["escalations", escPage, escStatus],
    queryFn: () => api.getEscalations(escPage, escStatus),
    enabled: activeTab === "escalations" || activeTab === "overview",
  });

  const stats = statsQuery.data;
  const allChannels = ["whatsapp", "email", "sms", "fax", "web"];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="font-montserrat text-2xl font-bold text-slate-900">
          Omnichannel Hub
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Customer communications across WhatsApp, Email, SMS, Fax, and Web
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6" aria-label="Channel tabs">
          {([
            { key: "overview" as const, label: "Overview" },
            { key: "conversations" as const, label: "Conversations" },
            { key: "escalations" as const, label: "Escalations" },
          ]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "whitespace-nowrap border-b-2 py-3 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ───────────── OVERVIEW TAB ───────────── */}
      {activeTab === "overview" && (
        <>
          {/* Channel cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {allChannels.map((ch) => {
              const meta = CHANNEL_META[ch];
              const data = stats?.channels[ch];
              const Icon = meta.icon;
              return (
                <div
                  key={ch}
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
                >
                  <div className="flex items-center gap-3">
                    <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", meta.bg)}>
                      <Icon className={cn("h-5 w-5", meta.color)} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{meta.label}</p>
                      <p className="text-xs text-slate-400">
                        {data ? `${formatNumber(data.message_count)} messages` : "No activity"}
                      </p>
                    </div>
                  </div>
                  {data && (
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Avg Response</p>
                        <p className="text-sm font-semibold text-slate-700">{data.avg_response_time}s</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Confidence</p>
                        <p className="text-sm font-semibold text-slate-700">{Math.round(data.avg_confidence * 100)}%</p>
                      </div>
                    </div>
                  )}
                  {!data && (
                    <p className="mt-4 text-xs text-slate-300 italic">Channel ready</p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Summary metrics row */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-200 border-l-4 border-l-industrial-500 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <Inbox className="h-4 w-4 text-industrial-600" />
                <span className="text-xs font-medium text-slate-500">Total Messages</span>
              </div>
              <p className="mt-1 text-2xl font-bold text-industrial-600">
                {formatNumber(stats?.total_messages ?? 0)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 border-l-4 border-l-orange-400 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-orange-600" />
                <span className="text-xs font-medium text-slate-500">Open Escalations</span>
              </div>
              <p className="mt-1 text-2xl font-bold text-orange-600">
                {formatNumber(stats?.open_escalations ?? 0)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 border-l-4 border-l-tech-500 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-tech-600" />
                <span className="text-xs font-medium text-slate-500">Active Channels</span>
              </div>
              <p className="mt-1 text-2xl font-bold text-tech-600">
                {Object.keys(stats?.channels ?? {}).length} / {allChannels.length}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 border-l-4 border-l-purple-500 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-purple-600" />
                <span className="text-xs font-medium text-slate-500">Total Escalations</span>
              </div>
              <p className="mt-1 text-2xl font-bold text-purple-600">
                {formatNumber(stats?.total_escalations ?? 0)}
              </p>
            </div>
          </div>

          {/* Recent conversations preview */}
          {messagesQuery.data && messagesQuery.data.items.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700">
                  Recent Conversations
                </h2>
                <button
                  onClick={() => setActiveTab("conversations")}
                  className="inline-flex items-center gap-1 text-xs font-medium text-industrial-600 hover:text-industrial-700"
                >
                  View All <ArrowUpRight className="h-3 w-3" />
                </button>
              </div>
              <div className="divide-y divide-slate-100">
                {messagesQuery.data.items.slice(0, 5).map((msg: ChannelMessage) => (
                  <div key={msg.id} className="flex items-start gap-3 px-5 py-3">
                    <div className={cn(
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                      CHANNEL_META[msg.channel]?.bg ?? "bg-slate-100"
                    )}>
                      <ChannelIcon channel={msg.channel} className={cn("h-4 w-4", CHANNEL_META[msg.channel]?.color ?? "text-slate-500")} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-800">{msg.from_id}</span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-400">
                          {CHANNEL_META[msg.channel]?.label ?? msg.channel}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-sm text-slate-500">{msg.content}</p>
                    </div>
                    <span className="shrink-0 text-xs text-slate-400">
                      {new Date(msg.timestamp).toLocaleString("en-US", {
                        month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
                      })}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ───────────── CONVERSATIONS TAB ───────────── */}
      {activeTab === "conversations" && (
        <>
          {/* Channel filter */}
          <div className="flex flex-wrap gap-2">
            {CHANNEL_FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => { setChannelFilter(f.key); setMsgPage(1); }}
                className={cn(
                  "rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
                  channelFilter === f.key
                    ? "bg-gray-900 text-white shadow-sm"
                    : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Loading */}
          {messagesQuery.isLoading && (
            <div className="flex items-center justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
              <span className="ml-3 text-sm text-gray-500">Loading messages...</span>
            </div>
          )}

          {/* Error */}
          {messagesQuery.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <p className="text-sm font-medium text-red-800">Failed to load messages</p>
              <p className="mt-1 text-sm text-red-600">
                {messagesQuery.error instanceof Error ? messagesQuery.error.message : "An unexpected error occurred."}
              </p>
            </div>
          )}

          {/* Table */}
          {messagesQuery.data && (
            <>
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr className="border-b bg-slate-50/80">
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Channel</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">From</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Message</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Intent</th>
                      <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">Response Time</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {messagesQuery.data.items.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-5 py-16 text-center text-sm text-gray-400">
                          No messages found.
                        </td>
                      </tr>
                    ) : (
                      messagesQuery.data.items.map((msg: ChannelMessage) => (
                        <tr key={msg.id} className="transition-colors hover:bg-gray-50">
                          <td className="whitespace-nowrap px-5 py-3">
                            <div className="flex items-center gap-2">
                              <ChannelIcon
                                channel={msg.channel}
                                className={cn("h-4 w-4", CHANNEL_META[msg.channel]?.color ?? "text-slate-400")}
                              />
                              <span className="text-xs font-medium text-slate-600">
                                {CHANNEL_META[msg.channel]?.label ?? msg.channel}
                              </span>
                            </div>
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-sm font-medium text-slate-800">
                            {msg.from_id}
                          </td>
                          <td className="max-w-xs truncate px-5 py-3 text-sm text-slate-600">
                            {msg.content}
                          </td>
                          <td className="whitespace-nowrap px-5 py-3">
                            <span className={cn(
                              "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
                              statusColor(msg.message_type)
                            )}>
                              {msg.message_type.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-right text-sm text-slate-500">
                            {msg.response_time != null ? `${msg.response_time.toFixed(2)}s` : "—"}
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-sm text-slate-500">
                            {new Date(msg.timestamp).toLocaleString("en-US", {
                              month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
                            })}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {messagesQuery.data.total_pages > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    Page {messagesQuery.data.page} of {messagesQuery.data.total_pages} ({messagesQuery.data.total} total)
                  </p>
                  <div className="flex gap-2">
                    <button
                      disabled={msgPage <= 1}
                      onClick={() => setMsgPage((p) => Math.max(1, p - 1))}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      disabled={msgPage >= messagesQuery.data.total_pages}
                      onClick={() => setMsgPage((p) => p + 1)}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ───────────── ESCALATIONS TAB ───────────── */}
      {activeTab === "escalations" && (
        <>
          {/* Status filter */}
          <div className="flex flex-wrap gap-2">
            {ESCALATION_STATUSES.map((s) => (
              <button
                key={s.key}
                onClick={() => { setEscStatus(s.key); setEscPage(1); }}
                className={cn(
                  "rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
                  escStatus === s.key
                    ? "bg-gray-900 text-white shadow-sm"
                    : "bg-white text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Loading */}
          {escalationsQuery.isLoading && (
            <div className="flex items-center justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
              <span className="ml-3 text-sm text-gray-500">Loading escalations...</span>
            </div>
          )}

          {/* Error */}
          {escalationsQuery.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <p className="text-sm font-medium text-red-800">Failed to load escalations</p>
            </div>
          )}

          {/* Table */}
          {escalationsQuery.data && (
            <>
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr className="border-b bg-slate-50/80">
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Priority</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Customer</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Subject</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Assigned To</th>
                      <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {escalationsQuery.data.items.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-5 py-16 text-center text-sm text-gray-400">
                          No escalation tickets found.
                        </td>
                      </tr>
                    ) : (
                      escalationsQuery.data.items.map((ticket: EscalationTicket) => (
                        <tr key={ticket.id} className="transition-colors hover:bg-gray-50">
                          <td className="whitespace-nowrap px-5 py-3">
                            <span className={cn(
                              "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize",
                              priorityColor(ticket.priority)
                            )}>
                              {ticket.priority}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-sm font-medium text-slate-800">
                            {ticket.customer_id}
                          </td>
                          <td className="max-w-xs truncate px-5 py-3 text-sm text-slate-600">
                            {ticket.subject}
                          </td>
                          <td className="whitespace-nowrap px-5 py-3">
                            <span className={cn(
                              "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize",
                              statusColor(ticket.status)
                            )}>
                              {ticket.status.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-sm text-slate-500">
                            {ticket.assigned_to ?? "—"}
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-sm text-slate-500">
                            {new Date(ticket.created_at).toLocaleDateString("en-US", {
                              month: "short", day: "numeric", year: "numeric"
                            })}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {escalationsQuery.data.total_pages > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    Page {escalationsQuery.data.page} of {escalationsQuery.data.total_pages} ({escalationsQuery.data.total} total)
                  </p>
                  <div className="flex gap-2">
                    <button
                      disabled={escPage <= 1}
                      onClick={() => setEscPage((p) => Math.max(1, p - 1))}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      disabled={escPage >= escalationsQuery.data.total_pages}
                      onClick={() => setEscPage((p) => p + 1)}
                      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
