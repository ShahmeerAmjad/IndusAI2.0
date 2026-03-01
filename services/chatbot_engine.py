# =======================
# Main Chatbot Engine - Message Processing Pipeline
# =======================

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from metrics.metrics import ACTIVE_SESSIONS, ERROR_COUNTER, MESSAGES_TOTAL, RESPONSE_TIME
from models.models import BotResponse, ChannelType, CustomerMessage
from services.ai.prompts import CONVERSATION_SUMMARY_PROMPT


class ChatbotEngine:
    SUMMARIZE_EVERY = 10  # Generate summary every N messages

    def __init__(self, logger, business_logic, classifier, db_manager, settings,
                 conversation_service=None, ai_service=None):
        self.logger = logger
        self.business_logic = business_logic
        self.classifier = classifier
        self.db_manager = db_manager
        self.settings = settings
        self.conversation_service = conversation_service
        self.ai_service = ai_service

    async def process_message(
        self,
        from_id: str,
        content: str,
        channel: ChannelType,
        conversation_id: Optional[str] = None,
    ) -> Optional[BotResponse]:
        """Run the full message processing pipeline:
        validate -> classify -> route -> respond -> persist.
        """
        start_time = time.time()

        try:
            # Input validation
            if len(content.strip()) < 2:
                return BotResponse(
                    content="Please provide more details so I can better assist you.",
                    suggested_actions=["Get help", "Contact support"],
                )

            # Build internal message object
            message = CustomerMessage(
                id=str(uuid.uuid4()),
                from_id=from_id,
                content=content,
                channel=channel,
                timestamp=datetime.now(timezone.utc),
            )

            ACTIVE_SESSIONS.inc()

            # Classify intent
            message_type, confidence = self.classifier.classify(content)
            message.message_type = message_type
            message.confidence = confidence

            if confidence < 0.5:
                self.logger.warning(
                    f"Low confidence classification ({confidence:.2f}) for: {content[:80]}..."
                )

            # Get or create conversation for multi-turn
            conv = None
            history = []
            if self.conversation_service:
                conv = await self.conversation_service.get_or_create(
                    conversation_id=conversation_id,
                    channel=channel.value,
                )
                conversation_id = str(conv["id"])

                # Build bounded context: summary + last 5 messages
                context_summary = conv.get("context_summary")
                msg_count = conv.get("message_count", 0)

                if context_summary and msg_count > self.SUMMARIZE_EVERY:
                    # Use summary + recent messages for bounded token usage
                    history = await self.conversation_service.get_history(
                        conversation_id, limit=5
                    )
                    # Prepend summary as a synthetic history entry
                    history = [
                        {"content": f"[Conversation summary: {context_summary}]",
                         "response_content": None, "from_id": "system"}
                    ] + history
                else:
                    history = await self.conversation_service.get_history(
                        conversation_id, limit=10
                    )

            # Generate response via business logic (pass history)
            response = await self.business_logic.process_message(
                message, conversation_history=history
            )

            response_time = time.time() - start_time

            # Update Prometheus metrics
            MESSAGES_TOTAL.labels(
                message_type=message_type.value,
                channel=channel.value,
            ).inc()
            RESPONSE_TIME.observe(response_time)

            # Persist to DB in background (fire-and-forget)
            asyncio.create_task(
                self.db_manager.save_message(message, response, response_time)
            )

            # Save to conversation history
            if self.conversation_service and conversation_id:
                asyncio.create_task(
                    self.conversation_service.add_message(
                        conversation_id=conversation_id,
                        role="user",
                        content=content,
                        from_id=from_id,
                        message_type=message_type.value,
                        response_content=response.content,
                    )
                )

                # Trigger summarization every N messages
                new_count = (conv.get("message_count", 0) if conv else 0) + 1
                if new_count > 0 and new_count % self.SUMMARIZE_EVERY == 0:
                    asyncio.create_task(
                        self._summarize_conversation(conversation_id)
                    )

            ACTIVE_SESSIONS.dec()

            # Attach conversation_id to response metadata
            if response.metadata is None:
                response.metadata = {}
            if conversation_id:
                response.metadata["conversation_id"] = conversation_id

            return response

        except Exception as e:
            self.logger.error(f"Message processing error: {e}", exc_info=True)
            ERROR_COUNTER.labels(error_type="message_processing").inc()
            ACTIVE_SESSIONS.dec()

            support_email = getattr(self.settings, 'support_email', 'support@company.com')
            return BotResponse(
                content=(
                    "I apologize, but I encountered an error processing your request. "
                    f"Please try again or contact our support team at {support_email}."
                ),
                suggested_actions=["Try again", "Contact support"],
            )

    async def _summarize_conversation(self, conversation_id: str) -> None:
        """Generate a rolling summary of the conversation using Claude."""
        try:
            if not self.ai_service or not self.ai_service.client:
                return

            history = await self.conversation_service.get_history(
                conversation_id, limit=20
            )
            if not history:
                return

            # Build conversation text
            lines = []
            for msg in history:
                lines.append(f"User: {msg.get('content', '')}")
                if msg.get("response_content"):
                    lines.append(f"Assistant: {msg['response_content']}")
            conversation_text = "\n".join(lines)

            prompt = CONVERSATION_SUMMARY_PROMPT.format(
                conversation_text=conversation_text
            )

            model = getattr(self.settings, 'ai_model', 'claude-3-5-sonnet-20241022')
            response = await self.ai_service.client.messages.create(
                model=model,
                max_tokens=200,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = response.content[0].text

            await self.conversation_service.update_summary(
                conversation_id, summary
            )
            self.logger.info(f"Conversation {conversation_id} summarized")

        except Exception as e:
            self.logger.error(f"Conversation summarization failed: {e}")
