"""Inventory adapter abstraction layer.

Adapter pattern for multiple inventory sources:
- PostgreSQL (internal warehouse, wraps InventoryService)
- REST API (external ERP / 3PL systems)
- Future: EDI, CSV import, etc.

The InventoryAdapterRegistry unifies queries across all adapters,
returning a consolidated view of stock across all sources.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class StockLevel:
    """Normalized stock level from any source."""
    sku: str
    warehouse: str
    source: str  # adapter name
    quantity_on_hand: float = 0
    quantity_reserved: float = 0
    quantity_available: float = 0
    quantity_on_order: float = 0
    lead_time_days: int | None = None
    unit_price: float | None = None
    last_updated: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class BaseInventoryAdapter(ABC):
    """Abstract interface for inventory data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name (e.g. 'postgres', 'erp-sap', 'api-vendor-x')."""

    @abstractmethod
    async def get_stock(self, sku: str, warehouse: str = "MAIN") -> StockLevel | None:
        """Get stock level for a single SKU at a warehouse."""

    @abstractmethod
    async def search_stock(self, sku: str) -> list[StockLevel]:
        """Search stock across all warehouses for a SKU."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return adapter health status."""

    async def close(self) -> None:
        """Cleanup resources. Override if adapter holds connections."""


class PostgreSQLInventoryAdapter(BaseInventoryAdapter):
    """Wraps the existing InventoryService (PostgreSQL-backed)."""

    def __init__(self, inventory_service):
        self._svc = inventory_service

    @property
    def name(self) -> str:
        return "postgres"

    async def get_stock(self, sku: str, warehouse: str = "MAIN") -> StockLevel | None:
        result = await self._svc.get_stock_by_sku(sku, warehouse)
        if not result:
            return None
        return StockLevel(
            sku=result.get("sku", sku),
            warehouse=result.get("warehouse_code", warehouse),
            source=self.name,
            quantity_on_hand=result.get("quantity_on_hand", 0),
            quantity_reserved=result.get("quantity_reserved", 0),
            quantity_available=result.get("quantity_available", 0),
            quantity_on_order=result.get("quantity_on_order", 0),
            last_updated=result.get("updated_at"),
            extra={"product_id": result.get("product_id"), "bin_location": result.get("bin_location")},
        )

    async def search_stock(self, sku: str) -> list[StockLevel]:
        # Search across all warehouses
        items, _ = await self._svc.get_all_stock(page=1, page_size=500)
        results = []
        for item in items:
            if item.get("sku", "").lower() == sku.lower():
                results.append(StockLevel(
                    sku=item["sku"],
                    warehouse=item.get("warehouse_code", "MAIN"),
                    source=self.name,
                    quantity_on_hand=item.get("quantity_on_hand", 0),
                    quantity_reserved=item.get("quantity_reserved", 0),
                    quantity_available=item.get("quantity_available", 0),
                    quantity_on_order=item.get("quantity_on_order", 0),
                    extra={"product_id": item.get("product_id")},
                ))
        return results

    async def health_check(self) -> dict[str, Any]:
        has_pool = bool(self._svc.db and self._svc.db.pool)
        return {"adapter": self.name, "healthy": has_pool, "type": "postgresql"}


class RestAPIInventoryAdapter(BaseInventoryAdapter):
    """Fetches inventory from an external REST API.

    Expected API contract (configurable via field mapping):
      GET {base_url}/stock?sku={sku}
      Returns JSON: { "items": [{ "sku": "...", "warehouse": "...", "on_hand": N, ... }] }
    """

    def __init__(
        self,
        adapter_name: str,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        field_map: dict[str, str] | None = None,
        timeout: float = 10.0,
    ):
        self._name = adapter_name
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        if headers:
            self._headers.update(headers)

        # Field mapping: our field -> API response field
        self._field_map = {
            "sku": "sku",
            "warehouse": "warehouse",
            "on_hand": "on_hand",
            "reserved": "reserved",
            "available": "available",
            "on_order": "on_order",
            "lead_time_days": "lead_time_days",
            "unit_price": "unit_price",
        }
        if field_map:
            self._field_map.update(field_map)

        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return self._name

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
            )
        return self._client

    def _parse_item(self, raw: dict[str, Any]) -> StockLevel:
        fm = self._field_map
        on_hand = float(raw.get(fm["on_hand"], 0))
        reserved = float(raw.get(fm["reserved"], 0))
        available = raw.get(fm["available"])
        if available is not None:
            available = float(available)
        else:
            available = on_hand - reserved

        lead_time = raw.get(fm["lead_time_days"])
        unit_price = raw.get(fm["unit_price"])

        return StockLevel(
            sku=raw.get(fm["sku"], ""),
            warehouse=raw.get(fm["warehouse"], "EXTERNAL"),
            source=self.name,
            quantity_on_hand=on_hand,
            quantity_reserved=reserved,
            quantity_available=available,
            quantity_on_order=float(raw.get(fm["on_order"], 0)),
            lead_time_days=int(lead_time) if lead_time is not None else None,
            unit_price=float(unit_price) if unit_price is not None else None,
        )

    async def get_stock(self, sku: str, warehouse: str = "MAIN") -> StockLevel | None:
        try:
            client = await self._get_client()
            resp = await client.get("/stock", params={"sku": sku, "warehouse": warehouse})
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [data] if "sku" in data else [])
            if not items:
                return None
            return self._parse_item(items[0])
        except Exception as e:
            logger.warning("REST adapter %s get_stock failed: %s", self.name, e)
            return None

    async def search_stock(self, sku: str) -> list[StockLevel]:
        try:
            client = await self._get_client()
            resp = await client.get("/stock", params={"sku": sku})
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [data] if "sku" in data else [])
            return [self._parse_item(item) for item in items]
        except Exception as e:
            logger.warning("REST adapter %s search_stock failed: %s", self.name, e)
            return []

    async def health_check(self) -> dict[str, Any]:
        try:
            client = await self._get_client()
            resp = await client.get("/health")
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        return {"adapter": self.name, "healthy": healthy, "type": "rest_api", "base_url": self._base_url}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class InventoryAdapterRegistry:
    """Unified inventory query across multiple adapters.

    Usage:
        registry = InventoryAdapterRegistry()
        registry.register(PostgreSQLInventoryAdapter(inventory_service))
        registry.register(RestAPIInventoryAdapter("vendor-x", "https://api.vendor-x.com"))

        # Search across all sources
        results = await registry.search_all("6205-2RS")
    """

    def __init__(self):
        self._adapters: dict[str, BaseInventoryAdapter] = {}

    def register(self, adapter: BaseInventoryAdapter) -> None:
        self._adapters[adapter.name] = adapter
        logger.info("Registered inventory adapter: %s", adapter.name)

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    @property
    def adapters(self) -> list[str]:
        return list(self._adapters.keys())

    async def get_stock(self, sku: str, warehouse: str = "MAIN") -> list[StockLevel]:
        """Query a specific SKU/warehouse across all adapters."""
        results: list[StockLevel] = []
        for adapter in self._adapters.values():
            try:
                stock = await adapter.get_stock(sku, warehouse)
                if stock:
                    results.append(stock)
            except Exception as e:
                logger.warning("Adapter %s failed for %s: %s", adapter.name, sku, e)
        return results

    async def search_all(self, sku: str) -> list[StockLevel]:
        """Search all warehouses across all adapters for a SKU."""
        results: list[StockLevel] = []
        for adapter in self._adapters.values():
            try:
                stocks = await adapter.search_stock(sku)
                results.extend(stocks)
            except Exception as e:
                logger.warning("Adapter %s search failed for %s: %s", adapter.name, sku, e)
        return results

    async def health_check(self) -> dict[str, Any]:
        """Health status of all adapters."""
        statuses = {}
        for name, adapter in self._adapters.items():
            try:
                statuses[name] = await adapter.health_check()
            except Exception as e:
                statuses[name] = {"adapter": name, "healthy": False, "error": str(e)}
        return {"adapters": statuses, "total": len(self._adapters)}

    async def close(self) -> None:
        """Cleanup all adapter resources."""
        for adapter in self._adapters.values():
            try:
                await adapter.close()
            except Exception as e:
                logger.warning("Failed to close adapter %s: %s", adapter.name, e)
