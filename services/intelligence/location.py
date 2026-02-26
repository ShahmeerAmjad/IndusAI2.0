"""Location optimizer — geocoding, distance calculation, shipping estimates."""

import logging
import math

logger = logging.getLogger(__name__)


class LocationOptimizer:
    """Calculate distances and estimate shipping between buyer and seller locations."""

    @staticmethod
    def haversine_distance(lat1: float, lng1: float,
                           lat2: float, lng2: float) -> float:
        """Great-circle distance in km between two lat/lng points."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def estimate_shipping(distance_km: float, weight_lbs: float = 5.0) -> tuple[float, int]:
        """Estimate shipping cost (USD) and transit days based on distance.

        Returns (cost, days). This is a rough heuristic — replace with
        carrier API (UPS/FedEx) for production accuracy.
        """
        distance_mi = distance_km * 0.621371

        if distance_mi < 50:
            days = 1
            base_cost = 0.0  # local pickup / free local delivery
        elif distance_mi < 300:
            days = 2
            base_cost = 12.0
        elif distance_mi < 1000:
            days = 3
            base_cost = 25.0
        elif distance_mi < 2000:
            days = 4
            base_cost = 40.0
        else:
            days = 5
            base_cost = 55.0

        # Weight surcharge: $0.50 per lb over 10 lbs
        weight_surcharge = max(0, (weight_lbs - 10)) * 0.50
        cost = round(base_cost + weight_surcharge, 2)

        return cost, days

    def rank_by_proximity(self, buyer_location: tuple[float, float],
                          seller_locations: list[dict]) -> list[dict]:
        """Rank seller locations by distance from buyer.

        Args:
            buyer_location: (lat, lng) of buyer
            seller_locations: list of dicts with 'lat', 'lng' keys

        Returns:
            Same list with 'distance_km', 'shipping_cost', 'transit_days' added,
            sorted by distance ascending.
        """
        buyer_lat, buyer_lng = buyer_location

        for seller in seller_locations:
            s_lat = seller.get("lat")
            s_lng = seller.get("lng")
            if s_lat is not None and s_lng is not None:
                dist = self.haversine_distance(buyer_lat, buyer_lng, s_lat, s_lng)
                cost, days = self.estimate_shipping(dist)
                seller["distance_km"] = round(dist, 1)
                seller["shipping_cost"] = cost
                seller["transit_days"] = days
            else:
                seller["distance_km"] = 99999
                seller["shipping_cost"] = 99.0
                seller["transit_days"] = 7

        return sorted(seller_locations, key=lambda s: s["distance_km"])
