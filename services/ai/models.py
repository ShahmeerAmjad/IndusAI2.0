"""Shared AI/NLP schemas for the MRO platform."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PartCategory(str, Enum):
    BEARING = "bearing"
    METRIC_FASTENER = "metric_fastener"
    IMPERIAL_FASTENER = "imperial_fastener"
    BELT = "belt"
    UNKNOWN = "unknown"


class ParsedPart(BaseModel):
    raw_input: str
    category: PartCategory
    parsed: dict[str, Any] = {}
    confidence: float = 1.0


class IntentType(str, Enum):
    ORDER_STATUS = "order_status"
    PART_LOOKUP = "part_lookup"
    INVENTORY_CHECK = "inventory_check"
    QUOTE_REQUEST = "quote_request"
    TECHNICAL_SUPPORT = "technical_support"
    ACCOUNT_INQUIRY = "account_inquiry"
    RETURN_REQUEST = "return_request"
    GENERAL_QUERY = "general_query"


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    requires_clarification: bool = False


class EntityResult(BaseModel):
    part_numbers: list[str] = []
    quantities: dict[str, int] = {}
    order_numbers: list[str] = []
    raw_entities: dict[str, Any] = {}
