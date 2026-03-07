"""Email connectors — abstract base + Gmail API implementation."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmailConnector(ABC):
    """Abstract interface for email providers."""

    @abstractmethod
    async def list_new_messages(
        self, inbox: str, since_history_id: str | None,
    ) -> list[dict]:
        ...

    @abstractmethod
    async def get_message(self, inbox: str, message_id: str) -> dict:
        ...

    @abstractmethod
    async def get_attachment(
        self, inbox: str, message_id: str, attachment_id: str,
    ) -> bytes:
        ...

    @abstractmethod
    async def get_history_id(self, inbox: str) -> str:
        ...


class GmailConnector(EmailConnector):
    """Gmail API connector using OAuth2 credentials stored in DB."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    _CACHE_TTL = 300  # 5 min credential cache

    def __init__(self, db_manager, encryption, logger=None):
        self._db = db_manager
        self._encryption = encryption
        self._log = logger or logging.getLogger(__name__)
        self._cred_cache: dict[str, tuple[object, float]] = {}

    async def _load_credentials(self, inbox: str):
        """Load OAuth2 credentials from DB (encrypted), with in-memory cache."""
        cached = self._cred_cache.get(inbox)
        if cached and (time.time() - cached[1]) < self._CACHE_TTL:
            return cached[0]

        from google.oauth2.credentials import Credentials

        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT access_token, refresh_token, token_expiry "
                "FROM email_oauth_tokens WHERE inbox_address = $1 AND is_active = true",
                inbox,
            )
        if not row:
            raise ValueError(f"No active OAuth token for inbox: {inbox}")

        access_token = self._encryption.decrypt(row["access_token"])
        refresh_token = self._encryption.decrypt(row["refresh_token"])

        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=self.SCOPES,
        )
        self._cred_cache[inbox] = (creds, time.time())
        return creds

    async def _refresh_if_needed(self, inbox: str, creds):
        """Refresh token if expired, persist new tokens to DB."""
        from google.auth.transport.requests import Request

        if not creds.expired:
            return creds

        def _do_refresh():
            creds.refresh(Request())

        await asyncio.to_thread(_do_refresh)

        # Persist refreshed tokens
        encrypted_access = self._encryption.encrypt(creds.token)
        encrypted_refresh = self._encryption.encrypt(creds.refresh_token)
        async with self._db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE email_oauth_tokens "
                "SET access_token = $1, refresh_token = $2, token_expiry = $3, updated_at = now() "
                "WHERE inbox_address = $4",
                encrypted_access, encrypted_refresh, creds.expiry, inbox,
            )
        # Update cache
        self._cred_cache[inbox] = (creds, time.time())
        return creds

    def _build_service(self, creds):
        """Build Gmail API service object."""
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=creds)

    async def list_new_messages(
        self, inbox: str, since_history_id: str | None, max_results: int = 50,
    ) -> list[dict]:
        """List new message IDs since last sync."""
        try:
            creds = await self._load_credentials(inbox)
            creds = await self._refresh_if_needed(inbox, creds)
        except Exception as e:
            self._log.error("Credential load failed for %s: %s", inbox, e)
            return []

        service = self._build_service(creds)

        try:
            if since_history_id:
                # Incremental: use history API
                def _list_history():
                    return service.users().history().list(
                        userId="me",
                        startHistoryId=since_history_id,
                        historyTypes=["messageAdded"],
                        maxResults=max_results,
                    ).execute()

                result = await asyncio.to_thread(_list_history)
                messages = []
                for h in result.get("history", []):
                    for ma in h.get("messagesAdded", []):
                        messages.append(ma["message"])
                return messages[:max_results]
            else:
                # Initial sync: recent inbox messages
                def _list_messages():
                    return service.users().messages().list(
                        userId="me",
                        q="in:inbox newer_than:1d",
                        maxResults=max_results,
                    ).execute()

                result = await asyncio.to_thread(_list_messages)
                return result.get("messages", [])[:max_results]

        except Exception as e:
            err_str = str(e)
            if "401" in err_str:
                return await self._handle_401(inbox, creds, service, since_history_id, max_results)
            if "503" in err_str or "429" in err_str:
                self._log.warning("Gmail rate limited/unavailable for %s, skipping cycle", inbox)
                return []
            self._log.error("Gmail list failed for %s: %s", inbox, e)
            return []

    async def _handle_401(self, inbox, creds, service, since_history_id, max_results):
        """Handle 401 by refreshing token once. Disable inbox if still 401."""
        try:
            creds = await self._refresh_if_needed(inbox, creds)
            service = self._build_service(creds)

            def _retry():
                if since_history_id:
                    return service.users().history().list(
                        userId="me",
                        startHistoryId=since_history_id,
                        historyTypes=["messageAdded"],
                        maxResults=max_results,
                    ).execute()
                return service.users().messages().list(
                    userId="me", q="in:inbox newer_than:1d", maxResults=max_results,
                ).execute()

            result = await asyncio.to_thread(_retry)
            return result.get("messages", result.get("history", []))[:max_results]
        except Exception:
            self._log.error("Persistent 401 for %s — disabling inbox", inbox)
            async with self._db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE email_oauth_tokens SET is_active = false WHERE inbox_address = $1",
                    inbox,
                )
            self._cred_cache.pop(inbox, None)
            return []

    async def get_message(self, inbox: str, message_id: str) -> dict:
        """Fetch full message payload by ID."""
        creds = await self._load_credentials(inbox)
        creds = await self._refresh_if_needed(inbox, creds)
        service = self._build_service(creds)

        def _get():
            return service.users().messages().get(
                userId="me", id=message_id, format="full",
            ).execute()

        return await asyncio.to_thread(_get)

    async def get_attachment(
        self, inbox: str, message_id: str, attachment_id: str,
    ) -> bytes:
        """Download attachment content."""
        import base64
        creds = await self._load_credentials(inbox)
        creds = await self._refresh_if_needed(inbox, creds)
        service = self._build_service(creds)

        def _get():
            return service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=attachment_id,
            ).execute()

        result = await asyncio.to_thread(_get)
        data = result.get("data", "")
        return base64.urlsafe_b64decode(data + "==")

    async def get_history_id(self, inbox: str) -> str:
        """Get the current history ID for an inbox."""
        creds = await self._load_credentials(inbox)
        creds = await self._refresh_if_needed(inbox, creds)
        service = self._build_service(creds)

        def _get_profile():
            return service.users().getProfile(userId="me").execute()

        profile = await asyncio.to_thread(_get_profile)
        return str(profile.get("historyId", ""))
