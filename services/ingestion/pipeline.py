"""Catalog Ingestion Pipeline — orchestrates the 4-stage process.

Parse → Normalize → Resolve → Build
"""

import logging
from dataclasses import dataclass, field

from services.ingestion.parser import CatalogParser
from services.ingestion.normalizer import CatalogNormalizer
from services.ingestion.resolver import EntityResolver
from services.ingestion.graph_builder import GraphBuilder, BuildResult

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Summary of a completed ingestion run."""
    total_parsed: int = 0
    total_normalized: int = 0
    created: int = 0
    updated: int = 0
    needs_review: int = 0
    errors: list[str] = field(default_factory=list)
    embeddings_generated: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_parsed == 0:
            return 0.0
        return (self.created + self.updated) / self.total_parsed


class IngestionPipeline:
    """Orchestrates the 4-stage catalog ingestion process."""

    def __init__(self, parser: CatalogParser, normalizer: CatalogNormalizer,
                 resolver: EntityResolver, builder: GraphBuilder):
        self.parser = parser
        self.normalizer = normalizer
        self.resolver = resolver
        self.builder = builder

    async def ingest_csv(self, file_bytes: bytes,
                         encoding: str = "utf-8") -> IngestionResult:
        """Ingest a CSV catalog file through the full pipeline."""
        logger.info("Starting CSV ingestion...")

        # Stage 1: Parse
        raw = await self.parser.parse_csv(file_bytes, encoding=encoding)
        logger.info("Stage 1 (Parse): %d raw products", len(raw))

        return await self._run_pipeline(raw)

    async def ingest_pdf(self, file_bytes: bytes) -> IngestionResult:
        """Ingest a PDF catalog through the full pipeline."""
        logger.info("Starting PDF ingestion...")

        # Stage 1: Parse
        raw = await self.parser.parse_pdf(file_bytes)
        logger.info("Stage 1 (Parse): %d raw products", len(raw))

        return await self._run_pipeline(raw)

    async def ingest_url(self, url: str, max_pages: int = 5) -> IngestionResult:
        """Ingest a web catalog through the full pipeline."""
        logger.info("Starting URL ingestion: %s", url)

        # Stage 1: Parse
        raw = await self.parser.scrape_url(url, max_pages=max_pages)
        logger.info("Stage 1 (Parse): %d raw products", len(raw))

        return await self._run_pipeline(raw)

    async def _run_pipeline(self, raw_products: list[dict]) -> IngestionResult:
        """Run stages 2-4 on parsed products."""
        result = IngestionResult(total_parsed=len(raw_products))

        if not raw_products:
            return result

        # Stage 2: Normalize
        normalized = await self.normalizer.normalize(raw_products)
        result.total_normalized = len(normalized)
        logger.info("Stage 2 (Normalize): %d normalized products", len(normalized))

        if not normalized:
            return result

        # Stage 3: Resolve
        resolved = await self.resolver.resolve(normalized)
        result.needs_review = len(resolved.needs_review)
        logger.info("Stage 3 (Resolve): %d new, %d matched, %d needs review",
                     len(resolved.new), len(resolved.matched), len(resolved.needs_review))

        # Stage 4: Build
        build_result = await self.builder.build(resolved)
        result.created = build_result.created
        result.updated = build_result.updated
        result.embeddings_generated = build_result.embeddings_generated
        result.errors = build_result.errors

        logger.info("Stage 4 (Build): %d created, %d updated, %d errors",
                     build_result.created, build_result.updated, len(build_result.errors))

        return result
