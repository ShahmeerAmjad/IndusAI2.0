"""Voyage AI embedding client for vector operations.

Uses the Voyage AI REST API directly via httpx (no voyageai SDK needed).
"""

import logging

import httpx

logger = logging.getLogger(__name__)

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"


class VoyageEmbeddingClient:
    """Handles all embedding operations via Voyage AI REST API."""

    def __init__(self, api_key: str, model: str = "voyage-3-large"):
        self._api_key = api_key
        self._model = model
        self._http = httpx.AsyncClient(
            base_url="https://api.voyageai.com/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        logger.info("Voyage AI embedding client initialized (model=%s)", model)

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed texts using Voyage AI.

        Args:
            texts: List of strings to embed.
            input_type: "document" for indexing, "query" for search queries.

        Returns:
            List of embedding vectors (1024 dimensions for voyage-3-large).
        """
        if not texts:
            return []

        response = await self._http.post(
            "/embeddings",
            json={
                "input": texts,
                "model": self._model,
                "input_type": input_type,
            },
        )
        response.raise_for_status()
        data = response.json()
        # Response format: {"data": [{"embedding": [...], "index": 0}, ...]}
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_items]

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        embeddings = await self.embed([query], input_type="query")
        return embeddings[0]

    async def embed_parts(self, parts: list[dict]) -> list[list[float]]:
        """Build rich text descriptions and embed a batch of parts.

        Args:
            parts: List of dicts with keys like sku, name, description,
                   category, manufacturer, specs.
        """
        texts = [self._build_part_text(p) for p in parts]
        return await self.embed(texts, input_type="document")

    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()

    @staticmethod
    def _build_part_text(part: dict) -> str:
        """Build a rich text representation of a part for embedding."""
        segments = []
        if part.get("name"):
            segments.append(part["name"])
        if part.get("sku"):
            segments.append(f"SKU: {part['sku']}")
        if part.get("manufacturer"):
            segments.append(f"Manufacturer: {part['manufacturer']}")
        if part.get("category"):
            segments.append(f"Category: {part['category']}")
        if part.get("description"):
            segments.append(part["description"])
        if part.get("specs"):
            spec_strs = [f"{k}: {v}" for k, v in part["specs"].items()]
            segments.append("Specs: " + ", ".join(spec_strs))
        return " | ".join(segments)
