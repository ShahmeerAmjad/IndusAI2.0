import pytest


def test_seller_schema_exists():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "seller_profiles" in PLATFORM_SCHEMA
    assert "seller_listings" in PLATFORM_SCHEMA
    assert "seller_warehouses" in PLATFORM_SCHEMA
    assert "rfq_requests" in PLATFORM_SCHEMA


def test_seller_service_importable():
    from services.seller_service import SellerService
    assert SellerService is not None
