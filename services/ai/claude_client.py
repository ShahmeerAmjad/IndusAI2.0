"""Claude LLM client with circuit breaker and model-tier routing.

Ported from:
- v2: services/ai_service.py (CircuitBreaker)
- v1: app/ai/llm_client.py (Anthropic chat)
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Claude model tiers
CLAUDE_MODELS = {
    "fast": "claude-haiku-4-5-20251001",
    "standard": "claude-sonnet-4-20250514",
    "heavy": "claude-opus-4-20250514",
}


class CircuitBreaker:
    """Prevents cascading failures from API outages."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time: Optional[float] = None

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning("Circuit breaker OPEN after %d failures", self.failure_count)

    def record_success(self):
        if self.state != self.CLOSED:
            logger.info("Circuit breaker CLOSED after successful request")
        self.failure_count = 0
        self.state = self.CLOSED

    def can_execute(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN: allow one attempt

    def get_state(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
            "timeout_seconds": self.timeout,
        }


class ClaudeClient:
    """Claude API client with circuit breaker, retry, and model-tier routing."""

    def __init__(self, api_key: str, max_retries: int = 3, retry_delay: float = 1.0,
                 circuit_breaker_threshold: int = 5, circuit_breaker_timeout: int = 60):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required: pip install anthropic")

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout=circuit_breaker_timeout,
        )
        logger.info("Claude client initialized")

    async def chat(self, messages: list[dict], system: str | None = None,
                   model: str = "claude-sonnet-4-20250514",
                   max_tokens: int = 1024, temperature: float = 0.3) -> str:
        """Send a chat request to Claude with retry and circuit breaker.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            system: Optional system prompt.
            model: Full model ID or tier name ("fast", "standard", "heavy").
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
        """
        # Resolve tier name to model ID
        resolved_model = CLAUDE_MODELS.get(model, model)

        if not self._circuit_breaker.can_execute():
            raise RuntimeError("Circuit breaker is OPEN — Claude API unavailable")

        last_error = None
        for attempt in range(self._max_retries):
            try:
                kwargs = {
                    "model": resolved_model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                }
                if system:
                    kwargs["system"] = system

                response = await self._client.messages.create(**kwargs)
                self._circuit_breaker.record_success()
                return response.content[0].text.strip()

            except anthropic.RateLimitError as e:
                last_error = e
                wait = self._retry_delay * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), waiting %.1fs",
                               attempt + 1, self._max_retries, wait)
                await asyncio.sleep(wait)

            except anthropic.APIStatusError as e:
                last_error = e
                if e.status_code >= 500:
                    wait = self._retry_delay * (2 ** attempt)
                    logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs",
                                   e.status_code, attempt + 1, self._max_retries, wait)
                    await asyncio.sleep(wait)
                else:
                    # Client error (4xx except 429) — don't retry
                    self._circuit_breaker.record_failure()
                    raise

            except Exception as e:
                last_error = e
                logger.error("Claude chat failed (attempt %d/%d): %s",
                             attempt + 1, self._max_retries, e)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))

        self._circuit_breaker.record_failure()
        raise RuntimeError(f"Claude API failed after {self._max_retries} attempts: {last_error}")

    async def chat_with_compaction(
        self,
        messages: list[dict],
        system: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        compaction_control: dict | None = None,
    ) -> str:
        """Chat with optional context compaction support.

        When compaction_control is provided, passes it to the Anthropic SDK.
        If the SDK version doesn't support compaction_control yet, falls back
        to a regular chat() call with a warning.
        """
        if not compaction_control:
            return await self.chat(
                messages, system=system, model=model,
                max_tokens=max_tokens, temperature=temperature,
            )

        resolved_model = CLAUDE_MODELS.get(model, model)

        if not self._circuit_breaker.can_execute():
            raise RuntimeError("Circuit breaker is OPEN — Claude API unavailable")

        last_error = None
        for attempt in range(self._max_retries):
            try:
                kwargs = {
                    "model": resolved_model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                    "compaction_control": compaction_control,
                }
                if system:
                    kwargs["system"] = system

                try:
                    response = await self._client.messages.create(**kwargs)
                except TypeError as te:
                    if "compaction_control" in str(te):
                        logger.warning(
                            "SDK does not support compaction_control yet, "
                            "falling back to regular chat: %s", te,
                        )
                        return await self.chat(
                            messages, system=system, model=model,
                            max_tokens=max_tokens, temperature=temperature,
                        )
                    raise

                self._circuit_breaker.record_success()
                return response.content[0].text.strip()

            except anthropic.RateLimitError as e:
                last_error = e
                wait = self._retry_delay * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), waiting %.1fs",
                               attempt + 1, self._max_retries, wait)
                await asyncio.sleep(wait)

            except anthropic.APIStatusError as e:
                last_error = e
                if e.status_code >= 500:
                    wait = self._retry_delay * (2 ** attempt)
                    logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs",
                                   e.status_code, attempt + 1, self._max_retries, wait)
                    await asyncio.sleep(wait)
                else:
                    self._circuit_breaker.record_failure()
                    raise

            except Exception as e:
                last_error = e
                logger.error("Claude chat_with_compaction failed (attempt %d/%d): %s",
                             attempt + 1, self._max_retries, e)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))

        self._circuit_breaker.record_failure()
        raise RuntimeError(f"Claude API failed after {self._max_retries} attempts: {last_error}")

    def get_circuit_breaker_state(self) -> dict:
        return self._circuit_breaker.get_state()
