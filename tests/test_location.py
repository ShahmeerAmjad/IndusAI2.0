import pytest
from services.intelligence.location import LocationOptimizer


class TestLocationOptimizer:
    def setup_method(self):
        self.optimizer = LocationOptimizer()

    def test_haversine_distance(self):
        # NYC to LA ~ 3944 km
        d = self.optimizer.haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < d < 4000

    def test_haversine_same_point(self):
        d = self.optimizer.haversine_distance(40.0, -74.0, 40.0, -74.0)
        assert d == 0.0

    def test_estimate_shipping_local(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=20, weight_lbs=10)
        assert cost < 15
        assert days <= 1

    def test_estimate_shipping_medium(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=500, weight_lbs=10)
        assert 10 < cost < 50
        assert 1 <= days <= 3

    def test_estimate_shipping_long(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=3000, weight_lbs=10)
        assert cost > 30
        assert days >= 3

    def test_rank_by_proximity(self):
        buyer = (40.7128, -74.0060)  # NYC
        sellers = [
            {"id": "far", "lat": 34.0522, "lng": -118.2437},   # LA
            {"id": "close", "lat": 39.9526, "lng": -75.1652},  # Philly
            {"id": "mid", "lat": 41.8781, "lng": -87.6298},    # Chicago
        ]
        ranked = self.optimizer.rank_by_proximity(buyer, sellers)
        assert ranked[0]["id"] == "close"
        assert ranked[-1]["id"] == "far"
        assert "distance_km" in ranked[0]
