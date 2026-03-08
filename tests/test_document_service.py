"""Tests for DocumentService — search, get_by_id, store, and extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestExtraction:
    @pytest.mark.asyncio
    async def test_extract_sds_fields_with_confidence(self):
        svc = DocumentService(MagicMock())
        with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "ghs_classification": {"value": "Not classified", "confidence": 0.97},
                "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
                "un_number": {"value": "N/A", "confidence": 0.85},
                "hazard_statements": {"value": [], "confidence": 0.90},
                "precautionary_statements": {"value": ["P264"], "confidence": 0.82},
                "first_aid": {"value": "Move to fresh air", "confidence": 0.88},
                "ppe_requirements": {"value": "Safety glasses, gloves", "confidence": 0.91},
                "fire_fighting": {"value": "Use water spray", "confidence": 0.78},
                "environmental_hazards": {"value": "No known hazards", "confidence": 0.80},
                "transport_info": {"value": "Not regulated", "confidence": 0.93},
            }
            fields = await svc.extract_sds_fields_with_confidence("sample sds text")
            assert fields["cas_numbers"]["confidence"] == 0.99
            assert fields["ghs_classification"]["value"] == "Not classified"

    @pytest.mark.asyncio
    async def test_extract_tds_fields_truncates_long_text(self):
        svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
        captured_prompt = None
        async def capture_chat(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return '{"density": "1.0"}'
        svc._ai.chat = capture_chat

        long_text = "A" * 20000
        await svc.extract_tds_fields(long_text)

        # The text portion of the prompt should be truncated
        assert len(captured_prompt) < 10000  # 8000 chars + prompt template


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

    @pytest.mark.asyncio
    async def test_call_llm_strips_markdown_fences(self):
        """_call_llm should handle LLM responses wrapped in ```json fences."""
        svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
        svc._ai.chat = AsyncMock(return_value='```json\n{"density": "1.05 g/mL"}\n```')
        result = await svc._call_llm("Extract fields")
        assert result == {"density": "1.05 g/mL"}

    @pytest.mark.asyncio
    async def test_call_llm_strips_triple_backtick_only(self):
        """_call_llm should handle responses with ``` but no json tag."""
        svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
        svc._ai.chat = AsyncMock(return_value='```\n{"pH": "7.0"}\n```')
        result = await svc._call_llm("Extract fields")
        assert result == {"pH": "7.0"}
