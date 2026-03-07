"""Auto-response engine for supplier sales emails.

Gathers per-intent context from Graph/DB, then calls Claude to draft
a cohesive response for human review. Never auto-sends.
"""

import logging
from typing import Any

from services.ai.models import EntityResult, IntentType, MultiIntentResult

logger = logging.getLogger(__name__)

# Module-level DI
_response_engine = None


def set_response_engine(engine):
    global _response_engine
    _response_engine = engine


def get_response_engine():
    return _response_engine


# Intent → handler method name mapping
_INTENT_HANDLERS: dict[IntentType, str] = {
    IntentType.REQUEST_TDS_SDS: "_gather_tds_sds",
    IntentType.REQUEST_QUOTE: "_gather_quote",
    IntentType.PLACE_ORDER: "_gather_place_order",
    IntentType.ORDER_STATUS: "_gather_order_status",
    IntentType.TECHNICAL_SUPPORT: "_gather_technical",
    IntentType.RETURN_COMPLAINT: "_gather_return",
    IntentType.REORDER: "_gather_reorder",
    IntentType.ACCOUNT_INQUIRY: "_gather_account",
    IntentType.SAMPLE_REQUEST: "_gather_sample",
}

_SYSTEM_PROMPT = """\
You are a professional customer service representative for an industrial \
parts supplier. Draft a helpful, concise email response addressing ALL of \
the customer's requests. Be polite but efficient. If data is missing or \
unavailable, acknowledge it and offer to follow up.

Do NOT include a subject line. Start with a greeting and end with a \
professional sign-off."""

_USER_PROMPT_TEMPLATE = """\
Customer email:
---
{body}
---

Customer account: {customer_account}

Detected intents and gathered context:
{context_block}

Draft a response addressing all the above intents."""


class AutoResponseEngine:
    """Generate AI draft responses for classified inbound emails."""

    def __init__(self, graph_service=None, tds_sds_service=None,
                 llm_router=None, db_manager=None):
        self._graph = graph_service
        self._tds_sds = tds_sds_service
        self._llm = llm_router
        self._db = db_manager

    async def generate_draft(
        self,
        body: str,
        classification: MultiIntentResult,
        customer_account: str | None = None,
    ) -> dict[str, Any]:
        """Generate a draft response for a classified email.

        Returns:
            {response_text, attachments, confidence, metadata}
        """
        if not classification.intents:
            return {
                "response_text": "",
                "attachments": [],
                "confidence": 0.0,
                "metadata": {"error": "no_intents_detected"},
            }

        entities = classification.entities
        contexts: list[dict[str, Any]] = []
        attachments: list[str] = []

        # Gather context for each intent
        for intent_result in classification.intents:
            handler_name = _INTENT_HANDLERS.get(intent_result.intent)
            if not handler_name:
                contexts.append({
                    "intent": intent_result.intent.value,
                    "context": "No handler for this intent type.",
                })
                continue

            handler = getattr(self, handler_name)
            try:
                ctx = await handler(entities, customer_account)
            except Exception as exc:
                logger.warning("Handler %s failed: %s", handler_name, exc)
                ctx = {"error": f"Failed to gather context: {exc}"}

            contexts.append({
                "intent": intent_result.intent.value,
                "context": ctx,
            })

            # Collect attachments from context
            if isinstance(ctx, dict):
                for att in ctx.get("attachments", []):
                    if att not in attachments:
                        attachments.append(att)

        # Build context block for LLM prompt
        context_block = "\n\n".join(
            f"Intent: {c['intent']}\nContext: {c['context']}"
            for c in contexts
        )

        # Calculate confidence
        confidence = self._calculate_confidence(classification, contexts)

        # Generate response via LLM
        response_text = await self._generate_llm_response(
            body, customer_account or "Unknown", context_block
        )

        return {
            "response_text": response_text,
            "attachments": attachments,
            "confidence": confidence,
            "metadata": {
                "intents": [c["intent"] for c in contexts],
                "context_summary": contexts,
            },
        }

    def _calculate_confidence(
        self, classification: MultiIntentResult, contexts: list[dict]
    ) -> float:
        """Confidence = mean(intent confidences) × data_found_factor."""
        if not classification.intents:
            return 0.0

        mean_confidence = sum(
            r.confidence for r in classification.intents
        ) / len(classification.intents)

        # Check if context gathering found useful data
        errors = sum(
            1 for c in contexts
            if isinstance(c.get("context"), dict) and "error" in c["context"]
        )
        if errors == len(contexts):
            data_factor = 0.5
        elif errors > 0:
            data_factor = 0.75
        else:
            data_factor = 1.0

        return round(min(mean_confidence * data_factor, 1.0), 3)

    async def _generate_llm_response(
        self, body: str, customer_account: str, context_block: str
    ) -> str:
        """Call LLM to draft the response."""
        if self._llm is None:
            return "[LLM unavailable — manual response required]"

        prompt = _USER_PROMPT_TEMPLATE.format(
            body=body,
            customer_account=customer_account,
            context_block=context_block,
        )

        try:
            return await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=_SYSTEM_PROMPT,
                task="response_generation",
                max_tokens=1024,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("LLM response generation failed: %s", exc)
            return "[Draft generation failed — manual response required]"

    # ------------------------------------------------------------------
    # Per-intent context gatherers
    # ------------------------------------------------------------------

    async def _gather_tds_sds(self, entities: EntityResult, _account) -> dict:
        """Gather TDS/SDS documents for mentioned products."""
        results = []
        attachments = []

        skus = entities.part_numbers or []
        # Also try CAS number lookup if no SKUs
        if not skus and entities.cas_numbers and self._graph:
            for cas in entities.cas_numbers:
                try:
                    parts = await self._graph.search_parts_fulltext(cas, limit=3)
                    for p in parts:
                        node = p.get("node", p)
                        sku = node.get("sku")
                        if sku and sku not in skus:
                            skus.append(sku)
                except Exception:
                    pass

        for sku in skus:
            entry = {"sku": sku, "tds": None, "sds": None}
            if self._tds_sds:
                try:
                    tds = await self._tds_sds.get_tds_properties(sku)
                    if tds:
                        entry["tds"] = tds
                        props = tds.get("props", tds)
                        if isinstance(props, dict) and props.get("pdf_url"):
                            attachments.append(props["pdf_url"])
                except Exception as exc:
                    entry["tds"] = {"error": str(exc)}

                try:
                    sds = await self._tds_sds.get_sds_properties(sku)
                    if sds:
                        entry["sds"] = sds
                        props = sds.get("props", sds)
                        if isinstance(props, dict) and props.get("pdf_url"):
                            attachments.append(props["pdf_url"])
                except Exception as exc:
                    entry["sds"] = {"error": str(exc)}
            else:
                entry["tds"] = {"error": "TDS/SDS service unavailable"}
                entry["sds"] = {"error": "TDS/SDS service unavailable"}
            results.append(entry)

        if not results:
            return {"info": "No product identifiers found in email", "attachments": []}
        return {"products": results, "attachments": attachments}

    async def _gather_quote(self, entities: EntityResult, customer_account) -> dict:
        """Gather pricing info for a quote request."""
        products = []
        for sku in entities.part_numbers:
            product_info = await self._lookup_part(sku)
            qty = entities.quantities.get(sku)
            products.append({
                "sku": sku,
                "product": product_info,
                "requested_qty": qty,
            })
        return {
            "products": products,
            "customer": customer_account,
            "note": "Quote requires pricing team approval before sending.",
        }

    async def _gather_place_order(self, entities: EntityResult, customer_account) -> dict:
        """Gather context for a purchase order."""
        products = []
        for sku in entities.part_numbers:
            product_info = await self._lookup_part(sku)
            qty = entities.quantities.get(sku)
            products.append({"sku": sku, "product": product_info, "qty": qty})
        return {
            "products": products,
            "po_numbers": entities.po_numbers,
            "customer": customer_account,
            "note": "Order must be confirmed in ERP before acknowledging.",
        }

    async def _gather_order_status(self, entities: EntityResult, _account) -> dict:
        """Gather order/PO status."""
        orders = entities.order_numbers or entities.po_numbers or []
        if not orders:
            return {"info": "No order/PO number found in email. Ask customer for reference."}

        # In MVP, we don't have real ERP order lookup — return what we know
        return {
            "order_references": orders,
            "note": "Order status lookup requires ERP integration (future). "
                    "Draft should acknowledge receipt and promise follow-up.",
        }

    async def _gather_technical(self, entities: EntityResult, _account) -> dict:
        """Gather technical data for support questions."""
        products = []
        for sku in entities.part_numbers:
            product_info = await self._lookup_part(sku)
            tds_info = None
            if self._tds_sds:
                try:
                    tds_info = await self._tds_sds.get_tds_properties(sku)
                except Exception:
                    pass
            products.append({"sku": sku, "product": product_info, "tds": tds_info})
        return {"products": products}

    async def _gather_return(self, entities: EntityResult, customer_account) -> dict:
        """Gather context for return/complaint."""
        return {
            "order_references": entities.order_numbers or entities.po_numbers or [],
            "products": entities.part_numbers,
            "customer": customer_account,
            "note": "Returns require RMA number. Draft should acknowledge issue "
                    "and explain RMA process.",
        }

    async def _gather_reorder(self, entities: EntityResult, customer_account) -> dict:
        """Gather context for a reorder request."""
        return {
            "customer": customer_account,
            "note": "Reorder requires looking up customer's last order in ERP. "
                    "Draft should confirm intent and ask for any quantity changes.",
        }

    async def _gather_account(self, entities: EntityResult, customer_account) -> dict:
        """Gather account/billing context."""
        return {
            "customer": customer_account,
            "note": "Account inquiries require finance team involvement. "
                    "Draft should acknowledge and route to billing.",
        }

    async def _gather_sample(self, entities: EntityResult, _account) -> dict:
        """Gather context for a sample request."""
        products = []
        for sku in entities.part_numbers:
            product_info = await self._lookup_part(sku)
            products.append({"sku": sku, "product": product_info})
        return {
            "products": products,
            "note": "Sample requests need sales manager approval.",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _lookup_part(self, sku: str) -> dict | None:
        """Look up a part in the graph. Returns None if unavailable."""
        if not self._graph:
            return None
        try:
            return await self._graph.get_part(sku)
        except Exception as exc:
            logger.debug("Part lookup failed for %s: %s", sku, exc)
            return None
