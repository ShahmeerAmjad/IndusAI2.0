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
        [{"product": {"name": "Product A", "sku": "CP-AAA"}, "manufacturer": "Dow",
          "industries": ["Adhesives"], "has_tds": True, "has_sds": False},
         {"product": {"name": "Product B", "sku": "CP-BBB"}, "manufacturer": None,
          "industries": [], "has_tds": False, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)

    result = await svc.list_products(page=1, page_size=25)

    assert len(result["items"]) == 2
    assert result["page"] == 1
    assert result["page_size"] == 25
    assert result["total"] == 2
    assert result["items"][0]["manufacturer"] == "Dow"
    assert result["items"][0]["has_tds"] is True
    assert graph.execute_read.call_count == 2


@pytest.mark.asyncio
async def test_list_products_with_search():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],  # count query
        [{"product": {"name": "POLYOX WSR-301", "sku": "CP-AAA"}, "manufacturer": "Dow",
          "industries": [], "has_tds": False, "has_sds": False}],
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


@pytest.mark.asyncio
async def test_list_products_with_manufacturer_filter():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": ["Adhesives"], "has_tds": True, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)
    result = await svc.list_products(page=1, page_size=25, manufacturer="Dow")
    assert result["total"] == 1
    assert result["items"][0]["manufacturer"] == "Dow"
    # Verify the Cypher uses required MATCH (not WHERE after OPTIONAL MATCH)
    count_query = graph.execute_read.call_args_list[0][0][0]
    assert "MATCH (p)-[:MANUFACTURED_BY]->(:Manufacturer {name: $manufacturer})" in count_query


@pytest.mark.asyncio
async def test_list_products_manufacturer_filter_uses_required_match():
    """Manufacturer filter should use required MATCH so industries aren't corrupted."""
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": ["Adhesives", "Coatings", "Plastics"], "has_tds": True, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)
    result = await svc.list_products(manufacturer="Dow")
    # All industries should be preserved, not just the filtered one
    assert result["items"][0]["industries"] == ["Adhesives", "Coatings", "Plastics"]


@pytest.mark.asyncio
async def test_list_products_industry_filter_uses_required_match():
    """Industry filter should use required MATCH so all industries for matching products are shown."""
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": ["Adhesives", "Coatings"], "has_tds": False, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)
    result = await svc.list_products(industry="Adhesives")
    # Verify required MATCH for industry
    count_query = graph.execute_read.call_args_list[0][0][0]
    assert "MATCH (p)-[:SERVES_INDUSTRY]->(:Industry {name: $industry})" in count_query


@pytest.mark.asyncio
async def test_list_products_search_covers_description_and_manufacturer():
    """Search should cover name, SKU, CAS, description, AND manufacturer name."""
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": [], "has_tds": False, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)
    result = await svc.list_products(search="water-soluble")
    data_query = graph.execute_read.call_args_list[1][0][0]
    # Should search across description and manufacturer name
    assert "p.description" in data_query
    assert "mfr.name" in data_query


@pytest.mark.asyncio
async def test_list_products_with_has_tds_filter():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = AsyncMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"product": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": [], "has_tds": True, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(None, graph)
    result = await svc.list_products(has_tds=True)
    assert result["total"] == 1


# ── get_filters ──


@pytest.mark.asyncio
async def test_get_filters_returns_manufacturers_and_industries():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = MagicMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"name": "Dow"}, {"name": "BASF"}],  # manufacturers
        [{"name": "Adhesives"}, {"name": "Coatings"}],  # industries
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=graph)
    result = await svc.get_filters()
    assert result == {
        "manufacturers": ["Dow", "BASF"],
        "industries": ["Adhesives", "Coatings"],
    }


@pytest.mark.asyncio
async def test_get_filters_empty():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = MagicMock()
    graph.execute_read = AsyncMock(side_effect=[[], []])
    svc = KnowledgeBaseService(pool=None, graph_service=graph)
    result = await svc.get_filters()
    assert result == {"manufacturers": [], "industries": []}


# ── get_product_extraction ──


@pytest.mark.asyncio
async def test_get_product_extraction_returns_tds_sds_fields():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = MagicMock()
    graph.execute_read = AsyncMock(side_effect=[
        [{"props": {"appearance": {"value": "Clear liquid", "confidence": 0.95},
                     "product_sku": "SKU-001", "pdf_url": "https://example.com/tds.pdf"}}],
        [{"props": {"ghs_classification": {"value": "Flam. Liq. 3", "confidence": 0.9},
                     "product_sku": "SKU-001", "cas_numbers": ["64-17-5"]}}],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=graph)
    result = await svc.get_product_extraction("SKU-001")
    assert result["sku"] == "SKU-001"
    assert "appearance" in result["tds"]["fields"]
    assert result["tds"]["fields"]["appearance"]["confidence"] == 0.95
    assert result["tds"]["pdf_url"] == "https://example.com/tds.pdf"
    assert "ghs_classification" in result["sds"]["fields"]
    assert result["sds"]["cas_numbers"] == ["64-17-5"]
    # Metadata keys should not be in fields
    assert "product_sku" not in result["tds"]["fields"]
    assert "product_sku" not in result["sds"]["fields"]


@pytest.mark.asyncio
async def test_get_product_extraction_no_docs():
    from services.knowledge_base_service import KnowledgeBaseService

    graph = MagicMock()
    graph.execute_read = AsyncMock(side_effect=[[], []])
    svc = KnowledgeBaseService(pool=None, graph_service=graph)
    result = await svc.get_product_extraction("NO-DOCS")
    assert result["sku"] == "NO-DOCS"
    assert result["tds"]["fields"] == {}
    assert result["sds"]["fields"] == {}


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
