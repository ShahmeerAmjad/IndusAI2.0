"""Tests for KnowledgeBaseService — Neo4j product ingestion and querying."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_pool():
    """Create a mock asyncpg pool with acquire context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


def _sample_product(**overrides):
    base = {
        "name": "POLYOX WSR-301",
        "manufacturer": "Dow",
        "cas_number": "25322-68-3",
        "description": "Water-soluble polymer",
        "tds_url": "https://example.com/tds.pdf",
        "sds_url": "https://example.com/sds.pdf",
        "industries": ["Adhesives", "Coatings"],
        "product_line": "POLYOX",
    }
    base.update(overrides)
    return base


# ── ingest_product ──


@pytest.mark.asyncio
async def test_ingest_product_creates_neo4j_nodes():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    sku = await svc.ingest_product(_sample_product())

    assert sku.startswith("CP-")
    assert len(sku) == 11  # CP- + 8 hex chars
    # 1 combined MERGE (Part + Manufacturer + ProductLine) + 2 Industry MERGEs = 3
    assert graph.execute_write.call_count == 3


@pytest.mark.asyncio
async def test_ingest_product_stores_tds_sds_urls():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    await svc.ingest_product(_sample_product())

    # Should insert TDS and SDS rows
    assert conn.execute.call_count == 2
    tds_call = conn.execute.call_args_list[0]
    assert "TDS" in str(tds_call)
    sds_call = conn.execute.call_args_list[1]
    assert "SDS" in str(sds_call)


@pytest.mark.asyncio
async def test_ingest_product_no_tds_sds():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    product = _sample_product(tds_url=None, sds_url=None)
    await svc.ingest_product(product)

    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_product_no_manufacturer():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    product = _sample_product(manufacturer=None, product_line=None, industries=[])
    await svc.ingest_product(product)

    # Only the Product node MERGE, no mfg/product_line/industry
    assert graph.execute_write.call_count == 1


@pytest.mark.asyncio
async def test_ingest_product_no_pool():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(None, graph)

    # Should still create Neo4j nodes but skip PG doc storage
    sku = await svc.ingest_product(_sample_product())
    assert sku.startswith("CP-")
    graph.execute_write.assert_called()


# ── ingest_batch ──


@pytest.mark.asyncio
async def test_ingest_batch_success():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    products = [_sample_product(name=f"Product {i}") for i in range(3)]
    result = await svc.ingest_batch(products)

    assert result["total"] == 3
    assert result["ingested"] == 3
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_ingest_batch_partial_failure():
    from services.knowledge_base_service import KnowledgeBaseService

    pool, conn = _make_pool()
    graph = AsyncMock()
    graph.execute_write = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(pool, graph)

    # Make the second call to ingest_product fail
    call_count = 0
    original_ingest = svc.ingest_product

    async def failing_ingest(product):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("Bad product data")
        return await original_ingest(product)

    svc.ingest_product = failing_ingest

    products = [_sample_product(name=f"Product {i}") for i in range(3)]
    result = await svc.ingest_batch(products)

    assert result["total"] == 3
    assert result["ingested"] == 2
    assert len(result["errors"]) == 1
    assert "Bad product data" in result["errors"][0]["error"]


@pytest.mark.asyncio
async def test_ingest_batch_empty():
    from services.knowledge_base_service import KnowledgeBaseService

    svc = KnowledgeBaseService(None, AsyncMock())
    result = await svc.ingest_batch([])

    assert result == {"total": 0, "ingested": 0, "errors": []}


# ── list_products ──


@pytest.mark.asyncio
async def test_list_products_basic():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 2}],  # count query
        [{"p": {"name": "Product A", "sku": "CP-AAA"}},
         {"p": {"name": "Product B", "sku": "CP-BBB"}}],  # data query
    ])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.list_products(page=1, page_size=25)

    assert len(result["items"]) == 2
    assert result["page"] == 1
    assert result["page_size"] == 25
    assert result["total"] == 2
    assert graph.execute_read.call_count == 2


@pytest.mark.asyncio
async def test_list_products_with_search():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],  # count query
        [{"p": {"name": "POLYOX WSR-301", "sku": "CP-AAA"}}],  # data query
    ])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.list_products(search="polyox")

    assert len(result["items"]) == 1
    assert result["total"] == 1
    # Verify the search term was passed in the data query params
    call_args = graph.execute_read.call_args
    params = call_args[0][1]  # second positional arg is the params dict
    assert params["search"] == "polyox"


@pytest.mark.asyncio
async def test_list_products_pagination():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 0}],  # count query
        [],  # data query
    ])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.list_products(page=3, page_size=10)

    assert result["page"] == 3
    assert result["page_size"] == 10
    assert result["total"] == 0
    # Verify skip/limit on the data query (second call)
    call_args = graph.execute_read.call_args
    params = call_args[0][1]
    assert params["skip"] == 20
    assert params["limit"] == 10


# ── get_product ──


@pytest.mark.asyncio
async def test_get_product_found():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(return_value=[{
        "p": {"name": "POLYOX WSR-301", "sku": "CP-AAA", "cas_number": "25322-68-3"},
        "manufacturer": "Dow",
        "product_line": "POLYOX",
        "industries": ["Adhesives", "Coatings"],
    }])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.get_product("CP-AAA")

    assert result is not None
    assert result["sku"] == "CP-AAA"
    assert result["manufacturer"] == "Dow"
    assert result["industries"] == ["Adhesives", "Coatings"]
    # With pool=None, TDS/SDS URLs should be None
    assert result["tds_url"] is None
    assert result["sds_url"] is None


@pytest.mark.asyncio
async def test_get_product_not_found():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(return_value=[])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.get_product("NONEXISTENT")

    assert result is None


@pytest.mark.asyncio
async def test_get_product_no_relationships():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(return_value=[{
        "p": {"name": "Bare Product", "sku": "CP-BARE"},
        "manufacturer": None,
        "product_line": None,
        "industries": [],
    }])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.get_product("CP-BARE")

    assert result is not None
    assert result["manufacturer"] is None
    assert result["industries"] == []


@pytest.mark.asyncio
async def test_get_product_with_pg_documents():
    """Verify get_product fetches TDS/SDS URLs from PostgreSQL when pool is available."""
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(return_value=[{
        "p": {"name": "POLYOX WSR-301", "sku": "CP-AAA"},
        "manufacturer": "Dow",
        "product_line": "POLYOX",
        "industries": [],
    }])
    pool, conn = _make_pool()
    conn.fetch.return_value = [
        {"doc_type": "TDS", "source_url": "https://example.com/tds.pdf"},
        {"doc_type": "SDS", "source_url": "https://example.com/sds.pdf"},
    ]
    svc = KnowledgeBaseService(pool, graph)

    result = await svc.get_product("CP-AAA")

    assert result["tds_url"] == "https://example.com/tds.pdf"
    assert result["sds_url"] == "https://example.com/sds.pdf"
