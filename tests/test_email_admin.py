"""Tests for routes.email_admin — email inbox management API."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from routes.email_admin import (
    router, set_email_admin_services,
    AddInboxRequest, UpdateInboxRequest,
)
import routes.email_admin as email_admin_mod


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

    enc = MagicMock()
    enc.encrypt = MagicMock(side_effect=lambda x: f"ENC:{x}")
    enc.is_configured = True

    ingestion = AsyncMock()
    ingestion.poll_all_inboxes = AsyncMock(return_value={
        "inboxes": 1, "messages": 5, "errors": 0, "skipped_backpressure": False
    })
    ingestion.poll_inbox = AsyncMock(return_value={"processed": 3, "errors": 0, "deduped": 1})

    set_email_admin_services(db, enc, ingestion)

    yield {
        "db": db, "conn": conn, "pool": pool,
        "enc": enc, "ingestion": ingestion,
    }

    # Cleanup
    set_email_admin_services(None, None, None)


class TestEmailAdminRoutes:
    @pytest.mark.asyncio
    async def test_list_inboxes(self, setup_services):
        conn = setup_services["conn"]
        now = datetime.now(timezone.utc)
        conn.fetch = AsyncMock(return_value=[
            {
                "inbox_address": "sales@test.com",
                "provider": "gmail",
                "is_active": True,
                "history_id": "123",
                "last_polled_at": now,
                "created_at": now,
                "updated_at": now,
            }
        ])

        from routes.email_admin import list_inboxes
        result = await list_inboxes(user={"role": "admin"})
        assert len(result) == 1
        assert result[0].inbox_address == "sales@test.com"

    @pytest.mark.asyncio
    async def test_add_inbox(self, setup_services):
        conn = setup_services["conn"]
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        from routes.email_admin import add_inbox
        req = AddInboxRequest(
            inbox_address="new@test.com",
            access_token="my-access-token",
            refresh_token="my-refresh-token",
        )
        result = await add_inbox(req, user={"role": "admin"})
        assert result["status"] == "ok"
        assert result["inbox_address"] == "new@test.com"
        assert result["encrypted"] is True
        # Verify tokens were encrypted
        call_args = conn.execute.call_args
        assert "ENC:my-access-token" in call_args.args
        assert "ENC:my-refresh-token" in call_args.args

    @pytest.mark.asyncio
    async def test_update_inbox(self, setup_services):
        conn = setup_services["conn"]
        conn.execute = AsyncMock(return_value="UPDATE 1")

        from routes.email_admin import update_inbox
        req = UpdateInboxRequest(is_active=False)
        result = await update_inbox("sales@test.com", req, user={"role": "admin"})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_update_inbox_not_found(self, setup_services):
        conn = setup_services["conn"]
        conn.execute = AsyncMock(return_value="UPDATE 0")

        from routes.email_admin import update_inbox
        req = UpdateInboxRequest(is_active=True)
        with pytest.raises(Exception) as exc_info:
            await update_inbox("missing@test.com", req, user={"role": "admin"})
        assert "404" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_delete_inbox(self, setup_services):
        conn = setup_services["conn"]
        conn.execute = AsyncMock(return_value="DELETE 1")

        from routes.email_admin import delete_inbox
        result = await delete_inbox("old@test.com", user={"role": "admin"})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_trigger_poll(self, setup_services):
        from routes.email_admin import trigger_poll
        result = await trigger_poll(user={"role": "admin"})
        assert result["status"] == "ok"
        assert result["messages"] == 5

    @pytest.mark.asyncio
    async def test_trigger_poll_single_inbox(self, setup_services):
        conn = setup_services["conn"]
        conn.fetchrow = AsyncMock(return_value={
            "inbox_address": "sales@test.com",
            "history_id": "999",
            "last_polled_at": None,
        })

        from routes.email_admin import trigger_poll_inbox
        result = await trigger_poll_inbox("sales@test.com", user={"role": "admin"})
        assert result["status"] == "ok"
        assert result["processed"] == 3

    @pytest.mark.asyncio
    async def test_get_audit_log(self, setup_services):
        conn = setup_services["conn"]
        conn.fetch = AsyncMock(return_value=[
            {"id": "abc", "event_type": "ingested", "gmail_message_id": "g1",
             "inbox_address": "sales@test.com", "detail": None, "created_at": datetime.now(timezone.utc),
             "message_id": None}
        ])

        from routes.email_admin import get_audit_log
        result = await get_audit_log(limit=10, user={"role": "admin"})
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_email_stats(self, setup_services):
        conn = setup_services["conn"]
        conn.fetchval = AsyncMock(side_effect=[2, 10, 15, 1])
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "sales@test.com", "last_polled_at": None, "history_id": "123"}
        ])

        from routes.email_admin import email_stats
        result = await email_stats(user={"role": "admin"})
        assert result["active_inboxes"] == 2
        assert len(result["inboxes"]) == 1

    @pytest.mark.asyncio
    async def test_generate_encryption_key(self, setup_services):
        from routes.email_admin import generate_encryption_key
        result = await generate_encryption_key(user={"role": "admin"})
        assert "key" in result
        assert len(result["key"]) > 0
        assert "EMAIL_ENCRYPTION_KEY" in result["instruction"]
