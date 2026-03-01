# =======================
# Tests — ConversationService
# =======================

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from services.conversation_service import ConversationService


# ---------- Fixtures ----------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.pool = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    return ConversationService(mock_db)


def _make_conn():
    """Create a mock connection with async context manager support."""
    conn = AsyncMock()
    mock_db_pool_ctx = AsyncMock()
    mock_db_pool_ctx.__aenter__ = AsyncMock(return_value=conn)
    mock_db_pool_ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, mock_db_pool_ctx


# ---------- create_conversation ----------

@pytest.mark.asyncio
async def test_create_conversation(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    now = datetime.now(timezone.utc)
    conv_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {
        "id": conv_id,
        "user_id": None,
        "channel": "web",
        "title": None,
        "context_summary": None,
        "message_count": 0,
        "last_message_at": now,
        "created_at": now,
    }

    result = await service.create_conversation(channel="web")
    assert result["id"] == conv_id
    assert result["channel"] == "web"
    assert result["message_count"] == 0
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_create_conversation_with_user(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    user_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "channel": "web",
        "title": "Test",
        "context_summary": None,
        "message_count": 0,
        "last_message_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    result = await service.create_conversation(user_id=user_id, title="Test")
    assert result["user_id"] == user_id
    assert result["title"] == "Test"


@pytest.mark.asyncio
async def test_create_conversation_no_pool(mock_db):
    mock_db.pool = None
    svc = ConversationService(mock_db)
    result = await svc.create_conversation()
    assert "id" in result
    assert result["message_count"] == 0


# ---------- get_or_create ----------

@pytest.mark.asyncio
async def test_get_or_create_existing(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    conv_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {
        "id": conv_id,
        "user_id": None,
        "channel": "web",
        "title": "Existing",
        "context_summary": None,
        "message_count": 5,
        "last_message_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    result = await service.get_or_create(conversation_id=conv_id)
    assert result["id"] == conv_id
    assert result["title"] == "Existing"


@pytest.mark.asyncio
async def test_get_or_create_new(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    new_id = str(uuid.uuid4())
    # First call: lookup returns None (not found)
    # Second call: create returns new row
    conn.fetchrow.side_effect = [
        None,
        {
            "id": new_id,
            "user_id": None,
            "channel": "web",
            "title": None,
            "context_summary": None,
            "message_count": 0,
            "last_message_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        },
    ]

    result = await service.get_or_create(conversation_id="nonexistent-id")
    assert result["id"] == new_id


# ---------- add_message ----------

@pytest.mark.asyncio
async def test_add_message(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    conv_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {"message_count": 0, "title": None}

    result = await service.add_message(
        conversation_id=conv_id,
        role="user",
        content="Hello world",
        from_id="test_user",
    )
    assert result["conversation_id"] == conv_id
    assert "id" in result
    # Should have inserted message and updated conversation
    assert conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_add_message_auto_title(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    conv_id = str(uuid.uuid4())
    # message_count=0 means first message, should auto-title
    conn.fetchrow.return_value = {"message_count": 0, "title": None}

    await service.add_message(
        conversation_id=conv_id,
        role="user",
        content="Find me SKF 6205 bearings",
    )

    # The UPDATE should include title
    update_call = conn.execute.call_args_list[-1]
    assert "title" in update_call[0][0]


@pytest.mark.asyncio
async def test_add_message_no_pool(mock_db):
    mock_db.pool = None
    svc = ConversationService(mock_db)
    result = await svc.add_message("conv-id", "user", "test")
    assert result["conversation_id"] == "conv-id"


# ---------- get_history ----------

@pytest.mark.asyncio
async def test_get_history(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    now = datetime.now(timezone.utc)
    conn.fetch.return_value = [
        {"id": "2", "from_id": "bot", "content": "Hi there", "message_type": "general_query", "response_content": None, "timestamp": now},
        {"id": "1", "from_id": "user", "content": "Hello", "message_type": "general_query", "response_content": None, "timestamp": now},
    ]

    history = await service.get_history("conv-id", limit=10)
    # Should be reversed (oldest first)
    assert len(history) == 2
    assert history[0]["id"] == "1"
    assert history[1]["id"] == "2"


@pytest.mark.asyncio
async def test_get_history_no_pool(mock_db):
    mock_db.pool = None
    svc = ConversationService(mock_db)
    result = await svc.get_history("conv-id")
    assert result == []


# ---------- get_recent_conversations ----------

@pytest.mark.asyncio
async def test_get_recent_conversations(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    conn.fetch.return_value = [
        {"id": "c1", "user_id": None, "channel": "web", "title": "Conv 1",
         "context_summary": None, "message_count": 3,
         "last_message_at": datetime.now(timezone.utc),
         "created_at": datetime.now(timezone.utc)},
    ]

    result = await service.get_recent_conversations()
    assert len(result) == 1
    assert result[0]["title"] == "Conv 1"


@pytest.mark.asyncio
async def test_get_recent_conversations_by_user(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx
    conn.fetch.return_value = []

    result = await service.get_recent_conversations(user_id="user-123")
    assert result == []
    # Should have used the user-filtered query
    call_args = conn.fetch.call_args[0]
    assert "user_id" in call_args[0]


# ---------- update_summary ----------

@pytest.mark.asyncio
async def test_update_summary(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    await service.update_summary("conv-id", "User asked about bearings.")
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "context_summary" in call_args[0]
    assert call_args[2] == "User asked about bearings."


# ---------- get_conversation ----------

@pytest.mark.asyncio
async def test_get_conversation(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx

    conv_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {
        "id": conv_id, "user_id": None, "channel": "web",
        "title": "Test", "context_summary": None, "message_count": 2,
        "last_message_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    result = await service.get_conversation(conv_id)
    assert result["id"] == conv_id


@pytest.mark.asyncio
async def test_get_conversation_not_found(service, mock_db):
    conn, ctx = _make_conn()
    mock_db.pool.acquire.return_value = ctx
    conn.fetchrow.return_value = None

    result = await service.get_conversation("nonexistent")
    assert result is None
