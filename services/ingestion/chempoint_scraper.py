"""Chempoint catalog scraper for seeding the knowledge graph.

Uses Firecrawl API to fetch pages and Claude LLM to extract structured
product data (name, manufacturer, CAS#, industries, TDS/SDS links).
"""

import json
import logging
import re

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
        """Scrape an industry listing page for product summaries."""
        html = await self._fetch_page(url)
        products = await self._extract_with_llm(html, INDUSTRY_EXTRACTION_PROMPT)
        return products

    async def scrape_manufacturer_page(self, url: str) -> list[dict]:
        """Scrape a manufacturer page for their product lines."""
        html = await self._fetch_page(url)
        products = await self._extract_with_llm(html, PRODUCT_EXTRACTION_PROMPT)
        return products

    async def download_document(self, url: str) -> bytes:
        """Download a TDS/SDS PDF file."""
        return await self._download_file(url)

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
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)

        return []

    async def _download_file(self, url: str) -> bytes:
        """Download a file and return its bytes."""
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
