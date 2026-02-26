"""Web scraper for distributor catalog sites.

Uses Firecrawl API as primary (clean markdown, JS rendering, anti-bot)
with BeautifulSoup as fallback when no API key is configured.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"

SCRAPE_EXTRACTION_PROMPT = """Extract product data from this distributor catalog page.
Return a JSON array of products. Each product should have:
- sku: part/SKU number
- name: product name
- price: unit price as a number (null if not found)
- manufacturer: manufacturer name (null if not found)
- description: short description
- specs: dict of specifications (e.g., {{"bore_mm": 20, "od_mm": 47}})
- qty_available: stock quantity if shown (null if not found)

Only extract REAL products. Skip navigation, headers, ads.
Return ONLY valid JSON array, no markdown.

Page content:
{content}"""


@dataclass
class ScrapedProduct:
    sku: str
    name: str
    price: float | None = None
    manufacturer: str = ""
    description: str = ""
    category: str = ""
    specs: dict = field(default_factory=dict)
    qty_available: int | None = None
    seller_name: str = ""
    source_url: str = ""
    reliability: float = 7.0
    source_type: str = "web_scrape"
    currency: str = "USD"


class WebScraper:
    """Scrape distributor websites and extract structured product data.

    Prefers Firecrawl API when api key is provided — returns clean markdown,
    handles JS rendering and anti-bot. Falls back to BeautifulSoup otherwise.
    """

    def __init__(self, llm_router=None, firecrawl_api_key: str | None = None):
        self._llm = llm_router
        self._firecrawl_key = firecrawl_api_key

    @property
    def _use_firecrawl(self) -> bool:
        return bool(self._firecrawl_key)

    async def scrape(self, url: str, seller_name: str,
                     max_pages: int = 5) -> list[ScrapedProduct]:
        """Scrape a URL and return structured products."""
        if self._use_firecrawl:
            return await self._scrape_firecrawl(url, seller_name, max_pages)
        return await self._scrape_bs4(url, seller_name, max_pages)

    # ------------------------------------------------------------------
    # Firecrawl path (primary)
    # ------------------------------------------------------------------

    async def _scrape_firecrawl(self, url: str, seller_name: str,
                                max_pages: int = 5) -> list[ScrapedProduct]:
        """Scrape using Firecrawl API — returns clean markdown for LLM."""
        all_products = []
        pages_scraped = 0
        current_url = url

        async with httpx.AsyncClient(timeout=60.0) as client:
            while current_url and pages_scraped < max_pages:
                try:
                    resp = await client.post(
                        FIRECRAWL_API_URL,
                        headers={
                            "Authorization": f"Bearer {self._firecrawl_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "url": current_url,
                            "formats": ["markdown"],
                        },
                    )

                    if resp.status_code != 200:
                        logger.warning(
                            "Firecrawl failed %s: HTTP %d — %s",
                            current_url, resp.status_code, resp.text[:200],
                        )
                        # Fall back to BS4 for this URL
                        fallback = await self._scrape_bs4_single(current_url, seller_name)
                        all_products.extend(fallback)
                        break

                    data = resp.json().get("data", {})
                    markdown = data.get("markdown", "")

                    if not markdown:
                        logger.warning("Firecrawl returned empty markdown for %s", current_url)
                        break

                    # Truncate for LLM context window
                    content = markdown[:12000]
                    products = await self._extract_products(content, current_url, seller_name)
                    all_products.extend(products)
                    pages_scraped += 1

                    logger.info(
                        "Firecrawl scraped page %d of %s: %d products",
                        pages_scraped, seller_name, len(products),
                    )

                    # Firecrawl doesn't return next page links directly,
                    # so we look for them in the markdown
                    current_url = self._find_next_page_in_markdown(markdown, current_url)

                except httpx.TimeoutException:
                    logger.warning("Firecrawl timeout for %s", current_url)
                    break
                except Exception as e:
                    logger.error("Firecrawl error for %s: %s", current_url, e)
                    break

        return all_products

    def _find_next_page_in_markdown(self, markdown: str, current_url: str) -> str | None:
        """Find next page link in markdown content."""
        # Look for markdown links like [Next](url) or [Next Page](url)
        for pattern in [
            r'\[(?:next|next page|next >|>>|>)\]\(([^)]+)\)',
            r'\[(?:Next|Next Page|NEXT)\]\(([^)]+)\)',
        ]:
            match = re.search(pattern, markdown, re.IGNORECASE)
            if match:
                href = match.group(1)
                if href.startswith("http"):
                    return href
                return urljoin(current_url, href)
        return None

    # ------------------------------------------------------------------
    # BeautifulSoup path (fallback)
    # ------------------------------------------------------------------

    async def _scrape_bs4(self, url: str, seller_name: str,
                          max_pages: int = 5) -> list[ScrapedProduct]:
        """Scrape using BeautifulSoup — basic HTML parsing fallback."""
        all_products = []

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0,
                headers={"User-Agent": "IndusAI-Catalog-Bot/1.0"}
            ) as client:
                pages_scraped = 0
                current_url = url

                while current_url and pages_scraped < max_pages:
                    resp = await client.get(current_url)
                    if resp.status_code != 200:
                        logger.warning("Scrape failed %s: HTTP %d", current_url, resp.status_code)
                        break

                    products, next_url = await self._extract_page_bs4(
                        resp.text, current_url, seller_name
                    )
                    all_products.extend(products)
                    pages_scraped += 1
                    current_url = next_url

                    logger.info("BS4 scraped page %d of %s: %d products",
                                pages_scraped, seller_name, len(products))

        except Exception as e:
            logger.error("Scrape error for %s: %s", url, e)

        return all_products

    async def _scrape_bs4_single(self, url: str, seller_name: str) -> list[ScrapedProduct]:
        """Scrape a single page with BS4 (used as Firecrawl fallback)."""
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0,
                headers={"User-Agent": "IndusAI-Catalog-Bot/1.0"}
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                products, _ = await self._extract_page_bs4(resp.text, url, seller_name)
                return products
        except Exception as e:
            logger.error("BS4 fallback error for %s: %s", url, e)
            return []

    async def _extract_page_bs4(self, html: str, url: str,
                                seller_name: str) -> tuple[list[ScrapedProduct], str | None]:
        """Extract products from a single HTML page using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = text[:8000]

        products = await self._extract_products(text, url, seller_name)
        next_url = self._find_next_page_bs4(soup, url)

        return products, next_url

    def _find_next_page_bs4(self, soup: BeautifulSoup, current_url: str) -> str | None:
        """Find 'next page' link in HTML."""
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True).lower()
            if text in ("next", "next page", "next >", ">>", ">"):
                href = link["href"]
                if href.startswith("http"):
                    return href
                return urljoin(current_url, href)
        return None

    # ------------------------------------------------------------------
    # Shared LLM extraction
    # ------------------------------------------------------------------

    async def _extract_products(self, content: str, url: str,
                                seller_name: str) -> list[ScrapedProduct]:
        """Use LLM to extract structured products from text/markdown content."""
        if not self._llm:
            return []

        try:
            prompt = SCRAPE_EXTRACTION_PROMPT.format(content=content)
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                task="catalog_extraction",
                max_tokens=4096,
                temperature=0.1,
            )
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                raw_products = json.loads(json_match.group())
                return [
                    ScrapedProduct(
                        sku=str(raw["sku"]).strip(),
                        name=raw.get("name", ""),
                        price=self._safe_float(raw.get("price")),
                        manufacturer=raw.get("manufacturer", ""),
                        description=raw.get("description", ""),
                        specs=raw.get("specs", {}),
                        qty_available=raw.get("qty_available"),
                        seller_name=seller_name,
                        source_url=url,
                    )
                    for raw in raw_products
                    if raw.get("sku")
                ]
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)

        return []

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Extract price from text like '$12.99' or 'USD 1,234.56'."""
        match = re.search(r'[\$]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(",", ""))
        return None

    @staticmethod
    def _safe_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
