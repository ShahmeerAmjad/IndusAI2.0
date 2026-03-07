"""Seed sample inbound messages for demo/development."""

import json
import logging

logger = logging.getLogger(__name__)

SAMPLE_MESSAGES = [
    {
        "channel": "email", "from_address": "john.smith@acmemfg.com",
        "subject": "Need TDS for POLYOX WSR-301",
        "body": "Hi, can you send me the technical data sheet for POLYOX WSR-301? We're evaluating it for a new adhesive formulation.",
        "intents": [{"intent": "request_tds_sds", "confidence": 0.95, "text_span": "send me the technical data sheet for POLYOX WSR-301"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi John,\n\nThank you for your interest in POLYOX WSR-301. I've attached the Technical Data Sheet for your review.\n\nKey specs:\n- Appearance: White granular powder\n- Molecular Weight: ~4,000,000\n- Viscosity (5% solution): 1,650-5,500 cps\n\nPlease let me know if you need any additional information or would like to discuss your adhesive application in more detail.\n\nBest regards",
        "ai_confidence": 0.92,
    },
    {
        "channel": "email", "from_address": "sarah@pacificcoatings.com",
        "subject": "Quote for epoxy resin - 2000kg",
        "body": "Hello, we need a quote for 2000kg of your standard epoxy resin. Delivery to our Portland facility. PO terms NET30.",
        "intents": [{"intent": "request_quote", "confidence": 0.93, "text_span": "need a quote for 2000kg of your standard epoxy resin"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Sarah,\n\nThank you for your quote request. Based on your NET30 terms and the quantity of 2,000kg, here's our pricing:\n\n- Product: Standard Epoxy Resin\n- Quantity: 2,000 kg\n- Unit Price: $12.50/kg\n- Total: $25,000.00\n- Delivery: Portland facility, est. 5-7 business days\n\nThis quote is valid for 30 days. Shall I proceed with a formal quote document?\n\nBest regards",
        "ai_confidence": 0.88,
    },
    {
        "channel": "email", "from_address": "mike.chen@westlabsupply.com",
        "subject": "SDS needed - CAS 9003-11-6",
        "body": "We need the Safety Data Sheet for the product with CAS number 9003-11-6. Our safety team needs it for compliance audit.",
        "intents": [{"intent": "request_tds_sds", "confidence": 0.96, "text_span": "Safety Data Sheet for the product with CAS number 9003-11-6"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Mike,\n\nI've attached the Safety Data Sheet for CAS 9003-11-6 (Polyvinyl Alcohol). This is our most current revision.\n\nKey safety information:\n- GHS Classification: Not classified as hazardous\n- PPE: Safety glasses, gloves recommended for handling\n- Storage: Keep in dry, cool area\n\nPlease let me know if you need SDS documents for any other products.\n\nBest regards",
        "ai_confidence": 0.94,
    },
    {
        "channel": "web", "from_address": "lisa@greenchemsolutions.com",
        "subject": "Order status PO-78432",
        "body": "Can you check on the status of our order PO-78432? It was supposed to arrive yesterday.",
        "intents": [{"intent": "order_status", "confidence": 0.97, "text_span": "status of our order PO-78432"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Lisa,\n\nI've checked on PO-78432. The shipment was dispatched on March 3rd via FedEx Freight (tracking: 789456123). It appears there was a delay at the Memphis hub.\n\nCurrent estimated delivery: March 6th.\n\nI apologize for the inconvenience. I'll monitor this and update you if there are any further changes.\n\nBest regards",
        "ai_confidence": 0.85,
    },
    {
        "channel": "email", "from_address": "david.r@industrialtechcorp.com",
        "subject": "Technical question about high-temp lubricants",
        "body": "What viscosity grade do you recommend for continuous operation at 250C in a food-grade environment? We're looking at silicone-based options.",
        "intents": [{"intent": "technical_support", "confidence": 0.91, "text_span": "What viscosity grade do you recommend for continuous operation at 250C"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi David,\n\nFor continuous operation at 250\u00b0C in a food-grade environment, I'd recommend our Food-Grade Silicone Lubricant (ISO VG 100-150 range).\n\nKey specs:\n- Operating range: -40\u00b0C to 300\u00b0C\n- NSF H1 registered for food contact\n- Viscosity: 100 cSt at 40\u00b0C\n\nI'm attaching the TDS for your review. Would you like a sample to test in your application?\n\nBest regards",
        "ai_confidence": 0.87,
    },
    {
        "channel": "email", "from_address": "anna.k@northstarplastics.com",
        "subject": "Damaged shipment - need RMA",
        "body": "We received our order #ORD-5521 today and 3 drums were damaged during shipping. Product is leaking. We need a replacement or credit.",
        "intents": [{"intent": "return_complaint", "confidence": 0.96, "text_span": "3 drums were damaged during shipping. Product is leaking"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Anna,\n\nI'm sorry to hear about the damage to your order ORD-5521. We take shipping quality seriously.\n\nI've initiated an RMA for the 3 damaged drums:\n- RMA #: RMA-2026-0312\n- Pickup will be scheduled within 48 hours\n- Replacement shipment will be expedited at no charge\n\nCould you please send photos of the damaged drums for our carrier claim?\n\nBest regards",
        "ai_confidence": 0.90,
    },
    {
        "channel": "email", "from_address": "tom@precisionadhesives.com",
        "subject": "Reorder - same as last month",
        "body": "Hi, please process the same order as our last one from February. Same quantities, same shipping address.",
        "intents": [{"intent": "reorder", "confidence": 0.94, "text_span": "same order as our last one from February"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Tom,\n\nI've pulled up your February order. Here's what I have:\n\n- 500kg Epoxy Resin Base (SKU: ER-500)\n- 200kg Hardener H-100 (SKU: HD-100)\n- 50L Solvent Cleaner (SKU: SC-050)\n\nTotal: $8,750.00 (same pricing as February)\nShipping to: 1234 Industrial Pkwy, Portland OR\n\nShall I confirm this order?\n\nBest regards",
        "ai_confidence": 0.82,
    },
    {
        "channel": "email", "from_address": "nancy@coastalchemicals.com",
        "subject": "Credit limit inquiry",
        "body": "Hi, I'd like to know our current credit limit and outstanding balance. Also, can we increase our credit line?",
        "intents": [{"intent": "account_inquiry", "confidence": 0.93, "text_span": "current credit limit and outstanding balance"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi Nancy,\n\nHere's your account summary:\n\n- Credit Limit: $50,000\n- Outstanding Balance: $12,340\n- Available Credit: $37,660\n- Payment Terms: NET30\n\nRegarding a credit line increase, I'll forward your request to our credit team. They typically review within 2-3 business days.\n\nBest regards",
        "ai_confidence": 0.86,
    },
    {
        "channel": "web", "from_address": "james@advancedmaterials.co",
        "subject": "Sample request - silicone sealants",
        "body": "We're evaluating silicone sealants for our new product line. Can we get samples of your top 3 options for outdoor use?",
        "intents": [{"intent": "sample_request", "confidence": 0.95, "text_span": "get samples of your top 3 options for outdoor use"}],
        "status": "draft_ready",
        "ai_draft_response": "Hi James,\n\nI'd be happy to arrange samples for you. For outdoor silicone sealants, I recommend:\n\n1. WeatherSeal Pro 500 - UV resistant, -40 to 200\u00b0C\n2. FlexBond Outdoor 300 - High elongation, paintable\n3. UltraClear Sealant 100 - Transparent, mold resistant\n\nI'll ship 500ml samples of each to your facility. Expected delivery: 3-5 business days.\n\nCould you confirm your shipping address?\n\nBest regards",
        "ai_confidence": 0.91,
    },
    {
        "channel": "email", "from_address": "rachel@techpolymers.com",
        "subject": "Multiple requests",
        "body": "Hi, a few things:\n1. Please send the TDS for POLYOX WSR-205\n2. What's the status of our order PO-9921?\n3. We'd also like a quote for 1000kg of polyethylene glycol",
        "intents": [
            {"intent": "request_tds_sds", "confidence": 0.94, "text_span": "send the TDS for POLYOX WSR-205"},
            {"intent": "order_status", "confidence": 0.92, "text_span": "status of our order PO-9921"},
            {"intent": "request_quote", "confidence": 0.90, "text_span": "quote for 1000kg of polyethylene glycol"},
        ],
        "status": "draft_ready",
        "ai_draft_response": "Hi Rachel,\n\nHappy to help with all three requests:\n\n**1. TDS for POLYOX WSR-205**\nAttached to this email. Key specs: MW ~600,000, viscosity 4,500-8,800 cps (5% solution).\n\n**2. Order PO-9921 Status**\nYour order shipped March 2nd via UPS Freight. Tracking: 1Z999AA10. Estimated delivery: March 7th.\n\n**3. Quote for Polyethylene Glycol**\n- Product: PEG 400 (standard grade)\n- Quantity: 1,000 kg\n- Unit Price: $4.20/kg\n- Total: $4,200.00\n- Valid for 30 days\n\nPlease let me know if you'd like to proceed with the quote or need anything else.\n\nBest regards",
        "ai_confidence": 0.89,
    },
    {
        "channel": "email", "from_address": "pat@globalplastics.com",
        "subject": "Urgent - wrong product shipped",
        "body": "We ordered Epoxy Resin ER-500 but received ER-300 instead. This is urgent - our production line is waiting.",
        "intents": [{"intent": "return_complaint", "confidence": 0.97, "text_span": "wrong product shipped"}],
        "status": "new",
        "ai_draft_response": None,
        "ai_confidence": 0.0,
    },
    {
        "channel": "email", "from_address": "unclear@nowhere.com",
        "subject": "Hello",
        "body": "Can someone call me please? My number is 555-0123.",
        "intents": [{"intent": "general_query", "confidence": 0.45, "text_span": "Can someone call me please"}],
        "status": "classified",
        "ai_draft_response": None,
        "ai_confidence": 0.0,
    },
    {
        "channel": "web", "from_address": "buyer@newclient.com",
        "subject": "First time buyer",
        "body": "We're interested in becoming a customer. What's your minimum order quantity and do you offer NET60 terms?",
        "intents": [{"intent": "account_inquiry", "confidence": 0.78, "text_span": "minimum order quantity and do you offer NET60 terms"}],
        "status": "draft_ready",
        "ai_draft_response": "Welcome! We'd be happy to set up your account.\n\n- Minimum order: $500 or 50kg (whichever is reached first)\n- Standard terms: NET30 for new accounts\n- NET60 available after 6 months of on-time payments\n\nTo get started, I'll need:\n1. Company name and address\n2. Tax ID / EIN\n3. Primary contact info\n\nWould you like me to send our new customer application form?",
        "ai_confidence": 0.84,
    },
    {
        "channel": "email", "from_address": "procurement@bigcorp.com",
        "subject": "Annual contract renewal",
        "body": "Our annual supply agreement is up for renewal. We'd like to discuss volume discounts for next year. Current spend is approximately $2M.",
        "intents": [{"intent": "request_quote", "confidence": 0.85, "text_span": "discuss volume discounts for next year"}],
        "status": "escalated",
        "ai_draft_response": "Dear Procurement Team,\n\nThank you for your continued partnership. For an annual spend of $2M, we can offer tiered volume discounts. I'm escalating this to our Key Accounts Manager who can discuss customized pricing.\n\nYou can expect a call within 24 hours to schedule a review meeting.\n\nBest regards",
        "ai_confidence": 0.80,
    },
    {
        "channel": "email", "from_address": "lab@researchtec.edu",
        "subject": "Small quantity for research",
        "body": "We're a university research lab studying polymer degradation. Can we purchase 100g of POLYOX WSR-301 for research purposes?",
        "intents": [{"intent": "sample_request", "confidence": 0.82, "text_span": "purchase 100g of POLYOX WSR-301 for research purposes"}],
        "status": "draft_ready",
        "ai_draft_response": "Hello,\n\nWe'd be happy to support your research. For academic institutions, we offer research quantities at reduced pricing.\n\n- Product: POLYOX WSR-301\n- Quantity: 100g sample\n- Price: $25.00 (academic rate)\n- Shipping: Standard ground, free for academic orders\n\nI'll also include the TDS and SDS for your records. Please provide your university shipping address and a faculty contact.\n\nBest regards",
        "ai_confidence": 0.88,
    },
]


async def seed_inbox_messages(pool):
    """Insert sample inbound messages for demo purposes. Skips if already seeded."""
    if not pool:
        return

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM inbound_messages")
        if count > 0:
            logger.info("Inbox already seeded (%d messages), skipping", count)
            return

        for msg in SAMPLE_MESSAGES:
            await conn.execute(
                """INSERT INTO inbound_messages
                   (channel, from_address, subject, body, intents, status,
                    ai_draft_response, ai_confidence)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                msg["channel"], msg["from_address"], msg["subject"], msg["body"],
                json.dumps(msg["intents"]), msg["status"],
                msg["ai_draft_response"], msg["ai_confidence"],
            )

        logger.info("Seeded %d sample inbox messages", len(SAMPLE_MESSAGES))
