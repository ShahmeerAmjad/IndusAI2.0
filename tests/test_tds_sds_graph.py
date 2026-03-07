"""Test creating TDS/SDS nodes and Industry relationships in Neo4j."""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_create_tds_node():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "tds-1"}])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.create_tds("SKU-001", {
        "appearance": "White powder",
        "density": "1.21 g/cm³",
        "flash_point": "N/A",
        "viscosity": "1200-4500 cP",
        "pdf_url": "/docs/tds.pdf",
        "revision_date": "2025-11-01",
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_sds_node():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "sds-1"}])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.create_sds("SKU-001", {
        "ghs_classification": "Not classified",
        "cas_numbers": ["25322-68-3"],
        "hazard_statements": [],
        "pdf_url": "/docs/sds.pdf",
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_industry_and_link_product():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{}])
    svc = TDSSDSGraphService(neo4j)
    await svc.link_product_to_industry("SKU-001", "Adhesives")
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_create_price_point():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{}])
    svc = TDSSDSGraphService(neo4j)
    await svc.set_price("SKU-001", {
        "unit_price": 42.50,
        "currency": "USD",
        "uom": "kg",
        "min_qty": 25,
    })
    neo4j.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_query_tds_property():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[{
        "flash_point": "N/A",
        "viscosity": "1200-4500 cP",
    }])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.get_tds_properties("SKU-001")
    assert result["flash_point"] == "N/A"


@pytest.mark.asyncio
async def test_set_inventory():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"qty": 100}])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.set_inventory("SKU-001", "WH-EAST", {"qty": 100})
    call_args = neo4j.execute_write.call_args
    params = call_args[0][1]
    assert params["sku"] == "SKU-001"
    assert params["wh"] == "WH-EAST"
    assert params["qty"] == 100


@pytest.mark.asyncio
async def test_get_sds_properties():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[{
        "ghs_classification": "Flammable",
        "cas_numbers": ["111-76-2"],
    }])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.get_sds_properties("SKU-001")
    assert result["ghs_classification"] == "Flammable"


@pytest.mark.asyncio
async def test_get_sds_properties_empty():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.get_sds_properties("SKU-NONE")
    assert result == {}


@pytest.mark.asyncio
async def test_get_tds_properties_empty():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.get_tds_properties("SKU-NONE")
    assert result == {}


@pytest.mark.asyncio
async def test_find_products_by_industry():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[
        {"sku": "SKU-001", "name": "Product A", "manufacturer": "Dow"},
        {"sku": "SKU-002", "name": "Product B", "manufacturer": "BASF"},
    ])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.find_products_by_industry("Adhesives")
    assert len(result) == 2
    assert result[0]["sku"] == "SKU-001"


@pytest.mark.asyncio
async def test_find_products_by_industry_none():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_read = AsyncMock(return_value=[])
    svc = TDSSDSGraphService(neo4j)
    result = await svc.find_products_by_industry("Nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_neo4j_write_failure_create_tds():
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(side_effect=Exception("Neo4j connection lost"))
    svc = TDSSDSGraphService(neo4j)
    with pytest.raises(Exception, match="Neo4j connection lost"):
        await svc.create_tds("SKU-001", {"appearance": "White powder"})


@pytest.mark.asyncio
async def test_create_tds_missing_optional_fields():
    """Defaults for revision_date and pdf_url when not in fields dict."""
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "tds-1"}])
    svc = TDSSDSGraphService(neo4j)
    await svc.create_tds("SKU-001", {"appearance": "Clear liquid"})
    call_args = neo4j.execute_write.call_args
    params = call_args[0][1]
    assert params["rev"] == "unknown"
    assert params["pdf_url"] is None


@pytest.mark.asyncio
async def test_create_sds_missing_optional_fields():
    """Defaults for cas_numbers and revision_date when not in fields dict."""
    from services.graph.tds_sds_service import TDSSDSGraphService
    neo4j = MagicMock()
    neo4j.execute_write = AsyncMock(return_value=[{"id": "sds-1"}])
    svc = TDSSDSGraphService(neo4j)
    await svc.create_sds("SKU-001", {"ghs_classification": "Not classified"})
    call_args = neo4j.execute_write.call_args
    params = call_args[0][1]
    assert params["cas"] == []
    assert params["pdf_url"] is None
    assert params["rev"] == "unknown"
