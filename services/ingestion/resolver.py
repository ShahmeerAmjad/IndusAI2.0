"""Stage 3: Entity Resolution & Deduplication.

Matches incoming products against existing graph nodes.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from services.ingestion.normalizer import NormalizedProduct

logger = logging.getLogger(__name__)

try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


@dataclass
class ResolvedProduct:
    """A product with resolution status against the graph."""
    product: NormalizedProduct
    status: str  # "new", "matched", "needs_review"
    matched_sku: str | None = None
    match_confidence: float = 0.0
    match_source: str = ""  # "exact_sku", "fuzzy_name", "cross_ref"


@dataclass
class ResolutionResult:
    """Results of resolving a batch of products."""
    new: list[ResolvedProduct] = field(default_factory=list)
    matched: list[ResolvedProduct] = field(default_factory=list)
    needs_review: list[ResolvedProduct] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.new) + len(self.matched) + len(self.needs_review)


class EntityResolver:
    """Resolve products against existing graph entities."""

    def __init__(self, graph_service):
        self._graph = graph_service

    async def resolve(self, products: list[NormalizedProduct]) -> ResolutionResult:
        """Resolve a batch of normalized products against the graph."""
        result = ResolutionResult()

        for product in products:
            resolved = await self._resolve_single(product)
            if resolved.status == "new":
                result.new.append(resolved)
            elif resolved.status == "matched":
                result.matched.append(resolved)
            else:
                result.needs_review.append(resolved)

        logger.info("Resolution: %d new, %d matched, %d needs_review",
                     len(result.new), len(result.matched), len(result.needs_review))
        return result

    async def _resolve_single(self, product: NormalizedProduct) -> ResolvedProduct:
        """Resolve a single product against the graph."""
        # 1. Exact SKU match
        existing = await self._graph.get_part(product.sku)
        if existing:
            return ResolvedProduct(
                product=product, status="matched",
                matched_sku=product.sku, match_confidence=1.0,
                match_source="exact_sku",
            )

        # 2. Check equivalents (maybe this SKU is a cross-ref)
        equivalents = await self._graph.resolve_part(product.sku)
        if equivalents:
            return ResolvedProduct(
                product=product, status="matched",
                matched_sku=equivalents[0].get("sku", product.sku),
                match_confidence=0.9, match_source="cross_ref",
            )

        # 3. Fuzzy name match via fulltext search
        if product.name and len(product.name) > 3:
            try:
                search_results = await self._graph.search_parts_fulltext(
                    product.name, limit=5
                )
                best_match = self._find_best_fuzzy_match(product, search_results)
                if best_match:
                    return best_match
            except Exception as e:
                logger.debug("Fulltext search failed: %s", e)

        # 4. No match — new product
        return ResolvedProduct(
            product=product, status="new",
            match_confidence=0.0,
        )

    def _find_best_fuzzy_match(self, product: NormalizedProduct,
                                search_results: list[dict]) -> ResolvedProduct | None:
        """Find the best fuzzy match from fulltext search results."""
        if not search_results or not FUZZY_AVAILABLE:
            return None

        best_score = 0
        best_sku = None

        for result in search_results:
            node = result.get("node", result)
            existing_name = node.get("name", "")
            existing_sku = node.get("sku", "")

            # Check name similarity
            name_score = fuzz.token_sort_ratio(product.name, existing_name)

            # Boost if SKU is similar
            sku_score = fuzz.ratio(product.sku.upper(), existing_sku.upper())

            combined = max(name_score, sku_score)
            if combined > best_score:
                best_score = combined
                best_sku = existing_sku

        if best_score >= 90:
            return ResolvedProduct(
                product=product, status="matched",
                matched_sku=best_sku, match_confidence=best_score / 100.0,
                match_source="fuzzy_name",
            )
        elif best_score >= 70:
            return ResolvedProduct(
                product=product, status="needs_review",
                matched_sku=best_sku, match_confidence=best_score / 100.0,
                match_source="fuzzy_name",
            )

        return None
