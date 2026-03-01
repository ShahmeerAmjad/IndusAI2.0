# =======================
# Business Logic - Message Routing and Response Generation
# =======================
"""
Routes classified messages to intent-specific handlers.
Now backed by real platform services (product catalog, inventory,
pricing, orders, quotes, RMA) instead of hardcoded responses.
"""

import logging
import re
from typing import Any, Dict, Optional

from models.models import BotResponse, CustomerMessage, MessageType

logger = logging.getLogger(__name__)


class BusinessLogic:
    def __init__(self, ai_service, db_manager, settings, escalation_service,
                 product_service=None, inventory_service=None,
                 pricing_service=None, order_service=None,
                 quote_service=None, customer_service=None, rma_service=None,
                 query_engine=None):
        self.ai_service = ai_service
        self.db_manager = db_manager
        self.settings = settings
        self.escalation_service = escalation_service
        # Platform services
        self.products = product_service
        self.inventory = inventory_service
        self.pricing = pricing_service
        self.orders = order_service
        self.quotes = quote_service
        self.customers = customer_service
        self.rma = rma_service
        self.query_engine = query_engine

    async def process_message(self, message: CustomerMessage, conversation_history: list = None) -> BotResponse:
        """Route a classified message to the appropriate handler and return a response."""

        # Fetch or create session context
        session = await self.db_manager.get_customer_session(message.from_id)
        context = session or {"message_count": 0}
        context["message_count"] = context.get("message_count", 0) + 1
        if conversation_history:
            context["conversation_history"] = conversation_history

        # Ensure customer record exists
        if self.customers:
            await self.customers.find_or_create_customer(message.from_id)

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

        metadata: Dict[str, Any] = {}

        if order_number and self.orders:
            # Try exact match then padded match
            order = await self.orders.get_order_by_number(f"ORD-{order_number.zfill(6)}")
            if not order:
                order = await self.orders.get_order_by_number(order_number)

            if order:
                status = order["status"]
                total = order.get("total_amount", 0)
                line_count = len(order.get("lines", []))
                content = (
                    f"Order #{order['order_number']} status: **{status.upper()}**\n"
                    f"- Items: {line_count} line(s)\n"
                    f"- Total: ${total:,.2f}\n"
                    f"- Payment terms: {order.get('payment_terms', 'N/A')}\n"
                )
                if order.get("shipped_at"):
                    content += f"- Shipped: {order['shipped_at'][:10]}\n"
                if order.get("required_date"):
                    content += f"- Required by: {order['required_date'][:10]}\n"
                for line in order.get("lines", [])[:5]:
                    content += f"  - {line['sku']}: {line.get('product_name', '')} (qty: {line['quantity']})\n"

                metadata = {"order_id": order["id"], "order_number": order["order_number"]}
            else:
                content = (
                    f"I couldn't find order #{order_number} in our system. "
                    f"Please verify the order or PO number and try again. "
                    f"You can find it in your order confirmation email or invoice."
                )
        elif order_number:
            content = (
                f"I'm looking up order #{order_number}. "
                f"Your order is currently in processing and is scheduled to ship within 2-3 business days. "
                f"You'll receive tracking information via email once it ships."
            )
        else:
            # Show recent orders for the customer
            customer_orders = []
            if self.orders and self.customers:
                cust = await self.customers.get_customer_by_external_id(message.from_id)
                if cust:
                    customer_orders, _ = await self.orders.list_orders(
                        customer_id=cust["id"], page_size=5,
                    )

            if customer_orders:
                content = "Here are your recent orders:\n\n"
                for o in customer_orders:
                    content += f"- **{o['order_number']}**: {o['status']} — ${o.get('total_amount', 0):,.2f}\n"
                content += "\nWhich order would you like details on?"
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
            metadata=metadata,
        )

    async def _handle_product_inquiry(self, message: CustomerMessage, context: Dict) -> BotResponse:
        # Try GraphRAG first if available
        if self.query_engine:
            try:
                result = await self.query_engine.process_query(message.content)
                if result.parts_found > 0:
                    return BotResponse(
                        content=result.response,
                        suggested_actions=["Get quote", "Check availability", "View cross-references"],
                        metadata={"graph_paths": result.graph_paths, "parts_found": result.parts_found},
                    )
            except Exception as e:
                logger.warning("GraphRAG product inquiry failed, falling back: %s", e)

        product_match = re.search(
            r'(?:product|item|sku|part|model)\s*[\-#]?\s*([A-Z0-9\-]+)', message.content, re.I
        )
        mro_match = re.search(r'(MRO-[A-Z0-9\-]+)', message.content, re.I)
        sku_to_find = None
        if mro_match:
            sku_to_find = mro_match.group(1).upper()
        elif product_match:
            sku_to_find = product_match.group(1).upper()

        metadata: Dict[str, Any] = {}

        if sku_to_find and self.products:
            product = await self.products.get_product_by_sku(sku_to_find)
            if product:
                content = f"**{product['name']}** (SKU: {product['sku']})\n\n"
                if product.get("description"):
                    content += f"{product['description']}\n\n"
                content += f"- Manufacturer: {product.get('manufacturer', 'N/A')}\n"
                content += f"- Mfr Part #: {product.get('manufacturer_part_number', 'N/A')}\n"
                content += f"- UOM: {product.get('uom', 'EA')}\n"
                content += f"- Min Order Qty: {product.get('min_order_qty', 1)}\n"
                content += f"- Lead Time: {product.get('lead_time_days', 'N/A')} days\n"

                if product.get("specs"):
                    content += "\n**Specifications:**\n"
                    for spec in product["specs"][:8]:
                        unit = f" {spec['unit']}" if spec.get("unit") else ""
                        content += f"  - {spec['name']}: {spec['value']}{unit}\n"

                if product.get("cross_references"):
                    content += "\n**Compatible/Alternative Parts:**\n"
                    for xref in product["cross_references"]:
                        content += f"  - {xref['cross_ref_type'].title()}: {xref['cross_ref_sku']}"
                        if xref.get("manufacturer"):
                            content += f" ({xref['manufacturer']})"
                        content += "\n"

                # Check stock
                if self.inventory:
                    stock = await self.inventory.get_stock(product["id"])
                    if stock:
                        avail = stock.get("quantity_available", 0)
                        content += f"\n**Availability:** {'In Stock' if avail > 0 else 'Out of Stock'}"
                        if avail > 0:
                            content += f" ({int(avail)} available)"
                        content += "\n"

                metadata = {"product_id": product["id"], "sku": product["sku"]}
            else:
                results, total = await self.products.search_products(query=sku_to_find, page_size=5)
                if results:
                    content = f"I didn't find an exact match for '{sku_to_find}', but here are similar products:\n\n"
                    for p in results:
                        content += f"- **{p['sku']}**: {p['name']} ({p.get('category', '')})\n"
                    content += "\nWould you like details on any of these?"
                else:
                    content = (
                        f"I couldn't find product '{sku_to_find}' in our catalog. "
                        f"Could you double-check the SKU or part number? "
                        f"I can also search by product name or category."
                    )
        elif self.products:
            # General inquiry — keyword search
            keywords = message.content.lower()
            search_terms = []
            for word in keywords.split():
                if word not in ("product", "item", "part", "about", "tell", "me", "the",
                                "what", "is", "do", "you", "have", "any", "need", "looking",
                                "for", "info", "information", "details", "can", "help", "i"):
                    search_terms.append(word)

            search_query = " ".join(search_terms[:3]) if search_terms else None
            if search_query:
                results, total = await self.products.search_products(query=search_query, page_size=5)
                if results:
                    content = f"Here are products matching '{search_query}':\n\n"
                    for p in results:
                        content += f"- **{p['sku']}**: {p['name']} ({p.get('category', '')})\n"
                    content += f"\n{total} total results. Would you like details on any of these?"
                else:
                    content = (
                        f"I couldn't find products matching '{search_query}'. "
                        f"Our MRO catalog includes bearings, filters, belts, lubricants, "
                        f"safety equipment, motors, fasteners, pumps, and welding supplies. "
                        f"What specific product or category are you looking for?"
                    )
            else:
                content = (
                    "I can help you find product information. Our MRO catalog includes:\n"
                    "- Bearings & Power Transmission\n- Filters & Hydraulics\n"
                    "- Lubricants & Chemicals\n- Safety / PPE Equipment\n"
                    "- Motors & Drives\n- Fasteners & Hardware\n"
                    "- Pumps & Plumbing\n- Welding Supplies\n\n"
                    "What category or product are you interested in?"
                )
        else:
            content = (
                "I can help you find product information. "
                "Please provide a SKU, part number, or describe what you're looking for."
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Browse catalog", "Get quote", "Check availability"],
            metadata=metadata,
        )

    async def _handle_price_request(self, message: CustomerMessage, context: Dict) -> BotResponse:
        product_match = re.search(
            r'(?:product|item|sku|part|model)\s*[\-#]?\s*([A-Z0-9\-]+)', message.content, re.I
        )
        mro_match = re.search(r'(MRO-[A-Z0-9\-]+)', message.content, re.I)
        sku_to_find = None
        if mro_match:
            sku_to_find = mro_match.group(1).upper()
        elif product_match:
            sku_to_find = product_match.group(1).upper()

        qty_match = re.search(r'(\d+)\s*(?:units?|pcs?|pieces?|qty|each)', message.content, re.I)
        qty = float(qty_match.group(1)) if qty_match else 1

        metadata: Dict[str, Any] = {}

        if sku_to_find and self.products and self.pricing:
            product = await self.products.get_product_by_sku(sku_to_find)
            if product:
                customer_id = None
                if self.customers:
                    cust = await self.customers.get_customer_by_external_id(message.from_id)
                    if cust:
                        customer_id = cust["id"]

                pricing = await self.pricing.get_price(product["id"], customer_id, qty)

                content = f"**Pricing for {product['name']}** (SKU: {product['sku']})\n\n"
                content += f"- List Price: ${pricing.get('list_price', 0):,.2f}\n"
                if pricing.get("discount_percent", 0) > 0:
                    content += f"- Your Price: ${pricing.get('customer_price', 0):,.2f} ({pricing['discount_percent']}% discount)\n"
                else:
                    content += f"- Unit Price: ${pricing.get('customer_price', 0):,.2f}\n"
                content += f"- Quantity: {int(qty)}\n"
                content += f"- **Total: ${pricing.get('total_price', 0):,.2f}**\n"
                if pricing.get("contract_number"):
                    content += f"- Contract: {pricing['contract_number']}\n"

                if qty == 1:
                    tiers = await self.pricing.get_bulk_pricing(product["id"], customer_id)
                    if len(tiers) > 1:
                        content += "\n**Volume Pricing:**\n"
                        for tier in tiers[:5]:
                            content += f"  - {int(tier['quantity'])}+: ${tier['customer_price']:,.2f}/ea\n"

                metadata = {"product_id": product["id"], "sku": sku_to_find}
            else:
                content = (
                    f"I couldn't find product '{sku_to_find}' for pricing. "
                    f"Please verify the SKU or part number."
                )
        else:
            content = (
                "I'd be happy to help with pricing. "
                "Please share the product SKU or part number and quantity needed. "
                "I can provide your customer-specific pricing including any contract discounts. "
                "We also offer volume discounts on larger orders."
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Request formal quote", "View bulk pricing", "Speak to sales rep"],
            metadata=metadata,
        )

    async def _handle_technical_support(self, message: CustomerMessage, context: Dict) -> BotResponse:
        urgent_keywords = ['urgent', 'emergency', 'critical', 'asap', 'immediately', 'down', 'safety']
        is_urgent = any(word in message.content.lower() for word in urgent_keywords)

        support_phone = getattr(self.settings, 'support_phone', '1-800-TECH-HELP')

        if is_urgent:
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
            # Try GraphRAG for technical spec questions
            if self.query_engine:
                try:
                    result = await self.query_engine.process_query(message.content)
                    if result.parts_found > 0:
                        return BotResponse(
                            content=result.response,
                            suggested_actions=["View specs", "Find alternatives", "Contact engineer"],
                        )
                except Exception:
                    pass  # Fall through to existing handlers

            mro_match = re.search(r'(MRO-[A-Z0-9\-]+)', message.content, re.I)
            product_context = ""
            if mro_match and self.products:
                product = await self.products.get_product_by_sku(mro_match.group(1).upper())
                if product:
                    product_context = f" for your {product['name']}"

            if any(kw in message.content.lower() for kw in ['install', 'setup', 'configure']):
                content = (
                    f"I can help with installation and setup{product_context}. "
                    "Please provide the product model number and describe what step you're on. "
                    "I can guide you through the process or connect you with a technician."
                )
            elif any(kw in message.content.lower() for kw in ['maintenance', 'service', 'schedule']):
                content = (
                    f"I can help with maintenance scheduling{product_context}. "
                    "Please provide the equipment model and serial number, "
                    "and I'll look up the recommended maintenance schedule and any open service bulletins."
                )
            else:
                content = (
                    "I'm here to help resolve your technical issue. "
                    "Could you please provide:\n"
                    "1. Product model number or SKU\n"
                    "2. Description of the problem\n"
                    "3. Any error messages or codes\n"
                    "This will help me provide the most accurate assistance."
                )
            escalate = False

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Describe issue", "Schedule callback", "View troubleshooting guide"],
            escalate=escalate,
        )

    async def _handle_returns(self, message: CustomerMessage, context: Dict) -> BotResponse:
        order_match = re.search(r'(?:order|po|#)\s*[\-#]?\s*(\d+)', message.content.lower())
        metadata: Dict[str, Any] = {}

        if order_match and self.orders:
            order_number = order_match.group(1)
            order = await self.orders.get_order_by_number(f"ORD-{order_number.zfill(6)}")
            if not order:
                order = await self.orders.get_order_by_number(order_number)

            if order:
                if order["status"] in ("shipped", "delivered"):
                    content = (
                        f"I can help with a return for order #{order['order_number']}.\n\n"
                        f"**Order Details:**\n"
                        f"- Status: {order['status']}\n"
                        f"- Total: ${order.get('total_amount', 0):,.2f}\n- Items:\n"
                    )
                    for line in order.get("lines", [])[:5]:
                        content += f"  - {line['sku']}: {line.get('product_name', '')} (qty: {line['quantity']})\n"
                    content += (
                        "\nOur return policy allows returns within 30 days of delivery. "
                        "Please confirm which items you'd like to return and the reason "
                        "(defective, wrong item, damaged, not needed, warranty)."
                    )
                    metadata = {"order_id": order["id"]}
                else:
                    content = (
                        f"Order #{order['order_number']} is in '{order['status']}' status. "
                        f"Returns can only be initiated for shipped or delivered orders."
                    )
                    if order["status"] in ("draft", "submitted", "confirmed"):
                        content += " Would you like to cancel this order instead?"
            else:
                content = (
                    f"I couldn't find order #{order_number}. "
                    "Please verify the order number and try again."
                )
        elif order_match:
            order_number = order_match.group(1)
            content = (
                f"I can help you with a return for order #{order_number}. "
                f"Our return policy allows returns within 30 days of delivery for most items. "
                f"I'll initiate an RMA for you. "
                f"Please confirm the items you'd like to return and the reason."
            )
        else:
            recent_orders = []
            if self.orders and self.customers:
                cust = await self.customers.get_customer_by_external_id(message.from_id)
                if cust:
                    orders_list, _ = await self.orders.list_orders(
                        customer_id=cust["id"], status="delivered", page_size=5,
                    )
                    recent_orders = orders_list

            if recent_orders:
                content = "Here are your recent delivered orders eligible for return:\n\n"
                for o in recent_orders:
                    content += f"- **{o['order_number']}**: ${o.get('total_amount', 0):,.2f}\n"
                content += "\nWhich order would you like to return items from?"
            else:
                content = (
                    "I can assist with returns and exchanges. "
                    "Please provide your order number and let me know which items you'd like to return. "
                    "Our standard return policy covers 30 days from delivery."
                )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Start return", "Check warranty", "Exchange item"],
            metadata=metadata,
        )

    async def _handle_general_query(self, message: CustomerMessage, context: Dict) -> BotResponse:
        if context.get("message_count", 0) > 1:
            content = (
                "Welcome back! I'm your MRO platform assistant. I can help with:\n"
                "- **Order tracking** — Check order status, delivery updates\n"
                "- **Product search** — Browse catalog, specs, availability\n"
                "- **Pricing & quotes** — Customer-specific pricing, volume discounts\n"
                "- **Technical support** — Installation, troubleshooting\n"
                "- **Returns** — RMA requests, warranty claims\n\n"
                "What can I help you with today?"
            )
        else:
            content = (
                "Hello! Welcome to the MRO Platform. "
                "I'm your AI-powered assistant for industrial supply operations.\n\n"
                "I can help with:\n"
                "- **Orders** — Place, track, and manage orders\n"
                "- **Products** — Search catalog, check specs & availability\n"
                "- **Pricing** — Get quotes with your contract pricing\n"
                "- **Technical support** — Installation and troubleshooting\n"
                "- **Returns** — Start returns and warranty claims\n\n"
                "How can I help you today?"
            )

        enhanced = await self.ai_service.enhance_response(message.content, content, context)
        return BotResponse(
            content=enhanced,
            suggested_actions=["Check order", "Browse products", "Get quote", "Get support"],
        )
