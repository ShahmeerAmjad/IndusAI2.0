"""End-to-end pipeline: scrape Chempoint → extract fields → build knowledge graph.

Orchestrates ChempointScraper, DocumentService, and TDSSDSGraphService
to populate the knowledge graph from Chempoint catalog pages.
"""

import logging
import re

logger = logging.getLogger(__name__)


def _make_sku(name: str) -> str:
    """Generate a SKU from product name (e.g. 'POLYOX WSR-301' → 'POLYOX-WSR-301')."""
    return re.sub(r'[^A-Za-z0-9]+', '-', name.strip()).strip('-').upper()


class ChempointSeedPipeline:
    def __init__(self, scraper, doc_service, graph_service, db_manager):
        self._scraper = scraper
        self._doc = doc_service
        self._graph = graph_service
        self._db = db_manager

    async def seed_from_url(self, url: str) -> dict:
        """Scrape a Chempoint product page and populate the knowledge graph."""
        products = await self._scraper.scrape_product_page(url)

        stats = {
            "products_created": 0,
            "tds_stored": 0,
            "sds_stored": 0,
            "industries_linked": 0,
        }

        for product_data in products:
            try:
                await self._process_product(product_data, stats)
            except Exception as e:
                logger.error("Failed to process product %s: %s",
                             product_data.get("name"), e)

        logger.info("Seed pipeline complete: %s", stats)
        return stats

    async def seed_from_industry(self, url: str) -> dict:
        """Scrape an industry page then process each product."""
        product_summaries = await self._scraper.scrape_industry_page(url)
        stats = {"products_created": 0, "tds_stored": 0, "sds_stored": 0, "industries_linked": 0}

        for summary in product_summaries:
            product_url = summary.get("url")
            if product_url:
                sub_stats = await self.seed_from_url(product_url)
                for k in stats:
                    stats[k] += sub_stats.get(k, 0)

        return stats

    async def _process_product(self, product_data: dict, stats: dict) -> None:
        """Process a single product: create in PG, download docs, build graph."""
        name = product_data.get("name", "")
        sku = _make_sku(name)
        manufacturer = product_data.get("manufacturer", "")

        # Upsert product in PostgreSQL
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO products (sku, name, manufacturer, description, is_active)
                   VALUES ($1, $2, $3, $4, TRUE)
                   ON CONFLICT (sku) DO UPDATE SET name = $2, manufacturer = $3
                   RETURNING id, sku""",
                sku, name, manufacturer, product_data.get("description", ""),
            )

        product_id = str(row["id"])
        stats["products_created"] += 1

        # Download and process TDS
        tds_url = product_data.get("tds_url")
        if tds_url:
            await self._process_document(product_id, sku, tds_url, "TDS", stats)

        # Download and process SDS
        sds_url = product_data.get("sds_url")
        if sds_url:
            await self._process_document(product_id, sku, sds_url, "SDS", stats)

        # Link to industries
        for industry in product_data.get("industries", []):
            await self._graph.link_product_to_industry(sku, industry)
            stats["industries_linked"] += 1

        # Link to product line
        product_line = product_data.get("product_line")
        if product_line:
            await self._graph.link_product_to_product_line(sku, product_line, manufacturer)

    async def _process_document(self, product_id: str, sku: str,
                                doc_url: str, doc_type: str, stats: dict) -> None:
        """Download a TDS/SDS PDF, extract text and fields, create graph node."""
        try:
            file_bytes = await self._scraper.download_document(doc_url)
            file_name = doc_url.split("/")[-1] or f"{doc_type.lower()}.pdf"

            await self._doc.store_document(
                product_id=product_id, doc_type=doc_type,
                file_bytes=file_bytes, file_name=file_name,
                source_url=doc_url,
            )

            text = await self._doc.extract_text_from_pdf(file_bytes)

            if doc_type == "TDS":
                fields = await self._doc.extract_tds_fields(text)
                fields["pdf_url"] = doc_url
                await self._graph.create_tds(sku, fields)
                stats["tds_stored"] += 1
            else:
                fields = await self._doc.extract_sds_fields(text)
                fields["pdf_url"] = doc_url
                await self._graph.create_sds(sku, fields)
                stats["sds_stored"] += 1

        except Exception as e:
            logger.warning("Failed to process %s from %s: %s", doc_type, doc_url, e)
