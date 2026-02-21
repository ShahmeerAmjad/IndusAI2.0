# =======================
# Intent Classification - Pattern + Fuzzy Matching
# =======================

import re
from typing import Tuple

from fuzzywuzzy import fuzz

from models.models import MessageType


class IntentClassifier:
    def __init__(self):
        self.patterns = {
            MessageType.ORDER_STATUS: [
                r'(?:status|track|where).*(?:order|po|shipment|purchase)',
                r'order.*(?:status|tracking|number)',
                r'(?:po|order|#)[\s-]?\d+',
                r'delivery.*(?:status|date|time|eta)',
                r'when.*(?:arrive|deliver|ship)',
                r'(?:shipment|shipping).*(?:update|info)',
            ],
            MessageType.PRODUCT_INQUIRY: [
                r'(?:product|item|sku|part).*(?:info|detail|spec|price|number)',
                r'tell.*about.*(?:product|item|part)',
                r'(?:availability|stock|inventory|in\s+stock)',
                r'(?:catalog|catalogue|datasheet)',
                r'(?:compatible|replacement|alternative).*(?:part|product)',
            ],
            MessageType.PRICE_REQUEST: [
                r'(?:price|cost|pricing|quote|estimate)',
                r'how\s+much.*(?:cost|price)',
                r'(?:bulk|volume|wholesale).*(?:price|discount|pricing)',
                r'(?:request|need|get).*quote',
            ],
            MessageType.TECHNICAL_SUPPORT: [
                r'(?:help|support|issue|problem|trouble)',
                r"(?:not|doesn't|won't|can't).*(?:work|working|function|start)",
                r'(?:error|failure|broken|defect|malfunction)',
                r'technical.*(?:support|help|assistance)',
                r'(?:install|setup|configure|calibrate)',
                r'(?:maintenance|repair|service).*(?:guide|manual|schedule)',
            ],
            MessageType.RETURNS: [
                r'(?:return|exchange|refund|rma)',
                r'(?:defective|damaged|wrong).*(?:product|item|part|order)',
                r'(?:warranty|guarantee).*(?:claim|issue)',
                r'send.*(?:back|return)',
            ],
        }

        self._fuzzy_examples = {
            MessageType.ORDER_STATUS: [
                "order status", "track order", "shipment tracking",
                "where is my order", "delivery date", "order update",
            ],
            MessageType.PRODUCT_INQUIRY: [
                "product info", "product details", "availability",
                "tell me about", "in stock", "part number", "datasheet",
            ],
            MessageType.PRICE_REQUEST: [
                "pricing", "how much", "get a quote",
                "bulk discount", "wholesale price",
            ],
            MessageType.TECHNICAL_SUPPORT: [
                "help", "support", "problem", "not working",
                "technical issue", "error", "broken", "troubleshoot",
            ],
            MessageType.RETURNS: [
                "return product", "refund", "exchange",
                "defective item", "warranty claim", "RMA",
            ],
        }

    def classify(self, text: str) -> Tuple[MessageType, float]:
        """Classify the intent of an incoming message.

        Returns a (MessageType, confidence) tuple.
        """
        text_lower = text.lower().strip()

        best_type = MessageType.UNKNOWN
        best_confidence = 0.0

        # Phase 1: regex pattern matching (high confidence)
        for msg_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_type = msg_type
                        best_confidence = confidence

        # Phase 2: fuzzy matching fallback for ambiguous messages
        if best_confidence < 0.5:
            fuzzy_type, fuzzy_conf = self._fuzzy_classify(text_lower)
            if fuzzy_conf > best_confidence:
                best_type = fuzzy_type
                best_confidence = fuzzy_conf

        return best_type, best_confidence

    def _fuzzy_classify(self, text: str) -> Tuple[MessageType, float]:
        """Fuzzy string matching fallback using partial_ratio."""
        best_type = MessageType.UNKNOWN
        best_score = 0.0

        for msg_type, examples in self._fuzzy_examples.items():
            for example in examples:
                score = fuzz.partial_ratio(text, example) / 100.0
                if score > best_score and score > 0.6:
                    best_score = score * 0.8  # scale down fuzzy confidence
                    best_type = msg_type

        return best_type, best_score
