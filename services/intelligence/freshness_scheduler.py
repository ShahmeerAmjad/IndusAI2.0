"""Freshness scheduler — auto re-scrape stale listings, update reliability scores."""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class FreshnessScheduler:
    """Manages scheduled tasks for data freshness:
    - Every 6 hours: check & re-scrape stale seller listings
    - Daily: update reliability scores based on age decay
    - Weekly: full crawl of all registered seller URLs
    """

    def __init__(self, seller_service=None, web_scraper=None,
                 reliability_scorer=None, db_manager=None):
        self._seller = seller_service
        self._scraper = web_scraper
        self._scorer = reliability_scorer
        self._db = db_manager
        self._scheduler = AsyncIOScheduler()

    def start(self):
        """Start the background scheduler."""
        # Every 6 hours: re-scrape stale listings
        self._scheduler.add_job(
            self._rescrape_stale,
            "interval", hours=6,
            id="rescrape_stale",
            name="Re-scrape stale listings",
        )

        # Daily at 3 AM: update reliability scores
        self._scheduler.add_job(
            self._update_reliability_scores,
            "cron", hour=3,
            id="update_reliability",
            name="Update reliability scores",
        )

        # Weekly on Sunday at 2 AM: full crawl
        self._scheduler.add_job(
            self._full_crawl,
            "cron", day_of_week="sun", hour=2,
            id="full_crawl",
            name="Full seller crawl",
        )

        self._scheduler.start()
        logger.info("Freshness scheduler started (3 jobs)")

    def shutdown(self):
        """Gracefully stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Freshness scheduler stopped")

    async def _rescrape_stale(self):
        """Find stale listings and re-scrape their seller sites."""
        if not self._seller:
            return

        try:
            stale = await self._seller.get_stale_listings(limit=50)
            logger.info("Found %d stale listings to refresh", len(stale))

            if not self._scraper or not stale:
                return

            # Group by seller to avoid duplicate scrapes
            sellers_to_scrape = {}
            for listing in stale:
                seller_name = listing.get("seller_name", "")
                website = listing.get("website")
                if website and seller_name not in sellers_to_scrape:
                    sellers_to_scrape[seller_name] = website

            for seller_name, url in sellers_to_scrape.items():
                try:
                    products = await self._scraper.scrape(url, seller_name, max_pages=3)
                    logger.info("Re-scraped %s: %d products", seller_name, len(products))

                    # Upsert the scraped products
                    for product in products:
                        if product.price is not None:
                            await self._seller.upsert_listing({
                                "seller_id": listing.get("seller_id"),
                                "sku": product.sku,
                                "part_sku": product.sku,
                                "price": product.price,
                                "qty_available": product.qty_available or 0,
                                "source_type": "web_scrape",
                                "reliability": product.reliability,
                            })

                except Exception as e:
                    logger.warning("Re-scrape failed for %s: %s", seller_name, e)

        except Exception as e:
            logger.error("Stale listing refresh failed: %s", e)

    async def _update_reliability_scores(self):
        """Recalculate reliability scores for all listings based on age."""
        if not self._db or not self._db.pool or not self._scorer:
            return

        try:
            async with self._db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT id, source_type, last_verified_at, reliability
                       FROM seller_listings
                       WHERE last_verified_at IS NOT NULL"""
                )

                updated = 0
                for row in rows:
                    new_score = self._scorer.compute(
                        source_type=row["source_type"] or "manual",
                        last_verified_at=row["last_verified_at"],
                    )
                    if abs(new_score - float(row["reliability"])) > 0.1:
                        await conn.execute(
                            "UPDATE seller_listings SET reliability = $1 WHERE id = $2",
                            new_score, row["id"],
                        )
                        updated += 1

                logger.info("Updated reliability scores for %d/%d listings",
                            updated, len(rows))

        except Exception as e:
            logger.error("Reliability score update failed: %s", e)

    async def _full_crawl(self):
        """Full crawl of all registered seller websites."""
        if not self._db or not self._db.pool or not self._scraper:
            return

        try:
            async with self._db.pool.acquire() as conn:
                sellers = await conn.fetch(
                    """SELECT id, name, website FROM seller_profiles
                       WHERE website IS NOT NULL AND website != ''"""
                )

            logger.info("Starting full crawl of %d sellers", len(sellers))

            for seller in sellers:
                try:
                    products = await self._scraper.scrape(
                        seller["website"], seller["name"], max_pages=5
                    )
                    logger.info("Full crawl %s: %d products",
                                seller["name"], len(products))

                    for product in products:
                        if product.price is not None:
                            await self._seller.upsert_listing({
                                "seller_id": str(seller["id"]),
                                "sku": product.sku,
                                "part_sku": product.sku,
                                "price": product.price,
                                "qty_available": product.qty_available or 0,
                                "source_type": "web_scrape",
                                "reliability": product.reliability,
                            })

                    # Update last_scraped_at
                    async with self._db.pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE seller_profiles SET last_scraped_at = now() WHERE id = $1",
                            seller["id"],
                        )

                except Exception as e:
                    logger.warning("Full crawl failed for %s: %s", seller["name"], e)

        except Exception as e:
            logger.error("Full crawl failed: %s", e)
