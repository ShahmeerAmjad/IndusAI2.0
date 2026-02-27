"""Context Merger — combines graph results + PostgreSQL data for LLM context."""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PartContext:
    """Enriched part data from graph + PostgreSQL."""
    sku: str
    name: str = ""
    manufacturer: str = ""
    category: str = ""
    description: str = ""
    specs: list[dict] = field(default_factory=list)
    cross_refs: list[dict] = field(default_factory=list)
    compatible_parts: list[dict] = field(default_factory=list)
    inventory: dict = field(default_factory=dict)  # {warehouse: qty}
    pricing: dict = field(default_factory=dict)     # {list_price, customer_price}
    source: str = ""  # "graph", "vector", "fulltext"
    score: float = 0.0


@dataclass
class MergedContext:
    """Complete context assembled for LLM response generation."""
    parts: list[PartContext] = field(default_factory=list)
    graph_paths: list[str] = field(default_factory=list)  # Explainability
    sources: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Render context as text for the LLM prompt."""
        sections = []

        for part in self.parts:
            lines = [f"**{part.name}** (SKU: {part.sku})"]
            if part.manufacturer:
                lines.append(f"  Manufacturer: {part.manufacturer}")
            if part.category:
                lines.append(f"  Category: {part.category}")

            if part.specs:
                spec_lines = [f"    {s['name']}: {s['value']}{' ' + s.get('unit', '') if s.get('unit') else ''}"
                              for s in part.specs if s.get("name")]
                if spec_lines:
                    lines.append("  Specifications:")
                    lines.extend(spec_lines)

            if part.cross_refs:
                xref_lines = [f"    {x.get('sku', '?')} ({x.get('manufacturer', '?')}) [{x.get('type', 'EQUIVALENT_TO')}]"
                              for x in part.cross_refs]
                lines.append("  Cross-references:")
                lines.extend(xref_lines)

            if part.inventory:
                total = sum(part.inventory.values())
                lines.append(f"  Inventory: {total} total ({', '.join(f'{k}: {v}' for k, v in part.inventory.items())})")

            if part.pricing:
                price_str = ", ".join(f"{k}: ${v:.2f}" for k, v in part.pricing.items() if v)
                if price_str:
                    lines.append(f"  Pricing: {price_str}")

            sections.append("\n".join(lines))

        if self.graph_paths:
            sections.append("Reasoning path: " + " → ".join(self.graph_paths))

        return "\n\n".join(sections) if sections else "No matching data found."


class ContextMerger:
    """Merge graph results with PostgreSQL data (inventory, pricing)."""

    def __init__(self, inventory_service=None, pricing_service=None):
        self._inventory = inventory_service
        self._pricing = pricing_service

    async def merge(self, graph_results: list[dict],
                    source: str = "graph",
                    customer_id: str | None = None) -> MergedContext:
        """Merge graph results with transactional data."""
        context = MergedContext()

        for result in graph_results:
            # Handle different result shapes
            node = result.get("node", result)
            if isinstance(node, dict) and "p" in node:
                node = node["p"]

            sku = node.get("sku", "")
            if not sku:
                continue

            part = PartContext(
                sku=sku,
                name=node.get("name", ""),
                manufacturer=node.get("manufacturer", ""),
                category=node.get("category", ""),
                description=node.get("description", ""),
                specs=node.get("specs", []),
                cross_refs=node.get("cross_refs", []),
                source=source,
                score=node.get("score", 0.0),
            )

            # Enrich with inventory from PostgreSQL
            if self._inventory:
                try:
                    inv = await self._inventory.check_inventory(sku)
                    if inv:
                        part.inventory = {
                            loc.get("warehouse_code", "main"): loc.get("quantity", 0)
                            for loc in inv.get("locations", [])
                        }
                except Exception as e:
                    logger.debug("Inventory lookup failed for %s: %s", sku, e)

            # Enrich with pricing from PostgreSQL
            if self._pricing:
                try:
                    prices = await self._pricing.get_price(sku, customer_id=customer_id)
                    if prices:
                        part.pricing = {
                            "list_price": prices.get("list_price"),
                            "customer_price": prices.get("final_price", prices.get("list_price")),
                        }
                except Exception as e:
                    logger.debug("Pricing lookup failed for %s: %s", sku, e)

            context.parts.append(part)
            context.sources.append(source)

        return context
