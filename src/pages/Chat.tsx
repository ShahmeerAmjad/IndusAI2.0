import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Search, Send, BarChart3, Brain, Database, Building2, CheckCircle2,
  Moon, Sun, PanelRightOpen, PanelRightClose, Clock,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const WELCOME: Message = {
  role: "assistant",
  content:
    "I'm your AI support assistant. I can help you look up product specs, find TDS/SDS documents, answer technical questions, and assist with customer inquiries.",
  timestamp: new Date(),
};

const SUGGESTED_QUERIES = [
  "Look up TDS for POLYOX WSR-301",
  "What are the specs for epoxy resin?",
  "Find SDS for CAS 9003-11-6",
  "What products do we carry for adhesives?",
  "Technical data on high-temp lubricants",
  "Search our catalog for silicone sealants",
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
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [thinkingStage, setThinkingStage] = useState(0);
  const [animatingIndex, setAnimatingIndex] = useState<number | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
      const response = await api.sourcingSearch(trimmed);
      const botMessage: Message = {
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
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
        {/* Chat Header */}
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
                AI Support Assistant
              </h2>
              <p className={cn("text-[11px]", darkMode ? "text-slate-400" : "text-gray-500")}>
                Product specs, TDS/SDS lookup, technical support
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
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
                How can I help you today?
              </h2>
              <p className={cn("mt-2 max-w-md text-center text-sm", darkMode ? "text-slate-400" : "text-slate-500")}>
                Ask about product specs, look up TDS/SDS documents, or get answers to technical questions.
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
                    { icon: Brain, label: "Analyzing your question..." },
                    { icon: Database, label: "Searching knowledge base..." },
                    { icon: Building2, label: "Looking up product data..." },
                    { icon: BarChart3, label: "Preparing response..." },
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
              placeholder="Ask about products, specs, or TDS/SDS documents..."
              disabled={isLoading}
              className={cn(
                "min-w-0 flex-1 rounded-full border px-4 py-2.5 text-sm shadow-sm transition-colors focus:border-industrial-500 focus:outline-none focus:ring-2 focus:ring-industrial-500/20 disabled:cursor-not-allowed",
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
            AI-powered support — Product specs, TDS/SDS, and technical answers
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
