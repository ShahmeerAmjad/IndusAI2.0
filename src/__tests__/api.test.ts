import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Import after mocking fetch
const { api } = await import("@/lib/api");

beforeEach(() => {
  mockFetch.mockReset();
});

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });
}

describe("api client", () => {
  describe("getDashboard", () => {
    it("fetches from /api/v1/analytics/dashboard", async () => {
      const metrics = { orders_today: 5, revenue_today: 1000 };
      mockFetch.mockReturnValueOnce(jsonResponse(metrics));

      const result = await api.getDashboard();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/analytics/dashboard",
        expect.objectContaining({
          headers: { "Content-Type": "application/json" },
        })
      );
      expect(result).toEqual(metrics);
    });
  });

  describe("getProducts", () => {
    it("fetches products with pagination", async () => {
      const data = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
      mockFetch.mockReturnValueOnce(jsonResponse(data));

      const result = await api.getProducts(2, "bearing");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/products?page=2&page_size=20&q=bearing",
        expect.any(Object)
      );
      expect(result).toEqual(data);
    });

    it("omits query param when empty", async () => {
      const data = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
      mockFetch.mockReturnValueOnce(jsonResponse(data));

      await api.getProducts(1, "");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/products?page=1&page_size=20",
        expect.any(Object)
      );
    });
  });

  describe("getOrders", () => {
    it("includes status filter when provided", async () => {
      const data = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
      mockFetch.mockReturnValueOnce(jsonResponse(data));

      await api.getOrders(1, "shipped");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/orders?page=1&page_size=20&status=shipped",
        expect.any(Object)
      );
    });
  });

  describe("submitOrder", () => {
    it("sends PATCH to /orders/:id/submit", async () => {
      const order = { id: "1", order_number: "ORD-001", status: "submitted" };
      mockFetch.mockReturnValueOnce(jsonResponse(order));

      const result = await api.submitOrder("1");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/orders/1/submit",
        expect.objectContaining({ method: "PATCH" })
      );
      expect(result).toEqual(order);
    });
  });

  describe("error handling", () => {
    it("throws with detail message on 4xx response", async () => {
      mockFetch.mockReturnValueOnce(
        Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: "Order not found" }),
        })
      );

      await expect(api.getOrder("bad-id")).rejects.toThrow("Order not found");
    });

    it("throws generic message when no detail in response", async () => {
      mockFetch.mockReturnValueOnce(
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.reject(new Error("not json")),
        })
      );

      await expect(api.getOrder("bad-id")).rejects.toThrow("Request failed: 500");
    });
  });
});
