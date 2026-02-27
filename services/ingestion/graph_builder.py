"""Stage 4: Graph Construction — writes resolved entities to Neo4j."""

import logging
from dataclasses import dataclass, field

from services.ingestion.resolver import ResolvedProduct, ResolutionResult

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Results of building graph entities from resolved products."""
    created: int = 0
    updated: int = 0
    cross_refs_added: int = 0
    embeddings_generated: int = 0
    errors: list[str] = field(default_factory=list)


class GraphBuilder:
    """Write resolved products to the Neo4j knowledge graph."""

    def __init__(self, graph_service, llm_router=None):
        self._graph = graph_service
        self._llm = llm_router

    async def build(self, resolved: ResolutionResult) -> BuildResult:
        """Build graph nodes and edges from resolved products."""
        result = BuildResult()

        # Process new products — create nodes
        for rp in resolved.new:
            try:
                await self._create_part(rp)
                result.created += 1
            except Exception as e:
                error_msg = f"Failed to create {rp.product.sku}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Process matched products — update existing nodes
        for rp in resolved.matched:
            try:
                await self._update_part(rp)
                result.updated += 1
            except Exception as e:
                error_msg = f"Failed to update {rp.product.sku}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Generate embeddings in batch if LLM router available
        if self._llm:
            all_products = [rp.product for rp in resolved.new + resolved.matched]
            embedded = await self._generate_embeddings(all_products)
            result.embeddings_generated = embedded

        logger.info("Build complete: %d created, %d updated, %d embeddings, %d errors",
                     result.created, result.updated, result.embeddings_generated,
                     len(result.errors))
        return result

    async def _create_part(self, resolved: ResolvedProduct) -> None:
        """Create a new Part node with all relationships."""
        p = resolved.product
        await self._graph.upsert_part(
            sku=p.sku,
            name=p.name,
            description=p.description,
            category=p.category,
            manufacturer=p.manufacturer,
            specs=p.specs if p.specs else None,
        )

        # If price available, set it
        if p.unit_price is not None:
            await self._graph.update_price_range(p.sku, p.unit_price, p.unit_price)

    async def _update_part(self, resolved: ResolvedProduct) -> None:
        """Update an existing Part node."""
        p = resolved.product
        target_sku = resolved.matched_sku or p.sku

        # If the incoming SKU differs from matched, it may be a cross-reference
        if resolved.match_source == "cross_ref" and target_sku != p.sku:
            # Create the new part and link as equivalent
            await self._graph.upsert_part(
                sku=p.sku, name=p.name, description=p.description,
                category=p.category, manufacturer=p.manufacturer,
                specs=p.specs if p.specs else None,
            )
            await self._graph.add_cross_reference(
                p.sku, target_sku, ref_type="EQUIVALENT_TO",
                confidence=resolved.match_confidence, source="ingestion",
            )
        else:
            # Update existing part with new data
            await self._graph.upsert_part(
                sku=target_sku, name=p.name, description=p.description,
                category=p.category, manufacturer=p.manufacturer,
                specs=p.specs if p.specs else None,
            )

    async def _generate_embeddings(self, products: list) -> int:
        """Generate and store embeddings for products in batches."""
        if not products or not self._llm:
            return 0

        BATCH_SIZE = 50
        total = 0

        for i in range(0, len(products), BATCH_SIZE):
            batch = products[i:i + BATCH_SIZE]
            part_dicts = [
                {
                    "sku": p.sku, "name": p.name, "description": p.description,
                    "category": p.category, "manufacturer": p.manufacturer,
                    "specs": p.specs,
                }
                for p in batch
            ]

            try:
                embeddings = await self._llm.embed_parts(part_dicts)
                for p, emb in zip(batch, embeddings):
                    await self._graph.upsert_part(
                        sku=p.sku, name=p.name, embedding=emb,
                    )
                total += len(embeddings)
            except Exception as e:
                logger.error("Embedding batch failed: %s", e)

        return total
