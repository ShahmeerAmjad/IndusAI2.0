"""Tests for services.email.connector — Gmail API connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.email.connector import GmailConnector
from services.email.encryption import FernetEncryption


@pytest.fixture
def mock_db():
    db = MagicMock()
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "access_token": "enc_access",
        "refresh_token": "enc_refresh",
        "token_expiry": None,
    })
    conn.execute = AsyncMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    db.pool = pool
    return db


@pytest.fixture
def mock_encryption():
    enc = MagicMock(spec=FernetEncryption)
    enc.decrypt.side_effect = lambda x: f"decrypted_{x}"
    enc.encrypt.side_effect = lambda x: f"encrypted_{x}"
    enc.is_configured = True
    return enc


@pytest.fixture
def connector(mock_db, mock_encryption):
    return GmailConnector(mock_db, mock_encryption)


class TestGmailConnector:
    @pytest.mark.asyncio
    async def test_initial_sync_lists_messages(self, connector):
        """First sync (no history_id) uses messages.list."""
        mock_service = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users().messages().list.return_value = mock_list

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred

            result = await connector.list_new_messages("inbox@test.com", None)
            assert len(result) == 2
            assert result[0]["id"] == "msg1"

    @pytest.mark.asyncio
    async def test_incremental_sync_uses_history(self, connector):
        """Subsequent syncs use history.list with historyId."""
        mock_service = MagicMock()
        mock_history = MagicMock()
        mock_history.execute.return_value = {
            "history": [
                {"messagesAdded": [{"message": {"id": "msg3"}}]},
                {"messagesAdded": [{"message": {"id": "msg4"}}]},
            ]
        }
        mock_service.users().history().list.return_value = mock_history

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred

            result = await connector.list_new_messages("inbox@test.com", "12345")
            assert len(result) == 2
            assert result[0]["id"] == "msg3"

    @pytest.mark.asyncio
    async def test_gmail_503_returns_empty(self, connector):
        """Gmail 503/429 should return empty list, not raise."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.side_effect = \
            Exception("503 Service Unavailable")

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred

            result = await connector.list_new_messages("inbox@test.com", None)
            assert result == []

    @pytest.mark.asyncio
    async def test_get_message(self, connector):
        """get_message fetches full payload."""
        mock_service = MagicMock()
        mock_get = MagicMock()
        mock_get.execute.return_value = {"id": "msg1", "payload": {"headers": []}}
        mock_service.users().messages().get.return_value = mock_get

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred

            result = await connector.get_message("inbox@test.com", "msg1")
            assert result["id"] == "msg1"

    @pytest.mark.asyncio
    async def test_get_attachment(self, connector):
        """get_attachment downloads and decodes base64 content."""
        import base64
        mock_service = MagicMock()
        encoded = base64.urlsafe_b64encode(b"file content").decode()
        mock_get = MagicMock()
        mock_get.execute.return_value = {"data": encoded}
        mock_service.users().messages().attachments().get.return_value = mock_get

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred

            result = await connector.get_attachment("inbox@test.com", "msg1", "att1")
            assert result == b"file content"

    @pytest.mark.asyncio
    async def test_credentials_cached(self, connector, mock_db):
        """Credentials should be cached and not re-fetched within TTL."""
        with patch.object(connector, "_build_service", return_value=MagicMock()), \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh:
            # First call loads from DB
            mock_refresh.side_effect = lambda inbox, creds: creds

            with patch("services.email.connector.Credentials", create=True):
                from unittest.mock import patch as _p
                from google.oauth2.credentials import Credentials
                with _p.object(Credentials, "__init__", return_value=None):
                    pass  # Let it load normally

            # Pre-populate cache
            import time
            mock_cred = MagicMock()
            connector._cred_cache["inbox@test.com"] = (mock_cred, time.time())

            cred = await connector._load_credentials("inbox@test.com")
            assert cred is mock_cred

    @pytest.mark.asyncio
    async def test_token_refresh_on_401(self, connector):
        """401 triggers token refresh; persistent 401 disables inbox."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.side_effect = \
            Exception("401 Unauthorized")

        with patch.object(connector, "_build_service", return_value=mock_service), \
             patch.object(connector, "_load_credentials", new_callable=AsyncMock) as mock_creds, \
             patch.object(connector, "_refresh_if_needed", new_callable=AsyncMock) as mock_refresh, \
             patch.object(connector, "_handle_401", new_callable=AsyncMock) as mock_handle:
            mock_cred = MagicMock()
            mock_creds.return_value = mock_cred
            mock_refresh.return_value = mock_cred
            mock_handle.return_value = []

            result = await connector.list_new_messages("inbox@test.com", None)
            mock_handle.assert_called_once()
            assert result == []
