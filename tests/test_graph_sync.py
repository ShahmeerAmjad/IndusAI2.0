"""Tests for GraphSyncService — PG-to-Neo4j sync."""

import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_graph_service():
    svc = AsyncMock()
    svc.upsert_part = AsyncMock(return_value={"sku": "6204-2RS"})
    svc.update_inventory_cache = AsyncMock()
    svc.update_price_range = AsyncMock()
    return svc


@pytest.fixture
def mock_embedding_client():
    client = AsyncMock()
    client.embed_parts = AsyncMock(return_value=[[0.1] * 1024])
    return client


@pytest.fixture
def sync_service(mock_graph_service, mock_embedding_client):
    from services.graph.sync import GraphSyncService
    return GraphSyncService(
        graph_service=mock_graph_service,
        embedding_client=mock_embedding_client,
    )


@pytest.mark.asyncio
async def test_sync_product_upserts_part(sync_service, mock_graph_service):
    product = {
        "sku": "6204-2RS",
        "name": "Deep Groove Ball Bearing",
        "description": "Sealed bearing 20x47x14mm",
        "category": "Ball Bearings",
        "manufacturer": "SKF",
        "specs": [{"name": "bore_mm", "value": "20", "unit": "mm"}],
    }
    await sync_service.sync_product(product)
    mock_graph_service.upsert_part.assert_called_once()
    call_kwargs = mock_graph_service.upsert_part.call_args
    assert call_kwargs[1]["sku"] == "6204-2RS"


@pytest.mark.asyncio
async def test_sync_product_generates_embedding(sync_service, mock_embedding_client, mock_graph_service):
    product = {"sku": "TEST-1", "name": "Test Part", "description": "A test"}
    await sync_service.sync_product(product)
    mock_embedding_client.embed_parts.assert_called_once()


@pytest.mark.asyncio
async def test_sync_product_skips_embedding_if_no_client(mock_graph_service):
    from services.graph.sync import GraphSyncService
    svc = GraphSyncService(graph_service=mock_graph_service, embedding_client=None)
    product = {"sku": "TEST-2", "name": "No Embed"}
    await svc.sync_product(product)
    mock_graph_service.upsert_part.assert_called_once()


@pytest.mark.asyncio
async def test_sync_inventory(sync_service, mock_graph_service):
    await sync_service.sync_inventory("6204-2RS", "MAIN", 150)
    mock_graph_service.update_inventory_cache.assert_called_once_with(
        sku="6204-2RS", warehouse="MAIN", qty_on_hand=150,
    )


@pytest.mark.asyncio
async def test_sync_price(sync_service, mock_graph_service):
    await sync_service.sync_price("6204-2RS", 5.50, 12.00)
    mock_graph_service.update_price_range.assert_called_once_with(
        sku="6204-2RS", min_price=5.50, max_price=12.00,
    )
