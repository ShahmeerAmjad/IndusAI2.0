"""Claude LLM router with task-based model selection.

Routes requests to the appropriate Claude model tier (Haiku/Sonnet/Opus)
based on task type. Uses Voyage AI for all embedding operations.
"""

import logging

logger = logging.getLogger(__name__)

TASK_MODELS = {
    "intent_classification": "fast",
    "entity_extraction": "fast",
    "chempoint_extraction": "fast",
    "chempoint_navigation": "fast",
    "response_generation": "standard",
    "catalog_normalization": "standard",
    "graph_construction": "standard",
    "tds_extraction": "standard",
    "sds_extraction": "standard",
    "complex_reasoning": "heavy",
}


class LLMRouter:
    """Routes LLM requests to the appropriate Claude model by task type.
    Uses Voyage AI for all embedding operations."""

    def __init__(self, claude_client, embedding_client):
        self._claude = claude_client
        self._embeddings = embedding_client
        logger.info("LLM Router initialized (Claude + Voyage AI)")

    async def chat(self, messages: list[dict], system: str | None = None,
                   task: str = "response_generation", max_tokens: int = 1024,
                   temperature: float = 0.3) -> str:
        """Route a chat request to the appropriate Claude model.

        Args:
            messages: Conversation messages.
            system: System prompt.
            task: Task type (determines model tier).
            max_tokens: Max response tokens.
            temperature: Sampling temperature.
        """
        model_tier = TASK_MODELS.get(task, "standard")
        return await self._claude.chat(
            messages, system=system, model=model_tier,
            max_tokens=max_tokens, temperature=temperature
        )

    async def chat_with_compaction(
        self,
        messages: list[dict],
        task: str = "response_generation",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        system: str | None = None,
        compaction_control: dict | None = None,
    ) -> str:
        """Chat with optional automatic context compaction for batch processing.

        When compaction_control is provided, uses the Anthropic SDK's
        compaction to manage context window in long loops.
        When None, falls back to regular chat.
        """
        if not compaction_control:
            return await self.chat(
                messages=messages, system=system, task=task,
                max_tokens=max_tokens, temperature=temperature,
            )

        model_tier = TASK_MODELS.get(task, "standard")
        return await self._claude.chat_with_compaction(
            messages, system=system, model=model_tier,
            max_tokens=max_tokens, temperature=temperature,
            compaction_control=compaction_control,
        )

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed texts using Voyage AI."""
        return await self._embeddings.embed(texts, input_type=input_type)

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        return await self._embeddings.embed_query(query)

    async def embed_parts(self, parts: list[dict]) -> list[list[float]]:
        """Embed a batch of parts with rich text descriptions."""
        return await self._embeddings.embed_parts(parts)

    def get_health(self) -> dict:
        """Return health status of underlying clients."""
        return {
            "claude": self._claude.get_circuit_breaker_state(),
            "embeddings": "available",
        }
