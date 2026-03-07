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
    # Supplier sales & support intents (9 primary)
    PLACE_ORDER = "place_order"
    REQUEST_QUOTE = "request_quote"
    REQUEST_TDS_SDS = "request_tds_sds"
    ORDER_STATUS = "order_status"
    TECHNICAL_SUPPORT = "technical_support"
    RETURN_COMPLAINT = "return_complaint"
    REORDER = "reorder"
    ACCOUNT_INQUIRY = "account_inquiry"
    SAMPLE_REQUEST = "sample_request"
    # Legacy aliases (kept for backward compatibility)
    PART_LOOKUP = "part_lookup"
    INVENTORY_CHECK = "inventory_check"
    QUOTE_REQUEST = "quote_request"
    RETURN_REQUEST = "return_request"
    GENERAL_QUERY = "general_query"


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    requires_clarification: bool = False
    text_span: str | None = None


class MultiIntentResult(BaseModel):
    intents: list["IntentResult"] = []
    entities: "EntityResult" = Field(default_factory=lambda: EntityResult())


class EntityResult(BaseModel):
    part_numbers: list[str] = []
    quantities: dict[str, int] = {}
    order_numbers: list[str] = []
    cas_numbers: list[str] = []
    po_numbers: list[str] = []
    raw_entities: dict[str, Any] = {}
