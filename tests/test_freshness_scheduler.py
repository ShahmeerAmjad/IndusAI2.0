import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.intelligence.freshness_scheduler import FreshnessScheduler


class TestFreshnessScheduler:
    def test_scheduler_importable(self):
        scheduler = FreshnessScheduler()
        assert scheduler is not None

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """AsyncIOScheduler requires a running event loop."""
        scheduler = FreshnessScheduler()
        scheduler.start()
        assert scheduler._scheduler.running
        # shutdown(wait=False) triggers async cleanup;
        # verify it doesn't raise and jobs are cleared
        scheduler._scheduler.shutdown(wait=False)
        scheduler.shutdown()  # idempotent — should not raise

    @pytest.mark.asyncio
    async def test_rescrape_stale_no_seller(self):
        """No-op when seller_service is None."""
        scheduler = FreshnessScheduler(seller_service=None)
        await scheduler._rescrape_stale()  # Should not raise

    @pytest.mark.asyncio
    async def test_update_reliability_no_db(self):
        """No-op when db_manager is None."""
        scheduler = FreshnessScheduler(db_manager=None)
        await scheduler._update_reliability_scores()  # Should not raise

    @pytest.mark.asyncio
    async def test_rescrape_stale_with_listings(self):
        mock_seller = AsyncMock()
        mock_seller.get_stale_listings.return_value = [
            {"seller_name": "TestCo", "website": "https://test.com",
             "seller_id": "s1", "sku": "A1"},
        ]

        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = []

        scheduler = FreshnessScheduler(
            seller_service=mock_seller,
            web_scraper=mock_scraper,
        )
        await scheduler._rescrape_stale()

        mock_seller.get_stale_listings.assert_called_once()
        mock_scraper.scrape.assert_called_once_with("https://test.com", "TestCo", max_pages=3)
