"""Tests for inventory adapter abstraction layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ingestion.inventory_adapter import (
    BaseInventoryAdapter,
    PostgreSQLInventoryAdapter,
    RestAPIInventoryAdapter,
    InventoryAdapterRegistry,
    StockLevel,
)


# ---------------------------------------------------------------------------
# PostgreSQL Adapter
# ---------------------------------------------------------------------------

class TestPostgreSQLInventoryAdapter:
    def _make_adapter(self, stock_by_sku_return=None, all_stock_return=None):
        svc = MagicMock()
        svc.get_stock_by_sku = AsyncMock(return_value=stock_by_sku_return)
        svc.get_all_stock = AsyncMock(return_value=all_stock_return or ([], 0))
        svc.db = MagicMock()
        svc.db.pool = True
        return PostgreSQLInventoryAdapter(svc), svc

    @pytest.mark.asyncio
    async def test_name(self):
        adapter, _ = self._make_adapter()
        assert adapter.name == "postgres"

    @pytest.mark.asyncio
    async def test_get_stock_found(self):
        adapter, svc = self._make_adapter(stock_by_sku_return={
            "sku": "6205-2RS",
            "warehouse_code": "MAIN",
            "quantity_on_hand": 100,
            "quantity_reserved": 10,
            "quantity_available": 90,
            "quantity_on_order": 50,
            "updated_at": "2026-02-27T00:00:00",
            "product_id": "abc-123",
            "bin_location": "A-01",
        })
        result = await adapter.get_stock("6205-2RS")
        assert result is not None
        assert result.sku == "6205-2RS"
        assert result.quantity_available == 90
        assert result.source == "postgres"
        svc.get_stock_by_sku.assert_called_once_with("6205-2RS", "MAIN")

    @pytest.mark.asyncio
    async def test_get_stock_not_found(self):
        adapter, _ = self._make_adapter(stock_by_sku_return=None)
        result = await adapter.get_stock("NONEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_stock(self):
        adapter, _ = self._make_adapter(all_stock_return=([
            {"sku": "6205-2RS", "warehouse_code": "MAIN", "quantity_on_hand": 100,
             "quantity_reserved": 5, "quantity_available": 95, "quantity_on_order": 0,
             "product_id": "abc"},
            {"sku": "6205-2RS", "warehouse_code": "WEST", "quantity_on_hand": 50,
             "quantity_reserved": 0, "quantity_available": 50, "quantity_on_order": 0,
             "product_id": "abc"},
            {"sku": "OTHER-SKU", "warehouse_code": "MAIN", "quantity_on_hand": 200,
             "quantity_reserved": 0, "quantity_available": 200, "quantity_on_order": 0,
             "product_id": "def"},
        ], 3))
        results = await adapter.search_stock("6205-2RS")
        assert len(results) == 2
        assert all(r.sku == "6205-2RS" for r in results)

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        adapter, _ = self._make_adapter()
        status = await adapter.health_check()
        assert status["healthy"] is True
        assert status["adapter"] == "postgres"

    @pytest.mark.asyncio
    async def test_health_check_no_pool(self):
        adapter, svc = self._make_adapter()
        svc.db.pool = None
        status = await adapter.health_check()
        assert status["healthy"] is False


# ---------------------------------------------------------------------------
# REST API Adapter
# ---------------------------------------------------------------------------

class TestRestAPIInventoryAdapter:
    @pytest.mark.asyncio
    async def test_name(self):
        adapter = RestAPIInventoryAdapter("vendor-x", "https://api.vendor-x.com")
        assert adapter.name == "vendor-x"

    @pytest.mark.asyncio
    async def test_get_stock_success(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "items": [{
                "sku": "6205-2RS",
                "warehouse": "NYC",
                "on_hand": 200,
                "reserved": 20,
                "available": 180,
                "on_order": 0,
                "lead_time_days": 3,
                "unit_price": 9.50,
            }]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        result = await adapter.get_stock("6205-2RS", "NYC")
        assert result is not None
        assert result.sku == "6205-2RS"
        assert result.quantity_available == 180
        assert result.lead_time_days == 3
        assert result.unit_price == 9.50
        assert result.source == "test-api"

    @pytest.mark.asyncio
    async def test_get_stock_empty_response(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        result = await adapter.get_stock("NONEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stock_network_error(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        adapter._client = mock_client

        result = await adapter.get_stock("6205-2RS")
        assert result is None  # graceful degradation

    @pytest.mark.asyncio
    async def test_custom_field_mapping(self):
        adapter = RestAPIInventoryAdapter(
            "custom-api", "https://api.custom.com",
            field_map={
                "sku": "part_number",
                "warehouse": "location",
                "on_hand": "qty_in_stock",
                "reserved": "qty_reserved",
                "available": "qty_free",
            },
        )
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "items": [{
                "part_number": "ABC-123",
                "location": "WEST",
                "qty_in_stock": 500,
                "qty_reserved": 50,
                "qty_free": 450,
                "on_order": 100,
            }]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        result = await adapter.get_stock("ABC-123")
        assert result.sku == "ABC-123"
        assert result.warehouse == "WEST"
        assert result.quantity_on_hand == 500
        assert result.quantity_available == 450

    @pytest.mark.asyncio
    async def test_search_stock(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "items": [
                {"sku": "6205-2RS", "warehouse": "NYC", "on_hand": 200, "reserved": 20},
                {"sku": "6205-2RS", "warehouse": "LA", "on_hand": 150, "reserved": 10},
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        results = await adapter.search_stock("6205-2RS")
        assert len(results) == 2
        assert results[0].warehouse == "NYC"
        assert results[1].warehouse == "LA"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        status = await adapter.health_check()
        assert status["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_down(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        adapter._client = mock_client

        status = await adapter.health_check()
        assert status["healthy"] is False

    @pytest.mark.asyncio
    async def test_close(self):
        adapter = RestAPIInventoryAdapter("test-api", "https://api.test.com")
        mock_client = AsyncMock()
        adapter._client = mock_client
        await adapter.close()
        mock_client.aclose.assert_called_once()
        assert adapter._client is None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestInventoryAdapterRegistry:
    def _make_mock_adapter(self, name: str, stock: StockLevel | None = None,
                           search_results: list[StockLevel] | None = None):
        adapter = AsyncMock(spec=BaseInventoryAdapter)
        adapter.name = name
        adapter.get_stock = AsyncMock(return_value=stock)
        adapter.search_stock = AsyncMock(return_value=search_results or [])
        adapter.health_check = AsyncMock(return_value={"adapter": name, "healthy": True})
        adapter.close = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_register_and_list(self):
        registry = InventoryAdapterRegistry()
        a1 = self._make_mock_adapter("source-a")
        a2 = self._make_mock_adapter("source-b")
        registry.register(a1)
        registry.register(a2)
        assert set(registry.adapters) == {"source-a", "source-b"}

    @pytest.mark.asyncio
    async def test_unregister(self):
        registry = InventoryAdapterRegistry()
        a1 = self._make_mock_adapter("source-a")
        registry.register(a1)
        registry.unregister("source-a")
        assert registry.adapters == []

    @pytest.mark.asyncio
    async def test_get_stock_aggregates(self):
        registry = InventoryAdapterRegistry()
        stock_a = StockLevel(sku="6205", warehouse="MAIN", source="a", quantity_available=100)
        stock_b = StockLevel(sku="6205", warehouse="EXT", source="b", quantity_available=50)
        registry.register(self._make_mock_adapter("a", stock=stock_a))
        registry.register(self._make_mock_adapter("b", stock=stock_b))

        results = await registry.get_stock("6205")
        assert len(results) == 2
        total_available = sum(r.quantity_available for r in results)
        assert total_available == 150

    @pytest.mark.asyncio
    async def test_get_stock_partial_failure(self):
        registry = InventoryAdapterRegistry()
        stock_a = StockLevel(sku="6205", warehouse="MAIN", source="a", quantity_available=100)
        good = self._make_mock_adapter("good", stock=stock_a)
        bad = self._make_mock_adapter("bad")
        bad.get_stock = AsyncMock(side_effect=Exception("connection lost"))
        registry.register(good)
        registry.register(bad)

        results = await registry.get_stock("6205")
        assert len(results) == 1  # gracefully skips failed adapter

    @pytest.mark.asyncio
    async def test_search_all(self):
        registry = InventoryAdapterRegistry()
        stocks_a = [StockLevel(sku="6205", warehouse="W1", source="a", quantity_available=100)]
        stocks_b = [
            StockLevel(sku="6205", warehouse="W2", source="b", quantity_available=50),
            StockLevel(sku="6205", warehouse="W3", source="b", quantity_available=25),
        ]
        registry.register(self._make_mock_adapter("a", search_results=stocks_a))
        registry.register(self._make_mock_adapter("b", search_results=stocks_b))

        results = await registry.search_all("6205")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_health_check(self):
        registry = InventoryAdapterRegistry()
        registry.register(self._make_mock_adapter("a"))
        registry.register(self._make_mock_adapter("b"))

        status = await registry.health_check()
        assert status["total"] == 2
        assert "a" in status["adapters"]
        assert "b" in status["adapters"]

    @pytest.mark.asyncio
    async def test_close_all(self):
        registry = InventoryAdapterRegistry()
        a1 = self._make_mock_adapter("a")
        a2 = self._make_mock_adapter("b")
        registry.register(a1)
        registry.register(a2)

        await registry.close()
        a1.close.assert_called_once()
        a2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_registry(self):
        registry = InventoryAdapterRegistry()
        results = await registry.get_stock("6205")
        assert results == []
        results = await registry.search_all("6205")
        assert results == []
        status = await registry.health_check()
        assert status["total"] == 0
