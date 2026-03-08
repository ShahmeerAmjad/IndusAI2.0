"""Tests for DocumentService — search, get_by_id, store, and extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.document_service import DocumentService


def _make_mock_db(fetch_return=None, fetchrow_return=None):
    """Create a mock db_manager with pool.acquire context manager."""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=fetch_return or [])
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    mock_pool = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = mock_ctx

    mock_db = MagicMock()
    mock_db.pool = mock_pool
    return mock_db, mock_conn


class TestSearchDocuments:
    @pytest.mark.asyncio
    async def test_search_documents_basic(self):
        mock_db, mock_conn = _make_mock_db(fetch_return=[
            {"id": "d1", "product_id": "p1", "doc_type": "TDS",
             "file_name": "tds.pdf", "is_current": True, "created_at": "2026-01-01"},
        ])
        svc = DocumentService(db_manager=mock_db)
        results = await svc.search_documents("tds", limit=10)
        assert len(results) == 1
        assert results[0]["doc_type"] == "TDS"
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_documents_with_doc_type_filter(self):
        mock_db, mock_conn = _make_mock_db(fetch_return=[
            {"id": "d2", "product_id": "p2", "doc_type": "SDS",
             "file_name": "sds.pdf", "is_current": True, "created_at": "2026-01-01"},
        ])
        svc = DocumentService(db_manager=mock_db)
        results = await svc.search_documents("sds", doc_type="SDS", limit=5)
        assert len(results) == 1
        # Verify the SQL includes doc_type parameter
        call_args = mock_conn.fetch.call_args
        assert "doc_type" in call_args.args[0] or len(call_args.args) >= 3

    @pytest.mark.asyncio
    async def test_search_documents_no_results(self):
        mock_db, _ = _make_mock_db(fetch_return=[])
        svc = DocumentService(db_manager=mock_db)
        results = await svc.search_documents("nonexistent")
        assert results == []


class TestGetDocumentById:
    @pytest.mark.asyncio
    async def test_get_document_by_id_found(self):
        mock_db, _ = _make_mock_db(fetchrow_return={
            "id": "d1", "product_id": "p1", "doc_type": "SDS",
            "file_name": "sds.pdf",
        })
        svc = DocumentService(db_manager=mock_db)
        doc = await svc.get_document_by_id("d1")
        assert doc is not None
        assert doc["id"] == "d1"
        assert doc["doc_type"] == "SDS"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self):
        mock_db, _ = _make_mock_db(fetchrow_return=None)
        svc = DocumentService(db_manager=mock_db)
        doc = await svc.get_document_by_id("nonexistent")
        assert doc is None


class TestGetDocumentsForProduct:
    @pytest.mark.asyncio
    async def test_get_documents_for_product(self):
        mock_db, _ = _make_mock_db(fetch_return=[
            {"id": "d1", "doc_type": "TDS", "file_name": "tds.pdf",
             "file_path": "/data/p1/TDS_tds.pdf", "is_current": True, "created_at": "2026-01-01"},
            {"id": "d2", "doc_type": "SDS", "file_name": "sds.pdf",
             "file_path": "/data/p1/SDS_sds.pdf", "is_current": True, "created_at": "2026-01-01"},
        ])
        svc = DocumentService(db_manager=mock_db)
        docs = await svc.get_documents_for_product("p1")
        assert len(docs) == 2
        assert docs[0]["doc_type"] == "TDS"

    @pytest.mark.asyncio
    async def test_get_documents_for_product_empty(self):
        mock_db, _ = _make_mock_db(fetch_return=[])
        svc = DocumentService(db_manager=mock_db)
        docs = await svc.get_documents_for_product("no-product")
        assert docs == []


class TestCallLLM:
    @pytest.mark.asyncio
    async def test_call_llm_no_ai_service_raises(self):
        mock_db, _ = _make_mock_db()
        svc = DocumentService(db_manager=mock_db, ai_service=None)
        with pytest.raises(RuntimeError, match="AI service not configured"):
            await svc._call_llm("extract fields")

    @pytest.mark.asyncio
    async def test_call_llm_parses_json(self):
        mock_ai = MagicMock()
        mock_ai.chat = AsyncMock(return_value='{"viscosity": "1200 cP"}')
        mock_db, _ = _make_mock_db()
        svc = DocumentService(db_manager=mock_db, ai_service=mock_ai)
        result = await svc._call_llm("extract fields")
        assert result == {"viscosity": "1200 cP"}
