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
    def __init__(self, scraper, doc_service, graph_service, db_manager, llm_router=None):
        self._scraper = scraper
        self._doc = doc_service
        self._graph = graph_service
        self._db = db_manager
        self._llm = llm_router

    async def seed_from_url(self, url: str, on_progress=None,
                            cancel_check=None) -> dict:
        """Scrape a Chempoint product page and populate the knowledge graph."""
        _emit = on_progress or (lambda e: None)
        _is_cancelled = cancel_check or (lambda: False)
        _emit({"stage": "scraping", "detail": f"Fetching {url}"})

        products = await self._scraper.scrape_product_page(url)
        total = len(products)

        stats = {
            "products_created": 0,
            "products_updated": 0,
            "tds_stored": 0,
            "sds_stored": 0,
            "industries_linked": 0,
            "errors": 0,
        }

        for i, product_data in enumerate(products):
            if _is_cancelled():
                _emit({"stage": "cancelled", "detail": f"Cancelled after {i} products"})
                break
            name = product_data.get("name", "unknown")
            try:
                _emit({"stage": "processing", "product": name,
                       "current": i + 1, "total": total})
                await self._process_product(product_data, stats, _emit)
            except Exception as e:
                logger.error("Failed to process product %s: %s", name, e)
                stats["errors"] += 1
                _emit({"stage": "error", "product": name, "detail": str(e)})

        _emit({"stage": "done", "detail": f"Completed: {stats}"})
        logger.info("Seed pipeline complete: %s", stats)
        return stats

    async def seed_from_industry(self, url: str, on_progress=None,
                                  max_products_remaining: int = 0,
                                  cancel_check=None) -> dict:
        """Scrape an industry page then process each product."""
        product_summaries = await self._scraper.scrape_industry_page(url)
        stats = {"products_created": 0, "products_updated": 0, "tds_stored": 0,
                 "sds_stored": 0, "industries_linked": 0, "errors": 0}

        for summary in product_summaries:
            if max_products_remaining and stats["products_created"] >= max_products_remaining:
                break
            product_url = summary.get("url")
            if product_url:
                sub_stats = await self.seed_from_url(product_url, on_progress=on_progress,
                                                     cancel_check=cancel_check)
                for k in stats:
                    stats[k] += sub_stats.get(k, 0)

        return stats

    async def seed_from_industries(self, industry_urls: list[str],
                                    on_progress=None,
                                    max_products: int = 0,
                                    cancel_check=None) -> dict:
        """Batch scrape multiple industry pages.

        Args:
            max_products: Global cap on products to create. 0 = unlimited.
            cancel_check: Callable returning True if job is cancelled.
        """
        _emit = on_progress or (lambda e: None)
        combined = {"products_created": 0, "products_updated": 0, "tds_stored": 0,
                    "sds_stored": 0, "industries_linked": 0, "errors": 0}

        for idx, url in enumerate(industry_urls):
            if max_products and combined["products_created"] >= max_products:
                _emit({"stage": "capped", "detail": f"Reached max_products={max_products}"})
                break
            _emit({"stage": "discovering", "detail": f"Industry {idx+1}/{len(industry_urls)}: {url}"})
            sub = await self.seed_from_industry(
                url, on_progress=on_progress,
                max_products_remaining=(max_products - combined["products_created"]
                                        if max_products else 0),
                cancel_check=cancel_check,
            )
            for k in combined:
                combined[k] += sub.get(k, 0)

        return combined

    async def _process_product(self, product_data: dict, stats: dict,
                                _emit=None) -> None:
        """Process a single product: create in PG, download docs, build graph."""
        _emit = _emit or (lambda e: None)
        name = product_data.get("name", "").strip()
        if not name:
            raise ValueError("Product has empty name — skipping")
        sku = _make_sku(name)
        manufacturer = product_data.get("manufacturer", "")

        # Upsert product in PostgreSQL
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO products (sku, name, manufacturer, description, is_active)
                   VALUES ($1, $2, $3, $4, TRUE)
                   ON CONFLICT (sku) DO UPDATE SET name = $2, manufacturer = $3
                   RETURNING id, sku, xmax""",
                sku, name, manufacturer, product_data.get("description", ""),
            )

        product_id = str(row["id"])
        # xmax = 0 means INSERT, > 0 means UPDATE
        if row.get("xmax", 0) == 0:
            stats["products_created"] += 1
        else:
            stats["products_updated"] += 1

        # Download and process TDS
        tds_url = product_data.get("tds_url")
        if tds_url:
            await self._process_document(product_id, sku, tds_url, "TDS", stats, _emit)

        # Download and process SDS
        sds_url = product_data.get("sds_url")
        if sds_url:
            await self._process_document(product_id, sku, sds_url, "SDS", stats, _emit)

        # Link to industries
        for industry in product_data.get("industries", []):
            await self._graph.link_product_to_industry(sku, industry)
            stats["industries_linked"] += 1

        # Link to product line
        product_line = product_data.get("product_line")
        if product_line:
            await self._graph.link_product_to_product_line(sku, product_line, manufacturer)

    async def _process_document(self, product_id: str, sku: str,
                                doc_url: str, doc_type: str, stats: dict,
                                _emit=None) -> None:
        """Download a TDS/SDS PDF, extract text and fields, create graph node."""
        _emit = _emit or (lambda e: None)
        try:
            _emit({"stage": "downloading_pdf", "product": sku,
                   "detail": f"{doc_type} from {doc_url}"})
            file_bytes = await self._scraper.download_document(doc_url)
            file_name = doc_url.split("/")[-1] or f"{doc_type.lower()}.pdf"

            await self._doc.store_document(
                product_id=product_id, doc_type=doc_type,
                file_bytes=file_bytes, file_name=file_name,
                source_url=doc_url,
            )

            _emit({"stage": "extracting", "product": sku,
                   "detail": f"OCR + Claude extraction for {doc_type}"})
            text = await self._doc.extract_text_from_pdf(file_bytes)

            if doc_type == "TDS":
                raw_fields = await self._doc.extract_tds_fields_with_confidence(text)
            else:
                raw_fields = await self._doc.extract_sds_fields_with_confidence(text)

            # Flatten for graph (store values only)
            flat_fields = {}
            for k, v in raw_fields.items():
                if isinstance(v, dict) and "value" in v:
                    flat_fields[k] = v["value"]
                else:
                    flat_fields[k] = v
            flat_fields["pdf_url"] = doc_url

            _emit({"stage": "building_graph", "product": sku,
                   "detail": f"{doc_type}: {len(flat_fields)} fields extracted"})

            if doc_type == "TDS":
                await self._graph.create_tds(sku, flat_fields)
                stats["tds_stored"] += 1
            else:
                await self._graph.create_sds(sku, flat_fields)
                stats["sds_stored"] += 1

        except Exception as e:
            logger.warning("Failed to process %s from %s: %s", doc_type, doc_url, e)
            stats["errors"] = stats.get("errors", 0) + 1
