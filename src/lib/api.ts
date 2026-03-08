const API_BASE = "/api/v1";
const AUTH_BASE = "/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("indusai_access_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function authRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${AUTH_BASE}${path}`, {
    headers: authHeaders(),
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

function get<T>(path: string) {
  return request<T>(path);
}

function post<T>(path: string, body: unknown) {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

function patch<T>(path: string, body?: unknown) {
  return request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });
}

// ---------- Types ----------

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string;
  category: string;
  subcategory: string;
  manufacturer: string;
  manufacturer_part_number: string;
  uom: string;
  min_order_qty: number;
  lead_time_days: number;
  hazmat: boolean;
  country_of_origin: string;
  specs?: Array<{ name: string; value: string; unit?: string }>;
  cross_references?: Array<{ cross_ref_type: string; cross_ref_sku: string; manufacturer?: string }>;
}

export interface InventoryItem {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  warehouse_code: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  quantity_available: number;
  reorder_point: number;
  reorder_qty: number;
  safety_stock: number;
  bin_location: string;
}

export interface Customer {
  id: string;
  external_id: string;
  name: string;
  email: string;
  phone: string;
  company: string;
  payment_terms: string;
  credit_limit: number;
  credit_used: number;
}

export interface Order {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name?: string;
  status: string;
  order_date: string;
  total_amount: number;
  subtotal: number;
  payment_terms: string;
  lines?: OrderLine[];
}

export interface OrderLine {
  id: string;
  sku: string;
  product_name: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface Quote {
  id: string;
  quote_number: string;
  customer_id: string;
  customer_name?: string;
  status: string;
  total_amount: number;
  valid_until?: string;
  created_at: string;
}

export interface Supplier {
  id: string;
  supplier_code: string;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  payment_terms: string;
  lead_time_days: number;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_name?: string;
  status: string;
  total_amount: number;
  order_date: string;
  expected_date?: string;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  customer_id: string;
  customer_name?: string;
  status: string;
  total_amount: number;
  balance_due: number;
  invoice_date: string;
  due_date: string;
}

export interface RMA {
  id: string;
  rma_number: string;
  customer_id: string;
  customer_name?: string;
  status: string;
  reason: string;
  created_at: string;
}

export interface DashboardMetrics {
  orders_today: number;
  orders_this_month: number;
  revenue_today: number;
  revenue_this_month: number;
  open_orders: number;
  pending_shipments: number;
  open_quotes: number;
  low_stock_items: number;
  open_pos: number;
  pending_invoices: number;
  overdue_invoices: number;
  open_rmas: number;
  top_products: Array<{ sku: string; name: string; total_qty: number; total_revenue: number }>;
  top_customers: Array<{ name: string; company: string; total_revenue: number; order_count: number }>;
  recent_orders: Array<{ order_number: string; status: string; total_amount: number; customer_name: string; order_date: string }>;
}

export interface ReorderAlert {
  product_id: string;
  sku: string;
  product_name: string;
  warehouse_code: string;
  quantity_available: number;
  reorder_point: number;
  reorder_qty: number;
  preferred_supplier?: string;
  supplier_price?: number;
}

export interface ChatResponse {
  success: boolean;
  conversation_id?: string;
  response?: {
    content: string;
    suggested_actions: string[];
    escalate: boolean;
  };
  message_id?: string;
  error?: string;
}

export interface ChannelMessage {
  id: string;
  from_id: string;
  content: string;
  channel: string;
  message_type: string;
  confidence: number;
  response_content: string | null;
  response_time: number | null;
  timestamp: string;
}

export interface ChannelStats {
  channels: Record<string, {
    message_count: number;
    avg_response_time: number;
    avg_confidence: number;
    last_message_at: string | null;
  }>;
  total_messages: number;
  open_escalations: number;
  total_escalations: number;
}

export interface EscalationTicket {
  id: string;
  customer_id: string;
  subject: string;
  description: string | null;
  priority: string;
  status: string;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourcingResult {
  sku: string;
  name: string;
  seller_name: string;
  unit_price: number;
  total_cost: number;
  transit_days: number;
  shipping_cost: number;
  distance_km: number | null;
  qty_available: number;
  manufacturer: string;
  reliability: number;
  cross_ref_type?: string;
}

export interface SourcingResponse {
  response: string;
  parts_found: number;
  intent: string | null;
  sourcing_results: SourcingResult[];
}

export interface GraphPart {
  sku: string;
  name: string;
  manufacturer?: string;
  category?: string;
  description?: string;
  specs?: Array<{ name: string; value: string | number; unit?: string }>;
  cross_refs?: Array<{ sku: string; name?: string; type: string }>;
  compatible_parts?: Array<{ sku: string; name?: string; manufacturer?: string; context?: string }>;
}

export interface GraphSearchResult {
  results: Array<{ node: GraphPart; score: number }>;
  total: number;
  query: string;
}

export interface GraphStats {
  nodes: Record<string, number>;
  edges: Record<string, number>;
}

export interface SourcingOrderResponse {
  order_id: string;
  status: string;
  message: string;
}

export interface Location {
  id: string;
  label: string;
  city: string;
  state: string;
  lat: number | null;
  lng: number | null;
}

// ---------- Inbox / Supplier Sales Types ----------

export interface InboxMessage {
  id: string;
  from_address: string;
  subject: string;
  body?: string;
  status: string;
  channel: string;
  intents: string | null;
  ai_draft_response?: string | null;
  ai_confidence?: number | null;
  assigned_to?: string | null;
  customer_account_id?: string | null;
  created_at: string;
}

export interface InboxListResponse {
  messages: InboxMessage[];
  total: number;
  limit: number;
  offset: number;
}

export interface InboxFilters {
  status?: string;
  channel?: string;
  intent?: string;
  assigned_to?: string;
  limit?: number;
  offset?: number;
}

export interface InboxStats {
  total: number;
  by_status: Array<{ status: string; count: number }>;
  by_intent: Array<{ intent: string; count: number }>;
}

export interface ClassificationFeedback {
  original_intent: string;
  corrected_intent: string;
  notes?: string;
}

export interface CustomerAccount {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  account_number?: string;
  pricing_tier?: string;
  payment_terms?: string;
  created_at?: string;
}

export interface DocumentMeta {
  id: string;
  product_id?: string;
  doc_type: string;
  file_name: string;
  file_path?: string;
  is_current?: boolean;
  created_at?: string;
}

export interface IngestionEvent {
  stage: string;
  product?: string;
  current?: number;
  total?: number;
  detail?: string;
  result?: Record<string, number>;
}

export interface IngestionJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  events: IngestionEvent[];
  result?: Record<string, number>;
  error?: string;
}

export interface GraphVizData {
  nodes: Array<{
    id: string;
    label: string;
    name: string;
    color: string;
    properties: Record<string, unknown>;
  }>;
  edges: Array<{
    source: string;
    target: string;
    relationship: string;
  }>;
}

// ---------- API Functions ----------

export const api = {
  // Dashboard
  getDashboard: () => get<DashboardMetrics>("/analytics/dashboard"),
  getSalesSummary: (period: string) => get<Array<{ period: string; order_count: number; revenue: number }>>(`/analytics/sales?period=${period}`),

  // Products
  getProducts: (page = 1, q = "") => get<PaginatedResponse<Product>>(`/products?page=${page}&page_size=20${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  getProduct: (id: string) => get<Product>(`/products/${id}`),
  getCategories: () => get<string[]>("/products/categories"),

  // Inventory
  getInventory: (page = 1) => get<PaginatedResponse<InventoryItem>>(`/inventory?page=${page}&page_size=20`),
  getReorderAlerts: () => get<ReorderAlert[]>("/inventory/reorder-alerts"),

  // Customers
  getCustomers: (page = 1) => get<PaginatedResponse<Customer>>(`/customers?page=${page}&page_size=20`),
  getCustomer: (id: string) => get<Customer>(`/customers/${id}`),

  // Orders
  getOrders: (page = 1, status = "") => get<PaginatedResponse<Order>>(`/orders?page=${page}&page_size=20${status ? `&status=${status}` : ""}`),
  getOrder: (id: string) => get<Order>(`/orders/${id}`),
  submitOrder: (id: string) => patch<Order>(`/orders/${id}/submit`),
  confirmOrder: (id: string) => patch<Order>(`/orders/${id}/confirm`),
  shipOrder: (id: string) => patch<Order>(`/orders/${id}/ship`),
  createOrder: (data: unknown) => post<Order>("/orders", data),

  // Quotes
  getQuotes: (page = 1) => get<PaginatedResponse<Quote>>(`/quotes?page=${page}&page_size=20`),
  getQuote: (id: string) => get<Quote>(`/quotes/${id}`),
  convertQuote: (id: string) => post<Order>(`/quotes/${id}/convert`, {}),

  // Suppliers
  getSuppliers: (page = 1) => get<PaginatedResponse<Supplier>>(`/suppliers?page=${page}&page_size=20`),

  // Purchase Orders
  getPurchaseOrders: (page = 1) => get<PaginatedResponse<PurchaseOrder>>(`/purchase-orders?page=${page}&page_size=20`),
  autoGeneratePOs: () => post<unknown>("/purchase-orders/auto-generate", {}),

  // Invoices
  getInvoices: (page = 1, status = "") => get<PaginatedResponse<Invoice>>(`/invoices?page=${page}&page_size=20${status ? `&status=${status}` : ""}`),
  getARaging: () => get<Record<string, { count: number; balance: number }>>("/invoices/aging"),

  // RMA
  getRMAs: (page = 1) => get<PaginatedResponse<RMA>>(`/rma?page=${page}&page_size=20`),

  // Chat (legacy)
  sendMessage: (content: string, from_id = "web_user", conversation_id?: string) =>
    fetch("/api/v1/message", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ from_id, content, channel: "web", conversation_id }),
    }).then((r) => r.json() as Promise<ChatResponse>),

  // Sourcing
  sourcingSearch: (query: string, qty = 1, locationId?: string) =>
    authRequest<SourcingResponse>("/sourcing/search", {
      method: "POST",
      body: JSON.stringify({ query, qty, location_id: locationId }),
    }),
  sourcingOrder: (data: { seller_name: string; sku: string; qty: number; unit_price: number }) =>
    authRequest<SourcingOrderResponse>("/sourcing/order", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Auth (locations)
  getLocations: () => authRequest<Location[]>("/auth/locations"),

  // Pricing
  getPrice: (productId: string, qty = 1) => get<unknown>(`/pricing/${productId}?quantity=${qty}`),
  getPriceTiers: (productId: string) => get<unknown>(`/pricing/${productId}/tiers`),

  // Channels / Omnichannel
  getChannelStats: () => get<ChannelStats>("/channels/stats"),
  getChannelMessages: (page = 1, channel = "") =>
    get<PaginatedResponse<ChannelMessage>>(`/channels/messages?page=${page}&page_size=20${channel ? `&channel=${channel}` : ""}`),
  getEscalations: (page = 1, status = "") =>
    get<PaginatedResponse<EscalationTicket>>(`/channels/escalations?page=${page}&page_size=20${status ? `&status=${status}` : ""}`),

  // Sourcing (AI-powered)
  searchSourcing: (query: string, qty = 1) =>
    fetch("/api/sourcing/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, qty }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Sourcing search failed: ${r.status}`);
      return r.json() as Promise<SourcingResponse>;
    }),

  // Knowledge Graph
  getGraphPart: (sku: string) => get<GraphPart>(`/graph/parts/${sku}`),
  searchGraph: (q: string, limit = 20) => get<GraphSearchResult>(`/graph/parts/search/fulltext?q=${encodeURIComponent(q)}&limit=${limit}`),
  getGraphStats: () => get<GraphStats>("/graph/stats"),

  // Admin
  adminGraphStats: () => authRequest<unknown>("/admin/graph/stats"),
  adminSellerFreshness: () => authRequest<unknown>("/admin/sellers/freshness"),
  adminRecentSourcing: () => authRequest<unknown>("/admin/sourcing/recent"),
  adminReliabilityScores: () => authRequest<unknown>("/admin/reliability/scores"),
  adminRecentOrders: () => authRequest<unknown>("/admin/orders/recent"),

  // Inbox (Supplier Sales)
  getInboxMessages: (filters?: InboxFilters) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    if (filters?.channel) params.set("channel", filters.channel);
    if (filters?.intent) params.set("intent", filters.intent);
    if (filters?.assigned_to) params.set("assigned_to", filters.assigned_to);
    if (filters?.limit) params.set("limit", String(filters.limit));
    if (filters?.offset) params.set("offset", String(filters.offset));
    const qs = params.toString();
    return get<InboxListResponse>(`/inbox/messages${qs ? `?${qs}` : ""}`);
  },
  getInboxMessage: (id: string) => get<InboxMessage>(`/inbox/messages/${id}`),
  classifyMessage: (id: string) => patch<unknown>(`/inbox/messages/${id}/classify`),
  approveMessage: (id: string) => patch<unknown>(`/inbox/messages/${id}/approve`),
  escalateMessage: (id: string, assignedTo?: string) =>
    patch<unknown>(`/inbox/messages/${id}/escalate${assignedTo ? `?assigned_to=${encodeURIComponent(assignedTo)}` : ""}`),
  updateDraft: (id: string, responseText: string) =>
    patch<unknown>(`/inbox/messages/${id}/draft`, { response_text: responseText }),
  submitFeedback: (id: string, feedback: ClassificationFeedback) =>
    post<unknown>(`/inbox/messages/${id}/feedback`, feedback),
  getInboxStats: () => get<InboxStats>("/inbox/messages/stats"),

  // Documents
  getDocumentsForProduct: (productId: string) => get<DocumentMeta[]>(`/documents/product/${productId}`),
  searchDocuments: (q: string, docType?: string) =>
    get<DocumentMeta[]>(`/documents/search?q=${encodeURIComponent(q)}${docType ? `&doc_type=${docType}` : ""}`),

  // Customer Accounts
  getCustomerAccounts: (limit = 50, offset = 0) =>
    get<{ accounts: CustomerAccount[]; limit: number; offset: number }>(`/customer-accounts?limit=${limit}&offset=${offset}`),
  getCustomerAccount: (id: string) => get<CustomerAccount>(`/customer-accounts/${id}`),
  lookupCustomerByEmail: (email: string) => get<CustomerAccount>(`/customer-accounts/lookup?email=${encodeURIComponent(email)}`),

  // Ingestion
  startIngestion: (url: string) =>
    post<{ job_id: string; status: string }>("/ingestion/start", { url }),
  startBatchIngestion: (industryUrls: string[], maxProducts = 50) =>
    post<{ job_id: string; status: string }>("/ingestion/start-batch", {
      industry_urls: industryUrls,
      max_products: maxProducts,
    }),
  getIngestionJob: (jobId: string) => get<IngestionJob>(`/ingestion/jobs/${jobId}`),

  // Graph Visualization
  getGraphViz: (industry?: string, manufacturer?: string) => {
    const params = new URLSearchParams();
    if (industry) params.set("industry", industry);
    if (manufacturer) params.set("manufacturer", manufacturer);
    const qs = params.toString();
    return get<GraphVizData>(`/knowledge-base/graph-viz${qs ? `?${qs}` : ""}`);
  },
};
