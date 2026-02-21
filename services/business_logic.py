# =======================
# Business Logic - Message Routing and Response Generation
# =======================

import re
from typing import Dict

from models.models import BotResponse, CustomerMessage, MessageType


class BusinessLogic:
    def __init__(self, ai_service, db_manager, settings, escalation_service):
        self.ai_service = ai_service
        self.db_manager = db_manager
        self.settings = settings
        self.escalation_service = escalation_service

    async def process_message(self, message: CustomerMessage) -> BotResponse:
        """Route a classified message to the appropriate handler and return a response."""

        # Fetch or create session context
        session = await self.db_manager.get_customer_session(message.from_id)
        context = session or {"message_count": 0}
        context["message_count"] = context.get("message_count", 0) + 1

        handler = {
            MessageType.ORDER_STATUS: self._handle_order_status,
            MessageType.PRODUCT_INQUIRY: self._handle_product_inquiry,
            MessageType.PRICE_REQUEST: self._handle_price_request,
            MessageType.TECHNICAL_SUPPORT: self._handle_technical_support,
            MessageType.RETURNS: self._handle_returns,
        }.get(message.message_type, self._handle_general_query)

        response = await handler(message, context)

        # Persist session
        await self.db_manager.save_customer_session(message.from_id, context)

        return response

    # ------ Intent handlers ------

    async def _handle_order_status(self, message: CustomerMessage, context: Dict) -> BotResponse:
        order_patterns = [
            r'(?:order|po|#)\s*[\-#]?\s*(\d+)',
            r'(\d{5,})',
        ]

        order_number = None
        for pattern in order_patterns:
            match = re.search(pattern, message.content.lower())
            if match:
                order_number = match.group(1)
                break

        if order_number:
            # TODO: integrate with ERP/order management system
            content = (
                f"I'm checking the status of order #{order_number}. "
                f"Your order is currently in processing and is scheduled to ship within 2-3 business days. "
                f"You'll receive tracking information via email once it ships. "
                f"Estimated delivery is 5-7 business days from ship date."
            )
        else:
            content = (
                "I'd be happy to help you check your order status. "
                "Could you please provide your order number or PO number? "
                "You can find it in your order confirmation email or invoice."
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Check another order", "Update delivery address", "Contact support"],
        )

    async def _handle_product_inquiry(self, message: CustomerMessage, context: Dict) -> BotResponse:
        product_match = re.search(
            r'(?:product|item|sku|part|model)\s*[\-#]?\s*([A-Z0-9\-]+)', message.content, re.I
        )

        if product_match:
            product_id = product_match.group(1)
            content = (
                f"I can help you with information about {product_id}. "
                f"This product is part of our industrial MRO equipment line. "
                f"For detailed specifications, current pricing, and lead times, "
                f"I can connect you with a product specialist or send you the full datasheet."
            )
        else:
            content = (
                "I can help you find product information. Our MRO catalog includes "
                "industrial equipment, safety supplies, tools, electrical components, "
                "fasteners, and maintenance products. "
                "What specific product or category are you interested in?"
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Browse catalog", "Get quote", "Check availability", "Request datasheet"],
        )

    async def _handle_price_request(self, message: CustomerMessage, context: Dict) -> BotResponse:
        product_match = re.search(
            r'(?:product|item|sku|part|model)\s*[\-#]?\s*([A-Z0-9\-]+)', message.content, re.I
        )

        if product_match:
            product_id = product_match.group(1)
            content = (
                f"I'll get you pricing for {product_id}. "
                f"For the most accurate pricing including any volume discounts or contract rates, "
                f"I can generate a formal quote. "
                f"Could you let me know the quantity you need?"
            )
        else:
            content = (
                "I'd be happy to help with pricing. "
                "Please share the product name, SKU, or part number you'd like a quote for, "
                "along with the quantity needed. "
                "We offer volume discounts on orders of 10+ units."
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Request formal quote", "View bulk pricing", "Speak to sales rep"],
        )

    async def _handle_technical_support(self, message: CustomerMessage, context: Dict) -> BotResponse:
        urgent_keywords = ['urgent', 'emergency', 'critical', 'asap', 'immediately', 'down', 'safety']
        is_urgent = any(word in message.content.lower() for word in urgent_keywords)

        support_phone = getattr(self.settings, 'support_phone', '1-800-TECH-HELP')
        support_email = getattr(self.settings, 'support_email', 'support@company.com')

        if is_urgent:
            # Create an escalation ticket
            await self.escalation_service.create_ticket(
                customer_id=message.from_id,
                subject=f"URGENT: {message.content[:100]}",
                description=message.content,
                priority="critical",
            )
            content = (
                "I understand this is an urgent technical issue. "
                "I've created a priority support ticket and our technical team has been notified. "
                f"A specialist will contact you within 15 minutes. "
                f"For immediate assistance, call our 24/7 support line at {support_phone}."
            )
            escalate = True
        else:
            if any(kw in message.content.lower() for kw in ['install', 'setup', 'configure']):
                content = (
                    "I can help with installation and setup. "
                    "Please provide the product model number and describe what step you're on. "
                    "I can guide you through the process or connect you with a technician."
                )
            elif any(kw in message.content.lower() for kw in ['maintenance', 'service', 'schedule']):
                content = (
                    "I can help you with maintenance scheduling and service information. "
                    "Please provide the equipment model and serial number, "
                    "and I'll look up the recommended maintenance schedule and any open service bulletins."
                )
            else:
                content = (
                    "I'm here to help resolve your technical issue. "
                    "Could you please provide:\n"
                    "1. Product model number\n"
                    "2. Description of the problem\n"
                    "3. Any error messages or codes\n"
                    "This will help me provide the most accurate assistance."
                )
            escalate = False

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Describe issue", "Schedule callback", "View troubleshooting guide", "Emergency support"],
            escalate=escalate,
        )

    async def _handle_returns(self, message: CustomerMessage, context: Dict) -> BotResponse:
        order_match = re.search(r'(?:order|po|#)\s*[\-#]?\s*(\d+)', message.content.lower())

        if order_match:
            order_number = order_match.group(1)
            content = (
                f"I can help you with a return for order #{order_number}. "
                f"Our return policy allows returns within 30 days of delivery for most items. "
                f"I'll initiate an RMA (Return Merchandise Authorization) for you. "
                f"Please confirm the items you'd like to return and the reason."
            )
        else:
            content = (
                "I can assist with returns and exchanges. "
                "Please provide your order number and let me know which items you'd like to return. "
                "Our standard return policy covers 30 days from delivery, "
                "and warranty claims are handled separately."
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Start return", "Check warranty", "Exchange item", "Contact support"],
        )

    async def _handle_general_query(self, message: CustomerMessage, context: Dict) -> BotResponse:
        if context.get("message_count", 0) > 1:
            content = (
                "Welcome back! I'm here to help with any questions you have. "
                "I can assist with:\n"
                "- Order tracking and status updates\n"
                "- Product information, specs, and pricing\n"
                "- Technical support and troubleshooting\n"
                "- Returns and warranty claims\n"
                "- Quote requests and bulk pricing\n\n"
                "What can I help you with today?"
            )
        else:
            content = (
                "Hello! Welcome to our MRO support center. "
                "I'm here to help with your industrial supply needs. I can assist with:\n"
                "- Order status and tracking\n"
                "- Product information and pricing\n"
                "- Technical support\n"
                "- Returns and exchanges\n"
                "- Quote requests\n\n"
                "How can I help you today?"
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Check order", "Browse products", "Get support", "Request quote"],
        )
