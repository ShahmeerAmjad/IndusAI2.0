# =======================
# Database Schema — Full Platform Tables
# =======================
"""
Creates all tables for the MRO back-office / middle-office platform.
Called from DatabaseManager.initialize() on startup.
"""

PLATFORM_SCHEMA = """

-- Enhanced customers table (add columns to existing)
ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS billing_address TEXT,
    ADD COLUMN IF NOT EXISTS shipping_address TEXT,
    ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(50) DEFAULT 'NET30',
    ADD COLUMN IF NOT EXISTS credit_limit DECIMAL(12,2),
    ADD COLUMN IF NOT EXISTS credit_used DECIMAL(12,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS tax_exempt BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS tax_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Products & Catalog
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    manufacturer VARCHAR(255),
    manufacturer_part_number VARCHAR(100),
    uom VARCHAR(20) DEFAULT 'EA',
    weight_lbs DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    min_order_qty INTEGER DEFAULT 1,
    lead_time_days INTEGER,
    hazmat BOOLEAN DEFAULT FALSE,
    country_of_origin VARCHAR(3),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_specs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    spec_name VARCHAR(100) NOT NULL,
    spec_value VARCHAR(500) NOT NULL,
    spec_unit VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_cross_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    cross_ref_type VARCHAR(50) NOT NULL,
    cross_ref_sku VARCHAR(50) NOT NULL,
    manufacturer VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Inventory
CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_code VARCHAR(20) NOT NULL DEFAULT 'MAIN',
    quantity_on_hand DECIMAL(12,2) DEFAULT 0,
    quantity_reserved DECIMAL(12,2) DEFAULT 0,
    quantity_on_order DECIMAL(12,2) DEFAULT 0,
    reorder_point DECIMAL(12,2),
    reorder_qty DECIMAL(12,2),
    safety_stock DECIMAL(12,2) DEFAULT 0,
    bin_location VARCHAR(50),
    last_counted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, warehouse_code)
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id),
    warehouse_code VARCHAR(20) NOT NULL DEFAULT 'MAIN',
    transaction_type VARCHAR(30) NOT NULL,
    quantity DECIMAL(12,2) NOT NULL,
    reference_type VARCHAR(30),
    reference_id UUID,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pricing & Contracts
CREATE TABLE IF NOT EXISTS price_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    currency VARCHAR(3) DEFAULT 'USD',
    is_default BOOLEAN DEFAULT FALSE,
    effective_date DATE,
    expiration_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price_list_id UUID NOT NULL REFERENCES price_lists(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    unit_price DECIMAL(12,4) NOT NULL,
    min_quantity DECIMAL(12,2) DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(price_list_id, product_id, min_quantity)
);

CREATE TABLE IF NOT EXISTS customer_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    contract_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    price_list_id UUID REFERENCES price_lists(id),
    discount_percent DECIMAL(5,2) DEFAULT 0,
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    credit_limit DECIMAL(12,2),
    effective_date DATE,
    expiration_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    lead_time_days INTEGER DEFAULT 14,
    is_active BOOLEAN DEFAULT TRUE,
    rating DECIMAL(3,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS supplier_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    supplier_sku VARCHAR(50),
    supplier_price DECIMAL(12,4),
    min_order_qty DECIMAL(12,2) DEFAULT 1,
    lead_time_days INTEGER,
    is_preferred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(supplier_id, product_id)
);

-- Orders (O2C)
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(30) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    status VARCHAR(30) DEFAULT 'draft',
    po_number VARCHAR(50),
    order_date TIMESTAMPTZ DEFAULT NOW(),
    required_date DATE,
    ship_to_address TEXT,
    bill_to_address TEXT,
    subtotal DECIMAL(12,2) DEFAULT 0,
    tax_amount DECIMAL(12,2) DEFAULT 0,
    shipping_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    payment_terms VARCHAR(50),
    shipping_method VARCHAR(50),
    notes TEXT,
    created_by VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    sku VARCHAR(50),
    description VARCHAR(500),
    quantity DECIMAL(12,2) NOT NULL,
    unit_price DECIMAL(12,4) NOT NULL,
    discount_percent DECIMAL(5,2) DEFAULT 0,
    line_total DECIMAL(12,2) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    warehouse_code VARCHAR(20) DEFAULT 'MAIN',
    tracking_number VARCHAR(100),
    shipped_quantity DECIMAL(12,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quotes
CREATE TABLE IF NOT EXISTS quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_number VARCHAR(30) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    status VARCHAR(20) DEFAULT 'draft',
    valid_until DATE,
    subtotal DECIMAL(12,2) DEFAULT 0,
    tax_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    converted_order_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quote_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    sku VARCHAR(50),
    description VARCHAR(500),
    quantity DECIMAL(12,2) NOT NULL,
    unit_price DECIMAL(12,4) NOT NULL,
    discount_percent DECIMAL(5,2) DEFAULT 0,
    line_total DECIMAL(12,2) NOT NULL,
    lead_time_days INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Purchase Orders (P2P)
CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number VARCHAR(30) UNIQUE NOT NULL,
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    status VARCHAR(30) DEFAULT 'draft',
    order_date TIMESTAMPTZ DEFAULT NOW(),
    expected_date DATE,
    subtotal DECIMAL(12,2) DEFAULT 0,
    tax_amount DECIMAL(12,2) DEFAULT 0,
    shipping_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    sku VARCHAR(50),
    description VARCHAR(500),
    quantity_ordered DECIMAL(12,2) NOT NULL,
    quantity_received DECIMAL(12,2) DEFAULT 0,
    unit_cost DECIMAL(12,4) NOT NULL,
    line_total DECIMAL(12,2) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Goods Receipts
CREATE TABLE IF NOT EXISTS goods_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_number VARCHAR(30) UNIQUE NOT NULL,
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
    received_date TIMESTAMPTZ DEFAULT NOW(),
    received_by VARCHAR(100),
    warehouse_code VARCHAR(20) DEFAULT 'MAIN',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goods_receipt_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES goods_receipts(id) ON DELETE CASCADE,
    po_line_id UUID NOT NULL REFERENCES purchase_order_lines(id),
    product_id UUID NOT NULL REFERENCES products(id),
    quantity_received DECIMAL(12,2) NOT NULL,
    quantity_accepted DECIMAL(12,2),
    quantity_rejected DECIMAL(12,2) DEFAULT 0,
    rejection_reason TEXT,
    bin_location VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number VARCHAR(30) UNIQUE NOT NULL,
    order_id UUID REFERENCES orders(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    status VARCHAR(20) DEFAULT 'draft',
    invoice_date DATE DEFAULT CURRENT_DATE,
    due_date DATE,
    subtotal DECIMAL(12,2) DEFAULT 0,
    tax_amount DECIMAL(12,2) DEFAULT 0,
    shipping_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    amount_paid DECIMAL(12,2) DEFAULT 0,
    balance_due DECIMAL(12,2) DEFAULT 0,
    payment_terms VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    product_id UUID REFERENCES products(id),
    order_line_id UUID REFERENCES order_lines(id),
    sku VARCHAR(50),
    description VARCHAR(500),
    quantity DECIMAL(12,2) NOT NULL,
    unit_price DECIMAL(12,4) NOT NULL,
    line_total DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_number VARCHAR(30) UNIQUE NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount DECIMAL(12,2) NOT NULL,
    payment_method VARCHAR(30),
    reference_number VARCHAR(100),
    payment_date DATE DEFAULT CURRENT_DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Returns / RMA
CREATE TABLE IF NOT EXISTS rma_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rma_number VARCHAR(30) UNIQUE NOT NULL,
    order_id UUID REFERENCES orders(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    status VARCHAR(20) DEFAULT 'requested',
    reason VARCHAR(50),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rma_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rma_id UUID NOT NULL REFERENCES rma_requests(id) ON DELETE CASCADE,
    order_line_id UUID REFERENCES order_lines(id),
    product_id UUID NOT NULL REFERENCES products(id),
    quantity DECIMAL(12,2) NOT NULL,
    disposition VARCHAR(30),
    refund_amount DECIMAL(12,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workflows
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_type VARCHAR(50) NOT NULL,
    reference_type VARCHAR(30),
    reference_id UUID,
    current_state VARCHAR(50) NOT NULL,
    previous_state VARCHAR(50),
    assigned_to VARCHAR(100),
    data JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    from_state VARCHAR(50),
    to_state VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    performed_by VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auth & Multi-tenancy
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    primary_location_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    org_id UUID REFERENCES organizations(id),
    role TEXT NOT NULL DEFAULT 'buyer',
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    label TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    country TEXT DEFAULT 'US',
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Seller / Supply Side
CREATE TABLE IF NOT EXISTS seller_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,
    website TEXT,
    catalog_source TEXT DEFAULT 'manual',
    last_scraped_at TIMESTAMPTZ,
    reliability_base REAL DEFAULT 5.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_warehouses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller_profiles(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(id),
    ships_to_regions TEXT[] DEFAULT '{"US"}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller_profiles(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    part_sku TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    qty_available INTEGER DEFAULT 0,
    warehouse_id UUID REFERENCES seller_warehouses(id),
    lead_time_days INTEGER DEFAULT 3,
    reliability REAL DEFAULT 5.0,
    source_type TEXT DEFAULT 'manual',
    last_verified_at TIMESTAMPTZ DEFAULT now(),
    stale_after TIMESTAMPTZ DEFAULT (now() + interval '7 days'),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(seller_id, sku, warehouse_id)
);

-- Sourcing & RFQ
CREATE TABLE IF NOT EXISTS sourcing_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    query_text TEXT NOT NULL,
    intent TEXT,
    results_json JSONB,
    location_id UUID REFERENCES locations(id),
    parts_found INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    part_description TEXT NOT NULL,
    part_sku TEXT,
    qty INTEGER NOT NULL DEFAULT 1,
    urgency TEXT DEFAULT 'standard',
    target_price NUMERIC(12,2),
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id UUID NOT NULL REFERENCES rfq_requests(id) ON DELETE CASCADE,
    seller_id UUID NOT NULL REFERENCES seller_profiles(id),
    price NUMERIC(12,2) NOT NULL,
    lead_time_days INTEGER,
    notes TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Conversations (multi-turn chatbot)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    channel VARCHAR(20) NOT NULL DEFAULT 'web',
    title TEXT,
    context_summary TEXT,
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Sourcing Orders (from chat)
CREATE TABLE IF NOT EXISTS sourcing_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    seller_name TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    total NUMERIC(12,2) NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Inbound Messages (email, web chat, fax)
CREATE TABLE IF NOT EXISTS inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL DEFAULT 'email',
    from_address TEXT NOT NULL,
    to_address TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    raw_payload JSONB,
    attachments JSONB,
    intents JSONB,
    status VARCHAR(20) DEFAULT 'new',
    assigned_to UUID,
    ai_draft_response TEXT,
    ai_confidence FLOAT,
    ai_suggested_attachments JSONB,
    conversation_id UUID,
    customer_account_id UUID,
    thread_id TEXT,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Customer Accounts
CREATE TABLE IF NOT EXISTS customer_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    fax_number TEXT,
    company TEXT,
    account_number TEXT UNIQUE,
    erp_customer_id TEXT,
    pricing_tier VARCHAR(20) DEFAULT 'standard',
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- TDS/SDS Document Storage
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID,
    doc_type VARCHAR(10) NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT,
    file_size_bytes INTEGER,
    mime_type VARCHAR(50),
    extracted_text TEXT,
    structured_data JSONB,
    source_url TEXT,
    revision_date DATE,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Classification Feedback (trainable classifier)
CREATE TABLE IF NOT EXISTS classification_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES inbound_messages(id) ON DELETE CASCADE,
    ai_intent VARCHAR(30),
    ai_confidence FLOAT,
    human_intent VARCHAR(30),
    text_excerpt TEXT,
    is_correct BOOLEAN,
    corrected_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

"""

PLATFORM_INDEXES = """
-- Products
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_manufacturer ON products(manufacturer);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_product_specs_product ON product_specs(product_id);
CREATE INDEX IF NOT EXISTS idx_product_xref_product ON product_cross_references(product_id);
CREATE INDEX IF NOT EXISTS idx_product_xref_sku ON product_cross_references(cross_ref_sku);

-- Inventory
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_code);
CREATE INDEX IF NOT EXISTS idx_inventory_low_stock ON inventory(quantity_on_hand) WHERE quantity_on_hand <= COALESCE(reorder_point, 0);
CREATE INDEX IF NOT EXISTS idx_inv_txn_product ON inventory_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_txn_ref ON inventory_transactions(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_inv_txn_created ON inventory_transactions(created_at DESC);

-- Pricing
CREATE INDEX IF NOT EXISTS idx_price_list_items_product ON price_list_items(product_id);
CREATE INDEX IF NOT EXISTS idx_price_list_items_list ON price_list_items(price_list_id);
CREATE INDEX IF NOT EXISTS idx_contracts_customer ON customer_contracts(customer_id);
CREATE INDEX IF NOT EXISTS idx_contracts_active ON customer_contracts(is_active) WHERE is_active = TRUE;

-- Suppliers
CREATE INDEX IF NOT EXISTS idx_supplier_products_supplier ON supplier_products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_products_product ON supplier_products(product_id);

-- Orders
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date DESC);
CREATE INDEX IF NOT EXISTS idx_order_lines_order ON order_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_order_lines_product ON order_lines(product_id);

-- Quotes
CREATE INDEX IF NOT EXISTS idx_quotes_customer ON quotes(customer_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_quote_lines_quote ON quote_lines(quote_id);

-- Purchase Orders
CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_lines_po ON purchase_order_lines(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_gr_po ON goods_receipts(purchase_order_id);

-- Invoices
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date) WHERE status NOT IN ('paid', 'void');
CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice ON invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);

-- RMA
CREATE INDEX IF NOT EXISTS idx_rma_customer ON rma_requests(customer_id);
CREATE INDEX IF NOT EXISTS idx_rma_order ON rma_requests(order_id);
CREATE INDEX IF NOT EXISTS idx_rma_status ON rma_requests(status);
CREATE INDEX IF NOT EXISTS idx_rma_lines_rma ON rma_lines(rma_id);

-- Workflows
CREATE INDEX IF NOT EXISTS idx_workflows_type ON workflows(workflow_type);
CREATE INDEX IF NOT EXISTS idx_workflows_ref ON workflows(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_workflows_state ON workflows(current_state);
CREATE INDEX IF NOT EXISTS idx_wf_transitions_wf ON workflow_transitions(workflow_id);

-- Auth
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_locations_org ON locations(org_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- Conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_msg ON conversations(last_message_at DESC);

-- Sellers
CREATE INDEX IF NOT EXISTS idx_seller_listings_part ON seller_listings(part_sku);
CREATE INDEX IF NOT EXISTS idx_seller_listings_seller ON seller_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_seller_listings_stale ON seller_listings(stale_after);
CREATE INDEX IF NOT EXISTS idx_sourcing_requests_org ON sourcing_requests(buyer_org_id);
CREATE INDEX IF NOT EXISTS idx_rfq_requests_org ON rfq_requests(buyer_org_id);
CREATE INDEX IF NOT EXISTS idx_rfq_responses_rfq ON rfq_responses(rfq_id);
CREATE INDEX IF NOT EXISTS idx_sourcing_orders_org ON sourcing_orders(buyer_org_id);
CREATE INDEX IF NOT EXISTS idx_sourcing_orders_user ON sourcing_orders(user_id);

-- Inbound Messages
CREATE INDEX IF NOT EXISTS idx_inbound_messages_status ON inbound_messages(status);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_channel ON inbound_messages(channel);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_created ON inbound_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_customer ON inbound_messages(customer_account_id);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_thread ON inbound_messages(thread_id);

-- Customer Accounts
CREATE INDEX IF NOT EXISTS idx_customer_accounts_email ON customer_accounts(email);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_company ON customer_accounts(company);

-- Documents
CREATE INDEX IF NOT EXISTS idx_documents_product ON documents(product_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);

-- Classification Feedback
CREATE INDEX IF NOT EXISTS idx_classification_feedback_message ON classification_feedback(message_id);
"""

# ── Supplier Sales & Support Automation Tables ──

SUPPLIER_SALES_SCHEMA = """
-- TDS/SDS Document Storage
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id),
    doc_type VARCHAR(10) NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT,
    file_size_bytes INTEGER,
    mime_type VARCHAR(50),
    extracted_text TEXT,
    structured_data JSONB,
    source_url TEXT,
    revision_date DATE,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Inbound Messages (email, web chat, fax)
CREATE TABLE IF NOT EXISTS inbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(20) NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    raw_payload JSONB,
    attachments JSONB,
    intents JSONB,
    status VARCHAR(20) DEFAULT 'new',
    assigned_to UUID,
    ai_draft_response TEXT,
    ai_confidence FLOAT,
    conversation_id UUID,
    customer_account_id UUID,
    thread_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Customer Accounts
CREATE TABLE IF NOT EXISTS customer_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    fax_number TEXT,
    company TEXT,
    account_number TEXT,
    erp_customer_id TEXT,
    pricing_tier VARCHAR(20),
    payment_terms VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Classification Feedback (trainable classifier)
CREATE TABLE IF NOT EXISTS classification_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES inbound_messages(id),
    ai_intent VARCHAR(30),
    ai_confidence FLOAT,
    human_intent VARCHAR(30),
    text_excerpt TEXT,
    is_correct BOOLEAN,
    corrected_by UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ERP Connections (future)
CREATE TABLE IF NOT EXISTS erp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    erp_type VARCHAR(30) NOT NULL,
    connection_config JSONB,
    sync_schedule VARCHAR(20),
    last_sync_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

SUPPLIER_SALES_INDEXES = """
-- Documents
CREATE INDEX IF NOT EXISTS idx_documents_product ON documents(product_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_current ON documents(is_current) WHERE is_current = TRUE;

-- Inbound Messages
CREATE INDEX IF NOT EXISTS idx_inbound_messages_channel ON inbound_messages(channel);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_status ON inbound_messages(status);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_customer ON inbound_messages(customer_account_id);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_thread ON inbound_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_created ON inbound_messages(created_at DESC);

-- Customer Accounts
CREATE INDEX IF NOT EXISTS idx_customer_accounts_email ON customer_accounts(email);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_company ON customer_accounts(company);
CREATE INDEX IF NOT EXISTS idx_customer_accounts_account_number ON customer_accounts(account_number);

-- Classification Feedback
CREATE INDEX IF NOT EXISTS idx_classification_feedback_message ON classification_feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_classification_feedback_correct ON classification_feedback(is_correct);

-- ERP Connections
CREATE INDEX IF NOT EXISTS idx_erp_connections_org ON erp_connections(org_id);
CREATE INDEX IF NOT EXISTS idx_erp_connections_status ON erp_connections(status);
"""

# ── Email Ingestion Pipeline Tables ──

EMAIL_SCHEMA = """
-- OAuth2 tokens per inbox (encrypted at app layer)
CREATE TABLE IF NOT EXISTS email_oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inbox_address TEXT UNIQUE NOT NULL,
    provider VARCHAR(20) NOT NULL DEFAULT 'gmail',
    access_token TEXT,
    refresh_token TEXT,
    token_expiry TIMESTAMPTZ,
    history_id TEXT,
    last_polled_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Immutable append-only audit log
CREATE TABLE IF NOT EXISTS email_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(30) NOT NULL,
    message_id UUID,
    gmail_message_id TEXT,
    inbox_address TEXT,
    detail JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Extend inbound_messages for email-specific fields
ALTER TABLE inbound_messages
    ADD COLUMN IF NOT EXISTS gmail_message_id TEXT,
    ADD COLUMN IF NOT EXISTS body_encrypted BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS pii_redacted BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS size_bytes INTEGER;
"""

EMAIL_INDEXES = """
-- OAuth tokens
CREATE INDEX IF NOT EXISTS idx_email_oauth_inbox ON email_oauth_tokens(inbox_address);
CREATE INDEX IF NOT EXISTS idx_email_oauth_active ON email_oauth_tokens(is_active) WHERE is_active = true;

-- Audit log
CREATE INDEX IF NOT EXISTS idx_email_audit_event ON email_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_email_audit_gmail_id ON email_audit_log(gmail_message_id);
CREATE INDEX IF NOT EXISTS idx_email_audit_created ON email_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_audit_inbox ON email_audit_log(inbox_address);

-- Gmail message dedup
CREATE UNIQUE INDEX IF NOT EXISTS idx_inbound_messages_gmail_id ON inbound_messages(gmail_message_id) WHERE gmail_message_id IS NOT NULL;
"""
