"""Seed demo sellers, warehouses, and listings into PostgreSQL.

5 sellers (Grainger, McMaster-Carr, MSC Industrial, Motion Industries, Global Industrial)
with US warehouse locations and 50+ seller_listings across existing parts.
"""

import logging
import random

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo seller data
# ---------------------------------------------------------------------------

SELLERS = [
    {
        "name": "Grainger",
        "website": "https://www.grainger.com",
        "reliability_base": 9.2,
        "warehouses": [
            {"label": "Grainger Chicago DC", "city": "Chicago", "state": "IL", "lat": 41.8781, "lng": -87.6298},
            {"label": "Grainger Dallas DC", "city": "Dallas", "state": "TX", "lat": 32.7767, "lng": -96.7970},
        ],
    },
    {
        "name": "McMaster-Carr",
        "website": "https://www.mcmaster.com",
        "reliability_base": 9.5,
        "warehouses": [
            {"label": "McMaster Los Angeles DC", "city": "Los Angeles", "state": "CA", "lat": 33.9425, "lng": -118.2551},
            {"label": "McMaster Cleveland DC", "city": "Cleveland", "state": "OH", "lat": 41.4993, "lng": -81.6944},
        ],
    },
    {
        "name": "MSC Industrial",
        "website": "https://www.mscdirect.com",
        "reliability_base": 8.8,
        "warehouses": [
            {"label": "MSC Harrisburg DC", "city": "Harrisburg", "state": "PA", "lat": 40.2732, "lng": -76.8867},
            {"label": "MSC Atlanta DC", "city": "Atlanta", "state": "GA", "lat": 33.7490, "lng": -84.3880},
        ],
    },
    {
        "name": "Motion Industries",
        "website": "https://www.motionindustries.com",
        "reliability_base": 8.5,
        "warehouses": [
            {"label": "Motion Birmingham HQ", "city": "Birmingham", "state": "AL", "lat": 33.5207, "lng": -86.8025},
            {"label": "Motion Houston DC", "city": "Houston", "state": "TX", "lat": 29.7604, "lng": -95.3698},
        ],
    },
    {
        "name": "Global Industrial",
        "website": "https://www.globalindustrial.com",
        "reliability_base": 7.8,
        "warehouses": [
            {"label": "Global Buford DC", "city": "Buford", "state": "GA", "lat": 34.1207, "lng": -83.9910},
        ],
    },
]

# Parts from seed_demo.py — each part gets listings from 2-4 sellers
# (sku, base_price, lead_time_range, stock_range)
PARTS = [
    ("6204-2RS", 8.50, (1, 3), (200, 1000)),
    ("6205-2Z", 9.25, (1, 3), (150, 800)),
    ("6206-2RS", 11.00, (1, 4), (100, 600)),
    ("22210-E1-K", 45.00, (2, 7), (20, 150)),
    ("7205-BEP", 22.50, (2, 5), (50, 300)),
    ("6204DDU", 7.80, (1, 4), (200, 900)),
    ("6205ZZ", 8.90, (1, 3), (150, 700)),
    ("6206DDU", 10.50, (1, 4), (100, 500)),
    ("FAG-6204-2RSR", 9.00, (2, 5), (80, 400)),
    ("SET401", 38.00, (3, 7), (30, 200)),
    ("LM48548/LM48510", 15.00, (2, 5), (50, 300)),
    ("M8X1.25X30-8.8-ZP", 0.35, (1, 2), (5000, 20000)),
    ("M10X1.5X50-10.9-BLK", 0.55, (1, 2), (3000, 15000)),
    ("M12X1.75X80-12.9", 1.20, (1, 3), (1000, 8000)),
    ("1/2-13X2-GR5-ZP", 0.42, (1, 2), (5000, 20000)),
    ("3/8-16X1.5-GR8-ZP", 0.28, (1, 2), (8000, 25000)),
    ("FW-M8-ZP", 0.05, (1, 1), (10000, 50000)),
    ("NUT-M8-8-ZP", 0.08, (1, 1), (10000, 50000)),
    ("A68", 12.50, (1, 3), (100, 500)),
    ("B75", 15.00, (1, 3), (80, 400)),
    ("3VX500", 18.00, (2, 5), (40, 200)),
    ("HTD-5M-450-15", 22.00, (2, 5), (30, 150)),
    ("CR-20X35X7-HMS5-RG", 6.50, (1, 3), (200, 800)),
    ("LGMT2-1", 14.00, (1, 2), (100, 500)),
    ("PL-205", 28.00, (2, 5), (40, 250)),
]


async def seed_sellers(db_manager, logger_override=None):
    """Seed seller profiles, warehouses, and listings.

    Idempotent — skips if sellers already exist.
    """
    log = logger_override or logger

    if not db_manager.pool:
        log.warning("No database pool — skipping seller seed")
        return

    async with db_manager.pool.acquire() as conn:
        # Check if already seeded
        count = await conn.fetchval("SELECT count(*) FROM seller_profiles")
        if count > 0:
            log.info("Sellers already seeded (%d profiles), skipping", count)
            return

        # We need an org for the sellers — use a system org
        org_id = await conn.fetchval(
            """INSERT INTO organizations (name, slug, plan)
               VALUES ('System', 'system', 'enterprise')
               ON CONFLICT (slug) DO UPDATE SET name = 'System'
               RETURNING id"""
        )

        random.seed(42)  # Reproducible demo data

        total_listings = 0

        for seller_data in SELLERS:
            # Create seller profile
            seller_id = await conn.fetchval(
                """INSERT INTO seller_profiles (org_id, name, website, catalog_source, reliability_base)
                   VALUES ($1, $2, $3, 'seed', $4)
                   RETURNING id""",
                org_id, seller_data["name"], seller_data["website"],
                seller_data["reliability_base"],
            )

            warehouse_ids = []
            for wh in seller_data["warehouses"]:
                # Create location
                loc_id = await conn.fetchval(
                    """INSERT INTO locations (org_id, label, city, state, country, lat, lng)
                       VALUES ($1, $2, $3, $4, 'US', $5, $6)
                       RETURNING id""",
                    org_id, wh["label"], wh["city"], wh["state"],
                    wh["lat"], wh["lng"],
                )
                # Create warehouse
                wh_id = await conn.fetchval(
                    """INSERT INTO seller_warehouses (seller_id, location_id)
                       VALUES ($1, $2)
                       RETURNING id""",
                    seller_id, loc_id,
                )
                warehouse_ids.append(wh_id)

            # Create listings — each seller gets 60-100% of parts
            num_parts = random.randint(
                int(len(PARTS) * 0.6), len(PARTS)
            )
            selected_parts = random.sample(PARTS, num_parts)

            for sku, base_price, lead_range, stock_range in selected_parts:
                # Price varies ±15% between sellers
                price_factor = random.uniform(0.85, 1.15)
                price = round(base_price * price_factor, 2)
                lead_time = random.randint(*lead_range)
                stock = random.randint(*stock_range)
                reliability = round(
                    seller_data["reliability_base"] + random.uniform(-0.5, 0.5), 1
                )
                reliability = max(1.0, min(10.0, reliability))

                # Pick a random warehouse for this listing
                wh_id = random.choice(warehouse_ids)

                await conn.execute(
                    """INSERT INTO seller_listings
                       (seller_id, sku, part_sku, price, qty_available,
                        warehouse_id, lead_time_days, reliability, source_type)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'seed')
                       ON CONFLICT (seller_id, sku, warehouse_id) DO NOTHING""",
                    seller_id, sku, sku, price, stock,
                    wh_id, lead_time, reliability,
                )
                total_listings += 1

        log.info(
            "Seller seed complete: %d sellers, %d listings",
            len(SELLERS), total_listings,
        )
