# =======================
# Communication Manager - Multi-Channel Message Delivery
# =======================

import asyncio
from typing import List, Optional

import httpx

from metrics.metrics import ERROR_COUNTER


class CommunicationManager:
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self.whatsapp_client = httpx.AsyncClient(timeout=30.0)

    async def send_whatsapp_message(
        self,
        to_id: str,
        content: str,
        suggested_actions: Optional[List[str]] = None,
    ) -> bool:
        """Send a WhatsApp message with retry and exponential backoff."""
        if not all([
            getattr(self.settings, 'whatsapp_access_token', None),
            getattr(self.settings, 'whatsapp_phone_number_id', None),
        ]):
            self.logger.warning(f"WhatsApp not configured - message to {to_id} not sent")
            return True  # non-blocking in dev mode

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                url = (
                    f"{self.settings.whatsapp_api_url}"
                    f"/{self.settings.whatsapp_phone_number_id}/messages"
                )
                headers = {
                    "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                }

                data: dict = {
                    "messaging_product": "whatsapp",
                    "to": to_id,
                    "type": "text",
                    "text": {"body": content},
                }

                # WhatsApp interactive buttons (max 3)
                if suggested_actions and len(suggested_actions) <= 3:
                    data["type"] = "interactive"
                    data["interactive"] = {
                        "type": "button",
                        "body": {"text": content},
                        "action": {
                            "buttons": [
                                {
                                    "type": "reply",
                                    "reply": {"id": f"action_{i}", "title": action[:20]},
                                }
                                for i, action in enumerate(suggested_actions[:3])
                            ]
                        },
                    }

                response = await self.whatsapp_client.post(url, json=data, headers=headers)
                response.raise_for_status()

                self.logger.info(f"WhatsApp message sent to {to_id}")
                return True

            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"WhatsApp API error (attempt {attempt + 1}): "
                    f"{e.response.status_code} - {e.response.text}"
                )
                if e.response.status_code == 429:
                    retry_delay *= 2
                elif e.response.status_code < 500:
                    break  # don't retry client errors

            except Exception as e:
                self.logger.error(f"WhatsApp send failed (attempt {attempt + 1}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        ERROR_COUNTER.labels(error_type="whatsapp_send").inc()
        return False

    async def close(self):
        """Close HTTP clients."""
        await self.whatsapp_client.aclose()
