import pytest
from datetime import datetime, timezone, timedelta
from services.intelligence.price_comparator import PriceComparator, SourcingResult


class TestPriceComparator:
    def setup_method(self):
        self.comparator = PriceComparator()

    def test_composite_score_basic(self):
        result = SourcingResult(
            sku="6204-2RS", name="Bearing", seller_name="TestCo",
            unit_price=4.20, qty_available=100,
            reliability=8.0, distance_km=50, transit_days=1, shipping_cost=0,
        )
        score = self.comparator.composite_score(result, qty=100)
        assert 0 < score <= 10

    def test_cheaper_ranks_higher(self):
        cheap = SourcingResult(
            sku="A", name="A", seller_name="Cheap",
            unit_price=3.00, reliability=7.0, distance_km=500,
            transit_days=3, shipping_cost=25, qty_available=100,
        )
        expensive = SourcingResult(
            sku="A", name="A", seller_name="Pricey",
            unit_price=6.00, reliability=7.0, distance_km=500,
            transit_days=3, shipping_cost=25, qty_available=100,
        )
        results = self.comparator.rank([cheap, expensive], qty=10)
        assert results[0].seller_name == "Cheap"

    def test_reliable_ranks_higher_at_similar_price(self):
        reliable = SourcingResult(
            sku="A", name="A", seller_name="Reliable",
            unit_price=4.00, reliability=9.0, distance_km=200,
            transit_days=2, shipping_cost=15, qty_available=100,
        )
        unreliable = SourcingResult(
            sku="A", name="A", seller_name="Sketchy",
            unit_price=3.90, reliability=4.0, distance_km=200,
            transit_days=2, shipping_cost=15, qty_available=100,
        )
        results = self.comparator.rank([unreliable, reliable], qty=10)
        assert results[0].seller_name == "Reliable"

    def test_excludes_stale(self):
        stale = SourcingResult(
            sku="A", name="A", seller_name="Stale",
            unit_price=2.00, reliability=2.0, distance_km=100,
            transit_days=1, shipping_cost=0, qty_available=100,
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        fresh = SourcingResult(
            sku="A", name="A", seller_name="Fresh",
            unit_price=5.00, reliability=8.0, distance_km=100,
            transit_days=1, shipping_cost=0, qty_available=100,
        )
        results = self.comparator.rank([stale, fresh], qty=10)
        assert len(results) == 1
        assert results[0].seller_name == "Fresh"

    def test_total_cost(self):
        r = SourcingResult(
            sku="A", name="A", seller_name="X",
            unit_price=4.20, shipping_cost=45.0,
            reliability=7.0, distance_km=200, transit_days=2, qty_available=100,
        )
        assert r.total_cost(qty=100) == 4.20 * 100 + 45.0
