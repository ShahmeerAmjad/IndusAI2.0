# =======================
# Conversation Service — Multi-Turn Chat Management
# =======================
"""
Manages conversation threads for multi-turn chatbot interactions.
Each conversation stores context and message history.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


class ConversationService:
    def __init__(self, db_manager):
        self.db = db_manager

    async def create_conversation(
        self,
        user_id: Optional[str] = None,
        channel: str = "web",
        title: Optional[str] = None,
    ) -> Dict:
        """Create a new conversation and return its data."""
        if not self.db.pool:
            return self._fallback_conversation()

        conv_id = str(uuid.uuid4())
        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (id, user_id, channel, title)
                VALUES ($1, $2::uuid, $3, $4)
                RETURNING id, user_id, channel, title, context_summary,
                          message_count, last_message_at, created_at
                """,
                conv_id,
                user_id,
                channel,
                title,
            )
            return dict(row)

    async def get_or_create(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        channel: str = "web",
    ) -> Dict:
        """Return existing conversation or create a new one."""
        if conversation_id and self.db.pool:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id, channel, title, context_summary,
                           message_count, last_message_at, created_at
                    FROM conversations WHERE id = $1
                    """,
                    conversation_id,
                )
                if row:
                    return dict(row)

        return await self.create_conversation(user_id=user_id, channel=channel)

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        from_id: Optional[str] = None,
        message_type: Optional[str] = None,
        response_content: Optional[str] = None,
    ) -> Dict:
        """Add a message to the conversation and update counters."""
        if not self.db.pool:
            return {"id": str(uuid.uuid4()), "conversation_id": conversation_id}

        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        async with self.db.pool.acquire() as conn:
            # Insert message
            await conn.execute(
                """
                INSERT INTO messages (id, from_id, content, channel, message_type,
                                      response_content, conversation_id, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                msg_id,
                from_id or role,
                content,
                "web",
                message_type or "general_query",
                response_content,
                conversation_id,
                now,
            )

            # Update conversation counters
            title_update = ""
            args: list = [conversation_id, now]
            # Auto-title from first user message
            row = await conn.fetchrow(
                "SELECT message_count, title FROM conversations WHERE id = $1",
                conversation_id,
            )
            if row and row["message_count"] == 0 and role == "user":
                title_update = ", title = $3"
                args.append(content[:100])

            await conn.execute(
                f"""
                UPDATE conversations
                SET message_count = message_count + 1,
                    last_message_at = $2
                    {title_update}
                WHERE id = $1
                """,
                *args,
            )

            return {"id": msg_id, "conversation_id": conversation_id}

    async def get_history(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Get recent messages in a conversation, ordered oldest-first."""
        if not self.db.pool:
            return []

        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, from_id, content, message_type,
                       response_content, timestamp
                FROM messages
                WHERE conversation_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                conversation_id,
                limit,
            )
            # Return oldest-first for building LLM context
            return [dict(r) for r in reversed(rows)]

    async def get_recent_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Get recent conversations, optionally filtered by user."""
        if not self.db.pool:
            return []

        async with self.db.pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, channel, title, context_summary,
                           message_count, last_message_at, created_at
                    FROM conversations
                    WHERE user_id = $1
                    ORDER BY last_message_at DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, channel, title, context_summary,
                           message_count, last_message_at, created_at
                    FROM conversations
                    ORDER BY last_message_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            return [dict(r) for r in rows]

    async def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a single conversation by ID."""
        if not self.db.pool:
            return None

        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, channel, title, context_summary,
                       message_count, last_message_at, created_at
                FROM conversations WHERE id = $1
                """,
                conversation_id,
            )
            return dict(row) if row else None

    async def update_summary(self, conversation_id: str, summary: str) -> None:
        """Update the rolling context summary for a conversation."""
        if not self.db.pool:
            return

        async with self.db.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversations SET context_summary = $2 WHERE id = $1
                """,
                conversation_id,
                summary,
            )

    def _fallback_conversation(self) -> Dict:
        """Return a minimal conversation object when DB is unavailable."""
        return {
            "id": str(uuid.uuid4()),
            "user_id": None,
            "channel": "web",
            "title": None,
            "context_summary": None,
            "message_count": 0,
            "last_message_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
