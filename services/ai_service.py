# =======================
# AI Service - Anthropic Claude Integration with Circuit Breaker
# =======================

import time
import asyncio
from typing import Dict, Optional

from metrics.metrics import ERROR_COUNTER

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures from AI service outages."""

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

    def record_success(self):
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
        # HALF_OPEN: allow one attempt
        return True

    def get_state(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
            "timeout_seconds": self.timeout,
        }


class AIService:
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self.client = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(settings, 'circuit_breaker_threshold', 5),
            timeout=getattr(settings, 'circuit_breaker_timeout', 60),
        )

        if ANTHROPIC_AVAILABLE and getattr(settings, 'anthropic_api_key', None):
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.logger.info("Anthropic AI client initialized")
        else:
            self.logger.warning("Anthropic AI not available - responses will use rule-based fallback")

    def get_circuit_breaker_state(self) -> dict:
        return self.circuit_breaker.get_state()

    async def enhance_response(self, user_message: str, basic_response: str, context: Dict = None) -> str:
        """Enhance a rule-based response using Claude AI."""
        if not self.client:
            return basic_response

        if not self.circuit_breaker.can_execute():
            self.logger.warning("AI circuit breaker is open - using basic response")
            return basic_response

        model = getattr(self.settings, 'ai_model', 'claude-3-5-sonnet-20241022')
        max_retries = getattr(self.settings, 'ai_max_retries', 3)
        retry_delay = getattr(self.settings, 'ai_retry_delay', 1.0)

        for attempt in range(max_retries):
            try:
                system_prompt = (
                    "You are a helpful B2B MRO (Maintenance, Repair, Operations) customer service AI assistant. "
                    "Enhance the given response to be more professional, helpful, and actionable. "
                    "Keep responses concise (under 150 words) and focused on solving the customer's problem. "
                    "Maintain a professional yet friendly tone suitable for industrial/business customers. "
                    "Reference specific product categories like safety equipment, industrial tools, "
                    "electrical components, and maintenance supplies when relevant."
                )

                user_prompt = f"Customer message: {user_message}\n\nDraft response: {basic_response}"

                if context:
                    msg_count = context.get('message_count', 0)
                    if msg_count > 1:
                        user_prompt += f"\n\nContext: Returning customer with {msg_count} messages in this session."

                # Build multi-turn messages if conversation history exists
                messages = self._build_messages(user_prompt, context)

                message = await self.client.messages.create(
                    model=model,
                    max_tokens=300,
                    temperature=0.3,
                    system=system_prompt,
                    messages=messages,
                )

                self.circuit_breaker.record_success()
                return message.content[0].text

            except Exception as e:
                self.logger.error(f"AI enhancement failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))

        self.circuit_breaker.record_failure()
        ERROR_COUNTER.labels(error_type="ai_enhancement").inc()
        return basic_response

    def _build_messages(self, current_prompt: str, context: Dict = None) -> list:
        """Build multi-turn messages array from conversation history.

        If conversation history exists, includes prior exchanges so Claude
        has full context for the enhancement.
        """
        history = (context or {}).get("conversation_history", [])
        if not history:
            return [{"role": "user", "content": current_prompt}]

        messages = []
        for msg in history:
            content = msg.get("content", "")
            response = msg.get("response_content")
            # User turn
            messages.append({"role": "user", "content": content})
            # Assistant turn (if we have the response)
            if response:
                messages.append({"role": "assistant", "content": response})

        # Add current turn
        messages.append({"role": "user", "content": current_prompt})
        return messages
