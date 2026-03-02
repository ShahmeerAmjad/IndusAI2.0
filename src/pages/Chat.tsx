import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type SourcingResult, type SourcingResponse, type Location } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Search, Send, MapPin, Package, BarChart3, Brain, Database, Building2, CheckCircle2,
  Moon, Sun, PanelRightOpen, PanelRightClose, Clock, ShoppingBag,
} from "lucide-react";
import { toast } from "sonner";
import ResultCard from "@/components/sourcing/ResultCard";
import ComparisonTable from "@/components/sourcing/ComparisonTable";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sourcing?: SourcingResponse;
  orderConfirmation?: { order_id: string; message: string };
}

const WELCOME: Message = {
  role: "assistant",
  content:
    "I'm your AI sourcing assistant. Tell me what MRO part you need — I'll find the best price, fastest delivery, and nearest supplier for you.",
  timestamp: new Date(),
};

const SUGGESTED_QUERIES = [
  "Find SKF 6205-2RS bearings",
  "Compare hydraulic filters",
  "Need 3M masking tape, 50 rolls",
  "Best price on Fluke 87V multimeter",
  "O-rings for high-temperature use",
  "Parker hydraulic hose 3/8\"",
];

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ── TypewriterMessage (Task 9a) ────────────────────────────── */
function TypewriterMessage({ content, onDone }: { content: string; onDone: () => void }) {
  const [displayed, setDisplayed] = useState("");
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    if (!content) return;
    setDisplayed("");
    setIsDone(false);
    let i = 0;
    const words = content.split(" ");
    const interval = setInterval(() => {
      i = Math.min(i + 1, words.length);
      setDisplayed(words.slice(0, i).join(" "));
      if (i >= words.length) {
        setIsDone(true);
        clearInterval(interval);
      }
    }, 15);
    return () => clearInterval(interval);
  }, [content]);

  useEffect(() => {
    if (isDone) onDone();
  }, [isDone, onDone]);

  return (
    <p className="text-sm whitespace-pre-wrap leading-relaxed">
      {displayed}
      {!isDone && <span className="inline-block w-1.5 h-4 bg-industrial-500 ml-0.5 animate-pulse" />}
    </p>
  );
}

/* ── Chat Component ─────────────────────────────────────────── */
export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [qty, setQty] = useState(1);
  const [locationId, setLocationId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [orderLoadingFor, setOrderLoadingFor] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [thinkingStage, setThinkingStage] = useState(0);
  const [animatingIndex, setAnimatingIndex] = useState<number | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: () => api.getLocations(),
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  /* Task 8b: Cycle through thinking stages when loading */
  useEffect(() => {
    if (!isLoading) {
      setThinkingStage(0);
      return;
    }
    let current = 0;
    const interval = setInterval(() => {
      current = Math.min(current + 1, 3);
      setThinkingStage(current);
    }, 800);
    return () => clearInterval(interval);
  }, [isLoading]);

  async function handleSearch(content: string) {
    const trimmed = content.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await api.sourcingSearch(trimmed, qty, locationId);
      const botMessage: Message = {
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
        sourcing: response,
      };
      setMessages((prev) => [...prev, botMessage]);
      setAnimatingIndex(messages.length + 1);
    } catch (err) {
      // Fallback to legacy chat if sourcing fails (e.g. user not asking about parts)
      try {
        const legacyRes = await api.sendMessage(trimmed, "web_user", conversationId);
        if (legacyRes.conversation_id) {
          setConversationId(legacyRes.conversation_id);
        }
        const botMessage: Message = {
          role: "assistant",
          content:
            legacyRes.success && legacyRes.response
              ? legacyRes.response.content
              : legacyRes.error || "Sorry, I encountered an issue.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, botMessage]);
        setAnimatingIndex(messages.length + 1);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Sorry, I'm having trouble connecting. Please try again.",
            timestamp: new Date(),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  async function handleOrder(result: SourcingResult) {
    const key = `${result.sku}-${result.seller_name}`;
    setOrderLoadingFor(key);
    try {
      const res = await api.sourcingOrder({
        seller_name: result.seller_name,
        sku: result.sku,
        qty,
        unit_price: result.unit_price,
      });
      const confirmation: Message = {
        role: "assistant",
        content: `Order placed successfully with ${result.seller_name} for ${qty}x ${result.name}.`,
        timestamp: new Date(),
        orderConfirmation: { order_id: res.order_id, message: res.message },
      };
      setMessages((prev) => [...prev, confirmation]);
      toast.success("Order placed successfully!");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to place order",
      );
    } finally {
      setOrderLoadingFor(null);
    }
  }

  function handleRequestQuote(result: SourcingResult) {
    toast.info(
      `RFQ sent to ${result.seller_name} for ${qty}x ${result.name}`,
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    handleSearch(input);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSearch(input);
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch(input);
    }
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] gap-0">
      {/* Main chat column */}
      <div
        className={cn(
          "flex flex-1 flex-col rounded-lg border shadow-sm transition-all",
          darkMode
            ? "bg-[hsl(222,47%,8%)] border-[hsl(217,33%,20%)]"
            : "bg-white border-gray-200",
          darkMode && "chat-dark",
        )}
      >
        {/* Chat Header — with qty & location */}
        <div
          className={cn(
            "flex items-center justify-between gap-3 border-b px-6 py-3 rounded-t-lg",
            darkMode
              ? "bg-[hsl(222,47%,12%)] border-[hsl(217,33%,20%)]"
              : "bg-gray-50 border-gray-200",
          )}
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-industrial-600">
              <Search className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className={cn("text-sm font-semibold", darkMode ? "text-white" : "text-gray-900")}>
                AI Sourcing Assistant
              </h2>
              <p className={cn("text-[11px]", darkMode ? "text-slate-400" : "text-gray-500")}>
                Search parts, compare prices, place orders
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Qty input */}
            <div className="flex items-center gap-1.5">
              <Package className="h-4 w-4 text-slate-400" />
              <input
                type="number"
                min={1}
                value={qty}
                onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
                className={cn(
                  "w-16 rounded-md border px-2 py-1.5 text-xs focus:border-industrial-500 focus:outline-none focus:ring-1 focus:ring-industrial-500/20",
                  darkMode
                    ? "bg-[hsl(222,47%,8%)] text-white border-[hsl(217,33%,20%)]"
                    : "border-slate-300 text-slate-700",
                )}
                title="Quantity"
              />
              <span className="text-[11px] text-slate-400">qty</span>
            </div>

            {/* Location selector */}
            {locations && locations.length > 0 && (
              <div className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-slate-400" />
                <select
                  value={locationId || ""}
                  onChange={(e) => setLocationId(e.target.value || undefined)}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-xs focus:border-industrial-500 focus:outline-none focus:ring-1 focus:ring-industrial-500/20",
                    darkMode
                      ? "bg-[hsl(222,47%,8%)] text-white border-[hsl(217,33%,20%)]"
                      : "border-slate-300 text-slate-700",
                  )}
                >
                  <option value="">Any location</option>
                  {locations.map((loc: Location) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.label} — {loc.city}, {loc.state}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Dark mode toggle */}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
                darkMode
                  ? "bg-industrial-600 text-white hover:bg-industrial-500"
                  : "text-slate-400 hover:bg-slate-100 hover:text-slate-600",
              )}
              title={darkMode ? "Light mode" : "Dark mode"}
            >
              {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            {/* Panel toggle */}
            <button
              onClick={() => setShowPanel(!showPanel)}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
                showPanel
                  ? "bg-industrial-100 text-industrial-600"
                  : darkMode
                    ? "text-slate-400 hover:bg-white/10"
                    : "text-slate-400 hover:bg-slate-100 hover:text-slate-600",
              )}
              title="Toggle history panel"
            >
              {showPanel ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Messages Area */}
        <div className={cn("flex-1 overflow-y-auto px-6 py-4 space-y-4", darkMode ? "bg-[hsl(222,47%,8%)]" : "")}>
          {/* Task 7b: Centered welcome hero when only welcome message */}
          {messages.length === 1 && !isLoading && (
            <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-industrial-600 to-industrial-800 shadow-lg">
                <Search className="h-8 w-8 text-white" />
              </div>
              <h2 className={cn("mt-6 text-xl font-semibold", darkMode ? "text-white" : "text-slate-800")}>
                What part are you looking for?
              </h2>
              <p className={cn("mt-2 max-w-md text-center text-sm", darkMode ? "text-slate-400" : "text-slate-500")}>
                Describe the MRO part you need. I'll search across suppliers, compare prices, and find the best option.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {SUGGESTED_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSearch(q)}
                    disabled={isLoading}
                    className={cn(
                      "rounded-full border px-4 py-2 text-sm font-medium transition-all hover:shadow-sm disabled:opacity-50",
                      darkMode
                        ? "border-[hsl(217,33%,25%)] bg-[hsl(222,47%,15%)] text-slate-300 hover:bg-[hsl(222,47%,20%)] hover:border-[hsl(217,33%,30%)]"
                        : "border-industrial-200 bg-industrial-50 text-industrial-700 hover:bg-industrial-100 hover:border-industrial-300",
                    )}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Render messages (skip index 0 when only welcome message is present) */}
          {messages.map((msg, index) => {
            if (messages.length === 1 && index === 0) return null;
            return (
              <div key={index}>
                {/* Message Bubble */}
                <div
                  className={cn(
                    "flex animate-fade-in",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-3",
                      msg.role === "user"
                        ? "bg-industrial-600 text-white rounded-br-md shadow-md"
                        : darkMode
                          ? "bg-[hsl(222,47%,15%)] border border-[hsl(217,33%,20%)] text-[hsl(210,40%,92%)] rounded-bl-md shadow-sm ring-1 ring-[hsl(217,91%,50%)]/20"
                          : "bg-white border border-slate-200 text-slate-900 rounded-bl-md shadow-sm",
                    )}
                  >
                    {msg.role === "assistant" && index === animatingIndex ? (
                      <TypewriterMessage
                        content={msg.content}
                        onDone={() => setAnimatingIndex(null)}
                      />
                    ) : (
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">
                        {msg.content}
                      </p>
                    )}
                  </div>
                </div>

                {/* Timestamp */}
                <div
                  className={cn(
                    "mt-1 flex",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <span className={cn("text-[10px]", darkMode ? "text-slate-500" : "text-gray-400")}>
                    {formatTime(msg.timestamp)}
                  </span>
                </div>

                {/* Order Confirmation */}
                {msg.orderConfirmation && (
                  <div className="mt-2 rounded-lg border border-green-200 bg-green-50 p-3">
                    <p className="text-xs font-medium text-green-800">
                      Order #{msg.orderConfirmation.order_id}
                    </p>
                    <p className="text-xs text-green-600">
                      {msg.orderConfirmation.message}
                    </p>
                  </div>
                )}

                {/* Sourcing Results */}
                {msg.sourcing &&
                  msg.sourcing.sourcing_results.length > 0 && (
                    <div className="mt-3 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className={cn("text-xs font-medium", darkMode ? "text-slate-400" : "text-slate-500")}>
                          {msg.sourcing.parts_found} part
                          {msg.sourcing.parts_found !== 1 ? "s" : ""} found
                          {" — "}
                          {msg.sourcing.sourcing_results.length} seller
                          {msg.sourcing.sourcing_results.length !== 1 ? "s" : ""}
                        </p>
                      </div>

                      {/* Task 12d: Auto-expand comparison table */}
                      {msg.sourcing.sourcing_results.length >= 2 && (
                        <ComparisonTable
                          results={msg.sourcing.sourcing_results}
                          qty={qty}
                        />
                      )}

                      <div className="grid gap-3 sm:grid-cols-2">
                        {msg.sourcing.sourcing_results.map((result, ri) => {
                          const results = msg.sourcing!.sourcing_results;
                          const bestPriceIdx = results.reduce((best, r, i) => r.unit_price < results[best].unit_price ? i : best, 0);
                          const fastestIdx = results.reduce((best, r, i) => r.transit_days < results[best].transit_days ? i : best, 0);
                          const withDistance = results.filter(r => r.distance_km != null);
                          const closestIdx = withDistance.length > 0
                            ? results.indexOf(withDistance.reduce((best, r) => (r.distance_km! < best.distance_km! ? r : best), withDistance[0]))
                            : -1;

                          return (
                            <ResultCard
                              key={`${result.sku}-${result.seller_name}`}
                              result={result}
                              qty={qty}
                              rank={ri + 1}
                              onOrder={handleOrder}
                              onRequestQuote={handleRequestQuote}
                              orderLoading={
                                orderLoadingFor ===
                                `${result.sku}-${result.seller_name}`
                              }
                              isBestPrice={ri === bestPriceIdx}
                              isFastestDelivery={ri === fastestIdx}
                              isClosest={ri === closestIdx}
                            />
                          );
                        })}
                      </div>
                    </div>
                  )}
              </div>
            );
          })}

          {/* Task 8d: AI Thinking Stages loading indicator */}
          {isLoading && (
            <div className="flex justify-start animate-fade-in">
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl rounded-bl-md border px-5 py-4 shadow-sm",
                  darkMode
                    ? "bg-[hsl(222,47%,15%)] border-[hsl(217,33%,20%)]"
                    : "bg-white border-slate-200",
                )}
              >
                <div className="space-y-2.5">
                  {[
                    { icon: Brain, label: "Analyzing your query..." },
                    { icon: Database, label: "Searching knowledge graph..." },
                    { icon: Building2, label: "Matching sellers..." },
                    { icon: BarChart3, label: "Ranking results..." },
                  ].map((stage, i) => (
                    <div
                      key={stage.label}
                      className={cn(
                        "flex items-center gap-2.5 transition-all duration-300",
                        i <= thinkingStage ? "opacity-100" : "opacity-0 h-0 overflow-hidden",
                        i === thinkingStage && (darkMode ? "text-industrial-400" : "text-industrial-600"),
                        i < thinkingStage && (darkMode ? "text-slate-500" : "text-slate-400"),
                      )}
                    >
                      <stage.icon className={cn("h-4 w-4 shrink-0", i === thinkingStage && "animate-pulse")} />
                      <span className="text-sm">{stage.label}</span>
                      {i < thinkingStage && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-tech-500 shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div
          className={cn(
            "border-t px-6 py-4 rounded-b-lg",
            darkMode
              ? "bg-[hsl(222,47%,12%)] border-[hsl(217,33%,20%)]"
              : "bg-gray-50 border-gray-200",
          )}
        >
          <form onSubmit={handleSubmit} className="flex items-center gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search for MRO parts — e.g. 'SKF 6205 bearing' or '3M masking tape'"
              disabled={isLoading}
              className={cn(
                "flex-1 rounded-full border px-4 py-2.5 text-sm shadow-sm transition-colors focus:border-industrial-500 focus:outline-none focus:ring-2 focus:ring-industrial-500/20 disabled:cursor-not-allowed",
                darkMode
                  ? "bg-[hsl(222,47%,8%)] text-white border-[hsl(217,33%,20%)] placeholder-slate-500 disabled:bg-[hsl(222,47%,6%)]"
                  : "bg-white text-gray-900 border-gray-300 placeholder-gray-400 disabled:bg-gray-100",
              )}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-industrial-600 text-white shadow-sm transition-colors hover:bg-industrial-700 focus:outline-none focus:ring-2 focus:ring-industrial-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
          <p className={cn("mt-2 text-center text-[11px]", darkMode ? "text-slate-500" : "text-gray-400")}>
            AI-powered sourcing — Results ranked by price, delivery, and proximity
          </p>
        </div>
      </div>

      {/* Side Panel (Task 11) */}
      {showPanel && (
        <div
          className={cn(
            "hidden lg:flex w-72 flex-col border rounded-lg shadow-sm ml-4 overflow-hidden animate-slide-in-right",
            darkMode
              ? "bg-[hsl(222,47%,12%)] border-[hsl(217,33%,20%)]"
              : "bg-white border-slate-200",
          )}
        >
          <div className={cn("border-b px-4 py-3", darkMode ? "border-[hsl(217,33%,20%)]" : "border-slate-200")}>
            <h3 className={cn("text-sm font-semibold", darkMode ? "text-white" : "text-slate-800")}>History</h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            {/* Recent Orders */}
            <div className={cn("border-b px-4 py-3", darkMode ? "border-[hsl(217,33%,20%)]" : "border-slate-200")}>
              <div className="flex items-center gap-2 mb-3">
                <ShoppingBag className="h-4 w-4 text-industrial-500" />
                <span className={cn("text-xs font-semibold uppercase tracking-wider", darkMode ? "text-slate-400" : "text-slate-500")}>Recent Orders</span>
              </div>
              {messages
                .filter(m => m.orderConfirmation)
                .slice(-5)
                .map((m, i) => (
                  <div key={i} className={cn("mb-2 rounded-lg p-2.5", darkMode ? "bg-white/5" : "bg-slate-50")}>
                    <p className={cn("text-xs font-medium", darkMode ? "text-slate-200" : "text-slate-700")}>#{m.orderConfirmation!.order_id}</p>
                    <p className={cn("text-[11px] truncate", darkMode ? "text-slate-500" : "text-slate-400")}>{m.content.slice(0, 60)}</p>
                  </div>
                ))
              }
              {messages.filter(m => m.orderConfirmation).length === 0 && (
                <p className={cn("text-xs italic", darkMode ? "text-slate-500" : "text-slate-400")}>No orders yet</p>
              )}
            </div>

            {/* Past Queries */}
            <div className="px-4 py-3">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="h-4 w-4 text-tech-500" />
                <span className={cn("text-xs font-semibold uppercase tracking-wider", darkMode ? "text-slate-400" : "text-slate-500")}>Past Queries</span>
              </div>
              {messages
                .filter(m => m.role === "user")
                .slice(-10)
                .reverse()
                .map((m, i) => (
                  <button
                    key={i}
                    onClick={() => handleSearch(m.content)}
                    disabled={isLoading}
                    className={cn(
                      "mb-1.5 w-full rounded-lg px-2.5 py-2 text-left text-xs transition-colors disabled:opacity-50",
                      darkMode
                        ? "text-slate-300 hover:bg-white/5 hover:text-white"
                        : "text-slate-600 hover:bg-industrial-50 hover:text-industrial-700",
                    )}
                  >
                    <p className="truncate">{m.content}</p>
                    <p className={cn("text-[10px] mt-0.5", darkMode ? "text-slate-600" : "text-slate-400")}>{formatTime(m.timestamp)}</p>
                  </button>
                ))
              }
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
