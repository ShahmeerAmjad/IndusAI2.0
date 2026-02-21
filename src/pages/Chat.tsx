import { useState, useRef, useEffect } from "react";
import { api, ChatResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MessageCircle, Send } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  suggested_actions?: string[];
}

const WELCOME_MESSAGE: Message = {
  role: "assistant",
  content:
    "Hello! I'm your MRO Platform AI assistant. I can help with orders, products, pricing, technical support, and returns. How can I help you today?",
  timestamp: new Date(),
  suggested_actions: [
    "Show my recent orders",
    "Check product availability",
    "Get a price quote",
    "Start a return",
  ],
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function sendMessage(content: string) {
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
      const response: ChatResponse = await api.sendMessage(trimmed);

      const botMessage: Message = {
        role: "assistant",
        content:
          response.success && response.response
            ? response.response.content
            : response.error || "Sorry, I encountered an issue. Please try again.",
        timestamp: new Date(),
        suggested_actions:
          response.success && response.response
            ? response.response.suggested_actions
            : undefined,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: "assistant",
        content:
          "Sorry, I'm having trouble connecting right now. Please try again in a moment.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleSuggestedAction(action: string) {
    sendMessage(action);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Chat Header */}
      <div className="flex items-center gap-3 border-b border-gray-200 bg-gray-50 px-6 py-4 rounded-t-lg">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600">
          <MessageCircle className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900">
              MRO AI Assistant
            </h2>
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-500" />
            </span>
          </div>
          <p className="text-xs text-gray-500">
            Online -- Ask about orders, products, pricing, and more
          </p>
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
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-3 shadow-sm",
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-md"
                    : "bg-gray-100 text-gray-900 rounded-bl-md"
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
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              <span className="text-[10px] text-gray-400">
                {formatTime(msg.timestamp)}
              </span>
            </div>

            {/* Suggested Actions */}
            {msg.role === "assistant" &&
              msg.suggested_actions &&
              msg.suggested_actions.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {msg.suggested_actions.map((action, actionIndex) => (
                    <button
                      key={actionIndex}
                      onClick={() => handleSuggestedAction(action)}
                      disabled={isLoading}
                      className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100 hover:border-blue-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {action}
                    </button>
                  ))}
                </div>
              )}
          </div>
        ))}

        {/* Loading indicator -- animated dots */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-gray-100 px-4 py-3 shadow-sm">
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
            </div>
          </div>
        )}

        {/* Scroll anchor */}
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
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1 rounded-full border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 shadow-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Send className="h-5 w-5" />
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-gray-400">
          AI-powered assistant -- Responses may not always be accurate
        </p>
      </div>
    </div>
  );
}
