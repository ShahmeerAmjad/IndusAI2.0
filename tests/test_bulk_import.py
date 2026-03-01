# =======================
# Tests — BulkImportService
# =======================

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.bulk_import_service import BulkImportService


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def service(mock_pool):
    pool, _ = mock_pool
    return BulkImportService(pool)


# ---------- Products CSV ----------

VALID_PRODUCTS_CSV = b"sku,name,category,manufacturer\nSKF-001,Test Bearing,Bearings,SKF\nNSK-002,NSK Bearing,Bearings,NSK"

@pytest.mark.asyncio
async def test_import_products_dry_run(service):
    result = await service.import_products(VALID_PRODUCTS_CSV, dry_run=True)
    assert result["success"] == 2
    assert result["total"] == 2
    assert result["dry_run"] is True
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_import_products_missing_sku(service):
    csv_data = b"sku,name\n,Test Bearing"
    result = await service.import_products(csv_data, dry_run=True)
    assert result["success"] == 0
    assert len(result["errors"]) == 1
    assert result["errors"][0]["field"] == "sku"


@pytest.mark.asyncio
async def test_import_products_missing_name(service):
    csv_data = b"sku,name\nSKF-001,"
    result = await service.import_products(csv_data, dry_run=True)
    assert len(result["errors"]) == 1
    assert result["errors"][0]["field"] == "name"


@pytest.mark.asyncio
async def test_import_products_missing_columns(service):
    csv_data = b"sku,category\nSKF-001,Bearings"
    result = await service.import_products(csv_data, dry_run=True)
    assert result["success"] == 0
    assert result["errors"][0]["field"] == "headers"


@pytest.mark.asyncio
async def test_import_products_too_large(service):
    csv_data = b"x" * (6 * 1024 * 1024)
    result = await service.import_products(csv_data, dry_run=True)
    assert result["success"] == 0
    assert "too large" in result["errors"][0]["error"].lower()


# ---------- Inventory CSV ----------

VALID_INVENTORY_CSV = b"sku,quantity_on_hand,warehouse_code,reorder_point\nSKF-001,150,MAIN,25"

@pytest.mark.asyncio
async def test_import_inventory_dry_run(service):
    result = await service.import_inventory(VALID_INVENTORY_CSV, dry_run=True)
    assert result["success"] == 1
    assert result["total"] == 1
    assert result["dry_run"] is True


@pytest.mark.asyncio
async def test_import_inventory_invalid_qty(service):
    csv_data = b"sku,quantity_on_hand\nSKF-001,not-a-number"
    result = await service.import_inventory(csv_data, dry_run=True)
    assert len(result["errors"]) == 1
    assert "invalid" in result["errors"][0]["error"].lower()


@pytest.mark.asyncio
async def test_import_inventory_negative_qty(service):
    csv_data = b"sku,quantity_on_hand\nSKF-001,-10"
    result = await service.import_inventory(csv_data, dry_run=True)
    assert len(result["errors"]) == 1
    assert "negative" in result["errors"][0]["error"].lower()


# ---------- Templates ----------

def test_product_template():
    data = BulkImportService.product_template()
    assert b"sku" in data
    assert b"name" in data
    assert b"SKF-6205-2RS" in data


def test_inventory_template():
    data = BulkImportService.inventory_template()
    assert b"sku" in data
    assert b"quantity_on_hand" in data


# ---------- Empty CSV ----------

@pytest.mark.asyncio
async def test_import_empty_csv(service):
    csv_data = b"sku,name"  # Headers only, no data
    result = await service.import_products(csv_data, dry_run=True)
    assert result["success"] == 0
    assert result["errors"][0]["error"] == "No data rows"
