"""Multi-intent classifier for supplier sales emails.

Detects ALL matching intents in a single message (not just the best one),
runs entity extraction, and falls back to LLM for ambiguous cases.
"""

import json
import logging
import re

from services.ai.entity_extractor import EntityExtractor
from services.ai.models import (
    EntityResult,
    IntentResult,
    IntentType,
    MultiIntentResult,
)

logger = logging.getLogger(__name__)

# Module-level DI
_classifier = None


def set_classifier(classifier):
    global _classifier
    _classifier = classifier


def get_classifier():
    return _classifier


# ---------------------------------------------------------------------------
# 9 Intent pattern groups
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[IntentType, list[re.Pattern]] = {
    IntentType.REQUEST_TDS_SDS: [
        re.compile(r'\b(?:sds|tds|msds)\b', re.I),
        re.compile(r'\b(?:safety\s+data\s+sheet|technical\s+data\s*(?:sheet)?)\b', re.I),
        re.compile(r'\bdatasheet\b', re.I),
        re.compile(r'\b(?:material\s+safety)\b', re.I),
    ],
    IntentType.REQUEST_QUOTE: [
        re.compile(r'\b(?:quote|pricing|price)\b', re.I),
        re.compile(r'\bhow\s+much\b', re.I),
        re.compile(r'\b(?:cost|estimate|bid)\b', re.I),
        re.compile(r'\brequest\s+(?:a\s+)?(?:quote|pricing)\b', re.I),
    ],
    IntentType.PLACE_ORDER: [
        re.compile(r'\bplace\s*(?:an?\s+)?order\b', re.I),
        re.compile(r'\bwant\s+to\s+order\b', re.I),
        re.compile(r'\b(?:purchase|buy)\b', re.I),
        re.compile(r'\bPO\s+attached\b', re.I),
        re.compile(r'\bsubmit(?:ting)?\s+(?:an?\s+)?(?:order|PO)\b', re.I),
    ],
    IntentType.ORDER_STATUS: [
        re.compile(r'\b(?:order|shipment|delivery)\s*(?:status|tracking)\b', re.I),
        re.compile(r'\btrack\b', re.I),
        re.compile(r'\bwhere\s+is\b', re.I),
        re.compile(r'\bwhen\s+(?:will|does|can).*(?:arrive|deliver|ship)\b', re.I),
        re.compile(r'\b(?:ETA|delivery\s+date)\b', re.I),
        re.compile(r'\bPO[-\s]?\d+\b', re.I),
    ],
    IntentType.TECHNICAL_SUPPORT: [
        re.compile(r'\b(?:viscosity|compatibility|specification|formulation)\b', re.I),
        re.compile(r'\b(?:application|grade)\s+(?:for|of|recommendation)\b', re.I),
        re.compile(r'\btechnical\s+(?:question|support|help|info)\b', re.I),
        re.compile(r'\b(?:what|which)\s+(?:grade|product)\s+(?:for|should|would)\b', re.I),
        re.compile(r'\bcompatib(?:le|ility)\b', re.I),
    ],
    IntentType.RETURN_COMPLAINT: [
        re.compile(r'\b(?:return|refund|RMA)\b', re.I),
        re.compile(r'\b(?:damaged|defective|wrong)\b', re.I),
        re.compile(r'\bcomplaint\b', re.I),
        re.compile(r'\b(?:not\s+(?:what|right)|incorrect)\b', re.I),
    ],
    IntentType.REORDER: [
        re.compile(r'\b(?:re-?order)\b', re.I),
        re.compile(r'\bsame\s+(?:as\s+last|order)\b', re.I),
        re.compile(r'\brepeat\s+order\b', re.I),
    ],
    IntentType.ACCOUNT_INQUIRY: [
        re.compile(r'\b(?:account|billing)\b', re.I),
        re.compile(r'\b(?:credit|payment\s+terms)\b', re.I),
        re.compile(r'\b(?:invoice|balance)\b', re.I),
    ],
    IntentType.SAMPLE_REQUEST: [
        re.compile(r'\bsample\b', re.I),
        re.compile(r'\b(?:trial|test\s+batch)\b', re.I),
        re.compile(r'\b(?:evaluation|free\s+sample)\b', re.I),
    ],
}

# Base confidence for pattern matches (can be boosted by multiple matches)
_BASE_CONFIDENCE = 0.75
_BOOST_PER_EXTRA_MATCH = 0.05
_MAX_CONFIDENCE = 0.95

# LLM fallback prompt
_LLM_PROMPT = """Classify ALL intents in this customer email. Return ONLY valid JSON:
{"intents": [{"intent": "...", "confidence": 0.0-1.0, "text_span": "..."}]}

Valid intents: place_order, request_quote, request_tds_sds, order_status, \
technical_support, return_complaint, reorder, account_inquiry, sample_request

Email:
"""


class MultiIntentClassifier:
    """Classify customer emails into one or more intents."""

    def __init__(self, llm_router=None, feedback_service=None):
        self._llm = llm_router
        self._entity_extractor = EntityExtractor()
        self._feedback = feedback_service

    def classify_patterns(self, text: str) -> MultiIntentResult:
        """Synchronous pattern-based classification.

        Returns ALL matching intents (not just best), each with text_span.
        Runs entity extraction. Deduplicates same intent, keeps highest confidence.
        """
        text_lower = text.lower()
        intent_matches: dict[IntentType, list[str]] = {}

        for intent_type, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    if intent_type not in intent_matches:
                        intent_matches[intent_type] = []
                    intent_matches[intent_type].append(match.group(0))

        # Build IntentResult list with confidence based on match count
        intents: list[IntentResult] = []
        for intent_type, spans in intent_matches.items():
            confidence = min(
                _BASE_CONFIDENCE + _BOOST_PER_EXTRA_MATCH * (len(spans) - 1),
                _MAX_CONFIDENCE,
            )
            intents.append(IntentResult(
                intent=intent_type,
                confidence=confidence,
                text_span=spans[0],
            ))

        # Sort by confidence descending
        intents.sort(key=lambda r: r.confidence, reverse=True)

        # Entity extraction
        entities = self._entity_extractor.extract(text)

        return MultiIntentResult(intents=intents, entities=entities)

    async def classify(self, text: str) -> MultiIntentResult:
        """Classify with pattern matching first, LLM fallback for low confidence.

        Uses LLM when no intents found or all intents < 0.5 confidence.
        """
        result = self.classify_patterns(text)

        # If we got good pattern matches, return them
        if result.intents and max(r.confidence for r in result.intents) >= 0.5:
            return result

        # LLM fallback
        if self._llm is not None:
            try:
                llm_result = await self._classify_llm(text)
                if llm_result.intents:
                    # Preserve entities from pattern phase
                    llm_result.entities = result.entities
                    return llm_result
            except Exception as exc:
                logger.warning("LLM intent classification failed: %s", exc)

        # Return whatever pattern matching found (even if low confidence)
        return result

    async def _classify_llm(self, text: str) -> MultiIntentResult:
        """Call LLM for intent classification, with few-shot examples if available."""
        # Prepend few-shot examples from feedback service
        few_shot_block = ""
        if self._feedback:
            try:
                # Get examples from most common intents
                all_examples = []
                for intent_type in IntentType:
                    examples = await self._feedback.get_few_shot_examples(intent_type.value, limit=2)
                    all_examples.extend(examples)
                if all_examples:
                    lines = ["Here are some correctly classified examples:"]
                    for ex in all_examples[:10]:  # Cap at 10 examples
                        lines.append(f'- Intent: {ex["intent"]}, Text: "{ex["text"]}"')
                    few_shot_block = "\n".join(lines) + "\n\nNow classify this email:\n"
            except Exception as exc:
                logger.debug("Few-shot example retrieval failed: %s", exc)

        prompt = _LLM_PROMPT if not few_shot_block else _LLM_PROMPT.replace("Email:\n", few_shot_block)
        messages = [{"role": "user", "content": prompt + text}]
        raw = await self._llm.chat(
            messages,
            task="intent_classification",
            max_tokens=512,
            temperature=0.1,
        )

        # Parse JSON from response (handle markdown code blocks)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        intents = []
        valid_intents = {e.value for e in IntentType}
        for item in data.get("intents", []):
            intent_str = item.get("intent", "")
            if intent_str in valid_intents:
                intents.append(IntentResult(
                    intent=IntentType(intent_str),
                    confidence=min(max(float(item.get("confidence", 0.5)), 0.0), 1.0),
                    text_span=item.get("text_span"),
                ))

        return MultiIntentResult(intents=intents)
