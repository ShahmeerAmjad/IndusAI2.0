"""Stage 1: Parse & Extract — handles CSV, PDF, and web scraping.

Ported from v1: app/services/scraper_service.py
"""

import csv
import io
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# LLM extraction prompt for unstructured content (web/PDF)
EXTRACTION_PROMPT = """You are a product data extraction engine. Given text from a supplier catalog, extract ALL products as a JSON array.

Each product must have these fields (use null if not found):
- part_number: string (required - the SKU, model number, or part identifier)
- description: string (required - product name and description)
- category: string (e.g. "bearing", "fastener", "belt", "seal", "coupling", "electrical", "motor")
- unit_price: number or null (price per unit, strip currency symbols)
- brand: string or null
- specifications: object (key-value pairs of technical specs)
- stock_status: string or null ("in_stock", "out_of_stock", "on_order", or null)

Rules:
- Extract EVERY product you can identify, even if some fields are missing
- Return ONLY the JSON array, no other text
- If no products found, return []

CONTENT:
{content}"""

# Common column name mappings for CSV import
COLUMN_ALIASES = {
    "sku": ["sku", "part_number", "part_no", "item_number", "item_no", "pn", "model", "catalog_number", "cat_no"],
    "name": ["name", "description", "product_name", "title", "item_description", "desc"],
    "category": ["category", "cat", "type", "product_type", "class", "group"],
    "manufacturer": ["manufacturer", "brand", "mfg", "mfr", "vendor", "make"],
    "price": ["price", "unit_price", "list_price", "cost", "msrp", "each"],
    "uom": ["uom", "unit", "unit_of_measure", "sell_unit"],
    "description": ["description", "long_description", "details", "notes", "full_description"],
}


class CatalogParser:
    """Parse product data from various file formats."""

    def __init__(self, llm_router=None):
        self._llm = llm_router

    async def parse_csv(self, file_bytes: bytes, encoding: str = "utf-8") -> list[dict]:
        """Parse a CSV/TSV file into normalized product dicts."""
        text = file_bytes.decode(encoding, errors="replace")

        # Detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(text[:2048])
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            return []

        # Build column mapping
        col_map = self._map_columns(reader.fieldnames)
        logger.info("CSV column mapping: %s", col_map)

        products = []
        for row in reader:
            product = self._normalize_row(row, col_map)
            if product.get("part_number"):
                products.append(product)

        logger.info("Parsed %d products from CSV", len(products))
        return products

    async def parse_pdf(self, file_bytes: bytes) -> list[dict]:
        """Extract products from a PDF catalog using pdfplumber + LLM."""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required for PDF parsing: pip install pdfplumber")

        all_text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

                # Also extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            all_text.append(" | ".join(str(cell or "") for cell in row))

        if not all_text:
            return []

        full_text = "\n".join(all_text)

        # Use LLM for extraction if available
        if self._llm:
            return await self._extract_with_llm(full_text)

        logger.warning("No LLM available for PDF extraction — returning raw text chunks")
        return [{"raw_text": full_text, "source": "pdf"}]

    async def scrape_url(self, url: str, max_pages: int = 5) -> list[dict]:
        """Scrape products from a URL using LLM extraction."""
        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("httpx and beautifulsoup4 are required for web scraping")

        if not self._llm:
            raise RuntimeError("LLM router required for web scraping")

        products = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for page_num in range(max_pages):
                page_url = url if page_num == 0 else f"{url}?page={page_num + 1}"
                try:
                    resp = await client.get(page_url)
                    resp.raise_for_status()
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", page_url, e)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove scripts, styles, nav
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                clean_text = soup.get_text(separator="\n", strip=True)
                if not clean_text.strip():
                    break

                page_products = await self._extract_with_llm(clean_text[:8000])
                products.extend(page_products)

                if len(page_products) == 0:
                    break  # No more products found

        logger.info("Scraped %d products from %s (%d pages)", len(products), url, max_pages)
        return products

    async def _extract_with_llm(self, content: str) -> list[dict]:
        """Use LLM to extract product data from unstructured text."""
        prompt = EXTRACTION_PROMPT.format(content=content[:6000])

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                task="catalog_normalization",
                max_tokens=4096,
                temperature=0.1,
            )

            # Parse JSON from response
            # Handle case where LLM wraps in markdown code block
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]

            products = json.loads(text)
            if isinstance(products, list):
                return products
            return []

        except (json.JSONDecodeError, Exception) as e:
            logger.error("LLM extraction failed: %s", e)
            return []

    def _map_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Map CSV column names to standard field names."""
        col_map = {}
        normalized = {f.strip().lower().replace(" ", "_"): f for f in fieldnames}

        for standard_name, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in normalized:
                    col_map[standard_name] = normalized[alias]
                    break

        return col_map

    def _normalize_row(self, row: dict, col_map: dict) -> dict[str, Any]:
        """Normalize a CSV row using the column mapping."""
        product = {}

        product["part_number"] = self._get_value(row, col_map, "sku")
        product["name"] = self._get_value(row, col_map, "name")
        product["category"] = self._get_value(row, col_map, "category")
        product["manufacturer"] = self._get_value(row, col_map, "manufacturer")
        product["description"] = self._get_value(row, col_map, "description")
        product["uom"] = self._get_value(row, col_map, "uom")

        price_str = self._get_value(row, col_map, "price")
        if price_str:
            try:
                product["unit_price"] = float(price_str.replace("$", "").replace(",", "").strip())
            except (ValueError, AttributeError):
                product["unit_price"] = None

        # Collect remaining columns as specs
        mapped_cols = set(col_map.values())
        specs = {}
        for col, value in row.items():
            if col not in mapped_cols and value and str(value).strip():
                specs[col.strip().lower().replace(" ", "_")] = str(value).strip()
        if specs:
            product["specifications"] = specs

        return product

    @staticmethod
    def _get_value(row: dict, col_map: dict, field: str) -> str:
        """Get a value from a row using the column mapping."""
        col = col_map.get(field)
        if col and col in row:
            val = row[col]
            return str(val).strip() if val else ""
        return ""
