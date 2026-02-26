"""Web scraper for distributor catalog sites."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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
    """Scrape distributor websites and extract structured product data."""

    def __init__(self, llm_router=None):
        self._llm = llm_router

    async def scrape(self, url: str, seller_name: str,
                     max_pages: int = 5) -> list[ScrapedProduct]:
        """Scrape a URL and return structured products."""
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

                    products, next_url = await self._extract_page(
                        resp.text, current_url, seller_name
                    )
                    all_products.extend(products)
                    pages_scraped += 1
                    current_url = next_url

                    logger.info("Scraped page %d of %s: %d products",
                                pages_scraped, seller_name, len(products))

        except Exception as e:
            logger.error("Scrape error for %s: %s", url, e)

        return all_products

    async def _extract_page(self, html: str, url: str,
                            seller_name: str) -> tuple[list[ScrapedProduct], str | None]:
        """Extract products from a single HTML page."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Truncate for LLM context
        text = text[:8000]

        products = []

        if self._llm:
            try:
                prompt = SCRAPE_EXTRACTION_PROMPT.format(content=text)
                response = await self._llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    task="catalog_extraction",
                    max_tokens=4096,
                    temperature=0.1,
                )
                # Parse JSON from response
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    raw_products = json.loads(json_match.group())
                    for raw in raw_products:
                        if raw.get("sku"):
                            products.append(ScrapedProduct(
                                sku=str(raw["sku"]).strip(),
                                name=raw.get("name", ""),
                                price=self._safe_float(raw.get("price")),
                                manufacturer=raw.get("manufacturer", ""),
                                description=raw.get("description", ""),
                                specs=raw.get("specs", {}),
                                qty_available=raw.get("qty_available"),
                                seller_name=seller_name,
                                source_url=url,
                            ))
            except Exception as e:
                logger.warning("LLM extraction failed: %s", e)

        # Find next page link
        next_url = self._find_next_page(soup, url)

        return products, next_url

    def _find_next_page(self, soup: BeautifulSoup, current_url: str) -> str | None:
        """Find 'next page' link in the HTML."""
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True).lower()
            if text in ("next", "next page", "next >", ">>", ">"):
                href = link["href"]
                if href.startswith("http"):
                    return href
                return urljoin(current_url, href)
        return None

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
