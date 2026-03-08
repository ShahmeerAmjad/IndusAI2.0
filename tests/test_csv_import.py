"""Tests for CSV/Excel product import service."""
import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.ingestion.csv_import_service import CSVImportService


def _make_service():
    pipeline = MagicMock()
    pipeline._process_product = AsyncMock()
    pipeline._process_document = AsyncMock()
    return CSVImportService(pipeline)


@pytest.mark.asyncio
async def test_parse_csv_standard_headers():
    svc = _make_service()
    csv_content = b"name,manufacturer,cas_number,description\nNovec 72DA,3M,64742-49-0,Heavy-duty solvent\n"
    products = await svc.parse_file(io.BytesIO(csv_content), "products.csv")
    assert len(products) == 1
    assert products[0]["name"] == "Novec 72DA"
    assert products[0]["manufacturer"] == "3M"
    assert products[0]["cas_number"] == "64742-49-0"


@pytest.mark.asyncio
async def test_parse_csv_nonstandard_headers():
    """Column aliases map non-standard names."""
    svc = _make_service()
    csv_content = b"Product Name,Supplier,CAS #\nNovec 72DA,3M,64742-49-0\n"
    products = await svc.parse_file(io.BytesIO(csv_content), "products.csv")
    assert len(products) == 1
    assert products[0]["name"] == "Novec 72DA"
    assert products[0]["manufacturer"] == "3M"
    assert products[0]["cas_number"] == "64742-49-0"


@pytest.mark.asyncio
async def test_parse_xlsx():
    """Excel files should also be parseable."""
    svc = _make_service()
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["name", "manufacturer"])
    ws.append(["Product A", "Acme Corp"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    products = await svc.parse_file(buf, "products.xlsx")
    assert len(products) == 1
    assert products[0]["name"] == "Product A"


@pytest.mark.asyncio
async def test_dry_run_returns_preview():
    svc = _make_service()
    csv_content = b"name,manufacturer\nP1,M1\nP2,M2\nP3,M3\nP4,M4\nP5,M5\nP6,M6\n"
    preview = await svc.dry_run(io.BytesIO(csv_content), "products.csv")
    assert len(preview["sample_rows"]) == 5  # First 5 only
    assert preview["total_rows"] == 6
    assert "name" in preview["columns"]


@pytest.mark.asyncio
async def test_import_creates_products():
    svc = _make_service()
    svc._pipeline._process_product = AsyncMock()
    svc._pipeline._db = MagicMock()
    products = [{"name": "P1", "manufacturer": "M1"}]
    stats = await svc.import_products(products, on_progress=lambda e: None)
    svc._pipeline._process_product.assert_called_once()
