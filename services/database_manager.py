# =======================
# Database Manager - PostgreSQL + Redis
# =======================

import json
import uuid
from typing import Dict, List, Optional

import asyncpg
import redis.asyncio as redis

from metrics.metrics import ERROR_COUNTER
from models.models import BotResponse, CustomerMessage


class DatabaseManager:
    def __init__(self, logger, settings):
        self.logger = logger
        self.settings = settings
        self.pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None

    async def initialize(self):
        """Initialize database and cache connections."""
        # PostgreSQL
        try:
            self.pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            self.logger.info("PostgreSQL connection pool established")
            await self._create_tables()
        except Exception as e:
            self.logger.error(f"PostgreSQL initialization failed: {e}")
            self.pool = None

        # Redis
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
            )
            await self.redis_client.ping()
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.error(f"Redis initialization failed: {e}")
            self.redis_client = None

    async def _create_tables(self):
        """Create required database tables and indexes."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    from_id VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    channel VARCHAR(20) NOT NULL,
                    message_type VARCHAR(50),
                    confidence REAL DEFAULT 0.0,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    response_content TEXT,
                    response_time REAL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    external_id VARCHAR(100) UNIQUE NOT NULL,
                    name VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    company VARCHAR(255),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_activity TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS escalation_tickets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    customer_id VARCHAR(100) NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT,
                    priority VARCHAR(20) DEFAULT 'medium',
                    status VARCHAR(20) DEFAULT 'open',
                    assigned_to VARCHAR(100),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_from_id ON messages(from_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_type_timestamp ON messages(message_type, timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_external_id ON customers(external_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_escalation_customer ON escalation_tickets(customer_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_escalation_status ON escalation_tickets(status)")

    # ------ Message persistence ------

    async def save_message(self, message: CustomerMessage, response: BotResponse, response_time: float):
        """Save message and response to database."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO messages
                    (id, from_id, content, channel, message_type, confidence, response_content, response_time, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    str(uuid.uuid4()),
                    message.from_id[:100],
                    message.content[:2000],
                    message.channel.value,
                    message.message_type.value,
                    float(message.confidence),
                    response.content[:5000],
                    float(response_time),
                    message.timestamp,
                )
        except Exception as e:
            self.logger.error(f"Failed to save message: {e}")
            ERROR_COUNTER.labels(error_type="database_save").inc()

    async def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """Get recent messages for admin dashboard."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT from_id, content, channel, message_type, confidence,
                           response_content, response_time, timestamp
                    FROM messages
                    ORDER BY timestamp DESC
                    LIMIT $1
                    """,
                    limit,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get recent messages: {e}")
            return []

    # ------ Session management (Redis) ------

    async def get_customer_session(self, customer_id: str) -> Optional[Dict]:
        """Get customer session from Redis cache."""
        if not self.redis_client:
            return None

        try:
            session_data = await self.redis_client.get(f"session:{customer_id}")
            if session_data:
                return json.loads(session_data)
        except Exception as e:
            self.logger.error(f"Failed to get session: {e}")

        return None

    async def save_customer_session(self, customer_id: str, session_data: Dict):
        """Save customer session to Redis with TTL."""
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                f"session:{customer_id}",
                86400,  # 24-hour TTL
                json.dumps(session_data),
            )
        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")

    # ------ Escalation tickets ------

    async def create_escalation_ticket(self, customer_id: str, subject: str, description: str, priority: str = "medium") -> Optional[str]:
        """Create an escalation ticket and return its ID."""
        if not self.pool:
            return None

        try:
            ticket_id = str(uuid.uuid4())
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO escalation_tickets (id, customer_id, subject, description, priority)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    ticket_id,
                    customer_id,
                    subject,
                    description,
                    priority,
                )
            return ticket_id
        except Exception as e:
            self.logger.error(f"Failed to create escalation ticket: {e}")
            return None

    async def get_open_tickets(self, limit: int = 50) -> List[Dict]:
        """Get open escalation tickets."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, customer_id, subject, priority, status, created_at
                    FROM escalation_tickets
                    WHERE status IN ('open', 'in_progress')
                    ORDER BY
                        CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                        created_at ASC
                    LIMIT $1
                    """,
                    limit,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get open tickets: {e}")
            return []

    # ------ Lifecycle ------

    async def close(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
        if self.redis_client:
            await self.redis_client.close()
