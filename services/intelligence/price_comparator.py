"""Price comparator — normalize prices, compute composite ranking."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.intelligence.reliability import ReliabilityScorer

logger = logging.getLogger(__name__)


@dataclass
class SourcingResult:
    """A single sourcing option for a part from a specific seller."""
    sku: str
    name: str
    seller_name: str
    unit_price: float
    qty_available: int = 0
    reliability: float = 5.0
    distance_km: float = 0.0
    transit_days: int = 3
    shipping_cost: float = 0.0
    seller_id: str = ""
    warehouse_id: str = ""
    manufacturer: str = ""
    cross_ref_type: str = ""  # "exact", "equivalent", "alternative"
    last_verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    debug: dict = field(default_factory=dict)

    def total_cost(self, qty: int = 1) -> float:
        return round(self.unit_price * qty + self.shipping_cost, 2)


# Composite ranking weights
W_RELIABILITY = 0.30
W_PRICE = 0.35
W_DELIVERY = 0.25
W_PROXIMITY = 0.10


class PriceComparator:
    """Rank sourcing results by composite score."""

    def __init__(self):
        self._reliability = ReliabilityScorer()

    def composite_score(self, result: SourcingResult, qty: int = 1) -> float:
        """Compute composite score (0-10, higher is better)."""
        # Reliability: already 0-10
        r_score = result.reliability

        # Price: normalize — lower total cost = higher score
        total = result.total_cost(qty)
        # Heuristic: $0 = 10, $10000+ = 0
        p_score = max(0, 10 - (total / 1000.0))

        # Delivery: faster = higher
        d_score = max(0, 10 - result.transit_days * 2)

        # Proximity: closer = higher
        # 0 km = 10, 5000+ km = 0
        x_score = max(0, 10 - (result.distance_km / 500.0))

        composite = (
            W_RELIABILITY * r_score +
            W_PRICE * p_score +
            W_DELIVERY * d_score +
            W_PROXIMITY * x_score
        )

        result.debug = {
            "reliability_score": round(r_score, 2),
            "price_score": round(p_score, 2),
            "delivery_score": round(d_score, 2),
            "proximity_score": round(x_score, 2),
            "composite": round(composite, 3),
            "total_cost": total,
        }

        return round(composite, 3)

    def rank(self, results: list[SourcingResult],
             qty: int = 1,
             exclude_stale: bool = True) -> list[SourcingResult]:
        """Rank results by composite score, optionally excluding stale data."""
        if exclude_stale:
            results = [
                r for r in results
                if not self._reliability.should_exclude(
                    r.last_verified_at, "price"
                )
            ]

        for r in results:
            self.composite_score(r, qty)

        return sorted(results, key=lambda r: r.debug.get("composite", 0), reverse=True)
