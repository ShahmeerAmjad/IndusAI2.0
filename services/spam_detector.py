# =======================
# Spam Detection
# =======================

import re
from typing import Tuple


class SpamDetector:
    """Rule-based spam detector for incoming messages."""

    def __init__(self):
        self.spam_patterns = [
            r'(?:viagra|cialis|casino|lottery|winner|jackpot)',
            r'(?:click here|limited time|act now|free money)',
            r'(?:million dollars|inheritance|prince|nigerian)',
            r'(?:congratulations.*won|you have been selected)',
            r'(?:earn \$|make money fast|work from home)',
            r'(?:buy now|order now|special offer|exclusive deal)',
        ]
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.spam_patterns]

        # Thresholds
        self.max_url_count = 3
        self.max_caps_ratio = 0.7
        self.min_length = 2

    def is_spam(self, text: str) -> Tuple[bool, str]:
        """Check whether a message is spam.

        Returns (is_spam: bool, reason: str).
        """
        if not text or len(text.strip()) < self.min_length:
            return True, "Message too short"

        text_lower = text.lower()

        # Pattern matching
        for pattern in self._compiled:
            if pattern.search(text_lower):
                return True, "Matched spam pattern"

        # Excessive URLs
        url_count = len(re.findall(r'https?://', text_lower))
        if url_count > self.max_url_count:
            return True, "Too many URLs"

        # Excessive caps (only check messages of reasonable length)
        if len(text) > 20:
            alpha_chars = [c for c in text if c.isalpha()]
            if alpha_chars:
                caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if caps_ratio > self.max_caps_ratio:
                    return True, "Excessive capitalization"

        # Repetitive characters
        if re.search(r'(.)\1{9,}', text):
            return True, "Repetitive characters"

        return False, ""


# Module-level singleton for import convenience
spam_detector = SpamDetector()
