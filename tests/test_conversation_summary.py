# =======================
# Tests — Conversation Context Summarization
# =======================

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.models import BotResponse, ChannelType, MessageType
from services.chatbot_engine import ChatbotEngine


@pytest.fixture
def mock_deps():
    logger = MagicMock()
    business_logic = AsyncMock()
    business_logic.process_message.return_value = BotResponse(
        content="Response text",
        suggested_actions=[],
    )
    classifier = MagicMock()
    classifier.classify.return_value = (MessageType.GENERAL_QUERY, 0.8)
    db_manager = MagicMock()
    db_manager.save_message = AsyncMock()
    settings = MagicMock()
    settings.support_email = "support@test.com"
    settings.ai_model = "claude-3-5-sonnet-20241022"
    conversation_service = AsyncMock()
    ai_service = MagicMock()
    ai_service.client = AsyncMock()
    return {
        "logger": logger,
        "business_logic": business_logic,
        "classifier": classifier,
        "db_manager": db_manager,
        "settings": settings,
        "conversation_service": conversation_service,
        "ai_service": ai_service,
    }


# ---------- Summary triggered at N messages ----------

@pytest.mark.asyncio
async def test_summarization_triggered_at_threshold(mock_deps):
    conv_id = str(uuid.uuid4())
    # message_count = 9 means the next message makes it 10 (SUMMARIZE_EVERY)
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 9, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = [
        {"content": "msg1", "response_content": "resp1", "from_id": "user"},
    ]

    # Mock Claude response for summarization
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Summary: user asked about bearings.")]
    mock_deps["ai_service"].client.messages.create = AsyncMock(return_value=mock_response)

    engine = ChatbotEngine(**mock_deps)
    await engine.process_message("user1", "Final message", ChannelType.WEB)

    # Wait for fire-and-forget tasks
    import asyncio
    await asyncio.sleep(0.1)

    # Summary should have been updated
    mock_deps["conversation_service"].update_summary.assert_called_once()
    call_args = mock_deps["conversation_service"].update_summary.call_args[0]
    assert call_args[0] == conv_id
    assert "bearings" in call_args[1]


@pytest.mark.asyncio
async def test_summarization_not_triggered_below_threshold(mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 5, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = []

    engine = ChatbotEngine(**mock_deps)
    await engine.process_message("user1", "Just a message", ChannelType.WEB)

    import asyncio
    await asyncio.sleep(0.1)

    # Summary should NOT be updated (5+1=6, not a multiple of 10)
    mock_deps["conversation_service"].update_summary.assert_not_called()


# ---------- Summary used in context ----------

@pytest.mark.asyncio
async def test_summary_prepended_to_history(mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id,
        "message_count": 15,  # > SUMMARIZE_EVERY
        "context_summary": "User wants SKF 6205 bearings, qty 100.",
    }
    recent = [
        {"content": "What about price?", "response_content": "Price is $5 each.", "from_id": "user"},
    ]
    mock_deps["conversation_service"].get_history.return_value = recent

    engine = ChatbotEngine(**mock_deps)
    await engine.process_message("user1", "OK, order them", ChannelType.WEB)

    # History passed to business_logic should include the summary
    call_args = mock_deps["business_logic"].process_message.call_args
    history = call_args.kwargs.get("conversation_history", [])
    assert len(history) == 2  # 1 summary entry + 1 recent message
    assert "summary" in history[0]["content"].lower()
    assert "SKF 6205" in history[0]["content"]


# ---------- Summarization failure is graceful ----------

@pytest.mark.asyncio
async def test_summarization_failure_is_graceful(mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 9, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = [
        {"content": "test", "response_content": "resp", "from_id": "user"},
    ]
    mock_deps["ai_service"].client.messages.create = AsyncMock(
        side_effect=Exception("API error")
    )

    engine = ChatbotEngine(**mock_deps)
    # Should not raise — summarization errors are caught
    response = await engine.process_message("user1", "Test msg", ChannelType.WEB)

    import asyncio
    await asyncio.sleep(0.1)

    assert response is not None
    mock_deps["logger"].error.assert_called()


# ---------- No AI service skips summarization ----------

@pytest.mark.asyncio
async def test_summarization_skipped_without_ai_service(mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 9, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = []
    mock_deps["ai_service"] = None

    engine = ChatbotEngine(**mock_deps)
    response = await engine.process_message("user1", "Test", ChannelType.WEB)

    import asyncio
    await asyncio.sleep(0.1)

    assert response is not None
    mock_deps["conversation_service"].update_summary.assert_not_called()
