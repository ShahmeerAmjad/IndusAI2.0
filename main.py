#!/usr/bin/env python3
"""
B2B AI Chatbot MVP - Production-Ready Version
A secure, scalable chatbot for B2B customer support
"""

import os
import re
import json
import asyncio
import logging
import time
import uuid
import html
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any, Union

# FastAPI and web framework
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, Header, Depends, status
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, field_validator
from contextlib import asynccontextmanager

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# HTTP client
import httpx

# JWT for authentication
import jwt

# NLP and AI
from fuzzywuzzy import fuzz

from metrics.metrics import ERROR_COUNTER
from models.models import BotResponse, ChannelType, CustomerMessage, MessageRequest
from services.ai_service import AIService
from services.business_logic import BusinessLogic
from services.chatbot_engine import ChatbotEngine
from services.communication_manager import CommunicationManager
from services.database_manager import DatabaseManager
from services.intent_classifier import IntentClassifier
from services.spam_detector import spam_detector
from services.escalation_service import EscalationService
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Database and caching


# Environment and configuration
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Monitoring
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Load environment variables
load_dotenv()

# Configure logging with security filter
class SecurityFilter(logging.Filter):
    """Filter sensitive data from logs"""
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            record.msg = self._redact_sensitive(str(record.msg))
        return True
    
    def _redact_sensitive(self, text):
        # Redact API keys and passwords
        text = re.sub(r'(api_key|token|password|secret)=["\']?([^"\'\s]+)', r'\1=***REDACTED***', text)
        # Redact phone numbers
        text = re.sub(r'\b\d{10,}\b', '***PHONE***', text)
        # Redact email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***EMAIL***', text)
        return text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
security_filter = SecurityFilter()
logger.addFilter(security_filter)

# =======================
# Configuration
# =======================

class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Basic app config
    app_name: str = "B2B AI Chatbot MVP"
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    admin_api_key: Optional[str] = Field(default=None, env="ADMIN_API_KEY")
    
    # Database URLs
    database_url: str = Field(default="postgresql://chatbot:password@localhost:5432/chatbot", env="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # WhatsApp Business API
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_phone_number_id: Optional[str] = Field(default=None, env="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_access_token: Optional[str] = Field(default=None, env="WHATSAPP_ACCESS_TOKEN")
    whatsapp_webhook_verify_token: Optional[str] = Field(default=None, env="WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    whatsapp_app_secret: Optional[str] = Field(default=None, env="WHATSAPP_APP_SECRET")
    
    # Anthropic AI
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ai_model: str = Field(default="claude-3-5-sonnet-20241022", env="AI_MODEL")
    ai_max_retries: int = Field(default=3, env="AI_MAX_RETRIES")
    ai_retry_delay: float = Field(default=1.0, env="AI_RETRY_DELAY")

    # Support contact info (configurable)
    support_email: str = Field(default="support@company.com", env="SUPPORT_EMAIL")
    support_phone: str = Field(default="1-800-TECH-HELP", env="SUPPORT_PHONE")

    # Circuit breaker settings
    circuit_breaker_threshold: int = Field(default=5, env="CIRCUIT_BREAKER_THRESHOLD")
    circuit_breaker_timeout: int = Field(default=60, env="CIRCUIT_BREAKER_TIMEOUT")

    # Email settings
    smtp_host: str = Field(default="localhost", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        if v == "dev-secret-key-change-in-production":
            raise ValueError("Must change secret key in production")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = 'ignore'

# Initialize settings
settings = Settings()

# =======================
# Rate Limiting Setup
# =======================

limiter = Limiter(key_func=get_remote_address)

# =======================
# Security
# =======================

security = HTTPBearer()

def create_admin_token(user_id: str) -> str:
    """Create admin JWT token"""
    payload = {
        "user_id": user_id,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin API token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid authentication")

def verify_whatsapp_signature(request_body: bytes, signature: str) -> bool:
    """Verify WhatsApp webhook signature"""
    if not settings.whatsapp_app_secret:
        return False
    
    expected_signature = hmac.new(
        settings.whatsapp_app_secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# Global database manager
db_manager = DatabaseManager(logger=logger, settings=settings)

# Global classifier
classifier = IntentClassifier()

# Global AI service
ai_service = AIService(logger=logger, settings=settings)

# Global escalation service
escalation_service = EscalationService(settings=settings, logger=logger, db_manager=db_manager)

# Global business logic (with settings and escalation service)
business_logic = BusinessLogic(
    ai_service=ai_service,
    db_manager=db_manager,
    settings=settings,
    escalation_service=escalation_service
)

# Global communication manager
comm_manager = CommunicationManager(logger=logger, settings=settings)

# Global chatbot engine
chatbot = ChatbotEngine(
    logger=logger,
    business_logic=business_logic,
    classifier=classifier,
    db_manager=db_manager,
    settings=settings
)

# =======================
# FastAPI Application
# =======================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting B2B AI Chatbot MVP")
    app.state.start_time = time.time()
    app.state.request_count = 0
    
    # Initialize database
    await db_manager.initialize()
    
    # Generate admin token for development
    if settings.debug and not settings.admin_api_key:
        admin_token = create_admin_token("admin")
        logger.info(f"Development admin token: {admin_token}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down B2B AI Chatbot MVP")
    await db_manager.close()
    await comm_manager.close()

# Create FastAPI app
app = FastAPI(
    title="B2B AI Chatbot MVP",
    description="Production-ready B2B customer service chatbot with AI enhancement",
    version="1.1.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.yourdomain.com", "http://localhost:3000"] if not settings.debug else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=86400
)

# Request counting middleware
@app.middleware("http")
async def count_requests(request: Request, call_next):
    app.state.request_count += 1
    response = await call_next(request)
    return response

# =======================
# Health & Monitoring
# =======================

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.1.0",
        "uptime_seconds": int(time.time() - app.state.start_time)
    }

@app.get("/health/detailed", dependencies=[Depends(verify_admin_token)])
async def detailed_health_check():
    """Detailed health check for monitoring systems"""
    db_healthy = False
    redis_healthy = False
    
    db_error = None
    redis_error = None

    # Check database
    if db_manager.pool:
        try:
            async with db_manager.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_healthy = True
        except Exception as e:
            db_error = str(e)
            logger.warning(f"Database health check failed: {e}")

    # Check Redis
    if db_manager.redis_client:
        try:
            await db_manager.redis_client.ping()
            redis_healthy = True
        except Exception as e:
            redis_error = str(e)
            logger.warning(f"Redis health check failed: {e}")
    
    return {
        "status": "healthy" if (db_healthy or not db_manager.pool) else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.1.0",
        "services": {
            "database": {
                "connected": db_manager.pool is not None,
                "healthy": db_healthy,
                "pool_size": db_manager.pool.get_size() if db_manager.pool else 0,
                "error": db_error
            },
            "redis": {
                "connected": db_manager.redis_client is not None,
                "healthy": redis_healthy,
                "error": redis_error
            },
            "whatsapp": {
                "configured": bool(settings.whatsapp_access_token)
            },
            "ai": {
                "available": ai_service.client is not None,
                "circuit_breaker": ai_service.get_circuit_breaker_state()
            }
        },
        "metrics": {
            "uptime_seconds": time.time() - app.state.start_time,
            "total_requests": app.state.request_count
        },
        "escalation": escalation_service.get_stats()
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")

# =======================
# API Endpoints
# =======================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "B2B AI Chatbot MVP",
        "version": "1.1.0",
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "features": [
            "WhatsApp Business integration",
            "AI-enhanced responses",
            "Intent classification",
            "Rate limiting",
            "Session management",
            "Admin dashboard",
            "Prometheus metrics"
        ]
    }

async def _process_message_internal(request: Request, message_request: MessageRequest):
    """Internal message processing logic (shared by versioned and legacy endpoints)"""
    # Check for spam using centralized spam detector
    is_spam, spam_reason = spam_detector.is_spam(message_request.content)
    if is_spam:
        logger.warning(f"Spam message rejected: {spam_reason}")
        raise HTTPException(status_code=400, detail="Message rejected")

    # Process message
    channel = ChannelType(message_request.channel)
    response = await chatbot.process_message(
        message_request.from_id,
        message_request.content,
        channel
    )

    if response:
        return {
            "success": True,
            "response": {
                "content": response.content,
                "suggested_actions": response.suggested_actions,
                "escalate": response.escalate
            },
            "message_id": str(uuid.uuid4())
        }
    else:
        return {"success": False, "error": "Failed to process message"}


# API v1 endpoints (versioned)
@app.post("/api/v1/message")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def process_api_message_v1(request: Request, message_request: MessageRequest):
    """Process message via API (v1)"""
    try:
        return await _process_message_internal(request, message_request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API message error: {e}")
        ERROR_COUNTER.labels(error_type="api_error").inc()
        raise HTTPException(status_code=500, detail="Internal server error")


# Legacy endpoint (deprecated, redirects to v1)
@app.post("/api/message")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def process_api_message(request: Request, message_request: MessageRequest):
    """Process message via API (legacy - use /api/v1/message instead)"""
    try:
        result = await _process_message_internal(request, message_request)
        # Add deprecation notice
        result["_deprecation_notice"] = "This endpoint is deprecated. Please use /api/v1/message"
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API message error: {e}")
        ERROR_COUNTER.labels(error_type="api_error").inc()
        raise HTTPException(status_code=500, detail="Internal server error")

# =======================
# WhatsApp Webhook
# =======================

@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """WhatsApp webhook verification"""
    if (hub_mode == "subscribe" and 
        hub_verify_token == settings.whatsapp_webhook_verify_token):
        logger.info("WhatsApp webhook verified")
        return int(hub_challenge)
    
    raise HTTPException(status_code=403, detail="Webhook verification failed")

@app.post("/webhook/whatsapp")
@limiter.limit("100/minute")
async def handle_whatsapp_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature: str = Header(None, alias="X-Hub-Signature-256")
):
    """Handle incoming WhatsApp messages"""
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature if provided
        if x_hub_signature and settings.whatsapp_app_secret:
            signature = x_hub_signature.replace("sha256=", "")
            if not verify_whatsapp_signature(body, signature):
                logger.warning("Invalid WhatsApp webhook signature")
                raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Parse webhook data
        data = json.loads(body)
        
        if "entry" in data:
            for entry in data["entry"]:
                if "changes" in entry:
                    for change in entry["changes"]:
                        if change.get("field") == "messages":
                            messages = change.get("value", {}).get("messages", [])
                            for msg in messages:
                                if msg.get("type") == "text":
                                    background_tasks.add_task(
                                        process_whatsapp_message,
                                        msg["from"],
                                        msg["text"]["body"]
                                    )
        
        return {"status": "received"}
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        ERROR_COUNTER.labels(error_type="webhook_error").inc()
        return {"status": "error", "message": str(e)}

async def process_whatsapp_message(from_number: str, text: str):
    """Process incoming WhatsApp message"""
    try:
        # Process through chatbot
        response = await chatbot.process_message(from_number, text, ChannelType.WHATSAPP)
        
        if response:
            # Send response via WhatsApp
            success = await comm_manager.send_whatsapp_message(
                from_number, 
                response.content, 
                response.suggested_actions
            )
            
            # Handle escalation
            if response.escalate:
                logger.info(f"Escalation needed for {from_number}: {text[:50]}...")
                # TODO: Implement escalation logic (create ticket, notify support, etc.)
    
    except Exception as e:
        logger.error(f"WhatsApp message processing error: {e}")
        # Send error message to user
        await comm_manager.send_whatsapp_message(
            from_number,
            "I apologize, but I encountered an error. Please try again or contact our support team."
        )

# =======================
# Admin Dashboard
# =======================

@app.get("/admin/dashboard", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def admin_dashboard(request: Request, token: str = Query(None)):
    """Admin dashboard with optional token auth"""
    # Require admin_api_key to be configured in production
    if not settings.debug:
        if not settings.admin_api_key:
            raise HTTPException(status_code=503, detail="Admin dashboard not configured")
        if not token or token != settings.admin_api_key:
            raise HTTPException(status_code=403, detail="Unauthorized")
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>B2B Chatbot Admin Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                background: #f0f2f5; 
                color: #1a1a1a;
            }
            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; 
                padding: 2rem; 
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .header h1 { margin-bottom: 0.5rem; }
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                padding: 2rem;
            }
            .controls {
                margin-bottom: 2rem;
                display: flex;
                gap: 1rem;
                flex-wrap: wrap;
            }
            .btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1rem;
                transition: all 0.3s;
            }
            .btn:hover {
                background: #5a6fd8;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }
            .metrics { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 1.5rem; 
                margin-bottom: 2rem;
            }
            .metric-card { 
                background: white; 
                padding: 2rem; 
                border-radius: 12px; 
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                transition: transform 0.3s;
            }
            .metric-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            }
            .metric-value { 
                font-size: 2.5rem; 
                font-weight: bold; 
                color: #667eea; 
                margin-bottom: 0.5rem;
            }
            .metric-label { 
                color: #666; 
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .messages { 
                background: white; 
                border-radius: 12px; 
                box-shadow: 0 2px 8px rgba(0,0,0,0.08); 
                overflow: hidden;
            }
            .messages h2 {
                padding: 1.5rem;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            table { 
                width: 100%; 
                border-collapse: collapse;
            }
            th, td { 
                padding: 1rem 1.5rem; 
                text-align: left; 
                border-bottom: 1px solid #f0f0f0;
            }
            th { 
                background: #f8f9fa; 
                font-weight: 600;
                color: #666;
                text-transform: uppercase;
                font-size: 0.85rem;
                letter-spacing: 0.5px;
            }
            td { 
                color: #333;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .confidence-badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            .confidence-high { background: #d4edda; color: #155724; }
            .confidence-medium { background: #fff3cd; color: #856404; }
            .confidence-low { background: #f8d7da; color: #721c24; }
            .status-indicator {
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 0.5rem;
            }
            .status-healthy { background: #28a745; }
            .status-degraded { background: #ffc107; }
            .status-error { background: #dc3545; }
            .loading {
                text-align: center;
                padding: 2rem;
                color: #666;
            }
            .error {
                background: #f8d7da;
                color: #721c24;
                padding: 1rem;
                border-radius: 8px;
                margin: 1rem 0;
            }
            .token-input {
                flex: 1;
                min-width: 300px;
                padding: 0.75rem 1rem;
                border: 1px solid #ccc;
                border-radius: 8px;
                font-size: 1rem;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                outline: none;
                transition: border-color 0.3s, box-shadow 0.3s;
            }

            .token-input:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
            }

            .token-input::placeholder {
                color: #999;
                font-size: 0.95rem;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 B2B Chatbot Admin Dashboard</h1>
            <p>Monitor your AI customer service performance in real-time</p>
        </div>
        
        <div class="container">
            <div class="controls">
                <input id="jwt-token" class="token-input" placeholder="Enter JWT Access Token" />
                <button class="btn" onclick="setToken()">✅ Set Token</button>
                <button class="btn" onclick="loadData()">🔄 Refresh</button>
                <button class="btn" onclick="toggleAutoRefresh()">
                    <span id="auto-refresh-status">▶️</span> Auto-refresh
                </button>
            </div>
            
            <div class="metrics" id="metrics">
                <div class="metric-card">
                    <div class="metric-value" id="total-messages">-</div>
                    <div class="metric-label">Total Messages</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="avg-confidence">-</div>
                    <div class="metric-label">Avg Confidence</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="avg-response-time">-</div>
                    <div class="metric-label">Avg Response Time</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="health-status">-</div>
                    <div class="metric-label">System Health</div>
                </div>
            </div>
            
            <div class="messages">
                <h2>Recent Messages</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>From</th>
                            <th>Message</th>
                            <th>Type</th>
                            <th>Confidence</th>
                            <th>Response Time</th>
                        </tr>
                    </thead>
                    <tbody id="messages-tbody">
                        <tr><td colspan="6" class="loading">Loading messages...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            let autoRefreshInterval = null;
            let jwtToken = "";

            function setToken() {
                jwtToken = document.getElementById('jwt-token').value.trim();
                if (!jwtToken) {
                    alert('Please enter a valid JWT token');
                } else {
                    alert('JWT token set successfully!');
                    loadData();
                }
            }
            
            async function loadData() {
                try {
                    const headers = jwtToken 
                        ? { 'Authorization': 'Bearer ' + jwtToken }
                        : {};
                    
                    // Load metrics
                    const metricsResponse = await fetch('/admin/api/metrics', { headers });
                    if (!metricsResponse.ok) throw new Error('Failed to load metrics');
                    const metrics = await metricsResponse.json();
                    
                    // Update metric displays
                    document.getElementById('total-messages').textContent = metrics.total_messages;
                    document.getElementById('avg-confidence').textContent = (metrics.avg_confidence * 100).toFixed(1) + '%';
                    document.getElementById('avg-response-time').textContent = (metrics.avg_response_time * 1000).toFixed(0) + 'ms';
                    
                    // Load health status
                    const healthResponse = await fetch('/health', { headers });
                    const health = await healthResponse.json();
                    const healthEl = document.getElementById('health-status');
                    healthEl.innerHTML = '<span class="status-indicator status-healthy"></span>Healthy';
                    
                    // Update messages table
                    const tbody = document.getElementById('messages-tbody');
                    if (metrics.recent_messages.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="loading">No messages yet</td></tr>';
                    } else {
                        tbody.innerHTML = metrics.recent_messages.map(msg => {
                            const confidence = msg.confidence * 100;
                            let confidenceClass = 'confidence-low';
                            if (confidence >= 80) confidenceClass = 'confidence-high';
                            else if (confidence >= 60) confidenceClass = 'confidence-medium';
                            
                            const timestamp = new Date(msg.timestamp);
                            const timeStr = timestamp.toLocaleTimeString() + ' ' + timestamp.toLocaleDateString();
                            
                            return `
                                <tr>
                                    <td>${timeStr}</td>
                                    <td>${msg.from_id}</td>
                                    <td title="${msg.content}">${msg.content.substring(0, 50)}${msg.content.length > 50 ? '...' : ''}</td>
                                    <td>${msg.message_type}</td>
                                    <td><span class="confidence-badge ${confidenceClass}">${confidence.toFixed(0)}%</span></td>
                                    <td>${(msg.response_time * 1000).toFixed(0)}ms</td>
                                </tr>
                            `;
                        }).join('');
                    }
                } catch (error) {
                    console.error('Failed to load data:', error);
                    document.getElementById('messages-tbody').innerHTML = 
                        '<tr><td colspan="6" class="error">Failed to load data. Please try again.</td></tr>';
                }
            }
            
            function toggleAutoRefresh() {
                const statusEl = document.getElementById('auto-refresh-status');
                if (autoRefreshInterval) {
                    clearInterval(autoRefreshInterval);
                    autoRefreshInterval = null;
                    statusEl.textContent = '▶️';
                } else {
                    autoRefreshInterval = setInterval(loadData, 5000);
                    statusEl.textContent = '⏸️';
                }
            }
            
            // Load data on page load
            loadData();
            
            // Start auto-refresh
            toggleAutoRefresh();
        </script>
    </body>
    </html>
    """
    return html

@app.get("/admin/api/metrics")
async def get_admin_metrics(admin = Depends(verify_admin_token)):
    """Get metrics for admin dashboard"""
    try:
        messages = await db_manager.get_recent_messages(100)
        
        total_messages = len(messages)
        avg_confidence = sum(msg.get('confidence', 0) for msg in messages) / max(total_messages, 1)
        avg_response_time = sum(msg.get('response_time', 0) for msg in messages) / max(total_messages, 1)
        
        # Calculate message type distribution
        type_counts = {}
        for msg in messages:
            msg_type = msg.get('message_type', 'unknown')
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
        
        # Format recent messages for display
        recent_messages = []
        for msg in messages[:20]:  # Last 20 messages
            recent_messages.append({
                'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else datetime.now().isoformat(),
                'from_id': msg['from_id'],
                'content': msg['content'],
                'message_type': msg['message_type'],
                'confidence': msg['confidence'] or 0,
                'response_time': msg['response_time'] or 0
            })
        
        return {
            "total_messages": total_messages,
            "avg_confidence": avg_confidence,
            "avg_response_time": avg_response_time,
            "type_distribution": type_counts,
            "recent_messages": recent_messages
        }
    
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {
            "total_messages": 0,
            "avg_confidence": 0,
            "avg_response_time": 0,
            "type_distribution": {},
            "recent_messages": []
        }

# =======================
# Development/Testing Endpoints
# =======================

if settings.debug:
    @app.post("/test/message")
    async def test_message(
        content: str = "Hello, I need help with my order #12345",
        from_id: str = "test_user",
        channel: str = "web"
    ):
        """Test endpoint for development"""
        response = await chatbot.process_message(from_id, content, ChannelType(channel))
        return {
            "input": {
                "from_id": from_id,
                "content": content,
                "channel": channel
            },
            "response": {
                "content": response.content,
                "suggested_actions": response.suggested_actions,
                "escalate": response.escalate
            } if response else None
        }
    
    @app.get("/test/admin-token")
    async def get_test_admin_token():
        """Get admin token for testing"""
        token = create_admin_token("test_admin")
        return {
            "token": token,
            "usage": "Use this token in Authorization header as: Bearer {token}"
        }

# =======================
# Application Entry Point
# =======================

if __name__ == "__main__":
    import uvicorn
    
    # Validate critical settings
    if not settings.secret_key or len(settings.secret_key) < 32:
        logger.error("SECRET_KEY must be at least 32 characters long")
        exit(1)
    
    logger.info(f"Starting in {'DEBUG' if settings.debug else 'PRODUCTION'} mode")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
