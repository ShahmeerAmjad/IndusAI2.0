"""Entity extraction from customer messages.

Extracts part numbers, quantities, order/PO numbers using regex patterns.

Ported from v1: app/ai/entity_extractor.py
"""

import re

from services.ai.models import EntityResult

# Part number patterns to extract (not parse - just find)
PART_NUMBER_PATTERNS = [
    re.compile(r'\b[Mm]\d{1,3}(?:\s*[xX×]\s*\d+\.?\d*){1,2}\b'),  # M8x1.25x30
    re.compile(r'\b\d+/\d+\s*-\s*\d+(?:\s*[xX×]\s*\d+\.?\d*)?\b'),  # 1/4-20 x 1.5
    re.compile(r'\b\#\d+\s*-\s*\d+(?:\s*[xX×]\s*\d+\.?\d*)?\b'),  # #10-32 x 0.75
    re.compile(r'\b\d{3,5}(?:[-/][A-Z0-9]{1,4})+\b', re.I),  # 6204-2RS, 22210-E
    re.compile(r'\b[345]?[VABCD]\d{2,4}\b', re.I),  # A48, 5V1000
    re.compile(r'\b\d{1,3}\s*[xX×]\s*\d{1,3}\s*[xX×]\s*\d{1,3}\b'),  # 20x47x14
    re.compile(r'\bSKU[-\s]?\d{3,6}\b', re.I),  # SKU-1234
]

# Quantity patterns: "100 pcs", "qty: 50", "need 200", "x50"
QUANTITY_PATTERNS = [
    re.compile(r'(\d+)\s*(?:pcs?|pieces?|units?|each|ea)\b', re.I),
    re.compile(r'\bqty\s*[:=]?\s*(\d+)\b', re.I),
    re.compile(r'\bneed\s+(\d+)\b', re.I),
    re.compile(r'\b(\d+)\s+(?:of|×|x)\s+', re.I),
    re.compile(r'\bquote\s+(?:for\s+)?(\d+)\b', re.I),
    re.compile(r'\b(\d{2,})\s+(?=M\d|[A-Z]\d{2,}|\d{3,5})', re.I),  # "100 M8x30"
]

# Order/PO number patterns
ORDER_PATTERNS = [
    re.compile(r'\bPO[-\s]?(\d{3,10})\b', re.I),
    re.compile(r'\border\s*#?\s*(\d{3,10})\b', re.I),
    re.compile(r'\b(?:ORD|INV)[-\s]?(\d{3,10})\b', re.I),
]


class EntityExtractor:
    """Extract structured entities from customer messages."""

    def extract(self, message: str) -> EntityResult:
        """Extract all entities from a message."""
        part_numbers = self._extract_part_numbers(message)
        quantities = self._extract_quantities(message, part_numbers)
        order_numbers = self._extract_order_numbers(message)

        return EntityResult(
            part_numbers=part_numbers,
            quantities=quantities,
            order_numbers=order_numbers,
            raw_entities={
                "part_count": len(part_numbers),
                "has_quantities": bool(quantities),
                "has_orders": bool(order_numbers),
            },
        )

    def _extract_part_numbers(self, message: str) -> list[str]:
        """Extract all potential part numbers from message."""
        found = []
        seen = set()
        for pattern in PART_NUMBER_PATTERNS:
            for match in pattern.finditer(message):
                pn = match.group(0).strip()
                pn_upper = pn.upper()
                if pn_upper not in seen and len(pn) >= 2:
                    seen.add(pn_upper)
                    found.append(pn)
        return found

    def _extract_quantities(self, message: str, part_numbers: list[str]) -> dict[str, int]:
        """Extract quantities, attempting to associate with part numbers."""
        quantities: dict[str, int] = {}
        raw_quantities: list[int] = []

        for pattern in QUANTITY_PATTERNS:
            for match in pattern.finditer(message):
                try:
                    qty = int(match.group(1))
                    if 1 <= qty <= 100000:  # Reasonable quantity range
                        raw_quantities.append(qty)
                except (ValueError, IndexError):
                    continue

        # Associate quantities with part numbers (simple: first qty → first part, etc.)
        for i, pn in enumerate(part_numbers):
            if i < len(raw_quantities):
                quantities[pn] = raw_quantities[i]

        # If we have quantities but no part numbers, store as generic
        if raw_quantities and not part_numbers:
            quantities["_unassociated"] = raw_quantities[0]

        return quantities

    def _extract_order_numbers(self, message: str) -> list[str]:
        """Extract order/PO numbers from message."""
        orders = []
        seen = set()
        for pattern in ORDER_PATTERNS:
            for match in pattern.finditer(message):
                order_num = match.group(0).strip()
                if order_num.upper() not in seen:
                    seen.add(order_num.upper())
                    orders.append(order_num)
        return orders
