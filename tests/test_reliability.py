import pytest
from datetime import datetime, timezone, timedelta
from services.intelligence.reliability import ReliabilityScorer


class TestReliabilityScorer:
    def setup_method(self):
        self.scorer = ReliabilityScorer()

    def test_base_score_by_source(self):
        assert self.scorer.base_score("manufacturer_datasheet") == 10.0
        assert self.scorer.base_score("api_feed") == 9.0
        assert self.scorer.base_score("web_scrape") == 7.0
        assert self.scorer.base_score("manual") == 6.0
        assert self.scorer.base_score("forum") == 4.0
        assert self.scorer.base_score("unknown") == 3.0

    def test_age_decay_fresh(self):
        verified = datetime.now(timezone.utc) - timedelta(days=1)
        decay = self.scorer.age_decay(verified)
        assert decay == 0.0  # within 7 days = no decay

    def test_age_decay_stale(self):
        verified = datetime.now(timezone.utc) - timedelta(days=21)
        decay = self.scorer.age_decay(verified)
        assert decay == 2.0  # 14 days past grace = 2 points

    def test_age_decay_very_old(self):
        verified = datetime.now(timezone.utc) - timedelta(days=60)
        decay = self.scorer.age_decay(verified)
        assert decay >= 5.0  # capped

    def test_compute_score(self):
        score = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=2),
            cross_validations=0,
        )
        assert 6.5 <= score <= 7.5

    def test_cross_validation_boost(self):
        base = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc),
            cross_validations=0,
        )
        boosted = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc),
            cross_validations=3,
        )
        assert boosted > base

    def test_is_stale(self):
        assert not self.scorer.is_stale(
            datetime.now(timezone.utc) - timedelta(days=5), "price"
        )
        assert self.scorer.is_stale(
            datetime.now(timezone.utc) - timedelta(days=35), "price"
        )

    def test_should_exclude(self):
        assert not self.scorer.should_exclude(
            datetime.now(timezone.utc) - timedelta(days=5), "price"
        )
        assert self.scorer.should_exclude(
            datetime.now(timezone.utc) - timedelta(days=35), "price"
        )
