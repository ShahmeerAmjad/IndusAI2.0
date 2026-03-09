"""End-to-end pipeline: scrape Chempoint → extract fields → build knowledge graph.

Orchestrates ChempointScraper, DocumentService, and TDSSDSGraphService
to populate the knowledge graph from Chempoint catalog pages.
"""

import json
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
                            cancel_check=None, max_products: int = 0) -> dict:
        """Scrape a Chempoint page and populate the knowledge graph.

        Detects URL type automatically:
        - /manufacturers/* → scrape manufacturer page (follows to all-products listing)
        - /industries/* → scrape industry page (extracts product URLs, then each product)
        - /products/* → scrape single product page
        """
        _emit = on_progress or (lambda e: None)
        _is_cancelled = cancel_check or (lambda: False)

        # Manufacturer pages list product lines, not products — need special handling
        if "/manufacturers/" in url:
            _emit({"stage": "scraping", "detail": f"Detected manufacturer page: {url}"})
            product_summaries = await self._scraper.scrape_manufacturer_page(url)
            return await self._seed_from_product_list(
                product_summaries, on_progress=on_progress, cancel_check=cancel_check,
                max_products_remaining=max_products,
            )

        # Industry sub-pages list products with URLs
        if "/industries/" in url:
            _emit({"stage": "scraping", "detail": f"Detected industry page: {url}"})
            return await self.seed_from_industry(url, on_progress=on_progress,
                                                  cancel_check=cancel_check,
                                                  max_products_remaining=max_products)

        # Product listing pages (1-3 path segments) are not single product pages —
        # they list many products. Extract product URLs and recurse into each.
        # e.g. /products/mitsubishi-chemical-america (1 seg)
        #      /products/dow/dow-paraloid-impact-modifiers (2 segs)
        #      /products/dow/dow-paraloid-impact-modifiers/paraloid-bta (3 segs)
        # vs. /products/dow/dow-paraloid/paraloid-bta/paraloid-bta-730 (4 segs = detail)
        if "/products/" in url:
            segments = url.split("/products/")[-1].strip("/").split("/")
            if len(segments) < 4:
                _emit({"stage": "scraping", "detail": f"Detected product listing page: {url}"})
                product_summaries = await self._scraper.scrape_product_listing(url)
                return await self._seed_from_product_list(
                    product_summaries, on_progress=on_progress, cancel_check=cancel_check,
                    max_products_remaining=max_products,
                )

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

    async def _seed_from_product_list(self, product_summaries: list[dict],
                                      on_progress=None,
                                      max_products_remaining: int = 0,
                                      cancel_check=None) -> dict:
        """Process a list of {name, url} product summaries by seeding each URL."""
        _emit = on_progress or (lambda e: None)
        _is_cancelled = cancel_check or (lambda: False)
        stats = {"products_created": 0, "products_updated": 0, "tds_stored": 0,
                 "sds_stored": 0, "industries_linked": 0, "errors": 0}

        for summary in product_summaries:
            if _is_cancelled():
                break
            if max_products_remaining and stats["products_created"] >= max_products_remaining:
                break
            product_url = summary.get("url")
            if not product_url:
                continue
            _emit({"stage": "discovering", "detail": f"Following product: {summary.get('name', product_url)}"})
            try:
                # Recurse — product URLs go through scrape_product_page path
                sub_stats = await self.seed_from_url(
                    product_url, on_progress=on_progress, cancel_check=cancel_check,
                )
                for k in stats:
                    stats[k] += sub_stats.get(k, 0)
            except Exception as e:
                logger.error("Failed to seed product %s: %s", product_url, e)
                stats["errors"] += 1
                _emit({"stage": "error", "product": summary.get("name", ""), "detail": str(e)})

        return stats

    async def seed_from_industry(self, url: str, on_progress=None,
                                  max_products_remaining: int = 0,
                                  cancel_check=None) -> dict:
        """Scrape an industry page then process each product."""
        product_summaries = await self._scraper.scrape_industry_page(url)
        return await self._seed_from_product_list(
            product_summaries, on_progress=on_progress,
            max_products_remaining=max_products_remaining,
            cancel_check=cancel_check,
        )

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

        product_id = row["id"]  # UUID from PG — keep as-is for FK inserts
        # xmax = 0 means INSERT, > 0 means UPDATE
        if row.get("xmax", 0) == 0:
            stats["products_created"] += 1
        else:
            stats["products_updated"] += 1

        # Ensure Part node exists in Neo4j (graph operations need it)
        await self._graph.ensure_part(
            sku=sku, name=name, manufacturer=manufacturer,
            description=product_data.get("description", ""),
        )

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
        """Download a TDS/SDS PDF, extract text and fields, create graph node.

        Uses scraper.download_document (which falls back to Firecrawl on 403).
        If pdfplumber can't parse the result (e.g. Firecrawl returned markdown
        bytes), falls back to Firecrawl text extraction directly.
        """
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
                   "detail": f"Extracting {doc_type} fields"})

            # Try pdfplumber first; if it fails (e.g. content is Firecrawl
            # markdown, not a real PDF), decode the bytes as text.
            try:
                text = await self._doc.extract_text_from_pdf(file_bytes)
            except Exception:
                logger.info("pdfplumber failed for %s — treating content as text", sku)
                text = file_bytes.decode("utf-8", errors="replace")

            if not text:
                # Last resort: fetch text via Firecrawl directly
                text = await self._scraper.fetch_document_text(doc_url)

            if not text:
                logger.warning("No text extracted for %s %s", doc_type, doc_url)
                stats["errors"] = stats.get("errors", 0) + 1
                return

            if doc_type == "TDS":
                raw_fields = await self._doc.extract_tds_fields_with_confidence(text)
            else:
                raw_fields = await self._doc.extract_sds_fields_with_confidence(text)

            # Flatten for graph: unwrap confidence wrappers, serialize
            # complex values (Neo4j only stores primitives and arrays of
            # primitives).
            flat_fields = {}
            for k, v in raw_fields.items():
                if isinstance(v, dict) and "value" in v:
                    v = v["value"]
                if v is None:
                    continue
                # Neo4j can't store dicts or lists-of-dicts — serialize to JSON
                if isinstance(v, dict):
                    flat_fields[k] = json.dumps(v)
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    flat_fields[k] = json.dumps(v)
                else:
                    flat_fields[k] = v
            flat_fields["pdf_url"] = doc_url
            # Ensure revision_date has a value (required by MERGE key)
            flat_fields.setdefault("revision_date", "unknown")

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
