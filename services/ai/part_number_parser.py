"""Industrial part number parser.

Parses bearings, metric/imperial fasteners, and V-belts from
free-text input using regex patterns. No API calls needed.

Ported from v1: app/ai/part_number_parser.py
"""

from __future__ import annotations

import re
from typing import Any, Optional

from services.ai.models import ParsedPart, PartCategory

# --- Bearing Patterns ---
# Standard: 6204-2RS, 6205-ZZ, 22210-E, NU206, 7308-B
BEARING_PATTERN = re.compile(
    r'\b('
    r'\d{3,5}'                      # base number (e.g., 6204, 22210, 7308)
    r'(?:[-/][A-Z0-9]{1,4})*'      # suffix like -2RS, -ZZ, -E, /C3
    r')\b',
    re.IGNORECASE
)

# Dimension-based: 20x47x14
BEARING_DIMENSION_PATTERN = re.compile(
    r'\b(\d{1,3})\s*[xX×]\s*(\d{1,3})\s*[xX×]\s*(\d{1,3})\b'
)

# Common bearing series prefixes
BEARING_SERIES = {
    '6': 'Deep Groove Ball Bearing',
    '7': 'Angular Contact Ball Bearing',
    '22': 'Spherical Roller Bearing',
    '32': 'Tapered Roller Bearing',
    'N': 'Cylindrical Roller Bearing',
    'NU': 'Cylindrical Roller Bearing',
    'NJ': 'Cylindrical Roller Bearing',
}

# Bore diameter lookup for 6xxx series (ID code × 5 for codes ≥ 04)
BORE_LOOKUP = {
    '00': 10, '01': 12, '02': 15, '03': 17,
}

# --- Metric Fastener Patterns ---
# M8x1.25x30, M10x40, M6x1.0x20
METRIC_FASTENER_PATTERN = re.compile(
    r'\b[Mm](\d{1,3})'              # M + diameter
    r'(?:\s*[xX×]\s*(\d+\.?\d*))?'  # optional pitch
    r'(?:\s*[xX×]\s*(\d+\.?\d*))?'  # optional length
    r'\b'
)

# Standard coarse pitches (mm)
METRIC_COARSE_PITCH = {
    3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5,
    12: 1.75, 14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5,
    24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5, 36: 4.0,
}

# --- Imperial Fastener Patterns ---
# 1/4-20 x 1.5, 3/8-16 x 2, #10-32 x 0.75
IMPERIAL_FASTENER_PATTERN = re.compile(
    r'\b(\d+/\d+|\#\d+)'           # diameter (fraction or # number)
    r'\s*-\s*(\d+)'                 # TPI
    r'(?:\s*[xX×]\s*(\d+\.?\d*))?' # optional length
    r'\b'
)

# Fractional to decimal lookup
FRACTION_TO_DECIMAL = {
    '#4': 0.112, '#6': 0.138, '#8': 0.164, '#10': 0.190, '#12': 0.216,
    '1/4': 0.250, '5/16': 0.3125, '3/8': 0.375, '7/16': 0.4375,
    '1/2': 0.500, '9/16': 0.5625, '5/8': 0.625, '3/4': 0.750,
    '7/8': 0.875, '1': 1.000,
}

# --- V-Belt Patterns ---
# A48, B60, 5V1000, 3V500
BELT_PATTERN = re.compile(
    r'\b([345]?[VABCDvabcd])(\d{2,4})\b'
)


class PartNumberParser:
    """Parse industrial part numbers from free text."""

    def parse(self, text: str) -> list[ParsedPart]:
        """Parse all recognizable part numbers from input text."""
        results = []
        seen = set()

        # Try each parser in order of specificity
        for parsed in self._parse_metric_fasteners(text):
            key = (parsed.category, parsed.raw_input)
            if key not in seen:
                seen.add(key)
                results.append(parsed)

        for parsed in self._parse_imperial_fasteners(text):
            key = (parsed.category, parsed.raw_input)
            if key not in seen:
                seen.add(key)
                results.append(parsed)

        for parsed in self._parse_bearings(text):
            key = (parsed.category, parsed.raw_input)
            if key not in seen:
                seen.add(key)
                results.append(parsed)

        for parsed in self._parse_belts(text):
            key = (parsed.category, parsed.raw_input)
            if key not in seen:
                seen.add(key)
                results.append(parsed)

        return results

    def parse_single(self, part_string: str) -> ParsedPart:
        """Parse a single part number string."""
        results = self.parse(part_string)
        if results:
            return results[0]
        return ParsedPart(
            raw_input=part_string,
            category=PartCategory.UNKNOWN,
            parsed={},
            confidence=0.0,
        )

    def _parse_bearings(self, text: str) -> list[ParsedPart]:
        results = []

        # Dimension-based bearings: 20x47x14
        for match in BEARING_DIMENSION_PATTERN.finditer(text):
            bore, od, width = int(match.group(1)), int(match.group(2)), int(match.group(3))
            results.append(ParsedPart(
                raw_input=match.group(0),
                category=PartCategory.BEARING,
                parsed={
                    "bore_mm": bore,
                    "od_mm": od,
                    "width_mm": width,
                    "format": "dimensions",
                },
                confidence=0.9,
            ))

        # Standard bearing numbers: 6204-2RS
        for match in BEARING_PATTERN.finditer(text):
            raw = match.group(0)
            # Avoid matching things that are clearly fasteners (M8, etc.) or belts
            if raw.upper().startswith('M') and raw[1:2].isdigit():
                continue
            if BELT_PATTERN.match(raw):
                continue

            parsed = self._decode_bearing(raw)
            if parsed:
                results.append(ParsedPart(
                    raw_input=raw,
                    category=PartCategory.BEARING,
                    parsed=parsed,
                    confidence=0.95,
                ))

        return results

    def _decode_bearing(self, part_number: str) -> Optional[dict[str, Any]]:
        """Decode a standard bearing number into components."""
        clean = part_number.upper().strip()

        # Extract base number and suffixes
        parts = re.split(r'[-/]', clean)
        if not parts:
            return None

        base = parts[0]
        suffixes = parts[1:] if len(parts) > 1 else []

        # Must start with digits for standard bearings
        if not base or not base[0].isdigit():
            # Check for NU, NJ, N series
            prefix_match = re.match(r'^(NU|NJ|N)(\d+)', base)
            if not prefix_match:
                return None
            series_prefix = prefix_match.group(1)
            number_part = prefix_match.group(2)
        else:
            series_prefix = None
            number_part = base

        if len(number_part) < 3:
            return None

        result: dict[str, Any] = {"part_number": part_number}

        # Determine series
        if series_prefix:
            result["series_type"] = BEARING_SERIES.get(series_prefix, "Roller Bearing")
            result["series"] = series_prefix + number_part
        else:
            # First 1-2 digits indicate series
            for prefix_len in (2, 1):
                prefix = number_part[:prefix_len]
                if prefix in BEARING_SERIES:
                    result["series_type"] = BEARING_SERIES[prefix]
                    break

            result["series"] = number_part

        # Calculate bore diameter
        bore_code = number_part[-2:]
        if bore_code in BORE_LOOKUP:
            result["bore_mm"] = BORE_LOOKUP[bore_code]
        elif bore_code.isdigit():
            code = int(bore_code)
            if code >= 4:
                result["bore_mm"] = code * 5

        # Parse suffixes
        suffix_str = "-".join(suffixes) if suffixes else ""
        if suffix_str:
            result["suffix"] = suffix_str
            if "2RS" in suffix_str.upper():
                result["seal"] = "2RS (Double Rubber Seal)"
            elif "ZZ" in suffix_str.upper():
                result["seal"] = "ZZ (Double Metal Shield)"
            elif "RS" in suffix_str.upper():
                result["seal"] = "RS (Single Rubber Seal)"
            if "C3" in suffix_str.upper():
                result["clearance"] = "C3 (Greater than Normal)"
            if "E" in suffix_str.upper():
                result["design"] = "E (Reinforced)"

        return result

    def _parse_metric_fasteners(self, text: str) -> list[ParsedPart]:
        results = []
        for match in METRIC_FASTENER_PATTERN.finditer(text):
            diameter = int(match.group(1))
            second = match.group(2)
            third = match.group(3)

            parsed: dict[str, Any] = {"diameter_mm": diameter}

            if second and third:
                # M8x1.25x30 format: pitch and length
                parsed["pitch_mm"] = float(second)
                parsed["length_mm"] = float(third)
                parsed["thread_type"] = "fine" if float(second) != METRIC_COARSE_PITCH.get(diameter, 0) else "coarse"
            elif second:
                value = float(second)
                # Heuristic: if value < diameter, it's likely pitch; if >= diameter, it's length
                if value < diameter and value in [v for v in METRIC_COARSE_PITCH.values()]:
                    parsed["pitch_mm"] = value
                    parsed["thread_type"] = "fine" if value != METRIC_COARSE_PITCH.get(diameter, 0) else "coarse"
                else:
                    # Assume length, use coarse pitch
                    parsed["length_mm"] = value
                    if diameter in METRIC_COARSE_PITCH:
                        parsed["pitch_mm"] = METRIC_COARSE_PITCH[diameter]
                    parsed["thread_type"] = "coarse"
            else:
                if diameter in METRIC_COARSE_PITCH:
                    parsed["pitch_mm"] = METRIC_COARSE_PITCH[diameter]
                parsed["thread_type"] = "coarse"

            results.append(ParsedPart(
                raw_input=match.group(0),
                category=PartCategory.METRIC_FASTENER,
                parsed=parsed,
                confidence=0.95,
            ))
        return results

    def _parse_imperial_fasteners(self, text: str) -> list[ParsedPart]:
        results = []
        for match in IMPERIAL_FASTENER_PATTERN.finditer(text):
            diameter_str = match.group(1)
            tpi = int(match.group(2))
            length_str = match.group(3)

            diameter_decimal = FRACTION_TO_DECIMAL.get(diameter_str)
            if diameter_decimal is None:
                # Try to evaluate fraction
                if '/' in diameter_str:
                    num, den = diameter_str.split('/')
                    try:
                        diameter_decimal = int(num) / int(den)
                    except (ValueError, ZeroDivisionError):
                        continue

            parsed: dict[str, Any] = {
                "diameter": diameter_str,
                "tpi": tpi,
            }
            if diameter_decimal is not None:
                parsed["diameter_decimal"] = diameter_decimal
            if length_str:
                parsed["length_inches"] = float(length_str)

            results.append(ParsedPart(
                raw_input=match.group(0),
                category=PartCategory.IMPERIAL_FASTENER,
                parsed=parsed,
                confidence=0.95,
            ))
        return results

    def _parse_belts(self, text: str) -> list[ParsedPart]:
        results = []
        for match in BELT_PATTERN.finditer(text):
            profile = match.group(1).upper()
            length = int(match.group(2))

            parsed: dict[str, Any] = {
                "profile": profile,
                "length": length,
            }

            # Determine belt type
            if profile in ('3V', '5V', '8V'):
                parsed["type"] = "Narrow V-Belt"
            elif profile in ('A', 'B', 'C', 'D'):
                parsed["type"] = "Classical V-Belt"
            else:
                parsed["type"] = "V-Belt"

            results.append(ParsedPart(
                raw_input=match.group(0),
                category=PartCategory.BELT,
                parsed=parsed,
                confidence=0.95,
            ))
        return results
