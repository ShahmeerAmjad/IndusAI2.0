import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    draft: "bg-slate-100 text-slate-700",
    submitted: "bg-blue-100 text-blue-700",
    confirmed: "bg-indigo-100 text-indigo-700",
    processing: "bg-yellow-100 text-yellow-800",
    shipped: "bg-purple-100 text-purple-700",
    delivered: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
    sent: "bg-blue-100 text-blue-700",
    accepted: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    expired: "bg-orange-100 text-orange-700",
    paid: "bg-green-100 text-green-700",
    partial_paid: "bg-teal-100 text-teal-700",
    overdue: "bg-red-100 text-red-700",
    void: "bg-gray-100 text-gray-500",
    requested: "bg-yellow-100 text-yellow-800",
    approved: "bg-blue-100 text-blue-700",
    received: "bg-indigo-100 text-indigo-700",
    refunded: "bg-green-100 text-green-700",
    open: "bg-blue-100 text-blue-700",
    closed: "bg-gray-100 text-gray-500",
    pending: "bg-yellow-100 text-yellow-800",
    partially_received: "bg-teal-100 text-teal-700",
    fully_received: "bg-green-100 text-green-700",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}
