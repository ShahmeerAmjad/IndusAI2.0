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


class ChatbotEngine:
    def __init__(self, logger, business_logic, classifier, db_manager, settings):
        self.logger = logger
        self.business_logic = business_logic
        self.classifier = classifier
        self.db_manager = db_manager
        self.settings = settings

    async def process_message(self, from_id: str, content: str, channel: ChannelType) -> Optional[BotResponse]:
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

            # Generate response via business logic
            response = await self.business_logic.process_message(message)

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

            ACTIVE_SESSIONS.dec()
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
