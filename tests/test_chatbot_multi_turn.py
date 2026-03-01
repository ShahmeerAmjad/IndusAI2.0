# =======================
# Tests — Multi-Turn Chatbot Pipeline
# =======================

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.models import BotResponse, ChannelType, MessageType
from services.chatbot_engine import ChatbotEngine


@pytest.fixture
def mock_deps():
    logger = MagicMock()
    business_logic = AsyncMock()
    business_logic.process_message.return_value = BotResponse(
        content="Here are the SKF bearings I found.",
        suggested_actions=["Order now"],
    )
    classifier = MagicMock()
    classifier.classify.return_value = (MessageType.PRODUCT_INQUIRY, 0.9)
    db_manager = MagicMock()
    db_manager.save_message = AsyncMock()
    settings = MagicMock()
    settings.support_email = "support@test.com"
    conversation_service = AsyncMock()
    return {
        "logger": logger,
        "business_logic": business_logic,
        "classifier": classifier,
        "db_manager": db_manager,
        "settings": settings,
        "conversation_service": conversation_service,
    }


@pytest.fixture
def engine(mock_deps):
    return ChatbotEngine(**mock_deps)


# ---------- Basic multi-turn flow ----------

@pytest.mark.asyncio
async def test_process_message_creates_conversation(engine, mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 0, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = []

    response = await engine.process_message("user1", "Find SKF bearings", ChannelType.WEB)

    assert response is not None
    assert response.metadata["conversation_id"] == conv_id
    mock_deps["conversation_service"].get_or_create.assert_called_once()


@pytest.mark.asyncio
async def test_process_message_with_existing_conversation(engine, mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 5, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = [
        {"content": "Find bearings", "response_content": "Here are some bearings", "from_id": "user1"},
    ]

    response = await engine.process_message(
        "user1", "What about NSK?", ChannelType.WEB, conversation_id=conv_id
    )

    assert response.metadata["conversation_id"] == conv_id
    mock_deps["conversation_service"].get_or_create.assert_called_once_with(
        conversation_id=conv_id, channel="web"
    )


@pytest.mark.asyncio
async def test_conversation_history_passed_to_business_logic(engine, mock_deps):
    conv_id = str(uuid.uuid4())
    history = [
        {"content": "Hello", "response_content": "Hi there!", "from_id": "user1", "message_type": "general_query"},
    ]
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 1, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = history

    await engine.process_message("user1", "Now find bearings", ChannelType.WEB, conversation_id=conv_id)

    # Business logic should receive the history
    call_args = mock_deps["business_logic"].process_message.call_args
    assert call_args.kwargs.get("conversation_history") == history


@pytest.mark.asyncio
async def test_message_saved_to_conversation(engine, mock_deps):
    conv_id = str(uuid.uuid4())
    mock_deps["conversation_service"].get_or_create.return_value = {
        "id": conv_id, "message_count": 0, "context_summary": None,
    }
    mock_deps["conversation_service"].get_history.return_value = []

    await engine.process_message("user1", "Test content", ChannelType.WEB)

    # add_message should be called (fire-and-forget task)
    mock_deps["conversation_service"].add_message.assert_called_once()
    call_args = mock_deps["conversation_service"].add_message.call_args
    assert call_args.kwargs["conversation_id"] == conv_id
    assert call_args.kwargs["content"] == "Test content"
    assert call_args.kwargs["role"] == "user"


# ---------- Without conversation service ----------

@pytest.mark.asyncio
async def test_process_message_without_conversation_service(mock_deps):
    mock_deps["conversation_service"] = None
    engine = ChatbotEngine(**mock_deps)

    response = await engine.process_message("user1", "Hello", ChannelType.WEB)
    assert response is not None
    assert response.content == "Here are the SKF bearings I found."


# ---------- Short input still works ----------

@pytest.mark.asyncio
async def test_short_input_returns_help(engine, mock_deps):
    response = await engine.process_message("user1", "a", ChannelType.WEB)
    assert "more details" in response.content


# ---------- Error handling ----------

@pytest.mark.asyncio
async def test_error_returns_fallback(mock_deps):
    mock_deps["conversation_service"].get_or_create.side_effect = Exception("DB error")
    engine = ChatbotEngine(**mock_deps)

    response = await engine.process_message("user1", "Hello world", ChannelType.WEB)
    assert "error" in response.content.lower()


# ---------- AIService._build_messages ----------

from services.ai_service import AIService


def test_build_messages_no_history():
    svc = AIService(MagicMock(), MagicMock())
    messages = svc._build_messages("Current prompt")
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Current prompt"


def test_build_messages_with_history():
    svc = AIService(MagicMock(), MagicMock())
    context = {
        "conversation_history": [
            {"content": "Find bearings", "response_content": "Here are bearings"},
            {"content": "Compare prices", "response_content": "Price comparison:"},
        ]
    }
    messages = svc._build_messages("Now order the cheapest", context)
    # 2 history exchanges (4 messages) + 1 current = 5
    assert len(messages) == 5
    assert messages[0] == {"role": "user", "content": "Find bearings"}
    assert messages[1] == {"role": "assistant", "content": "Here are bearings"}
    assert messages[-1] == {"role": "user", "content": "Now order the cheapest"}
