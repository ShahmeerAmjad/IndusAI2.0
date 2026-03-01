# =======================
# Tests — ReportService
# =======================

import csv
import io
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.report_service import ReportService


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
    return ReportService(pool)


SAMPLE_ORDERS = [
    {"order_number": "ORD-001", "customer_name": "Acme Corp", "status": "confirmed",
     "order_date": datetime(2026, 1, 15, 10, 30), "total_amount": Decimal("1250.00"),
     "payment_terms": "NET30", "shipping_method": "ground"},
    {"order_number": "ORD-002", "customer_name": "Widget Co", "status": "shipped",
     "order_date": datetime(2026, 1, 16, 14, 0), "total_amount": Decimal("890.50"),
     "payment_terms": "NET60", "shipping_method": "express"},
]


# ---------- CSV ----------

def test_generate_csv_with_data(service):
    result = service.generate_csv(SAMPLE_ORDERS)
    reader = csv.DictReader(io.StringIO(result.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["order_number"] == "ORD-001"
    assert rows[1]["customer_name"] == "Widget Co"


def test_generate_csv_empty(service):
    result = service.generate_csv([])
    assert result == b""


# ---------- Excel ----------

def test_generate_xlsx_with_data(service):
    result = service.generate_xlsx(SAMPLE_ORDERS, sheet_name="Orders")
    assert len(result) > 100  # Non-trivial file
    # Verify it's a valid xlsx (starts with PK zip header)
    assert result[:2] == b"PK"


def test_generate_xlsx_empty(service):
    result = service.generate_xlsx([])
    assert result[:2] == b"PK"  # Still a valid xlsx, just empty


# ---------- PDF ----------

def test_generate_pdf_with_data(service):
    result = service.generate_pdf(SAMPLE_ORDERS, title="Test Orders")
    assert len(result) > 100
    assert result[:5] == b"%PDF-"


def test_generate_pdf_empty(service):
    result = service.generate_pdf([], title="Empty Report")
    assert result[:5] == b"%PDF-"


# ---------- Data fetchers ----------

@pytest.mark.asyncio
async def test_fetch_orders(service, mock_pool):
    _, conn = mock_pool
    conn.fetch.return_value = [
        {"order_number": "ORD-001", "customer_name": "Acme", "status": "confirmed",
         "order_date": datetime(2026, 1, 15), "total_amount": 1250,
         "payment_terms": "NET30", "shipping_method": "ground"},
    ]
    rows = await service._fetch_orders()
    assert len(rows) == 1
    assert rows[0]["order_number"] == "ORD-001"


@pytest.mark.asyncio
async def test_fetch_inventory(service, mock_pool):
    _, conn = mock_pool
    conn.fetch.return_value = [
        {"sku": "SKF-6205", "name": "Bearing", "manufacturer": "SKF",
         "category": "Bearings", "warehouse_code": "MAIN",
         "quantity_on_hand": 150, "quantity_reserved": 10,
         "reorder_point": 25, "bin_location": "A-12"},
    ]
    rows = await service._fetch_inventory()
    assert len(rows) == 1
    assert rows[0]["sku"] == "SKF-6205"


@pytest.mark.asyncio
async def test_fetch_invoices(service, mock_pool):
    _, conn = mock_pool
    conn.fetch.return_value = []
    rows = await service._fetch_invoices()
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_sales(service, mock_pool):
    _, conn = mock_pool
    conn.fetch.return_value = [
        {"period": datetime(2026, 1, 1), "order_count": 42, "revenue": 125000},
    ]
    rows = await service._fetch_sales("month")
    assert len(rows) == 1
    assert rows[0]["order_count"] == 42


@pytest.mark.asyncio
async def test_fetch_no_pool():
    svc = ReportService(None)
    assert await svc._fetch_orders() == []
    assert await svc._fetch_inventory() == []
    assert await svc._fetch_invoices() == []
    assert await svc._fetch_sales() == []
