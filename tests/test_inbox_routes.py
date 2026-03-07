"""Tests for routes.inbox — inbound message inbox API."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from routes.inbox import router, set_inbox_services
import routes.inbox as inbox_mod


@pytest.fixture(autouse=True)
def setup_services():
    """Set up mock services for all tests."""
    db = MagicMock()
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    db.pool = pool

    classifier = AsyncMock()
    response_engine = AsyncMock()

    set_inbox_services(db_manager=db, classifier=classifier, response_engine=response_engine)

    yield {
        "db": db, "conn": conn, "pool": pool,
        "classifier": classifier, "response_engine": response_engine,
    }
    set_inbox_services(None, None, None)


class TestListMessages:
    @pytest.mark.asyncio
    async def test_list_messages_basic(self, setup_services):
        conn = setup_services["conn"]
        conn.fetch.return_value = [
            {"id": "msg-1", "from_address": "john@acme.com", "subject": "Quote",
             "status": "new", "channel": "email", "intents": None,
             "ai_confidence": None, "assigned_to": None, "created_at": "2026-03-05"},
        ]
        conn.fetchval.return_value = 1
        from routes.inbox import list_messages
        result = await list_messages()
        assert len(result["messages"]) == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_list_messages_with_filters(self, setup_services):
        conn = setup_services["conn"]
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0
        from routes.inbox import list_messages
        result = await list_messages(status="new", channel="email")
        assert result["total"] == 0
        # Verify SQL has filter params
        call_args = conn.fetch.call_args
        assert "new" in call_args[0]
        assert "email" in call_args[0]


class TestGetMessage:
    @pytest.mark.asyncio
    async def test_get_message_found(self, setup_services):
        conn = setup_services["conn"]
        conn.fetchrow.return_value = {
            "id": "msg-1", "from_address": "john@acme.com", "subject": "Quote",
            "body": "Need quote for Polyox", "status": "new",
            "intents": '[{"intent": "request_quote"}]',
            "ai_draft_response": "Here is your quote...",
            "ai_confidence": 0.85, "assigned_to": None,
            "customer_account_id": None, "channel": "email",
            "created_at": "2026-03-05",
        }
        from routes.inbox import get_message
        result = await get_message("msg-1")
        assert result["from_address"] == "john@acme.com"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, setup_services):
        conn = setup_services["conn"]
        conn.fetchrow.return_value = None
        from routes.inbox import get_message
        with pytest.raises(Exception) as exc_info:
            await get_message("nonexistent")
        assert exc_info.value.status_code == 404


class TestApproveMessage:
    @pytest.mark.asyncio
    async def test_approve(self, setup_services):
        conn = setup_services["conn"]
        conn.execute.return_value = "UPDATE 1"
        from routes.inbox import approve_message
        result = await approve_message("msg-1")
        assert result["status"] == "approved"
        conn.execute.assert_called_once()


class TestEscalateMessage:
    @pytest.mark.asyncio
    async def test_escalate(self, setup_services):
        conn = setup_services["conn"]
        conn.execute.return_value = "UPDATE 1"
        from routes.inbox import escalate_message
        result = await escalate_message("msg-1", assigned_to="agent-1")
        assert result["status"] == "escalated"
        assert result["assigned_to"] == "agent-1"


class TestUpdateDraft:
    @pytest.mark.asyncio
    async def test_update_draft(self, setup_services):
        conn = setup_services["conn"]
        conn.execute.return_value = "UPDATE 1"
        from routes.inbox import update_draft, DraftUpdateRequest
        body = DraftUpdateRequest(response_text="Edited draft")
        result = await update_draft("msg-1", body)
        assert result["draft_updated"] is True


class TestFeedback:
    @pytest.mark.asyncio
    async def test_submit_feedback(self, setup_services):
        conn = setup_services["conn"]
        conn.execute.return_value = "INSERT 1"
        from routes.inbox import submit_feedback, FeedbackRequest
        body = FeedbackRequest(
            original_intent="request_quote",
            corrected_intent="place_order",
            notes="Was actually placing an order",
        )
        result = await submit_feedback("msg-1", body)
        assert result["feedback_recorded"] is True


class TestClassifyMessage:
    @pytest.mark.asyncio
    async def test_classify(self, setup_services):
        conn = setup_services["conn"]
        conn.fetchrow.return_value = {"id": "msg-1", "body": "I need a quote"}
        conn.execute.return_value = "UPDATE 1"

        from services.ai.models import IntentResult, IntentType, MultiIntentResult, EntityResult

        classifier = setup_services["classifier"]
        classifier.classify.return_value = MultiIntentResult(
            intents=[IntentResult(intent=IntentType.REQUEST_QUOTE, confidence=0.9)],
            entities=EntityResult(),
        )
        response_engine = setup_services["response_engine"]
        response_engine.generate_draft.return_value = {
            "response_text": "Draft response",
            "confidence": 0.85,
        }

        from routes.inbox import classify_message
        result = await classify_message("msg-1")
        assert result["status"] == "classified"
        assert "request_quote" in result["intents"]


class TestMessageStats:
    @pytest.mark.asyncio
    async def test_stats(self, setup_services):
        conn = setup_services["conn"]
        conn.fetch.side_effect = [
            [{"status": "new", "count": 10}, {"status": "classified", "count": 5}],
            [{"intent": "request_quote", "count": 8}],
        ]
        conn.fetchval.return_value = 15
        from routes.inbox import message_stats
        result = await message_stats()
        assert result["total"] == 15
        assert len(result["by_status"]) == 2
