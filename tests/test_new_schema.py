"""Test that new supplier-sales tables exist after schema creation."""
import pytest
from unittest.mock import AsyncMock, MagicMock

REQUIRED_TABLES = [
    "documents",
    "inbound_messages",
    "customer_accounts",
    "classification_feedback",
    "erp_connections",
]

@pytest.mark.asyncio
async def test_new_tables_sql_contains_required_tables():
    """Verify the schema SQL string defines all required tables."""
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    for table in REQUIRED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SUPPLIER_SALES_SCHEMA, \
            f"Missing table: {table}"

@pytest.mark.asyncio
async def test_documents_table_has_tds_sds_fields():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "doc_type" in SUPPLIER_SALES_SCHEMA
    assert "extracted_text" in SUPPLIER_SALES_SCHEMA
    assert "structured_data" in SUPPLIER_SALES_SCHEMA
    assert "revision_date" in SUPPLIER_SALES_SCHEMA

@pytest.mark.asyncio
async def test_inbound_messages_has_multi_intent():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "intents JSONB" in SUPPLIER_SALES_SCHEMA
    assert "ai_draft_response" in SUPPLIER_SALES_SCHEMA
    assert "thread_id" in SUPPLIER_SALES_SCHEMA

@pytest.mark.asyncio
async def test_classification_feedback_table():
    from services.platform.schema import SUPPLIER_SALES_SCHEMA
    assert "ai_intent" in SUPPLIER_SALES_SCHEMA
    assert "human_intent" in SUPPLIER_SALES_SCHEMA
    assert "is_correct" in SUPPLIER_SALES_SCHEMA
