#!/usr/bin/env python3
"""
MRO Platform — Agentic Back-Office / Middle-Office Operating System
for Industrial MRO Distributors.

Modules: Product Catalog, Inventory, Orders (O2C), Quotes, Pricing,
Procurement (P2P), Invoicing, Payments, RMA/Returns, Workflows, Analytics.
Omnichannel conversational interface (WhatsApp, Web, Email, SMS).
"""

import os
import re
import json
import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

# FastAPI
from fastapi import (
    FastAPI, Request, HTTPException, BackgroundTasks,
    Query, Header, Depends,
)
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Validation & config
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# JWT
import jwt

# Monitoring
from prometheus_client import generate_latest

# Internal modules
from metrics.metrics import ERROR_COUNTER
from models.models import ChannelType, MessageRequest
from services.ai_service import AIService
from services.business_logic import BusinessLogic
from services.chatbot_engine import ChatbotEngine
from services.communication_manager import CommunicationManager
from services.database_manager import DatabaseManager
from services.escalation_service import EscalationService
from services.intent_classifier import IntentClassifier
from services.spam_detector import spam_detector

# Platform services
from services.platform.erp_connector import MockERPConnector
from services.platform.workflow_engine import WorkflowEngine
from services.platform.product_service import ProductService
from services.platform.inventory_service import InventoryService
from services.platform.customer_service import CustomerService
from services.platform.pricing_service import PricingService
from services.platform.order_service import OrderService
from services.platform.quote_service import QuoteService
from services.platform.procurement_service import ProcurementService
from services.platform.invoice_service import InvoiceService
from services.platform.rma_service import RMAService
from services.platform.analytics_service import AnalyticsService
from routes.platform import router as platform_router, set_services

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

APP_VERSION = "3.0.0"
BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Logging with sensitive-data redaction
# ---------------------------------------------------------------------------


class _SecurityFilter(logging.Filter):
    """Redact API keys, phone numbers, and emails from log output."""

    _patterns = [
        (re.compile(r'(api_key|token|password|secret)=["\']?([^"\'\s]+)'), r'\1=***REDACTED***'),
        (re.compile(r'\b\d{10,}\b'), '***PHONE***'),
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '***EMAIL***'),
    ]

    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            for pattern, replacement in self._patterns:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
        return True


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("mro_platform")
logger.addFilter(_SecurityFilter())

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """All application settings, loaded from environment or .env file."""

    # App
    app_name: str = "MRO Platform"
    debug: bool = Field(default=False)
    secret_key: str = Field(default=...)

    # Admin
    admin_api_key: Optional[str] = Field(default=None)

    # Database
    database_url: str = Field(default="postgresql://chatbot:password@localhost:5432/chatbot")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # WhatsApp Business API
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_phone_number_id: Optional[str] = Field(default=None)
    whatsapp_access_token: Optional[str] = Field(default=None)
    whatsapp_webhook_verify_token: Optional[str] = Field(default=None)
    whatsapp_app_secret: Optional[str] = Field(default=None)

    # Anthropic AI
    anthropic_api_key: Optional[str] = Field(default=None)
    ai_model: str = Field(default="claude-3-5-sonnet-20241022")
    ai_max_retries: int = Field(default=3)
    ai_retry_delay: float = Field(default=1.0)

    # Support contact info
    support_email: str = Field(default="support@company.com")
    support_phone: str = Field(default="1-800-TECH-HELP")

    # Circuit breaker
    circuit_breaker_threshold: int = Field(default=5)
    circuit_breaker_timeout: int = Field(default=60)

    # Email (SMTP)
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)

    # Rate limiting
    rate_limit_per_minute: int = Field(default=60)

    @field_validator('secret_key')
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------

_http_bearer = HTTPBearer()


def create_admin_token(user_id: str) -> str:
    """Issue a 24-hour admin JWT."""
    payload = {
        "user_id": user_id,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
):
    """FastAPI dependency that validates an admin JWT."""
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid authentication")


def _verify_whatsapp_signature(request_body: bytes, signature: str) -> bool:
    """Verify Meta webhook HMAC-SHA256 signature."""
    if not settings.whatsapp_app_secret:
        return False
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Service wiring (dependency graph)
# ---------------------------------------------------------------------------

db_manager = DatabaseManager(logger=logger, settings=settings)
classifier = IntentClassifier()
ai_service = AIService(logger=logger, settings=settings)
escalation_service = EscalationService(settings=settings, logger=logger, db_manager=db_manager)
comm_manager = CommunicationManager(logger=logger, settings=settings)

# Platform services — initialised after DB pool is ready (see lifespan)
erp_connector = MockERPConnector()
workflow_engine = WorkflowEngine(db_manager, logger)
product_service = ProductService(db_manager, logger)
inventory_service = InventoryService(db_manager, logger)
customer_service = CustomerService(db_manager, logger)
pricing_service = PricingService(db_manager, logger)
order_service = OrderService(db_manager, customer_service, pricing_service,
                             inventory_service, workflow_engine, logger)
quote_service = QuoteService(db_manager, pricing_service, order_service, logger)
procurement_service = ProcurementService(db_manager, inventory_service, workflow_engine, logger)
invoice_service = InvoiceService(db_manager, customer_service, logger)
rma_service = RMAService(db_manager, inventory_service, workflow_engine, logger)
analytics_service = AnalyticsService(db_manager, logger)

business_logic = BusinessLogic(
    ai_service=ai_service,
    db_manager=db_manager,
    settings=settings,
    escalation_service=escalation_service,
    product_service=product_service,
    inventory_service=inventory_service,
    pricing_service=pricing_service,
    order_service=order_service,
    quote_service=quote_service,
    customer_service=customer_service,
    rma_service=rma_service,
)
chatbot = ChatbotEngine(
    logger=logger,
    business_logic=business_logic,
    classifier=classifier,
    db_manager=db_manager,
    settings=settings,
)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info(f"Starting {settings.app_name} v{APP_VERSION}")
    app.state.start_time = time.time()
    app.state.request_count = 0

    await db_manager.initialize()

    # Create platform tables & indexes
    if db_manager.pool:
        try:
            from services.platform.schema import PLATFORM_SCHEMA, PLATFORM_INDEXES
            async with db_manager.pool.acquire() as conn:
                await conn.execute(PLATFORM_SCHEMA)
                await conn.execute(PLATFORM_INDEXES)
            logger.info("Platform schema ready")
        except Exception as e:
            logger.error(f"Platform schema creation failed: {e}")

    # Inject services into the platform API router
    set_services({
        "product_service": product_service,
        "inventory_service": inventory_service,
        "customer_service": customer_service,
        "pricing_service": pricing_service,
        "order_service": order_service,
        "quote_service": quote_service,
        "procurement_service": procurement_service,
        "invoice_service": invoice_service,
        "rma_service": rma_service,
        "workflow_engine": workflow_engine,
        "analytics_service": analytics_service,
    })

    # Seed demo data in debug mode
    if settings.debug and db_manager.pool:
        try:
            from services.platform.seed import seed_database
            await seed_database(
                db_manager, product_service, pricing_service,
                customer_service, procurement_service,
                inventory_service, logger,
            )
        except Exception as e:
            logger.error(f"Seed failed: {e}")

    if settings.debug:
        token = create_admin_token("admin")
        logger.info(f"Dev admin token: {token}")

    yield

    logger.info(f"Shutting down {settings.app_name}")
    await db_manager.close()
    await comm_manager.close()


app = FastAPI(
    title="MRO Platform API",
    description="Agentic Back-Office / Middle-Office Operating System for Industrial MRO Distributors",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Platform API routes
app.include_router(platform_router)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://*.yourdomain.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=86400,
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    app.state.request_count += 1
    return response


# ===========================================================================
# Health & Monitoring
# ===========================================================================


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "uptime_seconds": int(time.time() - app.state.start_time),
    }


@app.get("/health/detailed", dependencies=[Depends(verify_admin_token)])
async def detailed_health_check():
    db_healthy = False
    redis_healthy = False
    db_error = None
    redis_error = None

    if db_manager.pool:
        try:
            async with db_manager.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except Exception as e:
            db_error = str(e)

    if db_manager.redis_client:
        try:
            await db_manager.redis_client.ping()
            redis_healthy = True
        except Exception as e:
            redis_error = str(e)

    return {
        "status": "healthy" if (db_healthy or not db_manager.pool) else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "services": {
            "database": {
                "connected": db_manager.pool is not None,
                "healthy": db_healthy,
                "pool_size": db_manager.pool.get_size() if db_manager.pool else 0,
                "error": db_error,
            },
            "redis": {
                "connected": db_manager.redis_client is not None,
                "healthy": redis_healthy,
                "error": redis_error,
            },
            "whatsapp": {"configured": bool(settings.whatsapp_access_token)},
            "ai": {
                "available": ai_service.client is not None,
                "circuit_breaker": ai_service.get_circuit_breaker_state(),
            },
        },
        "metrics": {
            "uptime_seconds": time.time() - app.state.start_time,
            "total_requests": app.state.request_count,
        },
        "escalation": escalation_service.get_stats(),
    }


@app.get("/metrics")
async def prometheus_metrics():
    return Response(generate_latest(), media_type="text/plain")


# ===========================================================================
# Root
# ===========================================================================


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": APP_VERSION,
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "features": [
            "Product Catalog & Search",
            "Inventory Management & Reorder Alerts",
            "Order-to-Cash (Orders, Quotes, Fulfillment)",
            "Procure-to-Pay (POs, Goods Receipt, Suppliers)",
            "Dynamic Pricing Engine & Customer Contracts",
            "Invoicing, Payments & AR Aging",
            "RMA / Returns Processing",
            "Workflow Approvals Engine",
            "Analytics & Dashboard Metrics",
            "AI-enhanced Conversational Interface (Claude)",
            "WhatsApp Business Integration",
            "Prometheus Metrics & Admin Dashboard",
        ],
    }


# ===========================================================================
# Message API
# ===========================================================================


async def _process_message(message_request: MessageRequest) -> dict:
    """Core message processing shared by API endpoints."""
    is_spam_flag, spam_reason = spam_detector.is_spam(message_request.content)
    if is_spam_flag:
        logger.warning(f"Spam rejected: {spam_reason}")
        raise HTTPException(status_code=400, detail="Message rejected")

    channel = ChannelType(message_request.channel)
    response = await chatbot.process_message(
        message_request.from_id,
        message_request.content,
        channel,
    )

    if response:
        return {
            "success": True,
            "response": {
                "content": response.content,
                "suggested_actions": response.suggested_actions,
                "escalate": response.escalate,
            },
            "message_id": str(uuid.uuid4()),
        }

    return {"success": False, "error": "Failed to process message"}


@app.post("/api/v1/message")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def process_message_v1(request: Request, message_request: MessageRequest):
    """Process an incoming customer message (v1)."""
    try:
        return await _process_message(message_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        ERROR_COUNTER.labels(error_type="api_error").inc()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/message")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def process_message_legacy(request: Request, message_request: MessageRequest):
    """Process message (legacy - use /api/v1/message instead)."""
    try:
        result = await _process_message(message_request)
        result["_deprecation_notice"] = "This endpoint is deprecated. Use /api/v1/message."
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        ERROR_COUNTER.labels(error_type="api_error").inc()
        raise HTTPException(status_code=500, detail="Internal server error")


# ===========================================================================
# WhatsApp Webhook
# ===========================================================================


@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_webhook_verify_token:
        logger.info("WhatsApp webhook verified")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook/whatsapp")
@limiter.limit("100/minute")
async def handle_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature: str = Header(None, alias="X-Hub-Signature-256"),
):
    """Receive and process incoming WhatsApp messages."""
    try:
        body = await request.body()

        if x_hub_signature and settings.whatsapp_app_secret:
            sig = x_hub_signature.replace("sha256=", "")
            if not _verify_whatsapp_signature(body, sig):
                logger.warning("Invalid WhatsApp webhook signature")
                raise HTTPException(status_code=403, detail="Invalid signature")

        data = json.loads(body)

        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue
                for msg in change.get("value", {}).get("messages", []):
                    if msg.get("type") == "text":
                        background_tasks.add_task(
                            _process_whatsapp_message,
                            msg["from"],
                            msg["text"]["body"],
                        )

        return {"status": "received"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        ERROR_COUNTER.labels(error_type="webhook_error").inc()
        return {"status": "error"}


async def _process_whatsapp_message(from_number: str, text: str):
    """Background task: process a WhatsApp message and send the response."""
    try:
        response = await chatbot.process_message(from_number, text, ChannelType.WHATSAPP)
        if response:
            await comm_manager.send_whatsapp_message(
                from_number, response.content, response.suggested_actions,
            )
            if response.escalate:
                await escalation_service.create_ticket(
                    customer_id=from_number,
                    subject=f"WhatsApp escalation: {text[:100]}",
                    description=text,
                    priority="high",
                )
    except Exception as e:
        logger.error(f"WhatsApp processing error: {e}", exc_info=True)
        await comm_manager.send_whatsapp_message(
            from_number,
            "I apologize, but I encountered an error. Please try again or contact our support team.",
        )


# ===========================================================================
# Admin Dashboard
# ===========================================================================


@app.get("/admin/dashboard", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def admin_dashboard(request: Request, token: str = Query(None)):
    """Serve the admin dashboard HTML."""
    if not settings.debug:
        if not settings.admin_api_key:
            raise HTTPException(status_code=503, detail="Admin dashboard not configured")
        if not token or token != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="Unauthorized")

    template_path = BASE_DIR / "templates" / "dashboard.html"
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/admin/api/metrics")
async def get_admin_metrics(admin=Depends(verify_admin_token)):
    """Return dashboard metrics as JSON."""
    try:
        messages = await db_manager.get_recent_messages(100)

        total = len(messages)
        avg_confidence = sum(m.get('confidence', 0) for m in messages) / max(total, 1)
        avg_response_time = sum(m.get('response_time', 0) for m in messages) / max(total, 1)

        type_counts: dict = {}
        for m in messages:
            t = m.get('message_type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1

        recent = [
            {
                'timestamp': m['timestamp'].isoformat() if m.get('timestamp') else datetime.now(timezone.utc).isoformat(),
                'from_id': m.get('from_id', ''),
                'content': m.get('content', ''),
                'message_type': m.get('message_type', 'unknown'),
                'confidence': m.get('confidence') or 0,
                'response_time': m.get('response_time') or 0,
            }
            for m in messages[:20]
        ]

        stats = escalation_service.get_stats()

        return {
            "total_messages": total,
            "avg_confidence": avg_confidence,
            "avg_response_time": avg_response_time,
            "type_distribution": type_counts,
            "recent_messages": recent,
            "escalation_count": stats.get("total_created", 0),
        }

    except Exception as e:
        logger.error(f"Metrics error: {e}", exc_info=True)
        return {
            "total_messages": 0,
            "avg_confidence": 0,
            "avg_response_time": 0,
            "type_distribution": {},
            "recent_messages": [],
            "escalation_count": 0,
        }


# ===========================================================================
# Development / Testing Endpoints (debug mode only)
# ===========================================================================

if settings.debug:

    @app.post("/test/message")
    async def test_message(
        content: str = "Hello, I need help with my order #12345",
        from_id: str = "test_user",
        channel: str = "web",
    ):
        """Quick test endpoint for development."""
        response = await chatbot.process_message(from_id, content, ChannelType(channel))
        return {
            "input": {"from_id": from_id, "content": content, "channel": channel},
            "response": {
                "content": response.content,
                "suggested_actions": response.suggested_actions,
                "escalate": response.escalate,
            } if response else None,
        }

    @app.get("/test/admin-token")
    async def get_test_admin_token():
        """Generate a dev admin token."""
        token = create_admin_token("test_admin")
        return {"token": token, "usage": "Authorization: Bearer <token>"}


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting in {'DEBUG' if settings.debug else 'PRODUCTION'} mode")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
