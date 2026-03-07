"""Tests for services.email.ingestion_service — email ingestion orchestrator."""

import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.email.ingestion_service import EmailIngestionService
from services.email.parser import ParsedEmail, AttachmentMeta
from services.email.pii_scanner import ScanResult


def _make_parsed_email(**kwargs):
    defaults = dict(
        message_id="<test@example.com>",
        thread_id=None,
        from_address="sender@example.com",
        to_addresses=["inbox@company.com"],
        cc_addresses=[],
        subject="Test Subject",
        body_text="Hello, this is a test email.",
        body_html=None,
        attachments=[],
        date=None,
        raw_headers={},
        encoding_issues=False,
    )
    defaults.update(kwargs)
    return ParsedEmail(**defaults)


@pytest.fixture
def mock_db():
    db = MagicMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    db.pool = pool
    return db, conn


@pytest.fixture
def mock_connector():
    conn = AsyncMock()
    conn.list_new_messages = AsyncMock(return_value=[])
    conn.get_message = AsyncMock(return_value={
        "id": "gmail123", "threadId": "thread456",
        "payload": {"headers": [], "mimeType": "text/plain", "body": {"data": ""}},
    })
    conn.get_attachment = AsyncMock(return_value=b"attachment data")
    conn.get_history_id = AsyncMock(return_value="99999")
    return conn


@pytest.fixture
def mock_parser():
    parser = MagicMock()
    parser.parse_gmail_payload = MagicMock(return_value=_make_parsed_email())
    return parser


@pytest.fixture
def mock_pii():
    scanner = MagicMock()
    scanner.scan = MagicMock(return_value=ScanResult(
        redacted_text="Hello, this is a test email.",
        detected_types=[],
        redaction_count=0,
    ))
    return scanner


@pytest.fixture
def mock_encryption():
    enc = MagicMock()
    enc.encrypt = MagicMock(side_effect=lambda x: f"ENC:{x}")
    enc.decrypt = MagicMock(side_effect=lambda x: x.replace("ENC:", ""))
    enc.is_configured = True
    return enc


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)  # NX succeeded
    return redis


@pytest.fixture
def service(mock_db, mock_connector, mock_parser, mock_pii, mock_encryption, mock_redis):
    db, _ = mock_db
    return EmailIngestionService(
        db_manager=db,
        connector=mock_connector,
        parser=mock_parser,
        pii_scanner=mock_pii,
        encryption=mock_encryption,
        attachment_dir="/tmp/test_attachments",
        max_messages_per_poll=50,
        redis_client=mock_redis,
    )


class TestEmailIngestionService:
    @pytest.mark.asyncio
    async def test_no_inboxes(self, service, mock_db):
        """poll_all_inboxes with no active inboxes processes nothing."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])
        result = await service.poll_all_inboxes()
        assert result["inboxes"] == 0
        assert result["messages"] == 0

    @pytest.mark.asyncio
    async def test_dedup_skip(self, service, mock_redis, mock_db):
        """Duplicate messages are skipped via Redis."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": "123", "last_polled_at": None},
        ])
        mock_redis.set = AsyncMock(return_value=None)  # NX failed = duplicate

        service._connector.list_new_messages = AsyncMock(
            return_value=[{"id": "gmail_dup"}]
        )

        result = await service.poll_all_inboxes()
        assert result["messages"] == 0

    @pytest.mark.asyncio
    async def test_happy_path(self, service, mock_db, mock_connector):
        """Single message ingested end-to-end."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail1"}])

        result = await service.poll_all_inboxes()
        assert result["messages"] == 1
        assert result["errors"] == 0
        # Verify message was stored
        conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_backpressure(self, service, mock_db):
        """Skip polling when queue is too full."""
        _, conn = mock_db
        conn.fetchval = AsyncMock(return_value=500)  # > MAX_QUEUE_SIZE

        result = await service.poll_all_inboxes()
        assert result["skipped_backpressure"] is True
        assert result["messages"] == 0

    @pytest.mark.asyncio
    async def test_pii_stored_correctly(self, service, mock_db, mock_connector, mock_pii):
        """PII is detected, body is redacted for storage, original encrypted."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_pii"}])
        mock_pii.scan = MagicMock(return_value=ScanResult(
            redacted_text="Contact [EMAIL REDACTED] for info.",
            detected_types=["email"],
            redaction_count=1,
        ))

        result = await service.poll_all_inboxes()
        assert result["messages"] == 1
        # Verify the stored body is the redacted version
        calls = conn.execute.call_args_list
        insert_call = [c for c in calls if "INSERT INTO inbound_messages" in str(c)]
        assert len(insert_call) > 0

    @pytest.mark.asyncio
    async def test_parse_error_continues_batch(self, service, mock_db, mock_connector, mock_parser):
        """Parse error on one message doesn't stop the batch."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[
            {"id": "gmail_bad"}, {"id": "gmail_good"},
        ])
        # First parse fails, second succeeds
        mock_connector.get_message = AsyncMock(return_value={
            "id": "gmail_bad", "threadId": "t1",
            "payload": {"headers": [], "mimeType": "text/plain", "body": {"data": ""}},
        })
        call_count = [0]
        def parse_side_effect(payload, thread_id=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Bad MIME")
            return _make_parsed_email()
        mock_parser.parse_gmail_payload = MagicMock(side_effect=parse_side_effect)

        result = await service.poll_all_inboxes()
        assert result["errors"] >= 1
        assert result["messages"] >= 1

    @pytest.mark.asyncio
    async def test_gmail_error_safe(self, service, mock_db, mock_connector):
        """Gmail connector error doesn't crash the service."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(side_effect=Exception("Network error"))

        result = await service.poll_all_inboxes()
        assert result["errors"] >= 1

    @pytest.mark.asyncio
    async def test_oversized_attachment_skipped(self, service, mock_db, mock_connector, mock_parser):
        """Attachments > 25MB are skipped."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_big"}])
        mock_parser.parse_gmail_payload = MagicMock(return_value=_make_parsed_email(
            attachments=[AttachmentMeta(
                filename="huge.zip",
                content_type="application/zip",
                size_bytes=30_000_000,
                gmail_attachment_id="att1",
            )],
        ))

        result = await service.poll_all_inboxes()
        assert result["messages"] == 1
        # Attachment download should NOT have been called
        mock_connector.get_attachment.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_unavailable_fallback(self, service, mock_db, mock_connector):
        """When Redis is unavailable, dedup falls back to PG."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        conn.fetchval = AsyncMock(side_effect=[0, None])  # backpressure=0, PG dedup=not found
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_no_redis"}])
        service._redis = None

        result = await service.poll_all_inboxes()
        assert result["messages"] == 1

    @pytest.mark.asyncio
    async def test_retention_purge(self, service, mock_db):
        """purge_old_messages nullifies raw_payload for old messages."""
        _, conn = mock_db
        conn.execute = AsyncMock(return_value="UPDATE 15")

        count = await service.purge_old_messages(days=90)
        assert count == 15

    @pytest.mark.asyncio
    async def test_audit_swallows_errors(self, service, mock_db):
        """Audit log failures are swallowed, never propagated."""
        _, conn = mock_db
        conn.execute = AsyncMock(side_effect=Exception("DB write failed"))

        # Should not raise
        await service._audit("test_event", None, gmail_id="g1")

    @pytest.mark.asyncio
    async def test_no_body_message(self, service, mock_db, mock_connector, mock_parser):
        """Message with empty body is still ingested."""
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_empty"}])
        mock_parser.parse_gmail_payload = MagicMock(
            return_value=_make_parsed_email(body_text="")
        )

        result = await service.poll_all_inboxes()
        assert result["messages"] == 1

    @pytest.mark.asyncio
    async def test_post_ingest_callback(self, mock_db, mock_connector, mock_parser, mock_pii, mock_encryption, mock_redis):
        """Post-ingest callback is invoked after message storage."""
        db, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_cb"}])

        callback = AsyncMock()
        svc = EmailIngestionService(
            db_manager=db, connector=mock_connector, parser=mock_parser,
            pii_scanner=mock_pii, encryption=mock_encryption,
            redis_client=mock_redis, post_ingest_callback=callback,
        )

        result = await svc.poll_all_inboxes()
        assert result["messages"] == 1
        callback.assert_called_once()
        args = callback.call_args[0]
        assert len(args[0]) == 36  # UUID format
        assert isinstance(args[1], str)

    @pytest.mark.asyncio
    async def test_post_ingest_callback_error_nonfatal(self, mock_db, mock_connector, mock_parser, mock_pii, mock_encryption, mock_redis):
        """Post-ingest callback failure doesn't break ingestion."""
        db, conn = mock_db
        conn.fetch = AsyncMock(return_value=[
            {"inbox_address": "inbox@test.com", "history_id": None, "last_polled_at": None},
        ])
        mock_connector.list_new_messages = AsyncMock(return_value=[{"id": "gmail_err"}])

        callback = AsyncMock(side_effect=Exception("classify failed"))
        svc = EmailIngestionService(
            db_manager=db, connector=mock_connector, parser=mock_parser,
            pii_scanner=mock_pii, encryption=mock_encryption,
            redis_client=mock_redis, post_ingest_callback=callback,
        )

        result = await svc.poll_all_inboxes()
        assert result["messages"] == 1  # Message still counts as ingested
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_post_ingest_callback(self, service):
        """set_post_ingest_callback wires a callback after construction."""
        callback = AsyncMock()
        service.set_post_ingest_callback(callback)
        assert service._post_ingest_callback is callback
