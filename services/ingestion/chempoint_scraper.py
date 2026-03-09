"""Chempoint catalog scraper for seeding the knowledge graph.

Uses Firecrawl API to fetch pages and Claude LLM to extract structured
product data (name, manufacturer, CAS#, industries, TDS/SDS links).
"""

import json
import logging
import re
from html import unescape

import httpx

logger = logging.getLogger(__name__)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"

PRODUCT_EXTRACTION_PROMPT = """Extract chemical product data from this Chempoint product page.
Return a JSON array of products. Each product should have:
- name: product trade name
- manufacturer: manufacturer/supplier name
- cas_number: CAS registry number (null if not found)
- description: short product description
- tds_url: URL to Technical Data Sheet PDF (null if not found)
- sds_url: URL to Safety Data Sheet PDF (null if not found)
- industries: list of industry applications (e.g. ["Adhesives", "Coatings"])
- product_line: product line/family name (null if not found)

Only extract REAL products. Return ONLY valid JSON array, no markdown.

Page content:
{content}"""

INDUSTRY_EXTRACTION_PROMPT = """Extract a list of chemical products from this Chempoint industry page.
Return a JSON array. Each item should have:
- name: product trade name
- manufacturer: manufacturer name
- url: link to product detail page (null if not found)

Return ONLY valid JSON array, no markdown.

Page content:
{content}"""


def _clean_name(raw: str) -> str:
    """Strip HTML tags and decode entities from a product name.

    Firecrawl markdown can contain remnants like `<sup>&reg;</sup>` or
    `&amp;` — clean those so the product name is plain text.
    """
    cleaned = re.sub(r'<[^>]+>', '', raw)   # strip HTML tags
    cleaned = unescape(cleaned)              # decode &reg; &amp; etc.
    return cleaned.strip()


class ChempointScraper:
    """Scrape Chempoint catalog pages and extract structured product data."""

    def __init__(self, firecrawl_api_key: str, llm_router=None):
        self._firecrawl_key = firecrawl_api_key
        self._llm = llm_router

    async def scrape_product_page(self, url: str) -> list[dict]:
        """Scrape a single product page and return structured product data."""
        html = await self._fetch_page(url)
        products = await self._extract_with_llm(html, PRODUCT_EXTRACTION_PROMPT)
        return products

    async def scrape_industry_page(self, url: str) -> list[dict]:
        """Scrape an industry listing page for product summaries.

        Uses regex to extract product URLs directly from the markdown
        (the product cards are often past the 12K LLM truncation limit).
        Falls back to LLM extraction if regex finds nothing.
        """
        html = await self._fetch_page(url)

        # Extract product URLs and names directly from markdown
        # Pattern: ## [Product Name](https://www.chempoint.com/products/...)
        products = []
        seen_urls = set()
        seen_names = set()
        for match in re.finditer(
            r'## \[([^\]]+)\]\((https://www\.chempoint\.com/products/[^)]+)\)', html
        ):
            name, product_url = _clean_name(match.group(1)), match.group(2)
            if product_url not in seen_urls and name not in seen_names:
                seen_urls.add(product_url)
                seen_names.add(name)
                products.append({"name": name, "url": product_url})

        if products:
            logger.info("Extracted %d product URLs from %s via regex", len(products), url)
            return products

        # Fallback to LLM extraction
        products = await self._extract_with_llm(html, INDUSTRY_EXTRACTION_PROMPT)
        return products

    async def scrape_product_listing(self, url: str) -> list[dict]:
        """Scrape a product listing page and extract product detail URLs.

        Works for manufacturer product listings (/products/manufacturer-name)
        and product line listings (/products/mfg/line-name).
        Only returns URLs with 4+ path segments (actual product detail pages).
        Stops before "Related" / "You May Also Like" sections to avoid
        pulling in products from other manufacturers.
        """
        html = await self._fetch_page(url)

        # Truncate at "Related Products" / "You May Also Like" sections
        for marker in ("## Related", "## You May Also Like", "## Recommended",
                       "### Related", "### You May Also Like"):
            idx = html.find(marker)
            if idx != -1:
                logger.info("Truncating listing page at '%s' (pos %d)", marker, idx)
                html = html[:idx]

        # Extract the manufacturer slug from the listing URL so we can
        # reject product URLs that belong to a different manufacturer.
        listing_manufacturer = ""
        listing_segments = url.replace("https://www.chempoint.com/products/", "").strip("/").split("/")
        if listing_segments:
            listing_manufacturer = listing_segments[0].lower()

        products = []
        seen_urls = set()
        seen_names = set()
        for match in re.finditer(
            r'\[([^\]]+)\]\((https://www\.chempoint\.com/products/[^)]+)\)', html
        ):
            name, product_url = _clean_name(match.group(1)), match.group(2)
            if name in ("View Details", "SDS", "TDS", "View All Manufacturer Products"):
                continue
            if product_url in seen_urls or name in seen_names:
                continue
            segments = product_url.replace("https://www.chempoint.com/products/", "").strip("/").split("/")
            if len(segments) >= 4:
                # Reject products from a different manufacturer
                if listing_manufacturer and segments[0].lower() != listing_manufacturer:
                    logger.debug("Skipping cross-manufacturer product: %s", product_url)
                    continue
                seen_urls.add(product_url)
                seen_names.add(name)
                products.append({"name": name, "url": product_url})

        if products:
            logger.info("Extracted %d product URLs from listing page %s", len(products), url)
            return products

        # Fallback to LLM
        logger.info("No product URLs found via regex on %s, falling back to LLM", url)
        return await self._extract_with_llm(html, PRODUCT_EXTRACTION_PROMPT)

    async def scrape_manufacturer_page(self, url: str) -> list[dict]:
        """Scrape a manufacturer page and follow 'View All Manufacturer Products'.

        Manufacturer pages list product *lines*, not actual products.
        This method finds the all-products listing URL, fetches it, and
        extracts individual product detail URLs (4+ path segments).
        Falls back to LLM extraction if regex finds nothing.
        """
        html = await self._fetch_page(url)

        # Look for "View All Manufacturer Products" link
        all_products_match = re.search(
            r'\[View All Manufacturer Products\]\((https://www\.chempoint\.com/products/[^)]+)\)',
            html,
        )
        if all_products_match:
            all_products_url = all_products_match.group(1)
            logger.info("Following 'View All Manufacturer Products' → %s", all_products_url)
            html = await self._fetch_page(all_products_url)

        # Truncate at "Related Products" / "You May Also Like" sections
        for marker in ("## Related", "## You May Also Like", "## Recommended",
                       "### Related", "### You May Also Like"):
            idx = html.find(marker)
            if idx != -1:
                logger.info("Truncating manufacturer page at '%s' (pos %d)", marker, idx)
                html = html[:idx]

        # Extract manufacturer slug from URL for cross-manufacturer filtering
        mfg_slug = ""
        if "/manufacturers/" in url:
            mfg_slug = url.split("/manufacturers/")[-1].strip("/").split("/")[0].lower()

        # Extract product detail URLs (4+ path segments = actual products)
        products = []
        seen_urls = set()
        seen_names = set()
        for match in re.finditer(
            r'\[([^\]]+)\]\((https://www\.chempoint\.com/products/[^)]+)\)', html
        ):
            name, product_url = _clean_name(match.group(1)), match.group(2)
            # Skip generic labels and duplicate URLs
            if name in ("View Details", "SDS", "TDS", "View All Manufacturer Products"):
                continue
            if product_url in seen_urls or name in seen_names:
                continue
            # Only include URLs with 4+ segments (manufacturer/line/subline/product)
            segments = product_url.replace("https://www.chempoint.com/products/", "").strip("/").split("/")
            if len(segments) >= 4:
                # Reject cross-manufacturer products (from "Related" sections we missed)
                if mfg_slug and segments[0].lower() != mfg_slug:
                    logger.debug("Skipping cross-manufacturer product: %s", product_url)
                    continue
                seen_urls.add(product_url)
                seen_names.add(name)
                products.append({"name": name, "url": product_url})

        if products:
            logger.info("Extracted %d product URLs from manufacturer page via regex", len(products))
            return products

        # Fallback to LLM extraction
        logger.info("No product URLs found via regex, falling back to LLM")
        return await self._extract_with_llm(html, PRODUCT_EXTRACTION_PROMPT)

    async def download_document(self, url: str) -> bytes:
        """Download a TDS/SDS PDF file.

        Tries direct download first; falls back to Firecrawl if blocked (403)
        or on timeout.
        """
        try:
            return await self._download_file(url)
        except httpx.TimeoutException:
            logger.info("Direct download timed out for %s — trying Firecrawl", url)
            return await self._download_via_firecrawl(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                logger.info("Direct download 403 for %s — trying Firecrawl", url)
                return await self._download_via_firecrawl(url)
            raise

    async def fetch_document_text(self, url: str) -> str:
        """Fetch document text via Firecrawl (useful for PDFs behind auth walls).

        Returns the markdown text extracted by Firecrawl, which can be passed
        directly to the LLM for field extraction — no pdfplumber needed.
        """
        return await self._fetch_page(url)

    async def crawl_full_catalog(self, base_url: str, max_pages: int = 50) -> list[dict]:
        """Orchestrate a full catalog crawl starting from a base URL."""
        all_products = []
        visited = set()
        to_visit = [base_url]

        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                products = await self.scrape_product_page(url)
                all_products.extend(products)
                logger.info("Crawled %s: %d products", url, len(products))
            except Exception as e:
                logger.warning("Failed to crawl %s: %s", url, e)

        return all_products

    async def _fetch_page(self, url: str) -> str:
        """Fetch page content via Firecrawl API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                FIRECRAWL_API_URL,
                headers={
                    "Authorization": f"Bearer {self._firecrawl_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "formats": ["markdown"]},
            )
            if resp.status_code != 200:
                logger.warning("Firecrawl failed %s: HTTP %d", url, resp.status_code)
                return ""
            data = resp.json().get("data", {})
            return data.get("markdown", "")

    async def _extract_with_llm(self, content: str, prompt_template: str) -> list[dict]:
        """Use LLM to extract structured data from page content."""
        if not content:
            return []
        if self._llm is None:
            return []

        content_truncated = content[:12000]
        prompt = prompt_template.format(content=content_truncated)

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                task="chempoint_extraction",
                max_tokens=4096,
                temperature=0.1,
            )
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                products = json.loads(json_match.group())
                for p in products:
                    if "name" in p:
                        p["name"] = _clean_name(p["name"])
                return products
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)

        return []

    async def _download_file(self, url: str) -> bytes:
        """Download a file and return its bytes."""
        timeout = httpx.Timeout(30.0, connect=10.0, read=30.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def _download_via_firecrawl(self, url: str) -> bytes:
        """Fetch a PDF via Firecrawl and return its content as bytes.

        Firecrawl renders the page with a real browser session, bypassing
        403s from sites like Chempoint that block direct downloads.
        Returns markdown text encoded as UTF-8 bytes (not raw PDF binary),
        so downstream code should use extract_text-based paths.
        """
        timeout = httpx.Timeout(90.0, connect=10.0, read=90.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                FIRECRAWL_API_URL,
                headers={
                    "Authorization": f"Bearer {self._firecrawl_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "formats": ["markdown"]},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Firecrawl failed for {url}: HTTP {resp.status_code}")
            data = resp.json().get("data", {})
            markdown = data.get("markdown", "")
            if not markdown:
                raise RuntimeError(f"Firecrawl returned empty content for {url}")
            return markdown.encode("utf-8")
