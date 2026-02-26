"""Reliability scoring engine — scores data freshness and trustworthiness."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SOURCE_SCORES = {
    "manufacturer_datasheet": 10.0,
    "api_feed": 9.0,
    "seller_upload": 8.0,
    "web_scrape": 7.0,
    "manual": 6.0,
    "forum": 4.0,
}

# How many days before data starts decaying
GRACE_PERIODS = {
    "price": 7,
    "spec": 90,
    "availability": 3,
    "default": 7,
}

# How many days until data is excluded from results entirely
EXCLUDE_THRESHOLDS = {
    "price": 30,
    "spec": 365,
    "availability": 14,
    "default": 30,
}


class ReliabilityScorer:
    """Compute reliability scores for knowledge graph data."""

    @staticmethod
    def base_score(source_type: str) -> float:
        return SOURCE_SCORES.get(source_type, 3.0)

    @staticmethod
    def age_decay(last_verified_at: datetime,
                  data_type: str = "default") -> float:
        """Compute age-based decay. Returns points to subtract (0-5)."""
        grace = GRACE_PERIODS.get(data_type, 7)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        past_grace = max(0, age_days - grace)
        # 1 point per 7 days past grace, capped at 5
        return min(past_grace / 7.0, 5.0)

    def compute(self, source_type: str, last_verified_at: datetime,
                cross_validations: int = 0,
                data_type: str = "default") -> float:
        """Compute final reliability score (0-10)."""
        base = self.base_score(source_type)
        decay = self.age_decay(last_verified_at, data_type)
        xval_boost = min(cross_validations * 0.3, 1.5)
        score = base - decay + xval_boost
        return max(0.0, min(10.0, round(score, 1)))

    @staticmethod
    def is_stale(last_verified_at: datetime, data_type: str = "default") -> bool:
        """Check if data is past its exclude threshold."""
        threshold = EXCLUDE_THRESHOLDS.get(data_type, 30)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        return age_days > threshold

    @staticmethod
    def should_exclude(last_verified_at: datetime, data_type: str = "default") -> bool:
        """Alias for is_stale — data too old to show to buyers."""
        threshold = EXCLUDE_THRESHOLDS.get(data_type, 30)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        return age_days > threshold
