"""Regex-based PII detection and redaction for email bodies."""

import re
from dataclasses import dataclass, field

PII_PATTERNS: list[tuple[str, str]] = [
    ("email", r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    ("phone_us", r'\b(?:\+1[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b'),
    ("ssn", r'\b\d{3}-\d{2}-\d{4}\b'),
    ("credit_card", r'\b(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{3,4}\b'),
    ("cas_number", r'\b\d{2,7}-\d{2}-\d\b'),
]

_REDACTION_LABELS: dict[str, str] = {
    "email": "[EMAIL REDACTED]",
    "phone_us": "[PHONE REDACTED]",
    "ssn": "[SSN REDACTED]",
    "credit_card": "[CREDIT CARD REDACTED]",
    "cas_number": "[CAS NUMBER REDACTED]",
}


@dataclass
class ScanResult:
    redacted_text: str
    detected_types: list[str] = field(default_factory=list)
    redaction_count: int = 0


class PIIScanner:
    """Scan text for PII and return a redacted copy.

    CAS numbers (chemical registry IDs) are detected but NOT redacted by
    default because they are product identifiers, not personal data.
    """

    def scan(
        self, text: str, exclude_types: set[str] | None = None,
    ) -> ScanResult:
        if exclude_types is None:
            exclude_types = {"cas_number"}

        if not text:
            return ScanResult(redacted_text="", detected_types=[], redaction_count=0)

        detected: list[str] = []
        redacted = text
        count = 0

        for pii_type, pattern in PII_PATTERNS:
            matches = list(re.finditer(pattern, redacted))
            if not matches:
                continue
            if pii_type not in detected:
                detected.append(pii_type)
            if pii_type in exclude_types:
                continue
            label = _REDACTION_LABELS[pii_type]
            redacted = re.sub(pattern, label, redacted)
            count += len(matches)

        return ScanResult(
            redacted_text=redacted,
            detected_types=detected,
            redaction_count=count,
        )
