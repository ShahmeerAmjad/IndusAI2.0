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
from services.conversation_service import ConversationService
from services.communication_manager import CommunicationManager
from services.database_manager import DatabaseManager
from services.escalation_service import EscalationService
from services.intent_classifier import IntentClassifier
from services.spam_detector import spam_detector

# Knowledge Graph & AI (v3)
from services.graph.neo4j_client import Neo4jClient
from services.graph.graph_service import GraphService
from services.ai.claude_client import ClaudeClient
from services.ai.embedding_client import VoyageEmbeddingClient
from services.ai.llm_router import LLMRouter
from services.ai.part_number_parser import PartNumberParser
from services.ai.entity_extractor import EntityExtractor
from services.graphrag.query_engine import GraphRAGQueryEngine

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
from routes.auth import router as auth_router, set_auth_service, get_current_user
from services.auth_service import AuthService
from routes.sourcing import router as sourcing_router, set_sourcing_services
from routes.rfq import router as rfq_router, set_rfq_db
from routes.graph import router as graph_router, set_graph_services
from routes.admin_graph import router as admin_router, set_admin_services, set_seed_pipeline
from routes.reports import router as reports_router, set_report_service
from routes.bulk import router as bulk_router, set_bulk_service
from routes.email_admin import router as email_admin_router, set_email_admin_services
from services.report_service import ReportService
from services.bulk_import_service import BulkImportService
from services.seller_service import SellerService
from services.intelligence.location import LocationOptimizer
from services.intelligence.price_comparator import PriceComparator
from services.intelligence.reliability import ReliabilityScorer
from services.intelligence.freshness_scheduler import FreshnessScheduler
from services.ingestion.web_scraper import WebScraper
from services.multi_intent_classifier import MultiIntentClassifier, set_classifier
from services.auto_response_engine import AutoResponseEngine, set_response_engine
from routes.inbox import router as inbox_router, set_inbox_services
from routes.documents import router as documents_router, set_document_services
from routes.customer_accounts import router as customer_accounts_router, set_customer_account_services
from routes.knowledge_base import router as kb_router, set_kb_service, set_chempoint_scraper
from routes.ingestion_ws import router as ingestion_ws_router, set_ingestion_pipeline
from routes.settings import router as settings_router

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

    # Anthropic AI (Claude)
    anthropic_api_key: Optional[str] = Field(default=None)
    ai_model: str = Field(default="claude-sonnet-4-6-20250514")
    ai_max_retries: int = Field(default=3)
    ai_retry_delay: float = Field(default=1.0)

    # Voyage AI (Embeddings)
    voyage_api_key: Optional[str] = Field(default=None)

    # Firecrawl (Web Scraping)
    firecrawl_api_key: Optional[str] = Field(default=None)

    # Neo4j Knowledge Graph
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="changeme")

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

    # Email ingestion pipeline
    email_encryption_key: Optional[str] = Field(default=None)
    email_poll_interval_seconds: int = Field(default=60)
    email_max_messages_per_poll: int = Field(default=50)
    email_attachment_dir: str = Field(default="data/email_attachments")
    email_retention_days: int = Field(default=90)

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
part_parser = PartNumberParser()
entity_extractor = EntityExtractor()
ai_service = AIService(logger=logger, settings=settings)
escalation_service = EscalationService(settings=settings, logger=logger, db_manager=db_manager)
comm_manager = CommunicationManager(logger=logger, settings=settings)

# Platform services — initialised after DB pool is ready (see lifespan)
erp_connector = MockERPConnector()
workflow_engine = WorkflowEngine(db_manager, logger)
product_service = ProductService(db_manager, erp_connector, logger)
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
conversation_service = ConversationService(db_manager)
chatbot = ChatbotEngine(
    logger=logger,
    business_logic=business_logic,
    classifier=classifier,
    db_manager=db_manager,
    settings=settings,
    conversation_service=conversation_service,
    ai_service=ai_service,
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

    # Initialize LLM Router (Claude + Voyage AI) — independent of Neo4j
    llm_router = None
    try:
        claude_client = ClaudeClient(api_key=settings.anthropic_api_key)
        embedding_client = VoyageEmbeddingClient(api_key=settings.voyage_api_key)
        llm_router = LLMRouter(claude_client=claude_client, embedding_client=embedding_client)
        app.state.llm_router = llm_router

        # Wire intent classifier with LLM router
        classifier._llm = llm_router
        logger.info("LLM Router ready (Claude + Voyage AI)")
    except Exception as e:
        logger.warning("LLM Router initialization failed (non-fatal): %s", e)
        app.state.llm_router = None

    # Initialize Neo4j Knowledge Graph
    neo4j_client = None
    try:
        from services.graph.schema import create_schema

        neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        await neo4j_client.connect()
        await create_schema(neo4j_client)
        graph_service = GraphService(neo4j_client)
        logger.info("Neo4j knowledge graph ready")

        # Initialize sourcing intelligence services
        seller_service = SellerService(db_manager, logger)
        location_optimizer = LocationOptimizer()
        price_comparator = PriceComparator()

        # Initialize GraphRAG Query Engine (with sourcing)
        query_engine = GraphRAGQueryEngine(
            graph_service=graph_service,
            llm_router=llm_router,
            intent_classifier=classifier,
            entity_extractor=entity_extractor,
            part_parser=part_parser,
            seller_service=seller_service,
            location_optimizer=location_optimizer,
            price_comparator=price_comparator,
        )

        # Wire sourcing API routes
        set_sourcing_services(query_engine, seller_service, db_manager)

        # Wire GraphRAG into chat pipeline
        business_logic.query_engine = query_engine

        # Create sync service
        from services.graph.sync import GraphSyncService
        graph_sync = GraphSyncService(
            graph_service=graph_service,
            embedding_client=embedding_client,
        )
        app.state.graph_sync = graph_sync

        # Inject into platform services
        product_service._graph_sync = graph_sync
        inventory_service._graph_sync = graph_sync

        # Wire graph API routes
        set_graph_services(graph_service, graph_sync)

        # Store on app state for endpoint access
        app.state.neo4j_client = neo4j_client
        app.state.graph_service = graph_service
        app.state.query_engine = query_engine
        app.state.seller_service = seller_service

        # Initialize freshness scheduler
        reliability_scorer = ReliabilityScorer()
        web_scraper = WebScraper(
            llm_router=llm_router,
            firecrawl_api_key=settings.firecrawl_api_key,
        )
        app.state.web_scraper = web_scraper
        freshness_scheduler = FreshnessScheduler(
            seller_service=seller_service,
            web_scraper=web_scraper,
            reliability_scorer=reliability_scorer,
            db_manager=db_manager,
        )
        freshness_scheduler.start()
        app.state.freshness_scheduler = freshness_scheduler

        logger.info("GraphRAG query engine ready (with sourcing)")

    except Exception as e:
        logger.warning("Knowledge graph initialization failed (non-fatal): %s", e)
        app.state.neo4j_client = None
        app.state.graph_service = None
        app.state.query_engine = None

    # Create platform tables & indexes
    if db_manager.pool:
        try:
            from services.platform.schema import (
                PLATFORM_SCHEMA, PLATFORM_INDEXES,
                SUPPLIER_SALES_SCHEMA, SUPPLIER_SALES_INDEXES,
            )
            async with db_manager.pool.acquire() as conn:
                await conn.execute(PLATFORM_SCHEMA)
                await conn.execute(PLATFORM_INDEXES)
                await conn.execute(SUPPLIER_SALES_SCHEMA)
                await conn.execute(SUPPLIER_SALES_INDEXES)

                # Email ingestion tables
                from services.platform.schema import EMAIL_SCHEMA, EMAIL_INDEXES
                await conn.execute(EMAIL_SCHEMA)
                await conn.execute(EMAIL_INDEXES)
            logger.info("Platform schema ready")
        except Exception as e:
            logger.error(f"Platform schema creation failed: {e}")

    # Initialize auth service
    auth_service = AuthService(db_manager=db_manager, settings=settings)
    set_auth_service(auth_service)
    app.state.auth_service = auth_service

    # Wire RFQ routes
    set_rfq_db(db_manager)

    # Wire admin debug routes
    set_admin_services(
        graph_service=getattr(app.state, "graph_service", None),
        db_manager=db_manager,
    )

    # Wire report + bulk import services
    set_report_service(ReportService(db_manager.pool))
    set_bulk_service(BulkImportService(db_manager.pool))

    # Inject services into the platform API router
    set_services({
        "products": product_service,
        "inventory": inventory_service,
        "customers": customer_service,
        "pricing": pricing_service,
        "orders": order_service,
        "quotes": quote_service,
        "procurement": procurement_service,
        "invoices": invoice_service,
        "rma": rma_service,
        "workflow": workflow_engine,
        "analytics": analytics_service,
    })

    # Seed demo user (idempotent)
    if settings.debug and db_manager.pool:
        try:
            async with db_manager.pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM users WHERE email = $1", "demo@indusai.com"
                )
                if not exists:
                    org = await conn.fetchrow(
                        """INSERT INTO organizations (name, slug)
                           VALUES ('IndusAI Demo', 'indusai-demo')
                           ON CONFLICT DO NOTHING
                           RETURNING id""",
                    )
                    org_id = org["id"] if org else await conn.fetchval(
                        "SELECT id FROM organizations WHERE slug = 'indusai-demo'"
                    )
                    pw_hash = auth_service.hash_password("demo1234")
                    await conn.execute(
                        """INSERT INTO users (email, password_hash, name, org_id, role)
                           VALUES ($1, $2, $3, $4, 'admin')""",
                        "demo@indusai.com", pw_hash, "Demo User", str(org_id),
                    )
                    logger.info("Demo user seeded: demo@indusai.com / demo1234")
        except Exception as e:
            logger.error("Demo user seed failed: %s", e)

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

    # Seed seller demo data in debug mode
    if settings.debug and db_manager.pool:
        try:
            from services.platform.seed_sellers import seed_sellers
            await seed_sellers(db_manager, logger)
        except Exception as e:
            logger.error("Seller seed failed: %s", e)

    # Seed Neo4j demo data in debug mode
    if settings.debug and neo4j_client:
        try:
            from services.graph.seed_demo import seed_graph
            embed_client = getattr(app.state, "llm_router", None)
            embed_client = embed_client._embeddings if embed_client else None
            stats = await seed_graph(app.state.graph_service, embedding_client=embed_client)
            logger.info("Neo4j demo data seeded: %s", stats)
        except Exception as e:
            logger.error("Neo4j seed failed: %s", e)

    # Bulk sync PG products to Neo4j
    if neo4j_client and db_manager.pool:
        try:
            sync = getattr(app.state, "graph_sync", None)
            if sync:
                stats = await sync.bulk_sync_products(db_manager)
                logger.info("Bulk PG→Neo4j sync: %s", stats)
        except Exception as e:
            logger.warning("Bulk sync failed: %s", e)

    # Email ingestion pipeline (non-fatal)
    if db_manager.pool:
        try:
            from services.email.encryption import FernetEncryption
            from services.email.pii_scanner import PIIScanner
            from services.email.parser import EmailParser
            from services.email.connector import GmailConnector
            from services.email.ingestion_service import (
                EmailIngestionService, set_ingestion_service,
            )

            email_encryption = FernetEncryption(settings.email_encryption_key)
            gmail_connector = GmailConnector(db_manager, email_encryption, logger)
            email_parser = EmailParser()
            pii_scanner = PIIScanner()

            email_ingestion = EmailIngestionService(
                db_manager=db_manager,
                connector=gmail_connector,
                parser=email_parser,
                pii_scanner=pii_scanner,
                encryption=email_encryption,
                logger=logger,
                attachment_dir=settings.email_attachment_dir,
                max_messages_per_poll=settings.email_max_messages_per_poll,
                redis_client=getattr(comm_manager, "redis", None),
            )
            set_ingestion_service(email_ingestion)
            set_email_admin_services(db_manager, email_encryption, email_ingestion)

            # Add polling job to existing scheduler
            sched = getattr(app.state, "freshness_scheduler", None)
            if sched and hasattr(sched, "_scheduler"):
                sched._scheduler.add_job(
                    email_ingestion.poll_all_inboxes,
                    "interval",
                    seconds=settings.email_poll_interval_seconds,
                    id="email_poll",
                    name="Poll email inboxes",
                )
                sched._scheduler.add_job(
                    lambda: email_ingestion.purge_old_messages(settings.email_retention_days),
                    "cron",
                    day_of_week="sun", hour=4,
                    id="email_retention_purge",
                    name="Purge old email payloads",
                )
                logger.info("Email ingestion polling scheduled (%ds interval)",
                            settings.email_poll_interval_seconds)
            else:
                logger.warning("No scheduler available — email polling not started")

        except Exception as e:
            logger.warning("Email ingestion setup failed (non-fatal): %s", e)

    # Multi-intent classifier & auto-response engine (non-fatal)
    try:
        _llm = getattr(app.state, "llm_router", None)
        _graph = getattr(app.state, "graph_service", None)

        # Classification feedback service
        from services.classification_feedback_service import (
            ClassificationFeedbackService, set_feedback_service,
        )
        feedback_service = ClassificationFeedbackService(db_manager)
        set_feedback_service(feedback_service)

        multi_classifier = MultiIntentClassifier(llm_router=_llm, feedback_service=feedback_service)
        set_classifier(multi_classifier)
        app.state.multi_intent_classifier = multi_classifier

        # TDS/SDS service (needs neo4j_client)
        _neo4j = getattr(app.state, "neo4j_client", None)
        _tds_sds = None
        if _neo4j:
            from services.graph.tds_sds_service import TDSSDSGraphService
            _tds_sds = TDSSDSGraphService(_neo4j)

        response_engine = AutoResponseEngine(
            graph_service=_graph,
            tds_sds_service=_tds_sds,
            llm_router=_llm,
            db_manager=db_manager,
        )
        set_response_engine(response_engine)
        app.state.auto_response_engine = response_engine

        # Wire inbox routes
        set_inbox_services(
            db_manager=db_manager,
            classifier=multi_classifier,
            response_engine=response_engine,
        )

        # Wire document routes
        from services.document_service import DocumentService
        doc_service = DocumentService(db_manager, ai_service=_llm)
        set_document_services(document_service=doc_service)

        # Wire customer account routes
        from services.customer_account_service import CustomerAccountService
        acct_service = CustomerAccountService(db_manager)
        set_customer_account_services(account_service=acct_service)

        # Wire knowledge base routes
        from services.knowledge_base_service import KnowledgeBaseService
        kb_service = KnowledgeBaseService(
            pool=db_manager.pool,
            graph_service=getattr(app.state, "neo4j_client", None),
            llm_router=_llm,
        )
        set_kb_service(kb_service)
        if settings.firecrawl_api_key:
            from services.ingestion.chempoint_scraper import ChempointScraper
            chempoint_scraper = ChempointScraper(
                firecrawl_api_key=settings.firecrawl_api_key, llm_router=_llm,
            )
            set_chempoint_scraper(chempoint_scraper)
        logger.info("Knowledge base routes wired")

        # Wire post-ingest auto-classification into email ingestion service
        from services.email.ingestion_service import get_ingestion_service
        _ingestion = get_ingestion_service()
        if _ingestion and multi_classifier and response_engine:
            async def _auto_classify_callback(message_id: str, body: str):
                """Classify new message and generate AI draft response."""
                try:
                    result = await multi_classifier.classify(body)
                    intents_json = [
                        {"intent": i.intent.value if hasattr(i.intent, "value") else str(i.intent),
                         "confidence": i.confidence, "text_span": i.text_span}
                        for i in result.intents
                    ]
                    # Generate AI draft
                    draft = await response_engine.generate_draft(
                        body=body, intents=result, customer_account=None,
                    )
                    # Update message with classification + draft
                    async with db_manager.pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE inbound_messages
                               SET intents = $2, ai_draft_response = $3,
                                   ai_confidence = $4, status = 'classified',
                                   updated_at = now()
                               WHERE id = $1""",
                            uuid.UUID(message_id),
                            json.dumps(intents_json),
                            draft.get("response_text", ""),
                            draft.get("confidence", 0.0),
                        )
                    logger.info("Auto-classified message %s: %d intents, confidence=%.2f",
                                message_id, len(result.intents), draft.get("confidence", 0.0))
                except Exception as exc:
                    logger.warning("Auto-classification failed for %s: %s", message_id, exc)

            _ingestion.set_post_ingest_callback(_auto_classify_callback)
            logger.info("Post-ingest auto-classification callback wired")

        # Wire seed-chempoint pipeline (use ChempointScraper, not WebScraper)
        _cp_scraper = chempoint_scraper if settings.firecrawl_api_key else None
        if _tds_sds and doc_service and _cp_scraper:
            from services.ingestion.seed_chempoint import ChempointSeedPipeline
            seed_pipeline = ChempointSeedPipeline(
                scraper=_cp_scraper, doc_service=doc_service,
                graph_service=_tds_sds, db_manager=db_manager,
                llm_router=_llm,
            )
            set_seed_pipeline(seed_pipeline)
            set_ingestion_pipeline(seed_pipeline)
            logger.info("Seed-chempoint pipeline ready (with WebSocket ingestion)")

        logger.info("Multi-intent classifier, auto-response engine & API routes ready")
    except Exception as e:
        logger.warning("Classifier/response engine setup failed (non-fatal): %s", e)

    if settings.debug:
        token = create_admin_token("admin")
        logger.info(f"Dev admin token: {token}")

        # Seed inbox with sample messages in debug mode
        if db_manager.pool:
            from services.platform.seed_inbox import seed_inbox_messages
            await seed_inbox_messages(db_manager.pool)

    yield

    logger.info(f"Shutting down {settings.app_name}")
    # Stop freshness scheduler
    scheduler = getattr(app.state, "freshness_scheduler", None)
    if scheduler:
        scheduler.shutdown()

    # Close Neo4j connection
    if neo4j_client:
        try:
            await neo4j_client.close()
            logger.info("Neo4j connection closed")
        except Exception as e:
            logger.warning("Neo4j cleanup failed: %s", e)
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
app.include_router(auth_router)
app.include_router(sourcing_router)
app.include_router(rfq_router)
app.include_router(graph_router)
app.include_router(admin_router)
app.include_router(reports_router)
app.include_router(bulk_router)
app.include_router(email_admin_router)
app.include_router(inbox_router)
app.include_router(documents_router)
app.include_router(customer_accounts_router)
app.include_router(kb_router)
app.include_router(ingestion_ws_router)
app.include_router(settings_router)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — read allowed origins from env
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else []
if not _cors_origins:
    _cors_origins = ["*"] if settings.debug else ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
    neo4j_healthy = False
    db_error = None
    redis_error = None
    neo4j_error = None

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

    neo4j_client = getattr(app.state, "neo4j_client", None)
    if neo4j_client:
        try:
            neo4j_healthy = await neo4j_client.health_check()
        except Exception as e:
            neo4j_error = str(e)

    # Neo4j graph stats (if available)
    graph_stats = None
    graph_service = getattr(app.state, "graph_service", None)
    if graph_service and neo4j_healthy:
        try:
            graph_stats = await graph_service.get_graph_stats()
        except Exception:
            pass

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
            "neo4j": {
                "connected": neo4j_client is not None,
                "healthy": neo4j_healthy,
                "graph_stats": graph_stats,
                "error": neo4j_error,
            },
            "whatsapp": {"configured": bool(settings.whatsapp_access_token)},
            "ai": {
                "available": ai_service.client is not None,
                "circuit_breaker": ai_service.get_circuit_breaker_state(),
            },
            "graphrag": {
                "available": getattr(app.state, "query_engine", None) is not None,
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
            "Knowledge Graph Intelligence (Neo4j GraphRAG)",
            "AI-enhanced Conversational Interface (Claude)",
            "WhatsApp Business Integration",
            "Prometheus Metrics & Admin Dashboard",
        ],
    }


# ===========================================================================
# Channels / Omnichannel API
# ===========================================================================


@platform_router.get("/channels/messages")
async def get_channel_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: Optional[str] = Query(None, pattern="^(whatsapp|email|web|sms)$"),
):
    """Get paginated message history with optional channel filter."""
    if not db_manager.pool:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    async with db_manager.pool.acquire() as conn:
        where = "WHERE channel = $3" if channel else ""
        params_count: list = [page_size, (page - 1) * page_size]
        params_rows: list = [page_size, (page - 1) * page_size]
        if channel:
            params_count.append(channel)
            params_rows.append(channel)

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM messages {where}",
            *([channel] if channel else []),
        )
        rows = await conn.fetch(
            f"""
            SELECT id, from_id, content, channel, message_type, confidence,
                   response_content, response_time, timestamp
            FROM messages {where}
            ORDER BY timestamp DESC
            LIMIT $1 OFFSET $2
            """,
            page_size, (page - 1) * page_size,
            *([channel] if channel else []),
        )
        items = [dict(r) for r in rows]
        for item in items:
            if item.get("id"):
                item["id"] = str(item["id"])
            if item.get("timestamp"):
                item["timestamp"] = item["timestamp"].isoformat()

    import math as _math
    total_pages = _math.ceil(total / page_size) if total else 0
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


@platform_router.get("/channels/stats")
async def get_channel_stats():
    """Get per-channel message counts and aggregate metrics."""
    if not db_manager.pool:
        return {"channels": {}, "total_messages": 0, "total_escalations": 0}

    async with db_manager.pool.acquire() as conn:
        channel_rows = await conn.fetch(
            """
            SELECT channel, COUNT(*) as message_count,
                   AVG(response_time) as avg_response_time,
                   AVG(confidence) as avg_confidence,
                   MAX(timestamp) as last_message_at
            FROM messages
            GROUP BY channel
            ORDER BY message_count DESC
            """
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM messages")
        escalation_count = await conn.fetchval(
            "SELECT COUNT(*) FROM escalation_tickets WHERE status IN ('open', 'in_progress')"
        )
        total_escalations = await conn.fetchval("SELECT COUNT(*) FROM escalation_tickets")

    channels = {}
    for row in channel_rows:
        channels[row["channel"]] = {
            "message_count": row["message_count"],
            "avg_response_time": round(float(row["avg_response_time"] or 0), 2),
            "avg_confidence": round(float(row["avg_confidence"] or 0), 2),
            "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
        }

    return {
        "channels": channels,
        "total_messages": total or 0,
        "open_escalations": escalation_count or 0,
        "total_escalations": total_escalations or 0,
    }


@platform_router.get("/channels/escalations")
async def get_escalation_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(open|in_progress|resolved|closed)$"),
):
    """Get escalation tickets with optional status filter."""
    if not db_manager.pool:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    async with db_manager.pool.acquire() as conn:
        where = "WHERE status = $3" if status else ""

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM escalation_tickets {where}",
            *([status] if status else []),
        )
        rows = await conn.fetch(
            f"""
            SELECT id, customer_id, subject, description, priority, status,
                   assigned_to, created_at, updated_at
            FROM escalation_tickets {where}
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                created_at DESC
            LIMIT $1 OFFSET $2
            """,
            page_size, (page - 1) * page_size,
            *([status] if status else []),
        )
        items = [dict(r) for r in rows]
        for item in items:
            if item.get("id"):
                item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()

    import math as _math
    total_pages = _math.ceil(total / page_size) if total else 0
    return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


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
        conversation_id=message_request.conversation_id,
    )

    if response:
        result = {
            "success": True,
            "response": {
                "content": response.content,
                "suggested_actions": response.suggested_actions,
                "escalate": response.escalate,
            },
            "message_id": str(uuid.uuid4()),
        }
        # Include conversation_id for multi-turn
        conv_id = (response.metadata or {}).get("conversation_id")
        if conv_id:
            result["conversation_id"] = conv_id
        return result

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
