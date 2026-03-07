"""Tests for routes.documents — document upload, download, search."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from routes.documents import router, set_document_services
import routes.documents as doc_mod


@pytest.fixture(autouse=True)
def setup_services():
    """Set up mock document service."""
    mock_svc = MagicMock()
    mock_svc.get_documents_for_product = AsyncMock(return_value=[
        {"id": "d1", "doc_type": "TDS", "file_name": "tds.pdf", "is_current": True},
        {"id": "d2", "doc_type": "SDS", "file_name": "sds.pdf", "is_current": True},
    ])
    mock_svc.store_document = AsyncMock(return_value={
        "id": "d3", "product_id": "prod-1", "doc_type": "TDS",
        "file_name": "tds.pdf", "file_size_bytes": 1024,
        "is_current": True, "created_at": "2026-03-05",
    })
    mock_svc.get_document_by_id = AsyncMock(return_value={
        "id": "d1", "file_path": "/tmp/test.pdf", "file_name": "test.pdf",
    })
    mock_svc.search_documents = AsyncMock(return_value=[
        {"id": "d1", "product_id": "prod-1", "doc_type": "TDS",
         "file_name": "tds.pdf", "is_current": True, "created_at": "2026-03-05"},
    ])
    set_document_services(document_service=mock_svc)
    yield mock_svc
    set_document_services(None)


class TestListDocumentsForProduct:
    @pytest.mark.asyncio
    async def test_list_docs(self, setup_services):
        from routes.documents import list_documents_for_product
        result = await list_documents_for_product("prod-1")
        assert len(result) == 2
        setup_services.get_documents_for_product.assert_called_with("prod-1")


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_upload_tds(self, setup_services):
        from routes.documents import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="tds.pdf", file=io.BytesIO(b"fake-pdf"))
        result = await upload_document(product_id="prod-1", doc_type="TDS", file=mock_file)
        assert result["id"] == "d3"
        setup_services.store_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_invalid_type(self, setup_services):
        from routes.documents import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="doc.pdf", file=io.BytesIO(b"data"))
        with pytest.raises(Exception) as exc_info:
            await upload_document(product_id="prod-1", doc_type="INVALID", file=mock_file)
        assert exc_info.value.status_code == 400


class TestSearchDocuments:
    @pytest.mark.asyncio
    async def test_search(self, setup_services):
        from routes.documents import search_documents
        result = await search_documents(q="epoxy")
        assert len(result) == 1
        setup_services.search_documents.assert_called_once()


class TestDownloadDocument:
    @pytest.mark.asyncio
    async def test_download_not_found(self, setup_services):
        setup_services.get_document_by_id.return_value = None
        from routes.documents import download_document
        with pytest.raises(Exception) as exc_info:
            await download_document("nonexistent")
        assert exc_info.value.status_code == 404
