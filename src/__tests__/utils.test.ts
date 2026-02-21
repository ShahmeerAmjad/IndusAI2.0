import { describe, it, expect } from "vitest";
import { cn, formatCurrency, formatNumber, statusColor } from "@/lib/utils";

describe("cn (class name merge)", () => {
  it("merges basic class strings", () => {
    expect(cn("px-4", "py-2")).toBe("px-4 py-2");
  });

  it("resolves tailwind conflicts (last wins)", () => {
    expect(cn("px-4", "px-8")).toBe("px-8");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("handles undefined and null", () => {
    expect(cn("base", undefined, null, "end")).toBe("base end");
  });
});

describe("formatCurrency", () => {
  it("formats a whole number as USD", () => {
    expect(formatCurrency(1000)).toBe("$1,000.00");
  });

  it("formats a decimal value", () => {
    expect(formatCurrency(49.99)).toBe("$49.99");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0.00");
  });

  it("formats large numbers with commas", () => {
    expect(formatCurrency(1234567.89)).toBe("$1,234,567.89");
  });
});

describe("formatNumber", () => {
  it("formats whole numbers with commas", () => {
    expect(formatNumber(1000)).toBe("1,000");
  });

  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });

  it("formats large numbers", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
});

describe("statusColor", () => {
  it("returns correct class for draft status", () => {
    expect(statusColor("draft")).toBe("bg-slate-100 text-slate-700");
  });

  it("returns correct class for shipped status", () => {
    expect(statusColor("shipped")).toBe("bg-purple-100 text-purple-700");
  });

  it("returns correct class for paid status", () => {
    expect(statusColor("paid")).toBe("bg-green-100 text-green-700");
  });

  it("returns correct class for overdue status", () => {
    expect(statusColor("overdue")).toBe("bg-red-100 text-red-700");
  });

  it("returns fallback for unknown status", () => {
    expect(statusColor("unknown_status")).toBe("bg-gray-100 text-gray-600");
  });

  it("handles all defined statuses without error", () => {
    const statuses = [
      "draft", "submitted", "confirmed", "processing", "shipped",
      "delivered", "cancelled", "sent", "accepted", "rejected",
      "expired", "paid", "partial_paid", "overdue", "void",
      "requested", "approved", "received", "refunded", "open",
      "closed", "pending", "partially_received", "fully_received",
    ];
    for (const status of statuses) {
      expect(statusColor(status)).not.toBe("bg-gray-100 text-gray-600");
    }
  });
});
