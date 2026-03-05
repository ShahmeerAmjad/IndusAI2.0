"""Tests that the 4 supplier-sales tables and indexes exist in PLATFORM_SCHEMA / PLATFORM_INDEXES."""
import pytest

from services.platform.schema import PLATFORM_SCHEMA, PLATFORM_INDEXES


# ── Table existence ──────────────────────────────────────────────

REQUIRED_TABLES = [
    "inbound_messages",
    "customer_accounts",
    "documents",
    "classification_feedback",
]


@pytest.mark.parametrize("table", REQUIRED_TABLES)
def test_platform_schema_contains_table(table):
    assert f"CREATE TABLE IF NOT EXISTS {table}" in PLATFORM_SCHEMA, (
        f"PLATFORM_SCHEMA missing CREATE TABLE for '{table}'"
    )


# ── inbound_messages columns ─────────────────────────────────────

INBOUND_MESSAGES_COLUMNS = [
    "channel VARCHAR(20) NOT NULL DEFAULT 'email'",
    "from_address TEXT NOT NULL",
    "to_address TEXT",
    "subject TEXT",
    "body TEXT NOT NULL",
    "raw_payload JSONB",
    "attachments JSONB",
    "intents JSONB",
    "status VARCHAR(20) DEFAULT 'new'",
    "assigned_to UUID",
    "ai_draft_response TEXT",
    "ai_confidence FLOAT",
    "ai_suggested_attachments JSONB",
    "conversation_id UUID",
    "customer_account_id UUID",
    "thread_id TEXT",
    "reviewed_by UUID",
    "reviewed_at TIMESTAMPTZ",
    "sent_at TIMESTAMPTZ",
]


@pytest.mark.parametrize("col_def", INBOUND_MESSAGES_COLUMNS)
def test_inbound_messages_column(col_def):
    assert col_def in PLATFORM_SCHEMA, (
        f"inbound_messages missing column definition: {col_def}"
    )


# ── customer_accounts columns ────────────────────────────────────

CUSTOMER_ACCOUNTS_COLUMNS = [
    "name TEXT NOT NULL",
    "account_number TEXT UNIQUE",
    "pricing_tier VARCHAR(20) DEFAULT 'standard'",
    "payment_terms VARCHAR(50) DEFAULT 'NET30'",
    "updated_at TIMESTAMPTZ DEFAULT NOW()",
]


@pytest.mark.parametrize("col_def", CUSTOMER_ACCOUNTS_COLUMNS)
def test_customer_accounts_column(col_def):
    assert col_def in PLATFORM_SCHEMA, (
        f"customer_accounts missing column definition: {col_def}"
    )


# ── documents columns ────────────────────────────────────────────

DOCUMENTS_COLUMNS = [
    "doc_type VARCHAR(10) NOT NULL",
    "file_path TEXT NOT NULL",
    "extracted_text TEXT",
    "structured_data JSONB",
    "revision_date DATE",
    "is_current BOOLEAN DEFAULT true",
]


@pytest.mark.parametrize("col_def", DOCUMENTS_COLUMNS)
def test_documents_column(col_def):
    assert col_def in PLATFORM_SCHEMA, (
        f"documents missing column definition: {col_def}"
    )


# ── classification_feedback columns ───────────────────────────────

def test_classification_feedback_cascade():
    assert "REFERENCES inbound_messages(id) ON DELETE CASCADE" in PLATFORM_SCHEMA


def test_classification_feedback_columns():
    for col in ["ai_intent VARCHAR(30)", "human_intent VARCHAR(30)", "is_correct BOOLEAN"]:
        assert col in PLATFORM_SCHEMA, f"classification_feedback missing: {col}"


# ── Indexes ───────────────────────────────────────────────────────

REQUIRED_INDEXES = [
    "idx_inbound_messages_status",
    "idx_inbound_messages_channel",
    "idx_inbound_messages_created",
    "idx_inbound_messages_customer",
    "idx_inbound_messages_thread",
    "idx_customer_accounts_email",
    "idx_customer_accounts_company",
    "idx_documents_product",
    "idx_documents_type",
    "idx_classification_feedback_message",
]


@pytest.mark.parametrize("idx", REQUIRED_INDEXES)
def test_platform_indexes_contains(idx):
    assert idx in PLATFORM_INDEXES, (
        f"PLATFORM_INDEXES missing index: {idx}"
    )


def test_inbound_messages_created_index_desc():
    """The created_at index should be DESC for recent-first queries."""
    assert "idx_inbound_messages_created ON inbound_messages(created_at DESC)" in PLATFORM_INDEXES
