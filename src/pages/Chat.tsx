import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type SourcingResult, type SourcingResponse, type Location } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Search, Send, MapPin, Package, BarChart3 } from "lucide-react";
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
  "Find me SKF 6205-2RS bearings",
  "I need 3M 2090 masking tape, 50 rolls",
  "Best price on Parker hydraulic hose 3/8\"",
  "Compare prices for Fluke 87V multimeter",
];

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [qty, setQty] = useState(1);
  const [locationId, setLocationId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [orderLoadingFor, setOrderLoadingFor] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState<number | null>(null);
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
    } catch (err) {
      // Fallback to legacy chat if sourcing fails (e.g. user not asking about parts)
      try {
        const legacyRes = await api.sendMessage(trimmed);
        const botMessage: Message = {
          role: "assistant",
          content:
            legacyRes.success && legacyRes.response
              ? legacyRes.response.content
              : legacyRes.error || "Sorry, I encountered an issue.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, botMessage]);
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch(input);
    }
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Chat Header — with qty & location */}
      <div className="flex items-center justify-between gap-3 border-b border-gray-200 bg-gray-50 px-6 py-3 rounded-t-lg">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-industrial-600">
            <Search className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              AI Sourcing Assistant
            </h2>
            <p className="text-[11px] text-gray-500">
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
              className="w-16 rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-industrial-500 focus:outline-none focus:ring-1 focus:ring-industrial-500/20"
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
                className="rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-industrial-500 focus:outline-none focus:ring-1 focus:ring-industrial-500/20"
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
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, index) => (
          <div key={index}>
            {/* Message Bubble */}
            <div
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-3 shadow-sm",
                  msg.role === "user"
                    ? "bg-industrial-600 text-white rounded-br-md"
                    : "bg-gray-100 text-gray-900 rounded-bl-md",
                )}
              >
                <p className="text-sm whitespace-pre-wrap leading-relaxed">
                  {msg.content}
                </p>
              </div>
            </div>

            {/* Timestamp */}
            <div
              className={cn(
                "mt-1 flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <span className="text-[10px] text-gray-400">
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
                    <p className="text-xs font-medium text-slate-500">
                      {msg.sourcing.parts_found} part
                      {msg.sourcing.parts_found !== 1 ? "s" : ""} found
                      {" — "}
                      {msg.sourcing.sourcing_results.length} seller
                      {msg.sourcing.sourcing_results.length !== 1 ? "s" : ""}
                    </p>
                    {msg.sourcing.sourcing_results.length >= 2 && (
                      <button
                        onClick={() =>
                          setShowComparison(
                            showComparison === index ? null : index,
                          )
                        }
                        className="flex items-center gap-1 text-xs font-medium text-industrial-600 hover:text-industrial-700"
                      >
                        <BarChart3 className="h-3.5 w-3.5" />
                        {showComparison === index
                          ? "Hide comparison"
                          : "Compare sellers"}
                      </button>
                    )}
                  </div>

                  {showComparison === index && (
                    <ComparisonTable
                      results={msg.sourcing.sourcing_results}
                      qty={qty}
                    />
                  )}

                  <div className="grid gap-3 sm:grid-cols-2">
                    {msg.sourcing.sourcing_results.map((result, ri) => (
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
                      />
                    ))}
                  </div>
                </div>
              )}
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-gray-100 px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex items-center space-x-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
                <span className="text-xs text-gray-400">Searching suppliers...</span>
              </div>
            </div>
          </div>
        )}

        {/* Suggested queries (only shown on welcome) */}
        {messages.length === 1 && (
          <div className="mt-2">
            <p className="mb-2 text-xs font-medium text-slate-400">
              Try searching for:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSearch(q)}
                  disabled={isLoading}
                  className="rounded-full border border-industrial-200 bg-industrial-50 px-3 py-1.5 text-xs font-medium text-industrial-700 transition-colors hover:bg-industrial-100 hover:border-industrial-300 disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 rounded-b-lg">
        <form onSubmit={handleSubmit} className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search for MRO parts — e.g. 'SKF 6205 bearing' or '3M masking tape'"
            disabled={isLoading}
            className="flex-1 rounded-full border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm transition-colors focus:border-industrial-500 focus:outline-none focus:ring-2 focus:ring-industrial-500/20 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-industrial-600 text-white shadow-sm transition-colors hover:bg-industrial-700 focus:outline-none focus:ring-2 focus:ring-industrial-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Send className="h-5 w-5" />
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-gray-400">
          AI-powered sourcing — Results ranked by price, delivery, and proximity
        </p>
      </div>
    </div>
  );
}
