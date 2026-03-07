"""Tests for services.classification_feedback_service."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.classification_feedback_service import (
    ClassificationFeedbackService,
    set_feedback_service,
    get_feedback_service,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    db.pool = pool
    return db, conn


@pytest.fixture
def service(mock_db):
    db, _ = mock_db
    return ClassificationFeedbackService(db)


class TestClassificationFeedbackService:
    @pytest.mark.asyncio
    async def test_log_feedback(self, service, mock_db):
        """log_feedback inserts a row and returns a UUID."""
        _, conn = mock_db
        msg_id = str(uuid.uuid4())

        fb_id = await service.log_feedback(
            message_id=msg_id,
            ai_intent="request_quote",
            human_intent="request_quote",
            is_correct=True,
            ai_confidence=0.92,
            text_excerpt="Can you send me a quote for 500kg of resin?",
        )

        assert len(fb_id) == 36  # UUID format
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "INSERT INTO classification_feedback" in call_args[0]

    @pytest.mark.asyncio
    async def test_log_feedback_correction(self, service, mock_db):
        """log_feedback with is_correct=False stores the human correction."""
        _, conn = mock_db
        msg_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fb_id = await service.log_feedback(
            message_id=msg_id,
            ai_intent="request_quote",
            human_intent="place_order",
            is_correct=False,
            ai_confidence=0.45,
            text_excerpt="We'd like to order 200 units",
            corrected_by=user_id,
        )

        assert len(fb_id) == 36
        call_args = conn.execute.call_args[0]
        # Check human_intent is place_order (5th positional param)
        assert call_args[5] == "place_order"
        assert call_args[7] is False  # is_correct

    @pytest.mark.asyncio
    async def test_get_few_shot_examples(self, service, mock_db):
        """get_few_shot_examples returns formatted examples."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"human_intent": "request_quote", "text_excerpt": "quote for resin", "ai_confidence": 0.95},
            {"human_intent": "request_quote", "text_excerpt": "pricing on HDPE", "ai_confidence": 0.88},
        ])

        examples = await service.get_few_shot_examples("request_quote", limit=5)

        assert len(examples) == 2
        assert examples[0]["intent"] == "request_quote"
        assert examples[0]["text"] == "quote for resin"
        assert examples[1]["confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_get_few_shot_examples_empty(self, service, mock_db):
        """get_few_shot_examples returns empty list when no examples."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        examples = await service.get_few_shot_examples("sample_request")
        assert examples == []

    @pytest.mark.asyncio
    async def test_get_accuracy_stats(self, service, mock_db):
        """get_accuracy_stats returns overall and per-intent accuracy."""
        _, conn = mock_db
        # total, correct
        conn.fetchval = AsyncMock(side_effect=[100, 85])
        conn.fetch = AsyncMock(return_value=[
            {"ai_intent": "request_quote", "total": 40, "correct": 38},
            {"ai_intent": "order_status", "total": 30, "correct": 25},
            {"ai_intent": "technical_support", "total": 30, "correct": 22},
        ])

        stats = await service.get_accuracy_stats()

        assert stats["total_feedback"] == 100
        assert stats["correct"] == 85
        assert stats["accuracy"] == 85.0
        assert len(stats["per_intent"]) == 3
        assert stats["per_intent"][0]["intent"] == "request_quote"
        assert stats["per_intent"][0]["accuracy"] == 95.0

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_empty(self, service, mock_db):
        """get_accuracy_stats returns zeros when no feedback exists."""
        _, conn = mock_db
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        stats = await service.get_accuracy_stats()

        assert stats["total_feedback"] == 0
        assert stats["accuracy"] == 0.0
        assert stats["per_intent"] == []

    @pytest.mark.asyncio
    async def test_text_excerpt_truncation(self, service, mock_db):
        """Long text_excerpt is truncated to 500 chars."""
        _, conn = mock_db
        msg_id = str(uuid.uuid4())
        long_text = "A" * 1000

        await service.log_feedback(
            message_id=msg_id,
            ai_intent="technical_support",
            human_intent="technical_support",
            is_correct=True,
            text_excerpt=long_text,
        )

        call_args = conn.execute.call_args[0]
        # text_excerpt is 6th positional param
        assert len(call_args[6]) == 500

    def test_module_di(self):
        """Module-level DI works."""
        svc = MagicMock()
        set_feedback_service(svc)
        assert get_feedback_service() is svc
        set_feedback_service(None)
