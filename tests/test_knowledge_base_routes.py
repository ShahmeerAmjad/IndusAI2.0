"""Tests for routes.knowledge_base — product listing, crawl, document upload."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from routes.knowledge_base import (
    router, set_kb_service, set_chempoint_scraper, _crawl_jobs,
)
import routes.knowledge_base as kb_mod


@pytest.fixture(autouse=True)
def setup_services():
    """Inject mock services and clean up after each test."""
    mock_svc = MagicMock()
    mock_svc.list_products = AsyncMock(return_value={
        "items": [
            {"sku": "CP-001", "name": "Epikote 828", "cas_number": "25068-38-6"},
            {"sku": "CP-002", "name": "Silquest A-187", "cas_number": "2530-83-8"},
        ],
        "page": 1,
        "page_size": 25,
    })
    mock_svc.get_product = AsyncMock(return_value={
        "sku": "CP-001",
        "name": "Epikote 828",
        "cas_number": "25068-38-6",
        "manufacturer": "Hexion",
        "product_line": "Epikote",
        "industries": ["Adhesives", "Coatings"],
        "tds_url": "https://example.com/tds.pdf",
        "sds_url": "https://example.com/sds.pdf",
    })
    mock_svc.ingest_batch = AsyncMock(return_value={
        "total": 3, "ingested": 3, "errors": [],
    })
    mock_svc.get_graph_visualization = AsyncMock(return_value={
        "nodes": [], "edges": [],
    })

    mock_scraper = MagicMock()
    mock_scraper.crawl_full_catalog = AsyncMock(return_value=[
        {"name": "Product A", "sku": "CP-A"},
        {"name": "Product B", "sku": "CP-B"},
        {"name": "Product C", "sku": "CP-C"},
    ])

    set_kb_service(mock_svc)
    set_chempoint_scraper(mock_scraper)

    yield {"svc": mock_svc, "scraper": mock_scraper}

    set_kb_service(None)
    set_chempoint_scraper(None)
    _crawl_jobs.clear()


# ── Product listing ──


class TestListProducts:
    @pytest.mark.asyncio
    async def test_list_products_default(self, setup_services):
        from routes.knowledge_base import list_products
        result = await list_products(page=1, page_size=25, search=None)
        assert len(result["items"]) == 2
        setup_services["svc"].list_products.assert_called_once_with(
            page=1, page_size=25, search=None,
        )

    @pytest.mark.asyncio
    async def test_list_products_with_search(self, setup_services):
        from routes.knowledge_base import list_products
        await list_products(page=1, page_size=10, search="epoxy")
        setup_services["svc"].list_products.assert_called_once_with(
            page=1, page_size=10, search="epoxy",
        )

    @pytest.mark.asyncio
    async def test_list_products_includes_total(self, setup_services):
        setup_services["svc"].list_products = AsyncMock(return_value={
            "items": [{"sku": "X-1", "name": "Product X"}],
            "page": 1, "page_size": 25, "total": 42,
        })
        from routes.knowledge_base import list_products
        result = await list_products(page=1, page_size=25, search=None)
        assert "total" in result
        assert result["total"] == 42

    @pytest.mark.asyncio
    async def test_list_products_service_unavailable(self):
        set_kb_service(None)
        from routes.knowledge_base import list_products
        with pytest.raises(Exception) as exc_info:
            await list_products(page=1, page_size=25, search=None)
        assert exc_info.value.status_code == 503


# ── Product detail ──


class TestGetProduct:
    @pytest.mark.asyncio
    async def test_get_product_found(self, setup_services):
        from routes.knowledge_base import get_product
        result = await get_product("CP-001")
        assert result["sku"] == "CP-001"
        assert result["manufacturer"] == "Hexion"
        assert "Adhesives" in result["industries"]
        setup_services["svc"].get_product.assert_called_once_with("CP-001")

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, setup_services):
        setup_services["svc"].get_product.return_value = None
        from routes.knowledge_base import get_product
        with pytest.raises(Exception) as exc_info:
            await get_product("NONEXISTENT")
        assert exc_info.value.status_code == 404


# ── Crawl ──


class TestTriggerCrawl:
    @pytest.mark.asyncio
    async def test_trigger_crawl_returns_job_id(self, setup_services):
        from routes.knowledge_base import trigger_crawl
        result = await trigger_crawl(base_url="https://www.chempoint.com", max_pages=10)
        assert "job_id" in result
        assert result["status"] == "running"
        # Job should be tracked
        assert result["job_id"] in _crawl_jobs

    @pytest.mark.asyncio
    async def test_trigger_crawl_no_scraper(self):
        set_chempoint_scraper(None)
        from routes.knowledge_base import trigger_crawl
        with pytest.raises(Exception) as exc_info:
            await trigger_crawl(base_url="https://www.chempoint.com", max_pages=10)
        assert exc_info.value.status_code == 503


class TestGetCrawlStatus:
    @pytest.mark.asyncio
    async def test_crawl_status_found(self):
        _crawl_jobs["test-job"] = {"status": "completed", "products_found": 5, "error": None}
        from routes.knowledge_base import get_crawl_status
        result = await get_crawl_status("test-job")
        assert result["job_id"] == "test-job"
        assert result["status"] == "completed"
        assert result["products_found"] == 5

    @pytest.mark.asyncio
    async def test_crawl_status_not_found(self):
        from routes.knowledge_base import get_crawl_status
        with pytest.raises(Exception) as exc_info:
            await get_crawl_status("no-such-job")
        assert exc_info.value.status_code == 404


# ── Document upload ──


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_upload_tds(self, setup_services):
        from routes.knowledge_base import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="tds.pdf", file=io.BytesIO(b"fake-pdf-bytes"))
        result = await upload_document(product_id="CP-001", doc_type="TDS", file=mock_file)
        assert result["product_id"] == "CP-001"
        assert result["doc_type"] == "TDS"
        assert result["file_size_bytes"] == len(b"fake-pdf-bytes")
        assert result["status"] == "stored"

    @pytest.mark.asyncio
    async def test_upload_sds(self, setup_services):
        from routes.knowledge_base import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="sds.pdf", file=io.BytesIO(b"sds-content"))
        result = await upload_document(product_id="CP-002", doc_type="SDS", file=mock_file)
        assert result["doc_type"] == "SDS"

    @pytest.mark.asyncio
    async def test_upload_invalid_doc_type(self, setup_services):
        from routes.knowledge_base import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="doc.pdf", file=io.BytesIO(b"data"))
        with pytest.raises(Exception) as exc_info:
            await upload_document(product_id="CP-001", doc_type="MSDS", file=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_empty_file(self, setup_services):
        from routes.knowledge_base import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="empty.pdf", file=io.BytesIO(b""))
        with pytest.raises(Exception) as exc_info:
            await upload_document(product_id="CP-001", doc_type="TDS", file=mock_file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_service_unavailable(self):
        set_kb_service(None)
        from routes.knowledge_base import upload_document
        from fastapi import UploadFile
        import io

        mock_file = UploadFile(filename="tds.pdf", file=io.BytesIO(b"data"))
        with pytest.raises(Exception) as exc_info:
            await upload_document(product_id="CP-001", doc_type="TDS", file=mock_file)
        assert exc_info.value.status_code == 503


# ── Graph Visualization ──


class TestGraphVisualization:
    @pytest.mark.asyncio
    async def test_graph_visualization_endpoint(self, setup_services):
        from routes.knowledge_base import graph_visualization
        result = await graph_visualization(industry=None, manufacturer=None, limit=100)
        assert "nodes" in result
        assert "edges" in result
        setup_services["svc"].get_graph_visualization.assert_called_once_with(
            industry=None, manufacturer=None, limit=100,
        )

    @pytest.mark.asyncio
    async def test_graph_visualization_with_industry_filter(self, setup_services):
        from routes.knowledge_base import graph_visualization
        result = await graph_visualization(industry="Adhesives", manufacturer=None, limit=100)
        assert "nodes" in result
        setup_services["svc"].get_graph_visualization.assert_called_once_with(
            industry="Adhesives", manufacturer=None, limit=100,
        )
