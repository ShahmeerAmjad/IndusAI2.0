# =======================
# Data Models
# =======================

import html
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class MessageType(Enum):
    ORDER_STATUS = "order_status"
    PRODUCT_INQUIRY = "product_inquiry"
    PRICE_REQUEST = "price_request"
    TECHNICAL_SUPPORT = "technical_support"
    RETURNS = "returns"
    GENERAL_QUERY = "general_query"
    UNKNOWN = "unknown"


class ChannelType(Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    WEB = "web"
    SMS = "sms"


@dataclass
class CustomerMessage:
    id: str
    from_id: str
    content: str
    channel: ChannelType
    timestamp: datetime
    message_type: MessageType = MessageType.UNKNOWN
    confidence: float = 0.0


@dataclass
class BotResponse:
    content: str
    suggested_actions: List[str] = field(default_factory=list)
    escalate: bool = False
    metadata: Optional[dict] = field(default_factory=dict)


# =======================
# Request/Response Models
# =======================

class MessageRequest(BaseModel):
    from_id: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_\-@\+\.]+$')
    content: str = Field(..., min_length=1, max_length=2000)
    channel: str = Field(default="web", pattern='^(whatsapp|email|web|sms)$')
    conversation_id: Optional[str] = Field(default=None, max_length=36)

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v):
        return html.escape(v)

    @field_validator('from_id')
    @classmethod
    def validate_from_id(cls, v):
        if any(char in v for char in ['<', '>', '"', "'", '&']):
            raise ValueError("Invalid characters in from_id")
        return v
