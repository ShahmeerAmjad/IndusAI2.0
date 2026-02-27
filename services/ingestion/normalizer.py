"""Stage 2: LLM-Powered Normalization.

Uses part number parsers for category detection and spec extraction.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NormalizedProduct:
    """A product that has been parsed and normalized."""
    sku: str
    name: str
    description: str = ""
    category: str = ""
    manufacturer: str = ""
    unit_price: float | None = None
    uom: str = "EA"
    specs: dict[str, Any] = field(default_factory=dict)
    raw_data: dict = field(default_factory=dict)
    confidence: float = 0.0


class CatalogNormalizer:
    """Normalize raw product data using part parsers and LLM."""

    def __init__(self, part_parser, llm_router=None):
        self._parser = part_parser
        self._llm = llm_router

    async def normalize(self, raw_products: list[dict]) -> list[NormalizedProduct]:
        """Normalize a batch of raw product dicts."""
        results = []
        for raw in raw_products:
            normalized = self._normalize_single(raw)
            if normalized:
                results.append(normalized)

        logger.info("Normalized %d / %d products", len(results), len(raw_products))
        return results

    def _normalize_single(self, raw: dict) -> NormalizedProduct | None:
        """Normalize a single raw product dict."""
        sku = (raw.get("part_number") or raw.get("sku") or "").strip()
        if not sku:
            return None

        name = (raw.get("name") or raw.get("description") or sku).strip()
        description = (raw.get("description") or raw.get("long_description") or "").strip()
        manufacturer = (raw.get("manufacturer") or raw.get("brand") or "").strip()
        category = (raw.get("category") or "").strip()

        # Use part parser for category detection and spec enrichment
        parsed = self._parser.parse_single(sku)
        if parsed.confidence > 0.5:
            if not category:
                category = self._category_from_part_type(parsed.category.value)
            specs = parsed.parsed.copy()
        else:
            specs = {}

        # Merge in any raw specifications
        raw_specs = raw.get("specifications") or raw.get("specs") or {}
        if isinstance(raw_specs, dict):
            specs.update(raw_specs)

        # Price
        price = raw.get("unit_price")
        if isinstance(price, str):
            try:
                price = float(price.replace("$", "").replace(",", "").strip())
            except ValueError:
                price = None

        return NormalizedProduct(
            sku=sku,
            name=name,
            description=description,
            category=category,
            manufacturer=manufacturer,
            unit_price=price,
            uom=raw.get("uom", "EA") or "EA",
            specs=specs,
            raw_data=raw,
            confidence=max(parsed.confidence, 0.5),
        )

    @staticmethod
    def _category_from_part_type(part_type: str) -> str:
        """Map parsed part category to graph taxonomy category."""
        mapping = {
            "bearing": "Ball Bearings",
            "metric_fastener": "Bolts",
            "imperial_fastener": "Bolts",
            "belt": "V-Belts",
        }
        return mapping.get(part_type, "")
