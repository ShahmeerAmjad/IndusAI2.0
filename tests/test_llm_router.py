import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.claude_client import ClaudeClient, CircuitBreaker, CLAUDE_MODELS
from services.ai.embedding_client import VoyageEmbeddingClient
from services.ai.llm_router import LLMRouter, TASK_MODELS


# --- CircuitBreaker Tests ---

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.can_execute()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert not cb.can_execute()

    def test_closes_after_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=0)
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        # With timeout=0, should transition to HALF_OPEN immediately
        assert cb.can_execute()
        assert cb.state == CircuitBreaker.HALF_OPEN

    def test_get_state(self):
        cb = CircuitBreaker(failure_threshold=5, timeout=60)
        state = cb.get_state()
        assert state["state"] == "closed"
        assert state["threshold"] == 5


# --- ClaudeClient Tests ---

class TestClaudeClient:
    def test_model_tiers_defined(self):
        assert "fast" in CLAUDE_MODELS
        assert "standard" in CLAUDE_MODELS
        assert "heavy" in CLAUDE_MODELS
        assert "haiku" in CLAUDE_MODELS["fast"]
        assert "sonnet" in CLAUDE_MODELS["standard"]
        assert "opus" in CLAUDE_MODELS["heavy"]

    @patch("services.ai.claude_client.ANTHROPIC_AVAILABLE", True)
    @patch("services.ai.claude_client.anthropic")
    def test_init_creates_client(self, mock_anthropic):
        mock_anthropic.AsyncAnthropic.return_value = MagicMock()
        client = ClaudeClient(api_key="test-key")
        mock_anthropic.AsyncAnthropic.assert_called_once_with(api_key="test-key")

    @patch("services.ai.claude_client.ANTHROPIC_AVAILABLE", True)
    @patch("services.ai.claude_client.anthropic")
    @pytest.mark.asyncio
    async def test_chat_resolves_tier(self, mock_anthropic):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        mock_anthropic.RateLimitError = Exception
        mock_anthropic.APIStatusError = Exception

        client = ClaudeClient(api_key="test-key")
        result = await client.chat([{"role": "user", "content": "Hi"}], model="fast")

        assert result == "Hello"
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == CLAUDE_MODELS["fast"]


# --- VoyageEmbeddingClient Tests ---

class TestVoyageEmbeddingClient:
    def test_build_part_text(self):
        part = {
            "name": "Deep Groove Ball Bearing",
            "sku": "6204-2RS",
            "manufacturer": "SKF",
            "category": "Ball Bearings",
            "description": "Sealed bearing",
            "specs": {"bore_mm": 20, "od_mm": 47},
        }
        text = VoyageEmbeddingClient._build_part_text(part)
        assert "6204-2RS" in text
        assert "SKF" in text
        assert "bore_mm: 20" in text

    def test_build_part_text_minimal(self):
        text = VoyageEmbeddingClient._build_part_text({"name": "Bolt"})
        assert text == "Bolt"

    def test_build_part_text_empty(self):
        text = VoyageEmbeddingClient._build_part_text({})
        assert text == ""


# --- LLMRouter Tests ---

class TestLLMRouter:
    def test_task_models_mapping(self):
        assert TASK_MODELS["intent_classification"] == "fast"
        assert TASK_MODELS["response_generation"] == "standard"
        assert TASK_MODELS["complex_reasoning"] == "heavy"

    @pytest.mark.asyncio
    async def test_chat_routes_to_claude(self):
        mock_claude = AsyncMock()
        mock_claude.chat.return_value = "response"
        mock_claude.get_circuit_breaker_state.return_value = {"state": "closed"}
        mock_embeddings = AsyncMock()

        router = LLMRouter(claude_client=mock_claude, embedding_client=mock_embeddings)
        result = await router.chat(
            [{"role": "user", "content": "test"}],
            task="intent_classification"
        )

        assert result == "response"
        mock_claude.chat.assert_called_once()
        call_kwargs = mock_claude.chat.call_args[1]
        assert call_kwargs["model"] == "fast"

    @pytest.mark.asyncio
    async def test_embed_routes_to_voyage(self):
        mock_claude = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.embed.return_value = [[0.1, 0.2, 0.3]]

        router = LLMRouter(claude_client=mock_claude, embedding_client=mock_embeddings)
        result = await router.embed(["test text"])

        assert result == [[0.1, 0.2, 0.3]]
        mock_embeddings.embed.assert_called_once()

    def test_get_health(self):
        mock_claude = MagicMock()
        mock_claude.get_circuit_breaker_state.return_value = {"state": "closed"}
        mock_embeddings = MagicMock()

        router = LLMRouter(claude_client=mock_claude, embedding_client=mock_embeddings)
        health = router.get_health()
        assert health["claude"]["state"] == "closed"
        assert health["embeddings"] == "available"
