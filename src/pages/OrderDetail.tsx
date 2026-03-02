import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useParams, useNavigate } from "react-router-dom";
import { formatCurrency, statusColor, cn } from "@/lib/utils";

export default function OrderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: order,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["order", id],
    queryFn: () => api.getOrder(id!),
    enabled: !!id,
  });

  const submitMutation = useMutation({
    mutationFn: () => api.submitOrder(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order", id] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  const confirmMutation = useMutation({
    mutationFn: () => api.confirmOrder(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order", id] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  const shipMutation = useMutation({
    mutationFn: () => api.shipOrder(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order", id] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  const isMutating =
    submitMutation.isPending ||
    confirmMutation.isPending ||
    shipMutation.isPending;

  /* Loading */
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
        <span className="ml-3 text-sm text-gray-500">
          Loading order details...
        </span>
      </div>
    );
  }

  /* Error */
  if (isError || !order) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate("/orders")}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <span aria-hidden="true">&larr;</span> Back to Orders
        </button>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Failed to load order
          </p>
          <p className="mt-1 text-sm text-red-600">
            {error instanceof Error
              ? error.message
              : "Order not found or an unexpected error occurred."}
          </p>
        </div>
      </div>
    );
  }

  const lines = order.lines ?? [];
  const subtotal = order.subtotal ?? lines.reduce((s, l) => s + l.line_total, 0);
  const tax = (order.total_amount - subtotal) > 0 ? (order.total_amount - subtotal) * 0.7 : 0;
  const shipping = order.total_amount - subtotal - tax;

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <button
        onClick={() => navigate("/orders")}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900"
      >
        <span aria-hidden="true">&larr;</span> Back to Orders
      </button>

      {/* Order header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-900">
              {order.order_number}
            </h1>
            <span
              className={cn(
                "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                statusColor(order.status)
              )}
            >
              {order.status}
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Order placed on{" "}
            {new Date(order.order_date).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {order.status === "draft" && (
            <button
              disabled={isMutating}
              onClick={() => submitMutation.mutate()}
              className={cn(
                "rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors",
                isMutating
                  ? "cursor-not-allowed bg-industrial-400"
                  : "bg-industrial-600 hover:bg-industrial-700"
              )}
            >
              {submitMutation.isPending ? "Submitting..." : "Submit Order"}
            </button>
          )}
          {order.status === "submitted" && (
            <button
              disabled={isMutating}
              onClick={() => confirmMutation.mutate()}
              className={cn(
                "rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors",
                isMutating
                  ? "cursor-not-allowed bg-industrial-400"
                  : "bg-industrial-700 hover:bg-industrial-800"
              )}
            >
              {confirmMutation.isPending ? "Confirming..." : "Confirm Order"}
            </button>
          )}
          {order.status === "confirmed" && (
            <button
              disabled={isMutating}
              onClick={() => shipMutation.mutate()}
              className={cn(
                "rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors",
                isMutating
                  ? "cursor-not-allowed bg-tech-400"
                  : "bg-tech-600 hover:bg-tech-700"
              )}
            >
              {shipMutation.isPending ? "Processing..." : "Ship Order"}
            </button>
          )}
        </div>
      </div>

      {/* Mutation error */}
      {(submitMutation.isError || confirmMutation.isError || shipMutation.isError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            {(submitMutation.error ?? confirmMutation.error ?? shipMutation.error) instanceof Error
              ? (submitMutation.error ?? confirmMutation.error ?? shipMutation.error)!.message
              : "Action failed. Please try again."}
          </p>
        </div>
      )}

      {/* Customer info + order meta */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Customer info */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
            Customer Information
          </h2>
          <dl className="mt-4 space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Name</dt>
              <dd className="text-sm font-medium text-gray-900">
                {order.customer_name ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Customer ID</dt>
              <dd className="text-sm font-mono text-gray-700">
                {order.customer_id}
              </dd>
            </div>
          </dl>
        </div>

        {/* Payment & shipping */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
            Payment &amp; Shipping
          </h2>
          <dl className="mt-4 space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Payment Terms</dt>
              <dd className="text-sm font-medium text-gray-900">
                {order.payment_terms || "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Order Status</dt>
              <dd className="text-sm font-medium capitalize text-gray-900">
                {order.status}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Order lines table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 bg-gray-50 px-6 py-3">
          <h2 className="text-sm font-semibold text-gray-700">Order Lines</h2>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr className="border-b bg-slate-50/80">
              <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                #
              </th>
              <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                SKU
              </th>
              <th className="whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                Description
              </th>
              <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                Qty
              </th>
              <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                Unit Price
              </th>
              <th className="whitespace-nowrap px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                Line Total
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {lines.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-6 py-12 text-center text-sm text-gray-400"
                >
                  No line items for this order.
                </td>
              </tr>
            ) : (
              lines.map((line, idx) => (
                <tr key={line.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {idx + 1}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm font-mono text-gray-700">
                    {line.sku}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {line.description || line.product_name}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                    {line.quantity}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                    {formatCurrency(line.unit_price)}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                    {formatCurrency(line.line_total)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Summary */}
        {lines.length > 0 && (
          <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
            <dl className="ml-auto w-64 space-y-2">
              <div className="flex justify-between text-sm">
                <dt className="text-gray-500">Subtotal</dt>
                <dd className="font-medium text-gray-900">
                  {formatCurrency(subtotal)}
                </dd>
              </div>
              <div className="flex justify-between text-sm">
                <dt className="text-gray-500">Tax</dt>
                <dd className="font-medium text-gray-900">
                  {formatCurrency(tax)}
                </dd>
              </div>
              <div className="flex justify-between text-sm">
                <dt className="text-gray-500">Shipping</dt>
                <dd className="font-medium text-gray-900">
                  {formatCurrency(shipping)}
                </dd>
              </div>
              <div className="flex justify-between border-t border-gray-300 pt-2 text-sm">
                <dt className="font-semibold text-gray-900">Total</dt>
                <dd className="font-semibold text-gray-900">
                  {formatCurrency(order.total_amount)}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
