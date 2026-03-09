"""Tests for KnowledgeBaseService and knowledge_base routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.knowledge_base_service import KnowledgeBaseService


@pytest.mark.asyncio
async def test_get_filters_returns_manufacturers_and_industries():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"name": "Dow"}, {"name": "BASF"}],
        [{"name": "Adhesives"}, {"name": "Coatings"}],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.get_filters()
    assert result == {
        "manufacturers": ["Dow", "BASF"],
        "industries": ["Adhesives", "Coatings"],
    }


@pytest.mark.asyncio
async def test_get_product_extraction_returns_tds_sds_fields():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"props": {"appearance": {"value": "Clear liquid", "confidence": 0.95},
                     "product_sku": "SKU-001", "revision_date": "2025-01", "pdf_url": "http://tds.pdf"}}],
        [{"props": {"ghs_classification": {"value": "Flam. Liq. 3", "confidence": 0.9},
                     "product_sku": "SKU-001", "revision_date": "2025-02", "pdf_url": "http://sds.pdf",
                     "cas_numbers": ["64-17-5"]}}],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.get_product_extraction("SKU-001")
    assert result["sku"] == "SKU-001"
    assert "appearance" in result["tds"]["fields"]
    assert result["tds"]["fields"]["appearance"]["confidence"] == 0.95
    assert result["tds"]["pdf_url"] == "http://tds.pdf"
    assert "ghs_classification" in result["sds"]["fields"]
    assert result["sds"]["cas_numbers"] == ["64-17-5"]
    # Meta keys should not be in fields
    assert "product_sku" not in result["tds"]["fields"]
    assert "product_sku" not in result["sds"]["fields"]


@pytest.mark.asyncio
async def test_get_product_extraction_empty():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.get_product_extraction("MISSING")
    assert result["tds"]["fields"] == {}
    assert result["sds"]["fields"] == {}


@pytest.mark.asyncio
async def test_list_products_with_manufacturer_filter():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],  # count query
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": ["Adhesives"], "has_tds": True, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.list_products(page=1, page_size=25, manufacturer="Dow")
    assert result["total"] == 1
    assert result["items"][0]["manufacturer"] == "Dow"
    assert result["items"][0]["has_tds"] is True
    assert result["items"][0]["has_sds"] is False


@pytest.mark.asyncio
async def test_list_products_with_has_tds_filter():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"total": 2}],
        [
            {"product": {"sku": "A-1", "name": "Part A"}, "manufacturer": "Dow",
             "industries": [], "has_tds": True, "has_sds": True},
            {"product": {"sku": "B-1", "name": "Part B"}, "manufacturer": "BASF",
             "industries": ["Coatings"], "has_tds": True, "has_sds": False},
        ],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.list_products(page=1, page_size=25, has_tds=True)
    assert result["total"] == 2
    assert all(item["has_tds"] for item in result["items"])


# ── Route-level tests ──


@pytest.mark.asyncio
async def test_filters_route():
    """Test GET /api/v1/knowledge-base/filters returns manufacturers and industries."""
    from routes.knowledge_base import router, set_kb_service
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    app = FastAPI()
    app.include_router(router)

    mock_svc = MagicMock()
    mock_svc.get_filters = AsyncMock(return_value={
        "manufacturers": ["Dow", "BASF"],
        "industries": ["Adhesives"],
    })
    set_kb_service(mock_svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/knowledge-base/filters")
    assert resp.status_code == 200
    data = resp.json()
    assert "Dow" in data["manufacturers"]
    assert "Adhesives" in data["industries"]

    set_kb_service(None)


@pytest.mark.asyncio
async def test_extraction_route():
    """Test GET /api/v1/knowledge-base/products/{sku}/extraction."""
    from routes.knowledge_base import router, set_kb_service
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport

    app = FastAPI()
    app.include_router(router)

    mock_svc = MagicMock()
    mock_svc.get_product_extraction = AsyncMock(return_value={
        "sku": "TEST-001",
        "tds": {"fields": {"appearance": {"value": "Clear", "confidence": 0.9}},
                "pdf_url": None, "revision_date": None},
        "sds": {"fields": {}, "pdf_url": None, "revision_date": None, "cas_numbers": []},
    })
    set_kb_service(mock_svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/knowledge-base/products/TEST-001/extraction")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku"] == "TEST-001"
    assert data["tds"]["fields"]["appearance"]["confidence"] == 0.9

    set_kb_service(None)
