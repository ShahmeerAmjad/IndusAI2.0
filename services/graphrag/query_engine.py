"""5-Stage GraphRAG Query Engine.

Stage 1: Intent + Entity Extraction
Stage 2: Graph Resolution (Cypher)
Stage 3: Vector Fallback (if graph empty)
Stage 4: Context Assembly (merge graph + PostgreSQL)
Stage 5: LLM Response Generation
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from services.ai.models import IntentType, IntentResult, EntityResult
from services.ai.prompts import GRAPH_RESPONSE_PROMPT, SOURCING_RESPONSE_PROMPT
from services.graphrag.context_merger import ContextMerger, MergedContext

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of processing a customer query through GraphRAG."""
    response: str
    intent: IntentResult | None = None
    entities: EntityResult | None = None
    graph_paths: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    parts_found: int = 0
    sourcing_results: list = field(default_factory=list)  # SourcingResult objects
    debug: dict = field(default_factory=dict)


class GraphRAGQueryEngine:
    """5-stage query engine: Intent → Graph → Vector → Context → LLM."""

    def __init__(self, graph_service, llm_router,
                 intent_classifier, entity_extractor, part_parser,
                 inventory_service=None, pricing_service=None,
                 seller_service=None, location_optimizer=None,
                 price_comparator=None):
        self._graph = graph_service
        self._llm = llm_router
        self._classifier = intent_classifier
        self._entity_extractor = entity_extractor
        self._part_parser = part_parser
        self._seller_service = seller_service
        self._location_optimizer = location_optimizer
        self._price_comparator = price_comparator
        self._merger = ContextMerger(
            inventory_service=inventory_service,
            pricing_service=pricing_service,
        )

    async def process_query(self, message: str,
                            customer_id: str | None = None) -> QueryResult:
        """Process a customer message through the 5-stage GraphRAG pipeline."""
        # Stage 1: Intent + Entity Extraction
        intent = await self._classifier.classify_intent(message)
        entities = self._entity_extractor.extract(message)
        parsed_parts = self._part_parser.parse(message)

        logger.info("Stage 1: intent=%s (%.2f), parts=%d, entities=%d",
                     intent.intent.value, intent.confidence,
                     len(parsed_parts), len(entities.part_numbers))

        # Stage 2: Graph Resolution
        graph_results = await self._resolve_via_graph(entities, parsed_parts, intent)
        graph_paths = []

        if graph_results:
            graph_paths.append(f"Graph: found {len(graph_results)} results")
            logger.info("Stage 2: graph returned %d results", len(graph_results))

        # Stage 3: Vector Fallback
        vector_results = []
        if not graph_results:
            vector_results = await self._vector_fallback(message)
            if vector_results:
                graph_paths.append(f"Vector: found {len(vector_results)} similar parts")
                logger.info("Stage 3: vector returned %d results", len(vector_results))

        # Stage 4: Context Assembly
        all_results = graph_results + vector_results
        source = "graph" if graph_results else "vector"
        context = await self._merger.merge(all_results, source=source,
                                           customer_id=customer_id)
        context.graph_paths = graph_paths

        logger.info("Stage 4: context has %d parts", len(context.parts))

        # Stage 4b: Seller Matching + Location + Pricing
        sourcing_results = await self._match_sellers(context, buyer_location=None)

        if sourcing_results:
            graph_paths.append(f"Sourcing: {len(sourcing_results)} seller options")
            logger.info("Stage 4b: %d sourcing options found", len(sourcing_results))

        # Stage 5: LLM Response Generation
        response = await self._generate_response(
            message, context, intent, sourcing_results=sourcing_results
        )

        return QueryResult(
            response=response,
            intent=intent,
            entities=entities,
            graph_paths=graph_paths,
            sources=context.sources,
            parts_found=len(context.parts),
            sourcing_results=sourcing_results,
        )

    # ------------------------------------------------------------------
    # Stage 2: Graph Resolution
    # ------------------------------------------------------------------

    async def _resolve_via_graph(self, entities: EntityResult,
                                 parsed_parts: list,
                                 intent: IntentResult) -> list[dict]:
        """Resolve entities against the knowledge graph."""
        results = []

        # Try each extracted part number
        for pn in entities.part_numbers:
            try:
                # First: exact part lookup
                part = await self._graph.get_part(pn)
                if part:
                    results.append(part)
                    continue

                # Second: resolve (finds equivalents)
                resolved = await self._graph.resolve_part(pn)
                if resolved:
                    results.extend([{"node": r} for r in resolved])
                    continue

                # Third: fulltext search with the part number
                ft_results = await self._graph.search_parts_fulltext(pn, limit=5)
                results.extend(ft_results)

            except Exception as e:
                logger.warning("Graph resolution failed for %s: %s", pn, e)

        # If parsed parts found specs, search by specs
        if not results and parsed_parts:
            for pp in parsed_parts:
                if pp.parsed and pp.confidence > 0.7:
                    spec_constraints = {}
                    if "bore_mm" in pp.parsed:
                        spec_constraints["bore_mm"] = pp.parsed["bore_mm"]
                    if "diameter_mm" in pp.parsed:
                        spec_constraints["diameter_mm"] = pp.parsed["diameter_mm"]

                    if spec_constraints:
                        try:
                            spec_results = await self._graph.find_parts_by_specs(
                                spec_constraints, limit=10
                            )
                            results.extend(spec_results)
                        except Exception as e:
                            logger.warning("Spec search failed: %s", e)

        # For product inquiry with no specific parts, try fulltext on the message
        if not results and intent.intent in (IntentType.PART_LOOKUP, IntentType.INVENTORY_CHECK):
            try:
                # Extract key terms from message (skip common words)
                ft_results = await self._graph.search_parts_fulltext(
                    " ".join(entities.part_numbers) if entities.part_numbers else "",
                    limit=10,
                )
                results.extend(ft_results)
            except Exception as e:
                logger.debug("Fulltext fallback failed: %s", e)

        return results

    # ------------------------------------------------------------------
    # Stage 3: Vector Fallback
    # ------------------------------------------------------------------

    async def _vector_fallback(self, message: str) -> list[dict]:
        """If graph returned nothing, try vector similarity search."""
        try:
            query_embedding = await self._llm.embed_query(message)
            return await self._graph.search_parts_vector(
                query_embedding, limit=10, min_score=0.5
            )
        except Exception as e:
            logger.warning("Vector fallback failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Stage 4b: Seller Matching
    # ------------------------------------------------------------------

    async def _match_sellers(self, context: MergedContext,
                             buyer_location: tuple[float, float] | None = None) -> list:
        """Match parts from context against seller listings, rank by composite score."""
        if not self._seller_service or not context.parts:
            return []

        try:
            # Collect all part SKUs (including cross-refs)
            part_skus = []
            for part in context.parts:
                part_skus.append(part.sku)
                for xref in part.cross_refs:
                    if xref.get("sku"):
                        part_skus.append(xref["sku"])

            if not part_skus:
                return []

            # Query seller listings from PostgreSQL
            listings = await self._seller_service.find_listings_for_parts(part_skus)

            if not listings:
                return []

            # Build SourcingResult objects
            from services.intelligence.price_comparator import SourcingResult
            from datetime import datetime, timezone

            results = []
            for listing in listings:
                sr = SourcingResult(
                    sku=listing.get("part_sku", listing.get("sku", "")),
                    name=listing.get("seller_name", ""),
                    seller_name=listing.get("seller_name", ""),
                    unit_price=float(listing.get("price", 0)),
                    qty_available=listing.get("qty_available", 0),
                    reliability=float(listing.get("reliability", 5.0)),
                    seller_id=str(listing.get("seller_id", "")),
                    warehouse_id=str(listing.get("warehouse_id", "")),
                    distance_km=0.0,
                    transit_days=listing.get("lead_time_days", 3),
                    shipping_cost=0.0,
                )

                # Add location data if available
                if self._location_optimizer and buyer_location:
                    s_lat = listing.get("lat")
                    s_lng = listing.get("lng")
                    if s_lat is not None and s_lng is not None:
                        dist = self._location_optimizer.haversine_distance(
                            buyer_location[0], buyer_location[1], s_lat, s_lng
                        )
                        cost, days = self._location_optimizer.estimate_shipping(dist)
                        sr.distance_km = round(dist, 1)
                        sr.shipping_cost = cost
                        sr.transit_days = days

                results.append(sr)

            # Rank by composite score
            if self._price_comparator and results:
                results = self._price_comparator.rank(results)

            return results

        except Exception as e:
            logger.warning("Seller matching failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Stage 5: LLM Response Generation
    # ------------------------------------------------------------------

    async def _generate_response(self, question: str,
                                 context: MergedContext,
                                 intent: IntentResult,
                                 sourcing_results: list | None = None) -> str:
        """Generate a natural language response using Claude."""
        context_text = context.to_text()

        # Use sourcing prompt if we have seller options
        if sourcing_results:
            sourcing_text = self._format_sourcing_options(sourcing_results)
            prompt = SOURCING_RESPONSE_PROMPT.format(
                context=context_text,
                sourcing_options=sourcing_text,
                question=question,
            )
        else:
            prompt = GRAPH_RESPONSE_PROMPT.format(
                context=context_text,
                question=question,
            )

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                task="response_generation",
                max_tokens=1024,
                temperature=0.3,
            )
            return response
        except Exception as e:
            logger.error("LLM response generation failed: %s", e)
            # Fallback: return structured context directly
            if sourcing_results:
                lines = [f"Found {len(sourcing_results)} sourcing options:"]
                for sr in sourcing_results[:5]:
                    lines.append(f"- {sr.seller_name}: ${sr.unit_price:.2f}/ea, {sr.transit_days}d delivery")
                return "\n".join(lines)
            if context.parts:
                parts_summary = ", ".join(
                    f"{p.name} ({p.sku})" for p in context.parts[:5]
                )
                return f"I found these parts: {parts_summary}. Please let me know if you need more details."
            return "I wasn't able to find matching parts. Could you provide more details about what you're looking for?"

    @staticmethod
    def _format_sourcing_options(sourcing_results: list) -> str:
        """Format sourcing results as text for the LLM prompt."""
        lines = []
        for i, sr in enumerate(sourcing_results[:10], 1):
            line = (
                f"{i}. {sr.seller_name} — ${sr.unit_price:.2f}/ea, "
                f"{sr.qty_available} in stock, "
                f"{sr.transit_days}d delivery"
            )
            if sr.shipping_cost > 0:
                line += f", +${sr.shipping_cost:.2f} shipping"
            if sr.distance_km > 0:
                line += f" ({sr.distance_km:.0f} km away)"
            lines.append(line)
        return "\n".join(lines) if lines else "No seller options found."
